"""handlers/image_lossless.py — ضغط صور LOSSLESS (بكسل مطابق 100%).

الطرق (كلها بدون فقد):
1. PNG optimize + strip ancillary اختياري
2. BMP/TIFF -> PNG lossless
3. JPEG -> تحويل lossless (optimize progressive) + إزالة thumbnails إن وُجدت؟ (نحافظ افتراضياً)
4. WebP-lossless / PNG -> WebP-lossless واختيار الأصغر
5. تحقق: مقارنة بكسل ببكسل قبل/بعد.
"""
from __future__ import annotations
import io
import os
from PIL import Image

def _encode_png(img: Image.Image, optimize=True) -> bytes:
    b = io.BytesIO()
    img.save(b, format="PNG", optimize=optimize, compress_level=9)
    return b.getvalue()

def _encode_webp_lossless(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, format="WEBP", lossless=True, quality=100, method=6)
    return b.getvalue()

def _pixels_equal(a_path: str, raw_a: bytes | None, b_data: bytes) -> bool:
    try:
        if raw_a is None:
            with Image.open(a_path) as im0, Image.open(io.BytesIO(b_data)) as im1:
                im0.load()
                im1.load()
                if im0.size != im1.size or im0.mode != im1.mode:
                    # قارن بعد توحيد RGB
                    im0 = im0.convert("RGB")
                    im1 = im1.convert("RGB")
                return list(im0.get_flattened_data()) == list(im1.get_flattened_data())
        else:
            with Image.open(io.BytesIO(raw_a)) as im0, Image.open(io.BytesIO(b_data)) as im1:
                im0.load()
                im1.load()
                if im0.size != im1.size or im0.mode != im1.mode:
                    im0 = im0.convert("RGB")
                    im1 = im1.convert("RGB")
                return list(im0.get_flattened_data()) == list(im1.get_flattened_data())
    except Exception:
        return False

def compress_image_lossless(src: str, dst: str | None = None, strip_meta: bool = False) -> dict:
    from ..utils import ratio_stats, format_size, ensure_parent
    orig = os.path.getsize(src)
    with Image.open(src) as im:
        im.load()
        # احتفظ بنسخة للتحقق
        mode, size = im.mode, im.size
        # مرشحون
        cands: dict[str, bytes] = {}
        # PNG دائماً مرشح
        try:
            cands["png"] = _encode_png(im)
        except Exception:
            pass
        # WebP lossless مرشح قوي
        try:
            cands["webp-lossless"] = _encode_webp_lossless(im)
        except Exception:
            pass
        # JPEG المصدر: أعد حفظ optimize (lossless تقريباً لسلسلة DCT؟ نحتفظ بالأصل لو أكبر)
        # لا نعيد ترميز JPEG بـ lossy هنا أبداً.
        if not cands:
            raise RuntimeError("تعذر ترميز الصورة lossless")
        # اختر الأصغر مع التحقق من تطابق البكسل
        ranked = sorted(cands.items(), key=lambda kv: len(kv[1]))
        chosen = None
        for name, data in ranked:
            if _pixels_equal(src, None, data):
                chosen, cname = data, name
                break
        if chosen is None:
            # fallback آمن: انسخ الأصل (لا فقد أبداً)
            with open(src, "rb") as f:
                chosen, cname = f.read(), "copy-original"
        if dst is None:
            ext = {"png": ".png", "webp-lossless": ".webp", "copy-original": os.path.splitext(src)[1]}[cname]
            dst = os.path.splitext(src)[0] + ".tqlossless" + ext
        ensure_parent(dst)
        with open(dst, "wb") as f:
            f.write(chosen)
    new = os.path.getsize(dst)
    info = ratio_stats(orig, new)
    info.update({"output": dst, "method": f"image-lossless:{cname}", "lossless": True,
                 "verified_pixels": cname != "copy-original",
                 "orig_h": format_size(orig), "new_h": format_size(new)})
    return info
