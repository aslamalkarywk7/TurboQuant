"""Presets: balanced (~400MB -> 115MB) / extreme (~400MB -> 20MB) / micro (<=800KB)."""
from __future__ import annotations
from dataclasses import dataclass

KB = 1024
MB = 1024 * KB

@dataclass(frozen=True)
class Preset:
    name: str
    desc_ar: str
    # images
    image_format: str   # "WEBP" preferred
    quality: int        # starting quality
    max_dim: int | None # max width/height, None = keep
    allow_resize: bool
    # files
    file_codec: str     # "auto" | "zstd" | "lzma" | "bz2" | "gzip"
    zstd_level: int
    lzma_preset: int
    chunk_mb: int

PRESETS: dict[str, Preset] = {
    # سريع: أقل ضغط لكن أسرع وقت (lossless دائماً في v2)
    "fast": Preset(
        name="fast",
        desc_ar="سريع - ضغط خفيف lossless",
        image_format="WEBP", quality=82, max_dim=None,
        allow_resize=False, file_codec="auto", zstd_level=3, lzma_preset=1, chunk_mb=8,
    ),
    # متوازن: مثال 400MB -> ~115MB (نسبة ~28.7%) للبيانات القابلة للضغط
    "balanced": Preset(
        name="balanced",
        desc_ar="متوازن lossless - يستهدف ~28% من الحجم الأصلي (400م -> 115م)",
        image_format="WEBP", quality=72, max_dim=1920,
        allow_resize=True, file_codec="auto", zstd_level=12, lzma_preset=6, chunk_mb=8,
    ),
    # max: أقصى lossless متوازن (zstd-19 / lzma-9)
    "max": Preset(
        name="max",
        desc_ar="أقصى lossless متوازن (zstd-19 / lzma-9)",
        image_format="WEBP", quality=72, max_dim=1920,
        allow_resize=True, file_codec="auto", zstd_level=19, lzma_preset=9, chunk_mb=8,
    ),
    # ultra: أقصى ضغط lossless على الإطلاق (zstd-22 / lzma-9 + dedup)
    "ultra": Preset(
        name="ultra",
        desc_ar="أقصى lossless على الإطلاق (zstd-22 + dedup)",
        image_format="WEBP", quality=55, max_dim=1280,
        allow_resize=True, file_codec="auto", zstd_level=22, lzma_preset=9, chunk_mb=4,
    ),
    # متطرف: مثال 400MB -> ~20MB (نسبة ~5%) - عدواني، للصور يعيد الترميز بجودة منخفضة
    "extreme": Preset(
        name="extreme",
        desc_ar="متطرف - يستهدف ~5% من الحجم (400م -> 20م) بضغط lossy للوسائط",
        image_format="WEBP", quality=38, max_dim=1280,
        allow_resize=True, file_codec="auto", zstd_level=22, lzma_preset=9, chunk_mb=4,
    ),
    # ميكرو: إخراج نهائي <= 800KB مهما كان الدخل
    "micro_800k": Preset(
        name="micro_800k",
        desc_ar="ميكرو - إخراج 800 كيلو كحد أقصى",
        image_format="WEBP", quality=55, max_dim=1280,
        allow_resize=True, file_codec="auto", zstd_level=22, lzma_preset=9, chunk_mb=4,
    ),
}

# النسبة المستهدفة لكل وضع (new / orig) — استرشادية للبيانات القابلة للضغط
TARGET_RATIO = {
    "fast": 0.60,
    "balanced": 0.2875,  # 115 / 400
    "max": 0.15,
    "ultra": 0.05,     # 20 / 400
    "extreme": 0.05,
    "micro_800k": None,  # يحكمه target_bytes ثابت
}

MICRO_MAX_BYTES = 800 * KB

def get_preset(mode: str) -> Preset:
    mode = (mode or "balanced").lower()
    # أسماء بديلة للتوافق (لا تدمج extreme/micro_800k مع ultra — لكلٍّ preset خاص به)
    aliases = {"maximum": "max", "best": "ultra"}
    mode = aliases.get(mode, mode)
    if mode not in PRESETS:
        raise ValueError(f"mode غير معروف: {mode}. المتاح: {list(PRESETS)}")
    return PRESETS[mode]

def target_for_mode(orig_size: int, mode: str) -> int | None:
    r = TARGET_RATIO.get(mode.lower())
    if r is None:
        return None
    return max(1, int(orig_size * r))
