"""TurboQuant v2 — مكتبة ضغط موحدة لكل الملفات (lossless افتراضياً).

الاستخدام داخل برامجك:
    import turboquant as tq
    # lossless لكل الأنواع — بدون أي فقد جودة (موصى به)
    tq.compress_lossless("report.pdf", "report.tqz", mode="max")
    tq.compress_lossless("photo.png", "photo.tqz")          # بكسل مطابق 100%
    tq.compress_lossless("data.csv", "data.tqz", mode="ultra")
    tq.decompress_lossless("report.tqz", "report.pdf")      # sha256 verified

    # lossy للصور فقط عند الحاجة لحجم صغير جداً (800KB)
    tq.compress_image("in.jpg", "out.webp", target_bytes=800*1024)

    # تلقائي ذكي
    tq.compress_auto("anything", mode="balanced")
"""
from __future__ import annotations

from .presets import PRESETS, get_preset, MICRO_MAX_BYTES
from .detect import detect_kind, suggest_pipeline
from .codecs import available_codecs
from .image import compress_image, compress_images_batch
from .file import compress_file, decompress_file, compress_to_target_size, compress_dir
from .lossless import compress_lossless, decompress_lossless, compress_dir_lossless, optimize_lossless
from .progress import CancelToken, CancelledError, make_text_bar
from .bench import benchmark, print_benchmark, format_table
from .cert import verify_package, format_certificate
from .advanced.pipeline import analyze_file, smart_select, TRANSFORMS, ADV_CAP
from .parallel import best_of_parallel, compress_many
from .crypto import encrypt_file, decrypt_file, encrypt_bytes, decrypt_bytes
from .incremental import create_delta, apply_delta
from .media import compress_video, compress_audio, have_ffmpeg, probe
from .errors import (TurboQuantError, CorruptPackageError, UnsupportedCodecError,
                     VerificationError, PasswordError, BaseMismatchError, OutputLimitError)
from .log import logger, debug_mode
from .utils import format_size

__version__ = "2.5.0"
__all__ = [
    "compress_lossless", "decompress_lossless", "compress_dir_lossless", "optimize_lossless",
    "compress_image", "compress_images_batch",
    "compress_file", "decompress_file", "compress_to_target_size", "compress_dir",
    "compress_auto", "decompress_auto",
    "detect_kind", "suggest_pipeline",
    "CancelToken", "CancelledError", "make_text_bar",
    "benchmark", "print_benchmark", "format_table",
    "verify_package", "format_certificate",
    "analyze_file", "smart_select", "TRANSFORMS", "ADV_CAP",
    "best_of_parallel", "compress_many",
    "encrypt_file", "decrypt_file", "encrypt_bytes", "decrypt_bytes",
    "create_delta", "apply_delta",
    "compress_video", "compress_audio", "have_ffmpeg", "probe",
    "TurboQuantError", "CorruptPackageError", "UnsupportedCodecError",
    "VerificationError", "PasswordError", "BaseMismatchError", "OutputLimitError",
    "logger", "debug_mode",
    "get_preset", "PRESETS", "format_size", "available_codecs",
]

def compress_auto(src: str, dst: str | None = None, mode: str = "balanced",
                  target_bytes: int | None = None, lossless: bool | None = None,
                  on_progress=None, cancel=None, advanced: bool = False,
                  jobs: int = 1, **kw) -> dict:
    """دالة موحدة ذكية لكل الملفات.

    - lossless=True (أو None مع ملفات غير صور): مسار lossless بدون فقد جودة.
    - صور + target_bytes: مسار lossy للوصول لحجم صغير (800KB).
    - advanced=True: فعّل نظام الخوارزميات المتقدمة (bwt/delta/filters/zdict).
    """
    import os
    from .image import IMAGE_EXTS
    if os.path.isdir(src):
        if lossless is False:
            return compress_dir(src, dst, mode=mode)
        return compress_dir_lossless(src, dst, mode=mode, on_progress=on_progress, cancel=cancel)
    ext = os.path.splitext(src)[1].lower()
    is_img = ext in IMAGE_EXTS
    # صور مع هدف حجمي صريح -> lossy (الطريقة الوحيدة للوصول لـ 800KB من صور ضخمة)
    if is_img and (target_bytes is not None or lossless is False or mode in ("micro_800k",)):
        tb = target_bytes or (800 * 1024 if mode in ("balanced", "micro_800k") else 400 * 1024)
        from .image import compress_image as ci
        return ci(src, dst, target_bytes=tb, mode=mode if mode in PRESETS else "balanced", **kw)
    # صور بدون هدف -> lossless افتراضياً (بدون فقد)
    if is_img and lossless is not False and target_bytes is None and mode in ("fast", "balanced", "max", "ultra"):
        try:
            return compress_lossless(src, dst, mode=mode if mode in ("fast", "balanced", "max", "ultra") else "balanced",
                                     on_progress=on_progress, cancel=cancel, advanced=advanced, jobs=jobs)
        except Exception as e:
            from .log import warn_or_raise
            warn_or_raise("compress_auto(image-lossless)", e)
    if target_bytes is not None and not is_img:
        # ملف عام مع هدف: جرّب lossless أولاً وأخبر بالنتيجة الصادقة
        info = compress_lossless(src, dst or (src + ".tqz"), mode="ultra" if mode == "micro_800k" else mode,
                                 on_progress=on_progress, cancel=cancel, advanced=advanced, jobs=jobs)
        info["hit_target"] = info["new"] <= target_bytes
        info["target_bytes"] = target_bytes
        return info
    if lossless is False:
        return compress_file(src, dst, mode=mode if mode in PRESETS else "balanced")
    return compress_lossless(src, dst, mode=mode if mode in ("fast", "balanced", "max", "ultra", "extreme") else "balanced",
                             on_progress=on_progress, cancel=cancel, advanced=advanced, jobs=jobs)

def decompress_auto(src: str, dst: str | None = None, on_progress=None, cancel=None,
                    max_output_bytes: int | None = None) -> dict:
    """فك ضغط تلقائي (v2 أو v1) مع سقف حماية من المتفجرات."""
    with open(src, "rb") as f:
        magic = f.read(4)
    if magic == b"TQZ2":
        return decompress_lossless(src, dst, on_progress=on_progress, cancel=cancel,
                                   max_output_bytes=max_output_bytes)
    return decompress_file(src, dst, on_progress=on_progress, cancel=cancel,
                           max_output_bytes=max_output_bytes)
