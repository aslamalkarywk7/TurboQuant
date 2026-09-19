"""اختبارات إصلاحات v2.4: حدود + أخطاء + سجلات + تدفق + تغليف + خادم."""
import hashlib
import json
import logging
import os
import sqlite3
import pytest
import turboquant as tq
from turboquant import (
    TurboQuantError, CorruptPackageError, UnsupportedCodecError,
    VerificationError, PasswordError, BaseMismatchError, OutputLimitError,
)

crypt = pytest.importorskip("cryptography")

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

# ---- هرم الأخطاء (مع توافقية الـ builtins) ----

def test_error_taxonomy():
    assert issubclass(CorruptPackageError, (TurboQuantError, ValueError))
    assert issubclass(UnsupportedCodecError, (TurboQuantError, ValueError))
    assert issubclass(PasswordError, (TurboQuantError, ValueError))
    assert issubclass(BaseMismatchError, (TurboQuantError, ValueError))
    assert issubclass(VerificationError, (TurboQuantError, RuntimeError))
    assert issubclass(OutputLimitError, (TurboQuantError, RuntimeError))

def test_corrupt_package_typed(tmp_path):
    bad = tmp_path / "bad.tqz"
    bad.write_bytes(b"TQZ2\x00\x00\x00\x05oops-not-json")
    with pytest.raises(CorruptPackageError):
        tq.decompress_lossless(str(bad), str(tmp_path / "o"))
    with pytest.raises(ValueError):  # توافقية قديمة
        tq.decompress_lossless(str(bad), str(tmp_path / "o2"))

