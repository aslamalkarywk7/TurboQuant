"""zdict.py — قواميس zstd (Dictionary compression) للملفات الصغيرة المتشابهة.

الفكرة: ملف JSONL/CSV/سجل واحد قد لا يملك تكراراً يكفي، لكن بنيته تتكرر
(مفاتيح، هيدرات، قوالب). ندرّب قاموساً من شرائح الملف نفسه (self-dictionary)
ونضغط به → توفير كبير حيث تفشل الضواغط العادية. القاموس يُضمَّن في الحاوية
فلا يحتاج المستقبِل أي ملف خارجي.

الإطار داخل body (فقط عند transform=zdict):
[dict_len: u32][dict bytes][zstd frame مضغوط بالقاموس]
"""
from __future__ import annotations
import struct

MIN_SAMPLES = 8
SAMPLE_SIZE = 4096
MAX_SLICES = 24

def _need_zstd():
    try:
        import zstandard as zstd
        return zstd
    except ImportError:
        raise RuntimeError("zdict يتطلب zstandard: pip install zstandard")

def pick_slices(data: bytes, n: int = MAX_SLICES, size: int = SAMPLE_SIZE) -> list[bytes]:
    """شرائح موزعة بالتساوي على الملف لتمثيل بنيته كلها."""
    if len(data) < MIN_SAMPLES * size:
        return []
    step = max(1, (len(data) - size) // n)
    out = []
    off = 0
    while off + size <= len(data) and len(out) < n:
        out.append(data[off:off + size])
        off += step
    return out

def train_dict(samples: list[bytes], dict_size: int = 32768) -> bytes:
    zstd = _need_zstd()
    if len(samples) < MIN_SAMPLES:
        raise ValueError(f"التدريب يحتاج ≥ {MIN_SAMPLES} عينات")
    d = zstd.train_dictionary(dict_size, samples)
    return d.as_bytes()

def dict_compress(data: bytes, zdict: bytes, level: int = 12) -> bytes:
    zstd = _need_zstd()
    cctx = zstd.ZstdCompressor(level=level, dict_data=zstd.ZstdCompressionDict(zdict),
                               write_content_size=True)
    return cctx.compress(data)

def dict_decompress(frame: bytes, zdict: bytes) -> bytes:
    zstd = _need_zstd()
    dctx = zstd.ZstdDecompressor(dict_data=zstd.ZstdCompressionDict(zdict))
    return dctx.decompress(frame)

def self_train(data: bytes, dict_size: int = 32768) -> bytes | None:
    """درّب قاموساً ذاتياً من الملف نفسه، أو None لو صغير/غير مناسب."""
    sl = pick_slices(data)
    if not sl:
        return None
    try:
        return train_dict(sl, dict_size)
    except Exception:
        return None

def pack_body(zdict: bytes, frame: bytes) -> bytes:
    return struct.pack(">I", len(zdict)) + zdict + frame

def unpack_body(body: bytes) -> tuple[bytes, bytes]:
    if len(body) < 4:
        raise ValueError("zdict body تالف (قصير)")
    (dl,) = struct.unpack_from(">I", body, 0)
    if 4 + dl > len(body):
        raise ValueError("zdict body تالف (قاموس)")
    return body[4:4 + dl], body[4 + dl:]
