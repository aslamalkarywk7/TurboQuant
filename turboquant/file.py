"""File compression: generic large files (400MB -> 115MB balanced / -> 20MB extreme).

- صيغة الحاوية الخاصة: .tqz (header صغير + بيانات مضغوطة) لتُستخدم داخل برامجك.
- اختيار تلقائي لأفضل codec متاح: zstd > lzma > bz2 > gzip
- streaming/chunked حتى لا تنفجر الذاكرة مع الملفات الكبيرة.

ملاحظة أمانة علمية: ضغط lossless من 400م إلى 20م (20x) مستحيل للبيانات
العشوائية/المشفرة/الفيديو المضغوط أصلاً. لذلك وضع extreme:
  - للبيانات القابلة للضغط (نصوص، logs، raw): يحاول lzma-9 / zstd-22
  - للصور: يعيد الترميز lossy عبر turboquant.image (هنا يتحقق الـ 20x فعلاً)
  - غير ذلك: best-effort + تقرير صادق بالنسبة المحققة.
"""
from __future__ import annotations
import bz2
import gzip
import json
import lzma
import os
import struct

from .presets import get_preset, target_for_mode
from .utils import format_size, ratio_stats, ensure_parent

MAGIC = b"TQZ1"
HEADER_LEN_FMT = ">I"  # طول JSON header

def _have_zstd() -> bool:
    try:
        import zstandard  # type: ignore
        return True
    except Exception:
        return False

def _pick_codec(want: str) -> str:
    want = (want or "auto").lower()
    if want != "auto":
        if want == "zstd" and not _have_zstd():
            raise RuntimeError("zstandard غير مثبت: pip install zstandard")
        if want == "brotli":
            try:
                import brotli  # noqa
            except Exception:
                raise RuntimeError("brotli غير مثبت: pip install brotli")
        return want
    if _have_zstd():
        return "zstd"
    try:
        import brotli  # noqa
        return "brotli"
    except Exception:
        pass
    return "lzma"  # موجود دائماً في stdlib

# ---------- streaming compress / decompress ----------

def _compress_stream(fin, fout, codec: str, zstd_level: int, lzma_preset: int, chunk: int = 1 << 20,
                     on_chunk=None, cancel=None):
    def _tick(n: int, phase: str):
        if cancel is not None:
            cancel.check(phase)
        if on_chunk is not None:
            on_chunk(n)
    if codec == "zstd":
        import zstandard as zstd
        cctx = zstd.ZstdCompressor(level=zstd_level)
        with cctx.stream_writer(fout) as w:
            while True:
                b = fin.read(chunk)
                if not b:
                    break
                _tick(len(b), "compress:" + codec)
                w.write(b)
    elif codec == "lzma":
        with lzma.LZMAFile(fout, mode="wb", preset=lzma_preset,
                           filters=[{"id": lzma.FILTER_LZMA2, "preset": lzma_preset}]) as w:
            while True:
                b = fin.read(chunk)
                if not b:
                    break
                _tick(len(b), "compress:" + codec)
                w.write(b)
    elif codec == "bz2":
        with bz2.BZ2File(fout, mode="wb", compresslevel=9) as w:
            while True:
                b = fin.read(chunk)
                if not b:
                    break
                _tick(len(b), "compress:" + codec)
                w.write(b)
    elif codec == "brotli":
        import brotli
        comp = brotli.Compressor(quality=11)
        while True:
            b = fin.read(chunk)
            if not b:
                break
            _tick(len(b), "compress:" + codec)
            fout.write(comp.process(b))
        fout.write(comp.finish())
    elif codec == "gzip":
        with gzip.GzipFile(fileobj=fout, mode="wb", compresslevel=9) as w:
            while True:
                b = fin.read(chunk)
                if not b:
                    break
                _tick(len(b), "compress:" + codec)
                w.write(b)
    else:
        raise ValueError(codec)

def _decompress_stream(fin, fout, codec: str, chunk: int = 1 << 20,
                       on_chunk=None, cancel=None):
    def _tick(n: int, phase: str):
        if cancel is not None:
            cancel.check(phase)
        if on_chunk is not None:
            on_chunk(n)
    if codec == "zstd":
        import zstandard as zstd
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(fin) as r:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                _tick(len(b), "decompress:" + codec)
                fout.write(b)
    elif codec == "brotli":
        import brotli
        # فك متدفق (كان يقرأ الدخل كله في الذاكرة)
        dec = brotli.Decompressor()
        while True:
            b = fin.read(chunk)
            if not b:
                break
            _tick(len(b), "decompress:" + codec)
            out = dec.process(b)
            if out:
                fout.write(out)
    elif codec == "lzma":
        with lzma.LZMAFile(fin, mode="rb") as r:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                _tick(len(b), "decompress:" + codec)
                fout.write(b)
    elif codec == "bz2":
        with bz2.BZ2File(fin, mode="rb") as r:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                _tick(len(b), "decompress:" + codec)
                fout.write(b)
    elif codec == "gzip":
        with gzip.GzipFile(fileobj=fin, mode="rb") as r:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                _tick(len(b), "decompress:" + codec)
                fout.write(b)
    else:
        raise ValueError(codec)

