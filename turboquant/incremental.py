"""incremental.py — نسخ تزايدية (borg-style): خزّن فروق الملف فقط عن نسخة أساس.

الفكرة: قسّم الملفين بنفس FastCDC، وقارن بصمات chunks. الدلتا = chunks الجديدة
فقط + manifest الترتيب الجديد. نسخة سجل 100MB تتغير فيها 2MB → دلتا ~2MB.

الذاكرة محدودة دائماً (v2.4):
- الإنشاء: بصمات الأساس فقط في RAM (64 حرف/chunk)، والـ blobs الجديدة على
  SQLite مؤقت، والضغط بدفعات متوازية محدودة (لا O(n²) — مجموعة set للبحث).
- التركيب: فهرس (بصمة → إزاحة/طول) للأساس + قراءة شرائح عند الحاجة، وكتابة
  متدفقة مع sha جارٍ وسقف إخراج (لا تحميل كامل ولا قراءة ثانية).

الحاوية `.tqz` عادية مع method="delta" + حقول base_sha256/base_name/new_sha/new_size
في الهيدر (لا تغيير على تنسيق الـ body — نفس إطار dedup، §4 في FORMAT.md).
الفك يتطلب ملف الأساس نفسه ويتحقق من بصمته أولاً (حماية من التركيب الخطأ).
"""
from __future__ import annotations
import hashlib
import json
import os
import struct

from .lossless import _write_pkg, _read_pkg, sha256_file
from .utils import format_size, ratio_stats, ensure_parent
from .errors import BaseMismatchError, CorruptPackageError, VerificationError

def _iter_hashed(path: str):
    """مولّد (sha, offset, length, chunk) بقراءة متدفقة واحدة."""
    from .dedup import chunk_file_stream
    off = 0
    for ch in chunk_file_stream(path):
        yield hashlib.sha256(ch).hexdigest(), off, len(ch), ch
        off += len(ch)

def create_delta(base_file: str, new_file: str, out: str | None = None,
                 codec: str = "auto", mode: str = "balanced", jobs: int = 1) -> dict:
    """ابنِ دلتا: الفروق بين new_file و base_file فقط (ذاكرة محدودة)."""
    from .codecs import available_codecs
    from .chunkstore import temp_store
    from .parallel import compress_many
    if out is None:
        out = new_file + ".tdelta.tqz"
    ensure_parent(out)
    if codec == "auto":
        codec = available_codecs()[0]
    base_sha = sha256_file(base_file)
    new_sha = sha256_file(new_file)
    base_known: set[str] = set()
    for h, _off, _ln, _ch in _iter_hashed(base_file):
        base_known.add(h)
    order: list[str] = []
    seen_new: set[str] = set()
    first_seen: list[str] = []
    pending: list[tuple[str, bytes]] = []
    with temp_store() as store:
        def flush():
            for h, cdata in compress_many(pending, codec, mode, jobs):
                store.put(h, cdata)
            pending.clear()
        for h, _off, _ln, ch in _iter_hashed(new_file):
            order.append(h)
            if h not in base_known and h not in seen_new:
                seen_new.add(h)
                first_seen.append(h)
                pending.append((h, ch))
                if len(pending) >= 16:
                    flush()
        flush()
        man = json.dumps({"codec": codec, "order": order}).encode()
        body = bytearray(struct.pack(">I", len(man)) + man)
        body += struct.pack(">I", len(first_seen))
        for h in first_seen:
            cdata = store.get(h)
            hb = h.encode()
            body += struct.pack(">I", len(hb)) + hb + struct.pack(">Q", len(cdata)) + cdata
    meta = {"v": 2, "kind": "delta", "codec": f"delta+{codec}", "method": "delta",
            "pre": "none", "transform": "none", "tparams": {},
            "base_name": os.path.basename(base_file), "base_sha256": base_sha,
            "orig_name": os.path.basename(new_file), "new_sha": new_sha,
            "orig_size": os.path.getsize(new_file), "new_chunks": len(first_seen),
            "total_chunks": len(order), "mode": mode, "lossless": True}
    _write_pkg(out, meta, bytes(body))
    info = ratio_stats(os.path.getsize(new_file), os.path.getsize(out))
    info.update({"output": out, "kind": "delta", "codec": f"delta+{codec}",
                 "new_chunks": len(first_seen), "total_chunks": len(order),
                 "reused_chunks": len(order) - len({h for h in order if h in seen_new}),
                 "lossless": True, "orig_h": format_size(os.path.getsize(new_file)),
                 "new_h": format_size(os.path.getsize(out))})
    return info

