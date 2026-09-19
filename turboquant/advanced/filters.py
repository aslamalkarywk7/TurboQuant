"""filters.py — مرشحات تنبؤية بأسلوب PNG (None/Sub/Up/Average/Paeth)، lossless.

الفكرة (من مواصفة PNG): بدل تخزين البايت، خزّن الفرق بينه وبين توقع من
جيرانه (يسار/أعلى). البيانات الملساء (صور خام، جداول، مصفوفات) تتحول لأصفار
وأرقام صغيرة → تنضغط بقوة. اختيار أفضل مرشح لكل صف عبر sum-of-abs.

الإطار: [orig_len: u32][stride: u16][nrows: u32][per row: filter: u8 + stride bytes]
stride يُكتشف تلقائياً من المرشحين [1,2,4,8,16,64,256,1024] عبر وكيل Up السريع.
"""
from __future__ import annotations
import struct

STRIDE_CANDIDATES = (1, 2, 4, 8, 16, 64, 256, 1024)

def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c

def _filter_row(f: int, row: bytes, prev: bytes) -> bytes:
    n = len(row)
    out = bytearray(n)
    if f == 0:  # None
        return bytes(row)
    if f == 1:  # Sub
        for i in range(n):
            a = row[i - 1] if i >= 1 else 0
            out[i] = (row[i] - a) & 0xFF
    elif f == 2:  # Up
        for i in range(n):
            out[i] = (row[i] - prev[i]) & 0xFF
    elif f == 3:  # Average
        for i in range(n):
            a = row[i - 1] if i >= 1 else 0
            out[i] = (row[i] - ((a + prev[i]) >> 1)) & 0xFF
    else:  # Paeth
        for i in range(n):
            a = row[i - 1] if i >= 1 else 0
            b = prev[i]
            c = prev[i - 1] if i >= 1 else 0
            out[i] = (row[i] - _paeth(a, b, c)) & 0xFF
    return bytes(out)

def _unfilter_row(f: int, row: bytes, prev: bytes) -> bytes:
    n = len(row)
    out = bytearray(n)
    if f == 0:
        return bytes(row)
    if f == 1:
        for i in range(n):
            a = out[i - 1] if i >= 1 else 0
            out[i] = (row[i] + a) & 0xFF
    elif f == 2:
        for i in range(n):
            out[i] = (row[i] + prev[i]) & 0xFF
    elif f == 3:
        for i in range(n):
            a = out[i - 1] if i >= 1 else 0
            out[i] = (row[i] + ((a + prev[i]) >> 1)) & 0xFF
    else:
        for i in range(n):
            a = out[i - 1] if i >= 1 else 0
            b = prev[i]
            c = prev[i - 1] if i >= 1 else 0
            out[i] = (row[i] + _paeth(a, b, c)) & 0xFF
    return bytes(out)

def _score(raw: bytes) -> int:
    return sum(v if v < 128 else 256 - v for v in raw)

def _pick_stride(data: bytes) -> int:
    """وكيل سريع: stride الذي يقلل sum-abs لمرشح Up على عينة 64KB."""
    sample = data[:65536]
    best, best_stride = None, 1
    for st in STRIDE_CANDIDATES:
        if st >= len(sample):
            break
        prev = bytes(st)
        tot, off = 0, 0
        while off < len(sample):
            row = sample[off:off + st]
            if len(row) < st:
                row = row + bytes(st - len(row))
            tot += _score(_filter_row(2, row, prev))
            prev = row  # Up يقارن بالصف الخام السابق
            off += st
            if best is not None and tot > best:
                break
        if best is None or tot < best:
            best, best_stride = tot, st
    return best_stride

def filters_encode(data: bytes, stride: int | None = None) -> bytes:
    if not data:
        return struct.pack(">IH", 0, 1) + struct.pack(">I", 0)
    st = stride or _pick_stride(data)
    rows = [data[i:i + st] for i in range(0, len(data), st)]
    out = bytearray(struct.pack(">IH", len(data), st) + struct.pack(">I", len(rows)))
    prev = bytes(st)
    for row in rows:
        if len(row) < st:
            row = row + bytes(st - len(row))
        best_f, best_d, best_s = 0, row, _score(row)
        for f in (1, 2, 3, 4):
            d = _filter_row(f, row, prev)
            s = _score(d)
            if s < best_s:
                best_f, best_d, best_s = f, d, s
        out.append(best_f)
        out += best_d
        prev = row
    return bytes(out)

def filters_decode(data: bytes) -> bytes:
    if len(data) < 8:
        raise ValueError("filters payload تالف (قصير)")
    orig_len, stride = struct.unpack_from(">IH", data, 0)
    (nrows,) = struct.unpack_from(">I", data, 6)
    off = 10
    out = bytearray()
    prev = bytes(stride)
    for _ in range(nrows):
        if off + 1 + stride > len(data):
            raise ValueError("filters payload تالف (صف)")
        f = data[off]
        if f > 4:
            raise ValueError("filters payload فيه مرشح مجهول")
        row = _unfilter_row(f, data[off + 1:off + 1 + stride], prev)
        out += row
        prev = row
        off += 1 + stride
    if off != len(data):
        raise ValueError("filters payload فيه بايتات زائدة")
    return bytes(out[:orig_len])
