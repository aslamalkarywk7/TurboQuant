"""pipeline.py — المنسّق الذكي لنظام الخوارزميات المتقدمة.

خط العمل (كله lossless):
1. بوابة الإنتروبيا: بيانات عشوائية → تخزين خام (store) فوراً بلا حرق CPU.
2. ترشيح حسب النوع: كل نوع له مرشحوه (WAV → delta16le، نصوص → bwt/delta...).
3. سباق على عينة: كل مرشح يُطبَّق ويُضغط بأسرع codec، والفائز بالأصغر حجماً.
4. التنفيذ الكامل بالفائز + أفضل codec على العينة المحوَّلة.

الدوال: analyze_file (تقرير) / smart_select (اختيار) / apply/invert (تحويل).
"""
from __future__ import annotations

TRANSFORMS = ("none", "delta8", "xor8", "delta16le", "bwt", "pngfilter", "zdict")
ADV_CAP = 64 * 1024 * 1024   # فوقه: رجوع للمسار العادي (ذاكرة)
SELECT_CAP = 128 * 1024      # عينة السباق
BWT_SELECT_CAP = 64 * 1024   # BWT بطيء نسبياً → عينة أصغر
ZDICT_MIN = 64 * 1024        # ملفات أصغر لا تستحق قاموساً

CANDIDATES_BY_KIND = {
    "text": ["none", "delta8", "xor8", "bwt", "pngfilter", "zdict"],
    "csv": ["none", "delta8", "xor8", "bwt", "pngfilter", "zdict"],
    "json": ["none", "delta8", "xor8", "bwt", "zdict"],
    "generic": ["none", "delta8", "xor8", "bwt", "pngfilter", "zdict"],
    "audio_wav": ["none", "delta16le", "delta8"],
    "executable": ["none", "delta8", "bwt", "xor8"],
    # بيانات مُرمَّزة أصلاً: لا تحويل ينفعها → المسار العادي + بوابة الإنتروبيا
    "image": ["none"], "video": ["none"], "audio": ["none"],
    "archive": ["none"], "pdf": ["none"], "office": ["none"],
}

def _sel_codec() -> str:
    try:
        import zstandard  # noqa
        return "zstd"
    except ImportError:
        return "gzip"

def apply_transform(data: bytes, tid: str, tparams: dict | None = None) -> bytes:
    tparams = tparams or {}
    if tid == "none":
        return data
    if tid == "delta8":
        from .delta import delta8_encode
        return delta8_encode(data)
    if tid == "xor8":
        from .delta import xor8_encode
        return xor8_encode(data)
    if tid == "delta16le":
        from .delta import delta16le_encode
        return delta16le_encode(data)
    if tid == "bwt":
        from .bwt import bwt_encode
        return bwt_encode(data)
    if tid == "pngfilter":
        from .filters import filters_encode
        return filters_encode(data, tparams.get("stride"))
    if tid == "zdict":
        raise ValueError("zdict يُعالَج عبر مسار القاموس الخاص (self_dict_compress)")
    raise ValueError(f"تحويل مجهول: {tid}")

def invert_transform(data: bytes, tid: str, tparams: dict | None = None) -> bytes:
    tparams = tparams or {}
    if tid == "none":
        return data
    if tid == "delta8":
        from .delta import delta8_decode
        return delta8_decode(data)
    if tid == "xor8":
        from .delta import xor8_decode
        return xor8_decode(data)
    if tid == "delta16le":
        from .delta import delta16le_decode
        return delta16le_decode(data)
    if tid == "bwt":
        from .bwt import bwt_decode
        return bwt_decode(data)
    if tid == "pngfilter":
        from .filters import filters_decode
        return filters_decode(data)
    raise ValueError(f"تحويل مجهول: {tid}")

def _trial_size(tdata: bytes, codec: str) -> int | None:
    from ..codecs import compress_bytes
    from ..log import logger
    try:
        return len(compress_bytes(tdata, codec, "fast"))
    except Exception as e:
        logger.debug("trial failed for codec %s: %r", codec, e)
        return None

