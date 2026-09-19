"""dedup.py — إزالة التكرار على مستوى Chunks (FastCDC مبسط) — lossless 100%.

الفكرة (مثل Borg/Restic):
- قسّم الملف إلى chunks بأحجام متغيرة عبر rolling hash (content-defined).
- احسب sha256 لكل chunk، خزّن الفريد فقط.
- الملفات المتكررة (logs، نسخ، VM، قواعد بيانات، فيديو خام) تنكمش بقوة بدون أي فقد.

الحاوية .tqd داخل .tqz v2: manifest.json + blobs مضغوطة.
"""
from __future__ import annotations
import hashlib
import os
import struct

MIN_CHUNK = 64 * 1024
AVG_CHUNK = 256 * 1024
MAX_CHUNK = 1024 * 1024

def _chunk_boundaries(data: bytes, min_s=MIN_CHUNK, avg_s=AVG_CHUNK, max_s=MAX_CHUNK) -> list[tuple[int, int]]:
    """FastCDC مبسط: rolling hash (buzhash-like) — يعمل على bytes في الذاكرة للعينات."""
    n = len(data)
    if n == 0:
        return []
    mask = (avg_s - 1)  # avg_s قوة 2
    h = 0
    start = 0
    out = []
    for i, b in enumerate(data):
        h = ((h << 5) ^ (h >> 27) ^ b) & 0xFFFFFFFF
        cur = i - start + 1
        if cur >= max_s:
            out.append((start, i + 1))
            start = i + 1
            h = 0
        elif cur >= min_s and (h & mask) == 0:
            out.append((start, i + 1))
            start = i + 1
            h = 0
    if start < n:
        out.append((start, n))
    return out

def chunk_file_stream(path: str, min_s=MIN_CHUNK, avg_s=AVG_CHUNK, max_s=MAX_CHUNK,
                      read_mb: int = 32):
    """يقسّم ملفاً كبيراً دون تحميله كاملاً: يقرأ كتلاً ويطبق CDC على نافذة منزلقة.

    مبسط عملياً: fixed CDC عبر rolling hash على stream.
    yields: chunk bytes
    """
    mask = avg_s - 1
    h = 0
    buf = bytearray()
    with open(path, "rb") as f:
        while True:
            data = f.read(read_mb * 1024 * 1024)
            if not data:
                break
            for b in data:
                buf.append(b)
                h = ((h << 5) ^ (h >> 27) ^ b) & 0xFFFFFFFF
                if len(buf) >= max_s or (len(buf) >= min_s and (h & mask) == 0):
                    yield bytes(buf)
                    buf = bytearray()
                    h = 0
    if buf:
        yield bytes(buf)

def dedup_stats(path: str) -> dict:
    """حلّل نسبة التكرار بدون ضغط — مفيد لقرار dedup vs single."""
    seen: set[str] = set()
    total = uniq = 0
    n_chunks = 0
    for ch in chunk_file_stream(path):
        n_chunks += 1
        total += len(ch)
        d = hashlib.sha256(ch).hexdigest()
        if d not in seen:
            seen.add(d)
            uniq += len(ch)
    return {"chunks": n_chunks, "total": total,
            "unique_bytes": uniq, "dedup_ratio": (uniq / total) if total else 1.0}

def build_dedup_package(chunks: list[bytes], codec: str, mode: str, jobs: int = 1):
    """ابنِ حزمة dedup في الذاكرة: manifest + blob مضغوط — للملفات المتوسطة."""
    manifest = []
    raws: dict[str, bytes] = {}
    for ch in chunks:
        d = hashlib.sha256(ch).hexdigest()
        manifest.append({"sha": d, "size": len(ch)})
        if d not in raws:
            raws[d] = ch
    from .parallel import compress_many
    store = dict(compress_many([(h, b) for h, b in raws.items()], codec, mode, jobs))
    import json
    man = json.dumps({"codec": codec, "manifest": manifest,
                      "order": [m["sha"] for m in manifest]}).encode()
    # تنسيق blob: [len-manifest][manifest][n-blobs][ لكل: len-sha(64) + len-data + data ]...
    buf = bytearray()
    buf += struct.pack(">I", len(man)) + man
    buf += struct.pack(">I", len(store))
    for sha, cdata in store.items():
        sh = sha.encode()
        buf += struct.pack(">I", len(sh)) + sh
        buf += struct.pack(">Q", len(cdata)) + cdata
    return bytes(buf), {"unique": len(store), "total_chunks": len(manifest)}

