"""codecs.py — طبقة codecs موحدة lossless (bit-identical مضمون).

الأولوية: zstd > brotli > lzma > bz2 > gzip (الكل lossless).
كل دالة هنا تحافظ على البايتات 100% — لا يوجد أي فقد جودة.
"""
from __future__ import annotations
import bz2
import gzip
import io
import lzma

def available_codecs() -> list[str]:
    out = ["lzma", "bz2", "gzip"]
    try:
        import zstandard  # noqa
        out.insert(0, "zstd")
    except Exception:
        pass
    try:
        import brotli  # noqa
        out.insert(1 if "zstd" in out else 0, "brotli")
    except Exception:
        pass
    out.append("store")  # تخزين خام بلا ضغط (للبيانات العشوائية — أسرع وأصدق)
    return out

def _zstd_level(mode: str) -> int:
    return {"fast": 3, "balanced": 12, "max": 19, "ultra": 22, "extreme": 22, "micro_800k": 22}.get(mode, 12)

def _lzma_preset(mode: str) -> int:
    return {"fast": 1, "balanced": 6, "max": 9, "ultra": 9, "extreme": 9, "micro_800k": 9}.get(mode, 6)

def _brotli_quality(mode: str) -> int:
    return {"fast": 4, "balanced": 8, "max": 11, "ultra": 11, "extreme": 11, "micro_800k": 11}.get(mode, 8)

def compress_bytes(data: bytes, codec: str = "auto", mode: str = "balanced") -> bytes:
    codec = codec.lower()
    if codec == "auto":
        codec = available_codecs()[0]
    if codec == "zstd":
        import zstandard as zstd
        return zstd.ZstdCompressor(level=_zstd_level(mode)).compress(data)
    if codec == "brotli":
        import brotli
        return brotli.compress(data, quality=_brotli_quality(mode))
    if codec == "lzma":
        return lzma.compress(data, preset=_lzma_preset(mode),
                             filters=[{"id": lzma.FILTER_LZMA2, "preset": _lzma_preset(mode)}])
    if codec == "bz2":
        return bz2.compress(data, compresslevel=9)
    if codec == "gzip":
        return gzip.compress(data, compresslevel=9)
    if codec == "store":
        return bytes(data)
    raise ValueError(f"codec غير معروف: {codec}")

def decompress_bytes(data: bytes, codec: str, max_output_bytes: int | None = None) -> bytes:
    """Decompress with optional zip-bomb cap (None = auto 1GB min / 100000x ratio)."""
    codec = codec.lower()
    if codec == "zstd":
        import zstandard as zstd
        # zstd supports an explicit output cap to stop decompression bombs early.
        if max_output_bytes:
            out = zstd.ZstdDecompressor().decompress(data, max_output_size=max_output_bytes)
        else:
            from .limits import resolve_cap
            out = zstd.ZstdDecompressor().decompress(data, max_output_size=resolve_cap(None, len(data)))
        _check_cap(out, len(data), max_output_bytes)
        return out
    if codec == "brotli":
        import brotli
        out = brotli.decompress(data)
        _check_cap(out, len(data), max_output_bytes)
        return out
    if codec == "lzma":
        out = lzma.decompress(data)
        _check_cap(out, len(data), max_output_bytes)
        return out
    if codec == "bz2":
        out = bz2.decompress(data)
        _check_cap(out, len(data), max_output_bytes)
        return out
    if codec == "gzip":
        out = gzip.decompress(data)
        _check_cap(out, len(data), max_output_bytes)
        return out
    if codec == "store":
        out = bytes(data)
        _check_cap(out, len(data), max_output_bytes)
        return out
    raise ValueError(codec)


def _check_cap(out: bytes, compressed_len: int, max_output_bytes: int | None):
    from .limits import resolve_cap
    from .errors import OutputLimitError
    cap = resolve_cap(max_output_bytes, compressed_len)
    if len(out) > cap:
        raise OutputLimitError(
            f"تجاوز حد الإخراج ({len(out)} > {cap} بايت) — حاوية مشبوهة؟")