def smart_select(sample: bytes, kind: str, mode: str = "balanced") -> dict:
    """سابق المرشحين على عينة وأرجع الفائز. لا يرفع استثناءً أبداً (fallback=none)."""
    from .entropy import analyze
    from ..codecs import compress_bytes
    sel = _sel_codec()
    ent = analyze(sample)
    base = {"entropy": ent["entropy"], "verdict": ent["verdict"], "sel_codec": sel, "tests": {}}
    if ent["verdict"] == "incompressible":
        base.update({"transform": "none", "tparams": {}, "codec": "store",
                     "est_ratio": 1.0,
                     "why": "إنتروبيا عالية → تخزين خام أسرع وأصدق"})
        return base
    cands = CANDIDATES_BY_KIND.get(kind, CANDIDATES_BY_KIND["generic"])
    evalu = sample[:SELECT_CAP] if len(sample) > SELECT_CAP else sample
    results: dict[str, float] = {}
    tparams_map: dict[str, dict] = {}
    for tid in cands:
        try:
            if tid == "zdict":
                if len(evalu) < ZDICT_MIN:
                    continue
                from .zdict import self_train, pack_body, dict_compress
                from ..codecs import _zstd_level
                zd = self_train(evalu, 8192)
                if zd is None:
                    continue
                import zstandard as zstd
                frame = dict_compress(evalu, zd, _zstd_level("fast"))
                results[tid] = len(pack_body(zd, frame)) / len(evalu)
                tparams_map[tid] = {"dict_size": len(zd)}
                continue
            ev = evalu[:BWT_SELECT_CAP] if tid == "bwt" and len(evalu) > BWT_SELECT_CAP else evalu
            t = apply_transform(ev, tid, {})
            if tid == "pngfilter":
                import struct as _st
                st = _st.unpack_from(">H", t, 4)[0]
                tparams_map[tid] = {"stride": st}
            sz = _trial_size(t, sel)
            if sz is not None:
                results[tid] = sz / len(ev)
        except Exception as e:
            from ..log import logger
            logger.debug("candidate %s skipped: %r", tid, e)
            continue
    base["tests"] = {k: round(v, 4) for k, v in results.items()}
    if not results:
        base.update({"transform": "none", "tparams": {}, "codec": sel,
                     "est_ratio": 1.0, "why": "لا مرشح نجا → المسار العادي"})
        return base
    win = min(results, key=results.get)
    base.update({"transform": win, "tparams": tparams_map.get(win, {}), "codec": sel,
                 "est_ratio": round(results[win], 4),
                 "why": f"الفائز على العينة: {win} بنسبة {results[win]:.3f}"})
    return base

def analyze_file(path: str, mode: str = "balanced") -> dict:
    """تقرير تحليلي لملف: النوع + الإنتروبيا + التحويل المقترح (بدون ضغط فعلي)."""
    import os
    from ..detect import detect_kind, suggest_pipeline
    from ..utils import format_size
    from .entropy import analyze
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        sample = f.read(SELECT_CAP)
    kind = detect_kind(path)
    ent = analyze(sample)
    if size > ADV_CAP:
        sug = {"transform": "none", "codec": "auto",
               "why": f"الملف {format_size(size)} فوق سقف المسار المتقدم ({ADV_CAP // 1048576}MB) → المسار العادي المتدفق"}
    elif ent["verdict"] == "incompressible":
        sug = {"transform": "none", "codec": "store", "why": ent["why"]}
    else:
        sel = smart_select(sample, kind, mode)
        sug = {"transform": sel["transform"], "codec": sel["codec"], "why": sel["why"],
               "tests": sel.get("tests", {})}
    return {"path": path, "kind": kind, "kind_ar": suggest_pipeline(kind).get("note", ""),
            "size": size, "size_h": format_size(size),
            "entropy": ent["entropy"], "verdict": ent["verdict"], "why": ent["why"],
            "advanced_ok": size <= ADV_CAP, "suggestion": sug}