def parse_dedup_package(blob: bytes) -> tuple[list[str], dict[str, bytes], str]:
    import json
    off = 0
    (mlen,) = struct.unpack_from(">I", blob, off); off += 4
    man = json.loads(blob[off:off + mlen].decode()); off += mlen
    (n,) = struct.unpack_from(">I", blob, off); off += 4
    store = {}
    for _ in range(n):
        (sl,) = struct.unpack_from(">I", blob, off); off += 4
        sha = blob[off:off + sl].decode(); off += sl
        (dl,) = struct.unpack_from(">Q", blob, off); off += 8
        store[sha] = blob[off:off + dl]; off += dl
    return man["order"], store, man.get("codec", "lzma")

def restore_dedup_package(blob: bytes) -> bytes:
    from .codecs import decompress_bytes
    order, store, codec = parse_dedup_package(blob)
    return b"".join(decompress_bytes(store[s], codec) for s in order)

def build_dedup_package_stream(chunks_iter, codec: str, mode: str, jobs: int = 1,
                               batch: int = 16):
    """نسخة متدفقة من البناء: الـ blobs المضغوطة على SQLite مؤقت (لا RAM)،
    والضغط بدفعات متوازية محدودة. ترجع None لو chunk واحد فقط (لا فائدة).
    التنسيق مطابق تماماً للنسخة القديمة (متوافق مع المفككات الأصلية)."""
    import json
    from .chunkstore import temp_store
    from .parallel import compress_many
    order: list[dict] = []
    seen: set[str] = set()
    first_seen: list[str] = []
    pending: list[tuple[str, bytes]] = []
    total = 0
    with temp_store() as store:
        def flush():
            for h, cdata in compress_many(pending, codec, mode, jobs):
                store.put(h, cdata)
            pending.clear()
        for ch in chunks_iter:
            d = hashlib.sha256(ch).hexdigest()
            order.append({"sha": d, "size": len(ch)})
            total += 1
            if d not in seen:
                seen.add(d)
                first_seen.append(d)
                pending.append((d, ch))
                if len(pending) >= batch:
                    flush()
        flush()
        if total <= 1:
            return None
        man = json.dumps({"codec": codec, "manifest": order,
                          "order": [m["sha"] for m in order]}).encode()
        buf = bytearray()
        buf += struct.pack(">I", len(man)) + man
        buf += struct.pack(">I", len(first_seen))
        for h in first_seen:
            cdata = store.get(h)
            hb = h.encode()
            buf += struct.pack(">I", len(hb)) + hb
            buf += struct.pack(">Q", len(cdata)) + cdata
        return bytes(buf), {"unique": len(first_seen), "total_chunks": total}

def restore_dedup_package_to(blob: bytes, fout, on_chunk=None) -> str:
    """فك متدفق إلى ملف: الـ blobs المضغوطة على SQLite مؤقت، والإخراج chunk-chunk
    (الذاكرة ≈ أكبر chunk فقط). ترجع اسم الـ codec. ترفع CorruptPackageError عند التلف."""
    import json
    from .codecs import decompress_bytes
    from .chunkstore import temp_store
    from .errors import CorruptPackageError
    try:
        off = 0
        (mlen,) = struct.unpack_from(">I", blob, off); off += 4
        man = json.loads(blob[off:off + mlen].decode()); off += mlen
        codec = man.get("codec", "lzma")
        (n,) = struct.unpack_from(">I", blob, off); off += 4
        with temp_store() as store:
            for _ in range(n):
                (sl,) = struct.unpack_from(">I", blob, off); off += 4
                sha = blob[off:off + sl].decode(); off += sl
                (dl,) = struct.unpack_from(">Q", blob, off); off += 8
                store.put(sha, blob[off:off + dl]); off += dl
            for m in man["manifest"]:
                raw = decompress_bytes(store.get(m["sha"]), codec)
                fout.write(raw)
                if on_chunk is not None:
                    on_chunk(len(raw))
        return codec
    except (struct.error, KeyError, ValueError, UnicodeDecodeError) as e:
        raise CorruptPackageError(f"حزمة dedup تالفة: {e} / corrupt dedup package")
