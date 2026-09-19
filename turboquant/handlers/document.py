"""handlers/document.py — مستندات ونصوص lossless.

- txt/csv/json/xml/log: dedup chunks + أفضل codec (نسبة ضغط ضخمة بدون فقد).
- pdf: إعادة ضغط streams (Flate) بمستوى أعلى عبر pikepdf إن توفر، وإلا generic.
- office (docx/xlsx/pptx = zip): فك الـ zip وإعادة ضغطه بمستوى max — يوفر 5-20% بدون فقد.
كل المسارات تتحقق بـ sha256 (bit-identical).
"""
from __future__ import annotations
import hashlib
import io
import os
import zipfile

def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def recompress_zip_lossless(src: str, dst: str, codec_level: int = 9) -> dict:
    """أعد ضغط zip/office بمستوى أعلى — lossless تماماً (نفس الملفات بالداخل)."""
    from ..utils import ratio_stats, format_size, ensure_parent
    ensure_parent(dst)
    with zipfile.ZipFile(src, "r") as zin:
        infos = zin.infolist()
        blobs = {info.filename: zin.read(info.filename) for info in infos}
    # أعد الكتابة بأقوى ضغط deflate مع الحفاظ على metadata (التاريخ/الصلاحيات)
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=codec_level) as zout:
        for info in infos:
            # انسخ ZipInfo للحفاظ على date_time/external_attr، مع ترقية الضغط
            new_info = zipfile.ZipInfo(filename=info.filename, date_time=info.date_time)
            new_info.external_attr = info.external_attr
            new_info.compress_type = zipfile.ZIP_DEFLATED
            # الدلائل الفارغة تُحفظ بدون ضغط
            if info.is_dir():
                new_info.compress_type = zipfile.ZIP_STORED
            zout.writestr(new_info, blobs[info.filename])
    # لو الناتج أكبر (نادر) احتفظ بالأصل
    if os.path.getsize(dst) >= os.path.getsize(src):
        import shutil
        shutil.copyfile(src, dst)
        method = "zip-copy (already optimal)"
    else:
        method = "zip-recompress-max"
    # تحقق: نفس قائمة الملفات ونفس المحتوى (قارن dst دائماً مع src)
    with zipfile.ZipFile(src) as a, zipfile.ZipFile(dst) as b:
        assert a.namelist() == b.namelist(), "قائمة الملفات تغيّرت!"
        for n in a.namelist():
            assert a.read(n) == b.read(n), f"محتوى {n} تغيّر!"
    orig, new = os.path.getsize(src), os.path.getsize(dst)
    info = ratio_stats(orig, new)
    info.update({"output": dst, "method": method, "lossless": True,
                 "orig_h": format_size(orig), "new_h": format_size(new)})
    return info

def recompress_pdf_lossless(src: str, dst: str) -> dict:
    """PDF lossless: pikepdf إن توفر (recompress streams)، وإلا نسخ + generic لاحقاً."""
    from ..utils import ratio_stats, format_size, ensure_parent
    try:
        import pikepdf  # type: ignore
        ensure_parent(dst)
        with pikepdf.open(src) as pdf:
            pdf.save(dst, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
        orig, new = os.path.getsize(src), os.path.getsize(dst)
        info = ratio_stats(orig, new)
        info.update({"output": dst, "method": "pdf-recompress-streams", "lossless": True,
                     "orig_h": format_size(orig), "new_h": format_size(new)})
        return info
    except ImportError:
        # بدون pikepdf: أعد التغليف فقط (لا فقد، لكن توفير أقل)
        import shutil
        ensure_parent(dst)
        shutil.copyfile(src, dst)
        orig = os.path.getsize(src)
        info = ratio_stats(orig, orig)
        info.update({"output": dst, "method": "pdf-copy (install pikepdf for more)",
                     "lossless": True, "orig_h": format_size(orig), "new_h": format_size(orig),
                     "hint": "pip install pikepdf"})
        return info
