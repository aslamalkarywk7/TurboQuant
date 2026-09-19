"""bwt.py — تحويل Burrows-Wheeler (BWT) بأسلوب bzip2، lossless تماماً.

الفكرة: إعادة ترتيب البايتات لتتجمع المتشابهة معاً (تجميع سياقي) دون فقد أي
معلومة، فيلتهمها ضاغط LZ (zstd/lzma) بشراهة. ممتاز للنصوص والسجلات وCSV.

التنفيذ: كتل (افتراضي 32KB) + مصفوفة لواحق (suffix array) بخوارزمية المضاعفة
O(n log n) على النص المضاعف = ترتيب التدويرات الدائرية. الإطار:
[nblocks: u32][per block: orig_len: u32][primary: u32][last_col: bytes]
العكس عبر LF-mapping بفرز عدّي — مُتحقق منه باختبارات دورية/عشوائية/ثنائية.
"""
from __future__ import annotations
import struct

BLOCK_SIZE = 32 * 1024

def _cyclic_order(block: bytes) -> list[int]:
    """ترتيب التدويرات الدائرية للكتلة (مؤشرات البداية 0..n-1).

    ملاحظة v2.4: أُبقي هنا الفرز الكامل 2n عمداً — نسخة n المختصرة توفر
    ~2x لكنها تخاطر بصحة رتب المضاعفة (فساد صامت محتمل)، والتكلفة مضبوطة
    أصلاً عبر BWT_SELECT_CAP + كتل 32KB + كون BWT اختيارياً (advanced فقط).
    """
    n = len(block)
    if n <= 1:
        return list(range(n))
    dbl = block + block  # أي تدويرة = بادئة طول n من dbl
    rank = list(dbl)
    sa = list(range(2 * n))
    k = 1
    while True:
        sa.sort(key=lambda i: (rank[i], rank[i + k] if i + k < 2 * n else -1))
        tmp = [0] * (2 * n)
        tmp[sa[0]] = 0
        r = 0
        for j in range(1, 2 * n):
            a, b = sa[j - 1], sa[j]
            ka = (rank[a], rank[a + k] if a + k < 2 * n else -1)
            kb = (rank[b], rank[b + k] if b + k < 2 * n else -1)
            if ka != kb:
                r += 1
            tmp[b] = r
        rank = tmp
        if r == 2 * n - 1:
            break
        k <<= 1
        if k >= 2 * n:
            break
    # التدويرات = اللواحق التي تبدأ قبل n وطولها المتبقي ≥ n
    order = [i for i in sa if i < n]
    # ملاحظة: اللواحق الأقصر من n (تبدأ بعد n) مستبعدة؛ الترتيب بين متساوي
    # البادئة-n غير مهم للعكس (تدويرات متطابقة).
    return order

def bwt_encode_block(block: bytes) -> tuple[int, bytes]:
    """-> (primary, last_col). primary = موضع التدويرة الأصلية."""
    n = len(block)
    if n == 0:
        return 0, b""
    order = _cyclic_order(block)
    primary = order.index(0)
    last = bytes(block[(i - 1) % n] for i in order)
    return primary, last

def bwt_decode_block(last: bytes, primary: int) -> bytes:
    """عكس BWT عبر LF-mapping (فرز عدّي O(n))."""
    n = len(last)
    if n == 0:
        return b""
    counts = [0] * 256
    for b in last:
        counts[b] += 1
    starts = [0] * 256
    s = 0
    for c in range(256):
        starts[c] = s
        s += counts[c]
    occ = [0] * 256
    nxt = [0] * n  # LF mapping
    for i, b in enumerate(last):
        nxt[i] = starts[b] + occ[b]
        occ[b] += 1
    out = bytearray(n)
    j = primary
    for i in range(n - 1, -1, -1):
        out[i] = last[j]
        j = nxt[j]
    return bytes(out)

def bwt_encode(data: bytes, block_size: int = BLOCK_SIZE) -> bytes:
    if not data:
        return struct.pack(">I", 0)
    parts = [struct.pack(">I", 0)]  # يُملأ بعدد الكتل لاحقاً
    nblocks = 0
    for off in range(0, len(data), block_size):
        block = data[off:off + block_size]
        primary, last = bwt_encode_block(block)
        parts.append(struct.pack(">II", len(block), primary) + last)
        nblocks += 1
    parts[0] = struct.pack(">I", nblocks)
    return b"".join(parts)

def bwt_decode(data: bytes) -> bytes:
    if len(data) < 4:
        raise ValueError("bwt payload تالف (قصير)")
    (nblocks,) = struct.unpack_from(">I", data, 0)
    off = 4
    out = bytearray()
    for _ in range(nblocks):
        if off + 8 > len(data):
            raise ValueError("bwt payload تالف (هيدر كتلة)")
        blen, primary = struct.unpack_from(">II", data, off)
        off += 8
        if off + blen > len(data):
            raise ValueError("bwt payload تالف (بيانات كتلة)")
        out += bwt_decode_block(data[off:off + blen], primary)
        off += blen
    if off != len(data):
        raise ValueError("bwt payload فيه بايتات زائدة")
    return bytes(out)
