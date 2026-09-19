"""اختبارات v2.3: تشفير + دلتا + توازي + وسائط (تخطي آمن بلا ffmpeg)."""
import hashlib
import os
import pytest
import turboquant as tq

crypt = pytest.importorskip("cryptography")

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

def _txt(tmp_path, name="s.txt", n=5000, extra=""):
    p = tmp_path / name
    p.write_text(("hello TurboQuant\n" * n) + extra, encoding="utf-8")
    return str(p)

# ---- تشفير ----

def test_crypto_roundtrip(tmp_path):
    p = _txt(tmp_path)
    c = tq.compress_lossless(p, p + ".tqz", mode="balanced")
    e = tq.encrypt_file(p + ".tqz", password="s3cr3t!")
    assert e["output"].endswith(".tqze") and e["cipher"].startswith("AES-256")
    d = tq.decrypt_file(e["output"], password="s3cr3t!")
    assert sha(d["output"]) == sha(p + ".tqz")
    r = str(tmp_path / "restored.txt")
    tq.decompress_lossless(d["output"], r)
    assert sha(r) == sha(p)

def test_crypto_wrong_password_and_tamper(tmp_path):
    p = _txt(tmp_path)
    e = tq.encrypt_file(p, password="right")
    with pytest.raises(ValueError):
        tq.decrypt_file(e["output"], password="wrong")
    raw = bytearray(open(e["output"], "rb").read())
    raw[-5] ^= 0xFF  # عبث ببايت واحد
    tp = str(tmp_path / "evil.tqze")
    open(tp, "wb").write(bytes(raw))
    with pytest.raises(ValueError):
        tq.decrypt_file(tp, password="right")

# ---- دلتا تزايدية ----

def _big(tmp_path, name, seed: bytes, tail: bytes):
    p = tmp_path / name
    with open(p, "wb") as f:
        for _ in range(30):
            f.write(seed)
        f.write(tail)
    return str(p)

def test_delta_small_change(tmp_path):
    seed = os.urandom(60000)
    base = _big(tmp_path, "v1.bin", seed, b"version-one" * 2000)
    new = _big(tmp_path, "v2.bin", seed, b"version-TWO" * 2000)
    full = tq.compress_lossless(new, new + ".full.tqz", mode="balanced")
    dl = tq.create_delta(base, new, mode="balanced")
    assert dl["new_chunks"] < dl["total_chunks"], dl  # معظم chunks أُعيد استخدامها
    assert dl["new"] < full["new"], (dl["new"], full["new"])  # الدلتا أصغر من الكاملة
    out = str(tmp_path / "v2.out.bin")
    ap = tq.apply_delta(base, dl["output"], out)
    assert ap["verified"] is True and sha(out) == sha(new)

def test_delta_wrong_base_rejected(tmp_path):
    seed = os.urandom(60000)
    base = _big(tmp_path, "b1.bin", seed, b"one" * 1000)
    new = _big(tmp_path, "b2.bin", seed, b"two" * 1000)
    other = _big(tmp_path, "other.bin", os.urandom(60000), b"xxx" * 1000)
    dl = tq.create_delta(base, new, mode="fast")
    with pytest.raises(ValueError):
        tq.apply_delta(other, dl["output"], str(tmp_path / "x.out"))

def test_delta_identical_is_tiny(tmp_path):
    p = _txt(tmp_path, n=20000)
    dl = tq.create_delta(p, p, mode="balanced")
    assert dl["new_chunks"] == 0, dl  # لا جديد إطلاقاً
    out = str(tmp_path / "same.out")
    assert tq.apply_delta(p, dl["output"], out)["verified"] is True
    assert sha(out) == sha(p)

# ---- توازي ----

def test_parallel_same_bytes(tmp_path):
    p = _txt(tmp_path, n=8000)
    a = tq.compress_lossless(p, str(p) + ".s.tqz", mode="balanced", jobs=1)
    b = tq.compress_lossless(p, str(p) + ".p.tqz", mode="balanced", jobs=4)
    assert a["codec"] == b["codec"] and a["new"] == b["new"], (a, b)
    r = str(tmp_path / "p.out")
    tq.decompress_lossless(str(p) + ".p.tqz", r)
    assert sha(r) == sha(p)

def test_parallel_best_of(tmp_path):
    data = ("abc123\n" * 20000).encode()
    c1, b1 = tq.best_of_parallel(data, "balanced", jobs=1)
    c4, b4 = tq.best_of_parallel(data, "balanced", jobs=4)
    assert (c1, b1) == (c4, b4)

# ---- وسائط ----

def test_media_needs_ffmpeg(tmp_path):
    if tq.have_ffmpeg():
        pytest.skip("ffmpeg موجود — التغطية اليدوية في docs/MEDIA")
    p = tmp_path / "x.mp4"
    p.write_bytes(b"\x00" * 100)
    with pytest.raises(RuntimeError):
        tq.compress_video(str(p), str(p) + ".out.mp4")
    with pytest.raises(RuntimeError):
        tq.compress_audio(str(p), str(p) + ".out.ogg")