# ---------- public API ----------

def compress_file(
    src: str,
    dst: str | None = None,
    mode: str = "balanced",
    codec: str = "auto",
    chunk_mb: int | None = None,
    on_progress=None,
    cancel=None,
) -> dict:
    """اضغط أي ملف إلى .tqz.

    mode:
      fast     -> أسرع، ضغط خفيف
      balanced -> يستهدف ~28% (400م -> ~115م) للبيانات القابلة للضغط
      extreme  -> أقصى lossless (zstd-22 / lzma-9) - قد يصل 400م -> ~20م للنصوص المتكررة
      micro_800k -> يحاول الوصول لـ <=800KB (ينجح فقط لو البيانات قابلة جداً للضغط)
    """
    preset = get_preset(mode)
    codec = _pick_codec(codec if codec != "auto" else preset.file_codec)
    if dst is None:
        dst = src + ".tqz"
    ensure_parent(dst)
    chunk = int((chunk_mb or preset.chunk_mb) * 1024 * 1024)

    meta = {"codec": codec, "orig_name": os.path.basename(src),
            "mode": mode, "orig_size": os.path.getsize(src)}
    header = json.dumps(meta).encode("utf-8")

    import tempfile
    tmp = dst + ".tmp"
    # نكتب الجسم المضغوط أولاً في ملف مؤقت ثم ندمجه مع الهيدر (لتفادي تحميل الملف كاملاً)
    body_tmp = tmp + ".body"
    total = os.path.getsize(src)
    done = {"n": 0}
    def _cb(n: int):
        done["n"] += n
        if on_progress is not None:
            on_progress(min(done["n"], total), total, "compress")
    try:
        with open(src, "rb") as fin, open(body_tmp, "wb") as body:
            _compress_stream(fin, body, codec, preset.zstd_level, preset.lzma_preset, chunk,
                             on_chunk=_cb if (on_progress or cancel) else None, cancel=cancel)
        with open(body_tmp, "rb") as body, open(tmp, "wb") as out:
            out.write(MAGIC)
            out.write(struct.pack(HEADER_LEN_FMT, len(header)))
            out.write(header)
            while True:
                b = body.read(chunk)
                if not b:
                    break
                out.write(b)
        os.replace(tmp, dst)
    finally:
        # لا مخلفات: امسح المؤقتات دائماً (حتى عند الإلغاء/الفشل)
        for p in (body_tmp, tmp):
            try:
                if os.path.exists(p) and os.path.abspath(p) != os.path.abspath(dst):
                    os.remove(p)
            except OSError:
                pass
    if on_progress is not None:
        on_progress(total, total, "compress")

    orig = os.path.getsize(src)
    new = os.path.getsize(dst)
    info = ratio_stats(orig, new)
    info.update({"output": dst, "codec": codec, "mode": mode,
                 "orig_h": format_size(orig), "new_h": format_size(new),
                 "target_h": format_size(target_for_mode(orig, mode) or 0)})
    return info


def decompress_file(src: str, dst: str | None = None, on_progress=None, cancel=None,
                    max_output_bytes: int | None = None) -> dict:
    """فك ضغط ملف .tqz إلى أصله (v1 بلا sha — لا تحقق ممكن، والسقف يحمي من المتفجرات)."""
    from .errors import CorruptPackageError
    from .limits import CappedWriter, resolve_cap
    with open(src, "rb") as f:
        magic = f.read(4)
        if magic != MAGIC:
            raise CorruptPackageError("ليس ملف TurboQuant (.tqz) صالحاً")
        try:
            (hlen,) = struct.unpack(HEADER_LEN_FMT, f.read(4))
            meta = json.loads(f.read(hlen).decode("utf-8"))
        except (struct.error, ValueError, UnicodeDecodeError) as e:
            raise CorruptPackageError(f"هيدر v1 تالف: {e}")
        codec = meta.get("codec", "lzma")
        if dst is None:
            base = src[:-4] if src.endswith(".tqz") else src + ".out"
            # استعد الاسم الأصلي لو أمكن (basename فقط — حماية من path traversal)
            d = os.path.dirname(os.path.abspath(src))
            safe_name = os.path.basename(meta.get("orig_name") or os.path.basename(base))
            dst = os.path.join(d, safe_name or os.path.basename(base))
            if os.path.abspath(dst) == os.path.abspath(src):
                dst = dst + ".out"
        ensure_parent(dst)
        import tempfile
        total = meta.get("orig_size", 0) or os.path.getsize(src)
        done = {"n": 0}
        def _cb(n: int):
            done["n"] += n
            if on_progress is not None:
                on_progress(min(done["n"], total), total, "decompress")
        cap = resolve_cap(max_output_bytes, os.path.getsize(src))
        # f الآن عند بداية الجسم المضغوط -> فك تدفقي مُحصى ومُسقوف
        with open(dst, "wb") as raw_out:
            out = CappedWriter(raw_out, cap)
            try:
                _decompress_stream(f, out, codec, on_chunk=_cb if (on_progress or cancel) else None,
                                   cancel=cancel)
            except CorruptPackageError:
                raise
            except Exception as e:
                from .progress import CancelledError
                from .errors import OutputLimitError
                if isinstance(e, (CancelledError, OutputLimitError)):
                    raise
                raise CorruptPackageError(f"فك v1 فشل — حاوية تالفة على الأرجح ({type(e).__name__})")
        if on_progress is not None:
            on_progress(total, total, "decompress")
    return {"output": dst, "codec": codec, "size": os.path.getsize(dst),
            "size_h": format_size(os.path.getsize(dst))}


