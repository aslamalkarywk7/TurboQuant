"""parallel.py — ضغط متوازي على كل الأنوية (threads آمنة: كل مهمة ضاغط مستقل).

- best_of_parallel: تجربة codecs concurrently (C extensions تحرر GIL).
- compress_many: ضغط قائمة chunks concurrently مع حفظ الترتيب الأصلي.
jobs=1 → سلوك تسلسلي مطابق للقديم. jobs=None → عدد الأنوية.
"""
from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor

def _jobs_n(jobs: int | None) -> int:
    if jobs is None:
        return max(1, os.cpu_count() or 1)
    return max(1, int(jobs))

def best_of_parallel(data: bytes, mode: str = "balanced", jobs: int | None = None) -> tuple[str, bytes]:
    from .codecs import available_codecs, compress_bytes
    codecs = available_codecs()
    if _jobs_n(jobs) == 1 or len(codecs) == 1:
        from .codecs import best_of
        return best_of(data, mode)
    def _one(c: str):
        try:
            return c, compress_bytes(data, c, mode)
        except Exception:
            return c, None
    best = None
    with ThreadPoolExecutor(max_workers=min(_jobs_n(jobs), len(codecs))) as ex:
        for c, b in ex.map(_one, codecs):
            if b is not None and (best is None or len(b) < len(best[1])):
                best = (c, b)
    if best is None:
        raise RuntimeError("لا يوجد codec متاح")
    return best

def compress_many(items: list[tuple[str, bytes]], codec: str, mode: str,
                  jobs: int | None = 1) -> list[tuple[str, bytes]]:
    """اضغط [(key, raw)] concurrently وأرجع بنفس الترتيب [(key, compressed)]."""
    from .codecs import compress_bytes
    if not items:
        return []
    if _jobs_n(jobs) == 1 or len(items) == 1:
        return [(k, compress_bytes(b, codec, mode)) for k, b in items]
    def _one(pair: tuple[str, bytes]):
        k, b = pair
        return k, compress_bytes(b, codec, mode)
    with ThreadPoolExecutor(max_workers=_jobs_n(jobs)) as ex:
        return list(ex.map(_one, items))
