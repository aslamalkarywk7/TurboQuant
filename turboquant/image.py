"""Image compression: JPEG/PNG/WebP -> target size (default <=800KB).

الفكرة: binary-search على الجودة + تصغير تدريجي للأبعاد حتى نصل للحجم المطلوب.
تُستخدم داخل برامجك: from turboquant.image import compress_image
"""
from __future__ import annotations
import io
import os
from PIL import Image

from .presets import get_preset, MICRO_MAX_BYTES
from .utils import format_size, ratio_stats, ensure_parent

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".avif", ".heic", ".heif"}

def _save_buffer(img: Image.Image, fmt: str, quality: int) -> bytes:
    buf = io.BytesIO()
    f = fmt.upper()
    if f in ("JPG", "JPEG"):
        im = img.convert("RGB") if img.mode in ("RGBA", "LA", "P") else img
        im.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    elif f == "WEBP":
        # lossless=False هو سر الضغط العالي
        im = img
        if im.mode in ("P",):
            im = im.convert("RGB")
        im.save(buf, format="WEBP", quality=quality, method=6)
    elif f == "PNG":
        im = img
        im.save(buf, format="PNG", optimize=True)
    elif f == "AVIF":
        im = img.convert("RGB") if img.mode in ("RGBA", "LA", "P") else img
        im.save(buf, format="AVIF", quality=quality)
    else:
        raise ValueError(f"format غير مدعوم: {fmt}")
    return buf.getvalue()

def _resize(img: Image.Image, scale: float, max_dim: int | None) -> Image.Image:
    w, h = img.size
    if max_dim:
        s = min(1.0, max_dim / max(w, h))
        scale = min(scale, s)
    if scale >= 0.999:
        return img
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return img.resize((nw, nh), Image.LANCZOS)

def compress_image(
    src: str,
    dst: str | None = None,
    target_bytes: int = MICRO_MAX_BYTES,
    mode: str = "balanced",
    fmt: str = "auto",
    max_dim: int | None | str = "auto",
    min_quality: int = 5,
    max_quality: int = 95,
    allow_resize: bool | None = None,
) -> dict:
    """اضغط صورة واحدة إلى حجم مستهدف (افتراضي 800KB).

    Args:
        src: مسار الدخل
        dst: مسار الخرج (auto = نفس الاسم + .webp)
        target_bytes: الحجم الأقصى المطلوب بالبايت
        mode: fast | balanced | extreme | micro_800k (يحدد الجودة المبدئية والأبعاد)
        fmt: auto | WEBP | JPEG | PNG | AVIF
        max_dim: أكبر ضلع مسموح (auto = من الـ preset)
        allow_resize: السماح بالتصغير (auto = من الـ preset)

    Returns:
        dict فيه orig_size, new_size, ratio, saved_pct, quality, output ...
    """
    preset = get_preset(mode)
    if allow_resize is None:
        allow_resize = preset.allow_resize
    if max_dim == "auto":
        max_dim = preset.max_dim

    if fmt == "auto":
        fmt = preset.image_format  # WEBP افتراضياً لأعلى ضغط
        # لو الخرج PNG شفاف والدخل فيه ألفا، WEBP يحافظ على الشفافية - تمام
    fmt = fmt.upper().replace("JPG", "JPEG")

    # AVIF قد لا يكون مدعوماً في كل نسخ Pillow -> fallback إلى WEBP
    try:
        with Image.open(src) as _t:
            pass
    except Exception as e:
        raise RuntimeError(f"تعذر فتح الصورة {src}: {e}")

    orig_size = os.path.getsize(src)

    # لو الصورة أصلاً أصغر من الهدف ولا نريد تكبيرها -> انسخ/أعد ترميز خفيف فقط
    start_q = preset.quality if mode != "micro_800k" else min(preset.quality, 60)

    if dst is None:
        base, _ = os.path.splitext(src)
        ext = {"WEBP": ".webp", "JPEG": ".jpg", "PNG": ".png", "AVIF": ".avif"}[fmt]
        dst = base + ".tq" + ext
    ensure_parent(dst)

    with Image.open(src) as im:
        im.load()
        # جرّب: جودة binary search عند كل مقاس
        scales = [1.0, 0.85, 0.70, 0.55, 0.42, 0.30] if allow_resize else [1.0]
        best: bytes | None = None
        best_q = start_q
        best_scale = 1.0

        # لو الصورة صغيرة أصلاً: جرّب الجودة العليا أولاً
        for scale in scales:
            resized = _resize(im, scale, max_dim)
            lo, hi = min_quality, min(max_quality, start_q if scale == 1.0 else max_quality)
            # للـ extreme نبدأ منخفضاً أصلاً
            if mode == "extreme":
                hi = min(hi, 55)
            candidate: bytes | None = None
            cand_q = hi
            # binary search: أعلى جودة تحقق target_bytes
            low, high = lo, hi
            ok_q = None
            ok_data: bytes | None = None
            while low <= high:
                mid = (low + high) // 2
                try:
                    data = _save_buffer(resized, fmt, mid)
                except Exception:
                    # مثلاً AVIF غير مدعوم -> ارجع WEBP
                    if fmt == "AVIF":
                        fmt = "WEBP"
                        data = _save_buffer(resized, fmt, mid)
                    else:
                        raise
                if len(data) <= target_bytes:
                    ok_q, ok_data = mid, data
                    low = mid + 1   # جرّب جودة أعلى
                else:
                    high = mid - 1  # أنزل الجودة
            if ok_data is not None:
                best, best_q, best_scale = ok_data, ok_q, scale
                break
            # لم نصل للهدف عند هذا المقاس -> احتفظ بأصغر نسخة (أقل جودة) وجرّب مقاساً أصغر
            try:
                smallest = _save_buffer(resized, fmt, lo)
            except Exception:
                if fmt == "AVIF":
                    fmt = "WEBP"
                    smallest = _save_buffer(resized, fmt, lo)
                else:
                    raise
            candidate, cand_q = smallest, lo
            # تابع للحلقة بمقاس أصغر
            last_fallback = (candidate, cand_q, scale)

        if best is None:
            # حتى أصغر مقاس + أقل جودة أكبر من الهدف -> خذ أصغر ما وصلنا له (best effort)
            best, best_q, best_scale = last_fallback

        with open(dst, "wb") as f:
            f.write(best)

    new_size = os.path.getsize(dst)
    info = ratio_stats(orig_size, new_size)
    info.update({
        "output": dst,
        "format": fmt,
        "quality": best_q,
        "scale": round(best_scale, 3),
        "target_bytes": target_bytes,
        "target": format_size(target_bytes),
        "orig_h": format_size(orig_size),
        "new_h": format_size(new_size),
        "hit_target": new_size <= target_bytes,
        "mode": mode,
    })
    return info


def compress_images_batch(
    files: list[str],
    out_dir: str,
    target_bytes: int = MICRO_MAX_BYTES,
    mode: str = "balanced",
    fmt: str = "auto",
) -> list[dict]:
    """اضغط قائمة صور إلى مجلد. مريحة للاستخدام داخل البرامج."""
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for src in files:
        name = os.path.basename(src)
        base, _ = os.path.splitext(name)
        ext = {"auto": ".webp", "WEBP": ".webp", "JPEG": ".jpg", "PNG": ".png", "AVIF": ".avif"}.get(fmt, ".webp")
        dst = os.path.join(out_dir, base + ext)
        try:
            results.append(compress_image(src, dst, target_bytes, mode, fmt))
        except Exception as e:
            results.append({"output": None, "src": src, "error": str(e)})
    return results
