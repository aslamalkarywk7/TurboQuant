"""log.py — سجل موحد للمكتبة (صامت افتراضياً، للتضمين في التطبيقات).

- افتراضياً: NullHandler (لا يطبع شيئاً ولا يكسر أي تطبيق مضيف).
- فعّل التشخيص: TQ_DEBUG=1 → تحذيرات + إعادة رفع أخطاء الـ fallback.
- داخل تطبيقك: logging.getLogger("turboquant").addHandler(your_handler)
"""
from __future__ import annotations
import logging
import os

logger = logging.getLogger("turboquant")
logger.addHandler(logging.NullHandler())

def debug_mode() -> bool:
    return os.environ.get("TQ_DEBUG") == "1"

def warn_or_raise(where: str, exc: BaseException):
    """سجّل تحذيراً بالتفاصيل؛ وفي وضع التشخيص أعد الرفع بدل التدهور الصامت."""
    logger.warning("%s failed, falling back: %r", where, exc, exc_info=True)
    if debug_mode():
        raise exc
