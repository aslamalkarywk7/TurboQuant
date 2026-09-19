"""اختبار اتساق الإصدارات: مصدر واحد للحقيقة يُفحص آلياً."""
import json
import re

def _v_init():
    import turboquant
    return turboquant.__version__

def _v_pyproject():
    import pathlib
    txt = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
    assert m, "version missing in pyproject.toml"
    return m.group(1)

def _v_package_json():
    import pathlib, json as _j
    return _j.loads(pathlib.Path("package.json").read_text(encoding="utf-8"))["version"]

def test_versions_match():
    assert _v_init() == _v_pyproject() == _v_package_json()