def compress_to_target_size(
    src: str,
    dst: str | None = None,
    target_bytes: int = 800 * 1024,
    allow_lossy_image: bool = True,
) -> dict:
    """حاول الوصول لحجم مستهدف (افتراضي 800KB).

    - لو الملف صورة و allow_lossy_image=True -> يستخدم ضغط الصور (وهنا الـ 800K مضمون غالباً).
    - لو ملف عام -> يجرّب codecs من الأسرع للأقوى ويعيد أفضل نتيجة (best-effort).
    """
    from .image import IMAGE_EXTS, compress_image
    ext = os.path.splitext(src)[1].lower()
    if allow_lossy_image and ext in IMAGE_EXTS:
        # الصور: lossy يحقق المستحيل (400م صورة خام -> <800K ممكن فعلاً)
        out = dst or (os.path.splitext(src)[0] + ".tq.webp")
        # micro_800k مخصص لهذا
        return compress_image(src, out, target_bytes=target_bytes, mode="micro_800k")

    # ملف عام: جرّب بالتدريج
    import tempfile
    trials: list[tuple[str, dict | None]] = []
    order = ["zstd", "lzma", "bz2", "gzip"] if _have_zstd() else ["lzma", "bz2", "gzip"]
    best = None
    for codec in order:
        t = (dst + f".try-{codec}.tqz") if dst else (src + f".try-{codec}.tqz")
        try:
            # extreme يعطي أعلى مستوى لكل codec
            info = compress_file(src, t, mode="extreme", codec=codec)
            trials.append((codec, info))
            if best is None or info["new"] < best[1]["new"]:
                best = (codec, info)
            if info["new"] <= target_bytes:
                if dst and info["output"] != dst:
                    os.replace(info["output"], dst)
                    info["output"] = dst
                info["hit_target"] = True
                # نظّف باقي التجارب
                for c, inf in trials:
                    if inf and inf["output"] != info["output"] and os.path.exists(inf["output"]):
                        try:
                            os.remove(inf["output"])
                        except OSError:
                            pass
                return info
        except Exception as e:
            trials.append((codec, None))
            # احتفظ بآخر خطأ لرفعه لو فشلت كل المحاولات
            last_err = e
    # لم نصل للهدف -> أعد أفضل نتيجة
    if best is None:
        raise RuntimeError(f"فشل ضغط الملف بكل الـ codecs: {last_err}")
    info = best[1]
    if dst and info["output"] != dst:
        os.replace(info["output"], dst)
        info["output"] = dst
    for c, inf in trials:
        if inf and os.path.exists(inf["output"]) and inf["output"] != info["output"]:
            try:
                os.remove(inf["output"])
            except OSError:
                pass
    info["hit_target"] = info["new"] <= target_bytes
    info["note_ar"] = ("لم يصل للهدف لأن البيانات غير قابلة للضغط أكثر (مشفرة/مضغوطة أصلاً). "
                       "للوسائط استخدم ضغط الصور/الفيديو lossy.")
    return info


def compress_dir(src_dir: str, dst: str | None = None, mode: str = "balanced") -> dict:
    """اضغط مجلد كامل (tar + ضغط). مريحة للنسخ الاحتياطي."""
    import tarfile, tempfile
    preset = get_preset(mode)
    codec = _pick_codec(preset.file_codec)
    if dst is None:
        dst = src_dir.rstrip("/\\") + ".tqz"
    ensure_parent(dst)
    # tar إلى مؤقت ثم ضغط تدفقي بنفس حاوية tqz
    import tempfile
    tmp_tar = dst + ".tar.tmp"
    with tarfile.open(tmp_tar, "w") as tar:
        tar.add(src_dir, arcname=os.path.basename(src_dir.rstrip("/\\")))
    try:
        info = compress_file(tmp_tar, dst, mode=mode, codec=codec)
        info["src_dir"] = src_dir
        return info
    finally:
        try:
            os.remove(tmp_tar)
        except OSError:
            pass
