"""delta.py — ترميز الفروقات (Delta / XOR) كتحويل تمهيدي lossless.

الفكرة: البيانات المتسلسلة (صوت PCM، حساسات، أسعار، إحداثيات) قيمها متقاربة،
لكن بايتاتها الخام تبدو عشوائية للضاغط. الفروقات بين القيم المتتالية أرقام
صغيرة حول الصفر → تنضغط بقوة. الفك عكسي تماماً (bit-identical).

- delta8: فرق بايت-بايت (mod 256)، نفس الطول، بدون هيدر.
- xor8: XOR بايت-بايت، ممتاز للنصوص/القوائم (البتات العليا تثبت).
- delta16le: فرق عينات 16-بت (WAV/حساسات)، إطار [pad u8] + نفس الطول تقريباً.
"""
from __future__ import annotations
import struct

def delta8_encode(data: bytes) -> bytes:
    if not data:
        return b""
    out = bytearray(len(data))
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = (data[i] - data[i - 1]) & 0xFF
    return bytes(out)

def delta8_decode(data: bytes) -> bytes:
    if not data:
        return b""
    out = bytearray(len(data))
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = (data[i] + out[i - 1]) & 0xFF
    return bytes(out)

def xor8_encode(data: bytes) -> bytes:
    if not data:
        return b""
    out = bytearray(len(data))
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = data[i] ^ data[i - 1]
    return bytes(out)

def xor8_decode(data: bytes) -> bytes:
    if not data:
        return b""
    out = bytearray(len(data))
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = data[i] ^ out[i - 1]
    return bytes(out)

def delta16le_encode(data: bytes) -> bytes:
    """عينات int16 little-endian → فروقات. إطار: [pad: u8] + payload."""
    if not data:
        return b""
    pad = (2 - (len(data) % 2)) % 2
    raw = data + (b"\x00" * pad)
    n = len(raw) // 2
    vals = struct.unpack(f"<{n}h", raw)
    out = bytearray(1 + len(raw))
    out[0] = pad
    struct.pack_into("<h", out, 1, vals[0])
    for i in range(1, n):
        struct.pack_into("<h", out, 1 + 2 * i, ((vals[i] - vals[i - 1] + 32768) % 65536) - 32768)
    return bytes(out)

def delta16le_decode(data: bytes) -> bytes:
    if not data:
        return b""
    pad = data[0]
    raw = data[1:]
    n = len(raw) // 2
    diffs = struct.unpack(f"<{n}h", raw)
    out = bytearray(len(raw))
    acc = diffs[0]
    struct.pack_into("<h", out, 0, acc)
    for i in range(1, n):
        acc = ((acc + diffs[i] + 32768) % 65536) - 32768
        struct.pack_into("<h", out, 2 * i, acc)
    return bytes(out[:len(out) - pad]) if pad else bytes(out)

def xor_with(data: bytes, ref: bytes) -> bytes:
    """XOR مع مرجع بنفس الطول (لبنات متشابهة). عكسه نفسه."""
    if len(data) != len(ref):
        raise ValueError("xor_with يتطلب نفس الطول")
    return bytes(a ^ b for a, b in zip(data, ref))
