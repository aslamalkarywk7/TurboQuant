"""limits.py — حدود حماية من قنابل فك الضغط + كاتب مُحصي للبايتات.

القاعدة: أي فك ضغط لا يكتب أكثر من السقف. الافتراضي التلقائي =
max(1GB, ‏100_000 × حجم الحاوية المضغوطة) — يسمح بأسوأ الحالات المشروعة
(نص 1MB ← 369B ≈ نسبة 2600x) ويوقف المتفجرات مبكراً قبل نفاد الذاكرة/القرص.
مرّر max_output_bytes صريحاً للتشدد، أو 0/None للتلقائي.
"""
from __future__ import annotations

AUTO_RATIO = 100_000
AUTO_MIN = 1024 ** 3  # 1GB حد أدنى مطلق

def resolve_cap(max_output_bytes: int | None, compressed_len: int) -> int:
    if max_output_bytes:
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes يجب أن يكون موجباً")
        return max_output_bytes
    return max(AUTO_MIN, compressed_len * AUTO_RATIO)

class CappedWriter:
    """غلاف ملف: يعدّ البايتات ويرفع OutputLimitError عند التجاوز."""

    def __init__(self, fout, cap: int, hasher=None, on_write=None):
        from .errors import OutputLimitError
        self._fout = fout
        self._cap = cap
        self._n = 0
        self._hasher = hasher
        self._on_write = on_write
        self._err = OutputLimitError

    @property
    def written(self) -> int:
        return self._n

    def write(self, b: bytes) -> int:
        # zstd/brotli وغيرها قد تمرر memoryview — طبيعها أولاً
        if not isinstance(b, (bytes, bytearray)):
            b = bytes(b)
        self._n += len(b)
        if self._n > self._cap:
            raise self._err(
                f"تجاوز حد الإخراج ({self._n} > {self._cap} بايت) — حاوية مشبوهة؟ "
                f"Output limit exceeded (zip-bomb protection)")
        if self._hasher is not None:
            self._hasher.update(b)
        if self._on_write is not None:
            self._on_write(b)
        return self._fout.write(b)

    def flush(self):
        return self._fout.flush()

    def __getattr__(self, name):
        return getattr(self.__fout__, name)
