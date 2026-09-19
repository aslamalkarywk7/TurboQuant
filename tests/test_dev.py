"""اختبارات الحزم الجديدة: progress + cancel + benchmark + cert."""
import os
import turboquant as tq
from turboquant import verify_package


def _sample(tmp_path, name="s.txt", n=20000):
    p = tmp_path / name
    p.write_text("hello TurboQuant\n" * n, encoding="utf-8")
    return str(p)


def test_progress_called(tmp_path):
    p = _sample(tmp_path)
    calls = []
    tq.compress_lossless(p, p + ".tqz", mode="balanced",
                         on_progress=lambda d, t, ph: calls.append((d, t, ph)))
    assert calls, "on_progress لم يُستدعَ"
    assert calls[-1][0] <= calls[-1][1]


def test_cancel_raises(tmp_path):
    import pytest
    p = _sample(tmp_path)
    tok = tq.CancelToken()
    tok.cancel()
    with pytest.raises(tq.CancelledError):
        tq.compress_lossless(p, p + ".c.tqz", mode="balanced", cancel=tok)


def test_benchmark_rows(tmp_path):
    p = _sample(tmp_path, n=2000)
    rows = tq.benchmark(p, modes=("fast", "balanced"))
    assert len(rows) == 2
    for r in rows:
        assert r["verified"] is True
        assert r["ratio"] < 1.0


def test_cert_pass(tmp_path):
    p = _sample(tmp_path)
    tq.compress_lossless(p, p + ".tqz", mode="balanced")
    cert = verify_package(p + ".tqz")
    assert cert["verdict"] == "PASS"
    assert any(c["check"] == "sha256" and c["ok"] for c in cert["checks"])