def compress_stream(fin, fout, codec: str, mode: str = "balanced", chunk: int = 1 << 20,
                    on_chunk=None, cancel=None):
    codec = codec.lower()
    def _tick(n: int, phase: str):
        if cancel is not None:
            cancel.check(phase)
        if on_chunk is not None:
            on_chunk(n)
    if codec == "zstd":
        import zstandard as zstd
        cctx = zstd.ZstdCompressor(level=_zstd_level(mode))
        # closefd=False حتى لا يُغلق BytesIO الناتج (كان يسبب ValueError)
        with cctx.stream_writer(fout, closefd=False) as w:
            while True:
                b = fin.read(chunk)
                if not b:
                    break
                w.write(b)
                _tick(len(b), "compress:" + codec)
        return
    if codec == "brotli":
        import brotli
        comp = brotli.Compressor(quality=_brotli_quality(mode))
        while True:
            b = fin.read(chunk)
            if not b:
                break
            fout.write(comp.process(b))
            _tick(len(b), "compress:" + codec)
        fout.write(comp.finish())
        return
    if codec == "lzma":
        with lzma.LZMAFile(fout, mode="wb", preset=_lzma_preset(mode)) as w:
            while True:
                b = fin.read(chunk)
                if not b:
                    break
                w.write(b)
                _tick(len(b), "compress:" + codec)
        return
    if codec == "bz2":
        with bz2.BZ2File(fout, mode="wb", compresslevel=9) as w:
            while True:
                b = fin.read(chunk)
                if not b:
                    break
                w.write(b)
                _tick(len(b), "compress:" + codec)
        return
    if codec == "gzip":
        with gzip.GzipFile(fileobj=fout, mode="wb", compresslevel=9) as w:
            while True:
                b = fin.read(chunk)
                if not b:
                    break
                w.write(b)
                _tick(len(b), "compress:" + codec)
        return
    if codec == "store":
        while True:
            b = fin.read(chunk)
            if not b:
                break
            fout.write(b)
            _tick(len(b), "compress:store")
        return
    raise ValueError(codec)

def decompress_stream(fin, fout, codec: str, chunk: int = 1 << 20,
                      on_chunk=None, cancel=None):
    codec = codec.lower()
    def _tick(n: int, phase: str):
        if cancel is not None:
            cancel.check(phase)
        if on_chunk is not None:
            on_chunk(n)
    if codec == "zstd":
        import zstandard as zstd
        with zstd.ZstdDecompressor().stream_reader(fin) as r:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                fout.write(b)
                _tick(len(b), "decompress:" + codec)
        return
    if codec == "brotli":
        import brotli
        # فك متدفق (لا تحميل كامل في الذاكرة + دعم الإلغاء/التقدم)
        dec = brotli.Decompressor()
        while True:
            b = fin.read(chunk)
            if not b:
                break
            _tick(len(b), "decompress:" + codec)
            out = dec.process(b)
            if out:
                fout.write(out)
        return
    if codec == "lzma":
        with lzma.LZMAFile(fin, mode="rb") as r:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                fout.write(b)
                _tick(len(b), "decompress:" + codec)
        return
    if codec == "bz2":
        with bz2.BZ2File(fin, mode="rb") as r:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                fout.write(b)
                _tick(len(b), "decompress:" + codec)
        return
    if codec == "gzip":
        with gzip.GzipFile(fileobj=fin, mode="rb") as r:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                fout.write(b)
                _tick(len(b), "decompress:" + codec)
        return
    if codec == "store":
        while True:
            b = fin.read(chunk)
            if not b:
                break
            fout.write(b)
            _tick(len(b), "decompress:store")
        return
    raise ValueError(codec)

def best_of(data: bytes, mode: str = "balanced", jobs: int = 1) -> tuple[str, bytes]:
    """جرّب كل codecs المتاحة واختر الأصغر — lossless دائماً (jobs>1 → متوازي)."""
    if jobs is not None and int(jobs) > 1:
        from .parallel import best_of_parallel
        return best_of_parallel(data, mode, jobs)
    best = None
    for c in available_codecs():
        try:
            b = compress_bytes(data, c, mode)
        except Exception:
            continue
        if best is None or len(b) < len(best[1]):
            best = (c, b)
    if best is None:
        raise RuntimeError("لا يوجد codec متاح")
    return best
