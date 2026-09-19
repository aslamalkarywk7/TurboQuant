"""progress.py — شريط تقدم + إلغاء لاستخدام TurboQuant داخل البرامج (GUI/API).

المثال داخل برنامجك:
    import turboquant as tq
    tok = tq.CancelToken()
    def bar(done, total, phase):
        print(f"{phase}: {done/total:.0%}")  # اربطها بـ ProgressBar في Tkinter/PyQt
    info = tq.compress_lossless("big.bin", "big.tqz", mode="max",
                                on_progress=bar, cancel=tok)
    # من زر "إلغاء": tok.cancel()
"""
from __future__ import annotations
from typing import Callable, Optional

class CancelledError(RuntimeError):
    pass

class CancelToken:
    """رمز إلغاء آمن للخيوط (thread-safe بفضل GIL للعلم البسيط)."""
    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def check(self, phase: str = ""):
        if self._cancelled:
            raise CancelledError(f"أُلغي أثناء: {phase}" if phase else "أُلغي")

# on_progress(processed_bytes, total_bytes, phase)
ProgressFn = Callable[[int, int, str], None]

def make_text_bar(prefix: str = "") -> ProgressFn:
    """شريط تقدم نصي للـ CLI — يُستخدم مع --progress."""
    import sys
    last = {"n": -1}
    def cb(done: int, total: int, phase: str):
        pct = (done / total * 100) if total else 0
        n = int(pct // 5)
        if n != last["n"]:
            last["n"] = n
            sys.stdout.write(f"\r{prefix}{phase}: [{'#'*n}{'.'*(20-n)}] {pct:5.1f}%")
            sys.stdout.flush()
            if done >= total:
                sys.stdout.write("\n")
    return cb
