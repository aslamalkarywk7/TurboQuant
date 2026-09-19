"""bench.py — قياس أداء حقيقي: أي وضع/codec لأي ملف؟ (للمطورين + جدول PERFORMANCE).

المثال:
    import turboquant as tq
    rows = tq.benchmark("data.csv", modes=["fast", "balanced", "max", "ultra"])
    tq.print_benchmark(rows)
"""
from __future__ import annotations
import os
import time

def benchmark(src: str, modes=("fast", "balanced", "max", "ultra"), allow_dedup: bool = True,
              advanced: bool = False, jobs: int = 1) -> list[dict]:
    """يقيس كل وضع على نفس الملف (ضغط + فك + تحقق) ويرجع صفوفاً قابلة للطباعة."""
    import tempfile
    from .lossless import compress_lossless, decompress_lossless
    from .utils import format_size
    orig = os.path.getsize(src)
    rows = []
    for mode in modes:
        # مجلد مؤقت بسياق يُمسح تلقائياً (كان mkdtemp يتسرب في /tmp)
        with tempfile.TemporaryDirectory(prefix="tq_bench_") as td:
            c = os.path.join(td, "b.tqz")
            r = os.path.join(td, "b.out")
            t0 = time.perf_counter()
            try:
                info = compress_lossless(src, c, mode=mode, allow_dedup=allow_dedup, verify=False,
                                         advanced=advanced, jobs=jobs)
                t1 = time.perf_counter()
                d = decompress_lossless(c, r)
                t2 = time.perf_counter()
                ok = d.get("verified") is True and os.path.getsize(r) == orig
            except Exception as e:
                rows.append({"mode": mode, "error": str(e)})
                continue
            new = os.path.getsize(c)
        rows.append({
            "mode": mode,
            "codec": info.get("codec"),
            "transform": info.get("transform", "none"),
            "pipeline": info.get("pipeline"),
            "orig": orig, "new": new,
            "orig_h": format_size(orig), "new_h": format_size(new),
            "ratio": round(new / orig, 4) if orig else 0,
            "saved_pct": round((1 - new / orig) * 100, 2) if orig else 0,
            "compress_s": round(t1 - t0, 3),
            "decompress_s": round(t2 - t1, 3),
            "mb_s": round(orig / 1048576 / max(t1 - t0, 1e-9), 2),
            "verified": ok,
        })
    return rows

def format_table(rows: list[dict]) -> str:
    head = f"{'mode':<10}{'codec':<14}{'transform':<11}{'ratio':<8}{'saved%':<8}{'comp_s':<8}{'MB/s':<8}{'verified'}"
    lines = [head, "-" * len(head)]
    for r in rows:
        if "error" in r:
            lines.append(f"{r['mode']:<10}ERROR {r['error'][:60]}")
            continue
        lines.append(f"{r['mode']:<10}{str(r['codec']):<14}{str(r.get('transform', 'none')):<11}"
                     f"{r['ratio']:<8}{r['saved_pct']:<8}"
                     f"{r['compress_s']:<8}{r['mb_s']:<8}{r['verified']}")
    return "\n".join(lines)

def print_benchmark(rows: list[dict]):
    print(format_table(rows))
