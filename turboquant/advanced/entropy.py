"""entropy.py — تقدير إنتروبيا شانون (Shannon entropy) للتنبؤ بقابلية الضغط.

الفكرة: قبل حرق CPU في ضغط بيانات عشوائية/مشفرة، نقيس الإنتروبيا على عينة:
- منخفضة (< 6.5 بت/بايت) → قابلة للضغط → كمّل بكل قوة.
- متوسطة (6.5–7.6) → هامشية → جرّب بسرعة واقبل أي توفير.
- عالية (> 7.6) → شبه عشوائية → خزّن خام (store) ووفّر وقت CPU.

كله lossless — القرار يخص السرعة فقط، والجودة 100% دائماً.
"""
from __future__ import annotations
import math

COMPRESSIBLE_MAX = 6.5
INCOMPRESSIBLE_MIN = 7.6
SAMPLE_CAP = 1 << 20  # عينة 1MB تكفي للتقدير

def byte_entropy(data: bytes) -> float:
    """إنتروبيا شانون بت/بايت: 0.0 (ثابت) … 8.0 (عشوائي تماماً)."""
    n = len(data)
    if n == 0:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    h = 0.0
    for c in freq:
        if c:
            p = c / n
            h -= p * math.log2(p)
    return h

def analyze(data: bytes) -> dict:
    """حلّل عينة وأصدر حكماً: compressible | marginal | incompressible."""
    sample = data[:SAMPLE_CAP] if len(data) > SAMPLE_CAP else data
    h = byte_entropy(sample)
    if h <= COMPRESSIBLE_MAX:
        verdict = "compressible"
        why = f"entropy={h:.2f} ≤ {COMPRESSIBLE_MAX} → البيانات منظمة وتستحق أقوى خط أنابيب"
    elif h >= INCOMPRESSIBLE_MIN:
        verdict = "incompressible"
        why = f"entropy={h:.2f} ≥ {INCOMPRESSIBLE_MIN} → شبه عشوائية، التخزين الخام أسرع وأصدق"
    else:
        verdict = "marginal"
        why = f"entropy={h:.2f} في المنطقة الرمادية → جرّب سريعاً واقبل أي توفير"
    return {"entropy": round(h, 3), "sampled": len(sample),
            "verdict": verdict, "why": why}
