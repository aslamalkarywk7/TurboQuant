"""detect.py — اكتشاف نوع الملف (magic bytes + extension) لاختيار أفضل مسار lossless."""
from __future__ import annotations
import os

# (kind, description_ar)
KINDS = {
    "image": "صورة",
    "text": "نص/سجل",
    "csv": "جدول CSV",
    "json": "بيانات JSON",
    "pdf": "مستند PDF",
    "office": "مستند Office (docx/xlsx/pptx - مضغوط داخلياً)",
    "audio_wav": "صوت WAV خام",
    "audio": "صوت مضغوط",
    "video": "فيديو",
    "archive": "أرشيف مضغوط",
    "executable": "تنفيذي/ثنائي",
    "generic": "عام",
}

TEXT_EXTS = {".txt", ".log", ".md", ".csv", ".tsv", ".json", ".jsonl", ".xml", ".html",
             ".css", ".js", ".ts", ".py", ".java", ".cs", ".c", ".cpp", ".h", ".sql", ".yaml", ".yml", ".ini", ".cfg"}
IMAGE_EXTS2 = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif", ".avif", ".heic", ".heif", ".ico"}

def detect_kind(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    # 1) امتداد سريع
    if ext in IMAGE_EXTS2:
        return "image"
    if ext in (".wav", ".aiff", ".aif"):
        return "audio_wav"
    if ext in (".mp3", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma"):
        return "audio"
    if ext in (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"):
        return "video"
    if ext in (".pdf",):
        return "pdf"
    if ext in (".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".epub", ".apk", ".jar"):
        return "office"
    if ext in (".zip", ".rar", ".7z", ".gz", ".bz2", ".xz", ".zst", ".tqz", ".tgz"):
        return "archive"
    if ext in (".exe", ".dll", ".so", ".bin", ".dat", ".iso", ".img"):
        return "executable"
    if ext == ".csv" or ext == ".tsv":
        return "csv"
    if ext in (".json", ".jsonl"):
        return "json"
    if ext in TEXT_EXTS:
        return "text"
    # 2) magic bytes
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError:
        return "generic"
    if head.startswith(b"\xff\xd8\xff"):
        return "image"
    if head.startswith(b"\x89PNG"):
        return "image"
    if head.startswith(b"RIFF") and len(head) >= 12:
        return "audio_wav"  # غالباً WAV
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return "office"  # zip-based (docx/xlsx/...)
    if head.startswith(b"\x1f\x8b") or head.startswith(b"BZh") or head.startswith(b"\xfd7zXZ"):
        return "archive"
    if head.startswith(b"GIF8"):
        return "image"
    if head[:4] in (b"ftyp",) or head[4:8] == b"ftyp":
        return "video"
    # نص؟ جرّب فك ترميز عينة
    try:
        with open(path, "rb") as f:
            sample = f.read(8192)
        sample.decode("utf-8")
        if b"\x00" not in sample:
            return "text"
    except Exception:
        pass
    return "generic"

def suggest_pipeline(kind: str) -> dict:
    """يقترح أفضل خط أنابيب lossless لكل نوع — بدون أي فقد جودة."""
    table = {
        # الصور: تحويل lossless (BMP->PNG, PNG optimize, WebP-lossless) + إزالة ميتاداتا اختيارية
        "image": {"steps": ["lossless-reencode", "strip-meta?", "best-codec"], "note": "بكسل مطابق 100%"},
        "text": {"steps": ["dedup-chunks", "zstd-dict?", "max-codec"], "note": "أعلى نسبة (نصوص تتكرر)"},
        "csv": {"steps": ["column-normalize?", "dedup-chunks", "max-codec"], "note": "مرتبة حسب التكرار"},
        "json": {"steps": ["dedup-chunks", "max-codec"], "note": "minify اختياري lossless منطقياً"},
        "pdf": {"steps": ["recompress-streams", "dedup", "max-codec"], "note": "إعادة ضغط streams داخلياً"},
        "office": {"steps": ["unzip-recompress", "dedup", "max-codec"], "note": "فك zip وإعادة ضغطه بمستوى أعلى"},
        "audio_wav": {"steps": ["flac-if-available", "dedup", "max-codec"], "note": "WAV->FLAC lossless يوفر ~50%"},
        "audio": {"steps": ["repack-only", "dedup"], "note": "مضغوط أصلاً — dedup فقط"},
        "video": {"steps": ["repack-only", "dedup"], "note": "مضغوط أصلاً — لا إعادة ترميز lossy هنا"},
        "archive": {"steps": ["recompress-if-zip", "dedup"], "note": "إعادة ضغط zip بمستوى أعلى إن أمكن"},
        "executable": {"steps": ["dedup", "delta?", "max-codec"], "note": "ثنائيات تستفيد من dedup"},
        "generic": {"steps": ["dedup", "best-codec"], "note": "تجربة كل codecs واختيار الأصغر"},
    }
    return table.get(kind, table["generic"])