def apply_delta(base_file: str, delta_file: str, out: str | None = None,
                max_output_bytes: int | None = None) -> dict:
    """ركّب الدلتا على ملف الأساس → النسخة الجديدة (بتحقق مزدوج، تدفق كامل)."""
    from .codecs import decompress_bytes
    from .chunkstore import temp_store
    from .limits import CappedWriter, resolve_cap
    try:
        meta, body, _ = _read_pkg(delta_file)
    except Exception as e:
        from .errors import CorruptPackageError as _C
        raise _C(str(e))
    if meta.get("method") != "delta":
        raise CorruptPackageError("ليست حزمة دلتا (method != delta)")
    if sha256_file(base_file) != meta.get("base_sha256"):
        raise BaseMismatchError("ملف الأساس لا يطابق الدلتا (base_sha256 مختلف) — مرّر النسخة الصحيحة")
    if out is None:
        # basename فقط — حماية من path traversal
        safe_name = os.path.basename(meta.get("orig_name") or (os.path.basename(delta_file) + ".out"))
        d = os.path.dirname(os.path.abspath(delta_file))
        out = os.path.join(d, safe_name or (os.path.basename(delta_file) + ".out"))
    ensure_parent(out)
    try:
        off = 0
        (ml,) = struct.unpack_from(">I", body, off); off += 4
        man = json.loads(body[off:off + ml].decode()); off += ml
        (n,) = struct.unpack_from(">I", body, off); off += 4
        codec = man.get("codec", "lzma")
        with temp_store() as store:
            for _ in range(n):
                (sl,) = struct.unpack_from(">I", body, off); off += 4
                h = body[off:off + sl].decode(); off += sl
                (dl,) = struct.unpack_from(">Q", body, off); off += 8
                store.put(h, body[off:off + dl]); off += dl
            # فهرس الأساس: بصمة → (إزاحة، طول) فقط — البايتات تُقرأ عند الحاجة
            index: dict[str, tuple[int, int]] = {}
            for h, o, ln, _ch in _iter_hashed(base_file):
                index.setdefault(h, (o, ln))
            cap = resolve_cap(max_output_bytes, len(body))
            hasher = hashlib.sha256()
            with open(base_file, "rb") as bf, open(out, "wb") as raw_out:
                capped = CappedWriter(raw_out, cap, hasher)
                for h in man["order"]:
                    if store.contains(h):
                        try:
                            chunk_raw = decompress_bytes(store.get(h), codec)
                        except Exception as e:
                            raise CorruptPackageError(f"chunk دلتا تالف ({h[:16]}…): {type(e).__name__}")
                        capped.write(chunk_raw)
                    elif h in index:
                        o, ln = index[h]
                        bf.seek(o)
                        capped.write(bf.read(ln))
                    else:
                        raise CorruptPackageError(f"chunk مفقود في الدلتا والأساس: {h[:16]}…")
    except CorruptPackageError:
        raise
    except (struct.error, KeyError, ValueError, UnicodeDecodeError) as e:
        raise CorruptPackageError(f"حزمة دلتا تالفة: {e}")
    if hasher.hexdigest() != meta.get("new_sha"):
        raise VerificationError("التركيب تالف: البصمة النهائية لا تطابق")
    return {"output": out, "size": os.path.getsize(out), "size_h": format_size(os.path.getsize(out)),
            "verified": True}