def test_output_limit_trips(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("hello\n" * 5000, encoding="utf-8")
    c = str(p) + ".tqz"
    tq.compress_lossless(str(p), c, mode="balanced")
    with pytest.raises(OutputLimitError):
        tq.decompress_lossless(c, str(tmp_path / "o"), max_output_bytes=10)
    with pytest.raises(RuntimeError):  # توافقية قديمة
        tq.decompress_lossless(c, str(tmp_path / "o2"), max_output_bytes=10)

def test_tampered_fails_verification_typed(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("data\n" * 3000, encoding="utf-8")
    c = str(p) + ".tqz"
    tq.compress_lossless(str(p), c, mode="balanced")
    raw = bytearray(open(c, "rb").read())
    raw[-10] ^= 0xFF
    t = str(tmp_path / "evil.tqz")
    open(t, "wb").write(bytes(raw))
    with pytest.raises((VerificationError, CorruptPackageError)):
        tq.decompress_lossless(t, str(tmp_path / "o"))

# ---- السجلات ووضع التشخيص ----

def test_warn_or_raise_debug(monkeypatch):
    from turboquant.log import warn_or_raise
    monkeypatch.delenv("TQ_DEBUG", raising=False)
    warn_or_raise("x", ValueError("quiet"))  # لا يرفع
    monkeypatch.setenv("TQ_DEBUG", "1")
    with pytest.raises(ValueError):
        warn_or_raise("x", ValueError("loud"))

def test_trial_logs_debug(monkeypatch, caplog):
    from turboquant.advanced import pipeline
    monkeypatch.setattr(pipeline, "_sel_codec", lambda: "nope-codec")
    with caplog.at_level(logging.DEBUG, logger="turboquant"):
        sel = pipeline.smart_select(b"hello world " * 5000, "text")
    assert sel["transform"] == "none"
    assert any("nope-codec" in r.message for r in caplog.records)

# ---- التدفق: نفس البايتات القديمة ----

def test_stream_build_matches_legacy(tmp_path):
    from turboquant.dedup import (chunk_file_stream, build_dedup_package,
                                  build_dedup_package_stream, restore_dedup_package)
    p = tmp_path / "m.bin"
    blk = os.urandom(70000)
    with open(p, "wb") as f:
        for _ in range(12):
            f.write(blk)
        f.write(os.urandom(5000))
    chunks = list(chunk_file_stream(str(p)))
    old_body, _ = build_dedup_package(chunks, "gzip", "balanced")
    new_res = build_dedup_package_stream(iter(chunks), "gzip", "balanced", jobs=2)
    assert new_res is not None
    new_body, info = new_res
    assert restore_dedup_package(new_body) == restore_dedup_package(old_body) == open(p, "rb").read()
    assert info["total_chunks"] == len(chunks)

def test_stream_build_single_returns_none(tmp_path):
    from turboquant.dedup import build_dedup_package_stream
    assert build_dedup_package_stream(iter([b"abc"]), "gzip", "balanced") is None

def test_chunkstore_sqlite_backend(tmp_path):
    from turboquant.chunkstore import SQLiteChunkStore, temp_store
    s = SQLiteChunkStore()
    s.put("a", b"123")
    assert s.get("a") == b"123" and s.contains("a") and len(s) == 1
    s.close()
    with temp_store() as st:
        st.put_many([(f"k{i}", bytes([i]) * 10) for i in range(200)])
        assert len(st) == 200 and st.get("k199") == bytes([199]) * 10
    # ملف فعلي على القرص + WAL
    dbp = str(tmp_path / "c.db")
    fs = SQLiteChunkStore(dbp, fast=False)
    fs.put("x", b"yz")
    fs.close()
    assert sqlite3.connect(dbp).execute("SELECT COUNT(*) FROM blobs").fetchone()[0] == 1

def test_delta_multichunk_streaming(tmp_path):
    seed = os.urandom(90000)
    def w(name, tail):
        p = tmp_path / name
        with open(p, "wb") as f:
            for _ in range(30):
                f.write(seed)
            f.write(tail)
        return str(p)
    base = w("b1.bin", b"one" * 4000)
    new = w("b2.bin", b"two" * 4000)
    dl = tq.create_delta(base, new, mode="balanced", jobs=2)
    assert dl["total_chunks"] >= 3, dl
    out = str(tmp_path / "nb.bin")
    assert tq.apply_delta(base, dl["output"], out)["verified"] is True
    assert sha(out) == sha(new)

# ---- bench لا يسرّب + v1 progress ----

def test_bench_no_leak(tmp_path, monkeypatch):
    n0 = set(os.listdir(str(tmp_path)))
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    p = tmp_path / "s.txt"
    p.write_text("x\n" * 2000, encoding="utf-8")
    tq.benchmark(str(p), modes=("fast",))
    left = set(os.listdir(str(tmp_path))) - n0 - {"s.txt"}
    assert not [x for x in left if x.startswith("tq_bench_")], left

def test_v1_progress_and_cap(tmp_path):
    p = tmp_path / "v.txt"
    p.write_text("v1 line\n" * 4000, encoding="utf-8")
    calls = []
    c = str(p) + ".tqz"
    tq.compress_file(str(p), c, mode="balanced",
                     on_progress=lambda d, t, ph: calls.append((d, t, ph)))
    assert calls and calls[-1][0] <= calls[-1][1]
    d = str(tmp_path / "v.out")
    tq.decompress_file(c, d, on_progress=lambda *a: calls.append(a))
    assert open(d, encoding="utf-8").read() == open(p, encoding="utf-8").read()
    with pytest.raises(OutputLimitError):
        tq.decompress_file(c, str(tmp_path / "v2.out"), max_output_bytes=5)

# ---- media بلا ffmpeg (محاكاة منطق البحث) ----

class _FakeRun:
    def __init__(self, sizes):
        self.sizes = sizes  #(saved_bytes per out path suffix rule)
        self.calls = []

    def __call__(self, cmd, timeout=3600):
        self.calls.append(cmd)
        out = cmd[-1]
        n = self.sizes(out)
        with open(out, "wb") as f:
            f.write(b"\x00" * n)
        class R:
            returncode = 0
        return R()

def test_media_video_search_mock(tmp_path, monkeypatch):
    import turboquant.media as M
    monkeypatch.setattr(M, "have_ffmpeg", lambda: True)
    fake = _FakeRun(lambda out: int(out.split(".crf")[1].split(".")[0]) * 10 * 1024)
    monkeypatch.setattr(M, "_run", fake)
    src = tmp_path / "f.mp4"
    src.write_bytes(b"\x00" * 100)
    info = M.compress_video(str(src), str(tmp_path / "o.mp4"), target_bytes=300 * 1024, preset="720p")
    assert info["settings"]["crf"] == 18 and info["hit_target"] is True
    left = [f for f in os.listdir(str(tmp_path)) if ".tmp.mp4" in f]
    assert left == [], left  # لا مخلفات glob

def test_media_audio_ladder_mock(tmp_path, monkeypatch):
    import turboquant.media as M
    monkeypatch.setattr(M, "have_ffmpeg", lambda: True)
    table = {"128k": 400 * 1024, "96k": 300 * 1024, "64k": 200 * 1024,
             "48k": 150 * 1024, "32k": 100 * 1024, "24k": 80 * 1024}
    def sizes(out):
        for br, sz in table.items():
            if f".{br}.tmp" in out:
                return sz
        return 1
    monkeypatch.setattr(M, "_run", _FakeRun(sizes))
    src = tmp_path / "s.wav"
    src.write_bytes(b"\x00" * 100)
    info = M.compress_audio(str(src), str(tmp_path / "o.ogg"), target_bytes=300 * 1024)
    assert info["settings"]["bitrate"] == "96k" and info["hit_target"] is True

# ---- تغليف + خادم ----

def test_packaging_includes():
    import pathlib
    assert "*.mjs" in pathlib.Path("MANIFEST.in").read_text(encoding="utf-8")
    txt = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    assert '"gui*"' in txt
    assert pathlib.Path(".gitignore").read_text(encoding="utf-8").find("dist/") >= 0

def test_server_max_body(tmp_path, monkeypatch):
    import http.client
    import threading
    import time
    from http.server import HTTPServer
    from turboquant.server import H
    monkeypatch.setenv("TQ_MAX_MB", "1")
    srv = HTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        time.sleep(0.3)
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("POST", "/compress?mode=fast", body=b"x" * (2 * 1024 * 1024))
        assert c.getresponse().status == 413
        c2 = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c2.request("GET", "/health")
        assert c2.getresponse().status == 200
    finally:
        srv.shutdown()
        th.join(timeout=5)
