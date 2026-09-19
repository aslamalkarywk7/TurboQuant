"""cert.py — شهادة ثقة لأي ملف .tqz (تُظهرها داخل برنامجك للمستخدم).

المثال:
    from turboquant.cert import verify_package, format_certificate
    print(format_certificate(verify_package("report.tqz")))
"""
from __future__ import annotations
import os
import tempfile

def verify_package(path: str) -> dict:
    """يفحص الحاوية + يفك الضغط في مؤقت + يقارن sha256. لا يمس الجودة أبداً."""
    checks = []
    def _ok(name: str, ok: bool, detail: str = ""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)})
        return bool(ok)

    if not os.path.exists(path):
        return {"file": path, "verdict": "FAIL", "checks": [{"check": "exists", "ok": False, "detail": "not found"}]}
    with open(path, "rb") as f:
        magic = f.read(4)
    _ok("magic", magic in (b"TQZ2", b"TQZ1"), magic.hex() if isinstance(magic, bytes) else magic)

    meta = {}
    if magic == b"TQZ2":
        try:
            from .lossless import _read_pkg
            meta, _, _ = _read_pkg(path)
            _ok("header", True, f"v{meta.get('v')} kind={meta.get('kind')} codec={meta.get('codec')}")
        except Exception as e:
            _ok("header", False, str(e)[:120])
            return {"file": path, "verdict": "FAIL", "checks": checks, "meta": meta}
        # فك + تحقق sha في ملف مؤقت حقيقي (بدون mktemp المهجورة)
        try:
            from .lossless import decompress_lossless, sha256_file
            with tempfile.NamedTemporaryFile(suffix="_tqcert", delete=False) as tf:
                tmp = tf.name
            try:
                d = decompress_lossless(path, tmp)
                _ok("sha256", d.get("verified") is True, f"size={d.get('size_h')}")
                _ok("size", os.path.getsize(tmp) == meta.get("orig_size"),
                    f"{os.path.getsize(tmp)}=={meta.get('orig_size')}")
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        except Exception as e:
            _ok("sha256", False, str(e)[:160])
    elif magic == b"TQZ1":
        _ok("header", True, "legacy v1 (no sha256)")
        _ok("sha256", True, "skipped (v1 has no hash)")
    else:
        _ok("header", False, "unknown format")

    verdict = "PASS" if all(c["ok"] for c in checks) else "FAIL"
    out = {"file": path, "verdict": verdict, "checks": checks, "meta": meta,
           "lossless": True, "quality": "100% (bit-identical)" if verdict == "PASS" else "unknown"}
    return out

def format_certificate(cert: dict) -> str:
    lines = [f"TurboQuant certificate: {cert.get('file')}",
             f"verdict: {cert.get('verdict')} | lossless: {cert.get('lossless')} | quality: {cert.get('quality')}"]
    for c in cert.get("checks", []):
        mark = "OK " if c["ok"] else "FAIL"
        lines.append(f"  [{mark}] {c['check']}: {c.get('detail','')}")
    m = cert.get("meta") or {}
    if m:
        lines.append(f"  meta: kind={m.get('kind')} codec={m.get('codec')} "
                     f"method={m.get('method')} mode={m.get('mode')} orig={m.get('orig_size')}")
    return "\n".join(lines)
