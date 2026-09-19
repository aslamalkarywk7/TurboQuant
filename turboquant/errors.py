"""errors.py — هرم استثناءات موحد (إنجليزية أساسية + تلميح عربي).

القاعدة: أخطاء تلف البيانات والتحقق والحدود ترفع دائماً (لا ابتلاع)،
أما قرارات التدهور (fallback لcodec أضعف) فتُسجَّل في السجل فقط.

توافقية: كل خطأ يرث أيضاً الـ builtin المناظر (ValueError/RuntimeError)
حتى لا ينكسر أي كود قديم يلتقط الأنواع القياسية.
"""
from __future__ import annotations

class TurboQuantError(Exception):
    """أساس كل أخطاء TurboQuant."""

class CorruptPackageError(TurboQuantError, ValueError):
    """الحاوية تالفة أو ليست TurboQuant صالحة. / Container is corrupt."""

class UnsupportedCodecError(TurboQuantError, ValueError):
    """codec/transform/method غير مدعوم في هذا المسار."""

class VerificationError(TurboQuantError, RuntimeError):
    """فشل التحقق (sha256) — البيانات لا تطابق الأصل."""

class PasswordError(TurboQuantError, ValueError):
    """كلمة السر خطأ أو البيانات تعرضت للعبث (فشل مصادقة GCM)."""

class BaseMismatchError(TurboQuantError, ValueError):
    """ملف الأساس لا يطابق الدلتا المطلوبة."""

class OutputLimitError(TurboQuantError, RuntimeError):
    """تجاوز حد حجم الإخراج (حماية من قنابل فك الضغط)."""
