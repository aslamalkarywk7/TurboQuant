"""اختبارات نظام الخوارزميات المتقدمة: كلها lossless (roundtrip + sha)."""
import hashlib
import os
import pytest
import turboquant as tq
from turboquant.advanced import (
    byte_entropy, analyze, smart_select, analyze_file, TRANSFORMS,
    delta8_encode, delta8_decode, xor8_encode, xor8_decode,
    delta16le_encode, delta16le_decode, bwt_encode, bwt_decode,
    filters_encode, filters_decode,
)

zstd = pytest.importorskip("zstandard")

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

def test_entropy_scale():
    assert byte_entropy(bytes(5000)) == 0.0
    assert byte_entropy(os.urandom(20000)) > 7.6
    assert analyze(b"x" * 9999)["verdict"] == "compressible"
    assert analyze(os.urandom(20000))["verdict"] == "incompressible"

def test_bwt_adversarial():
    for d in [b"", b"A", b"Z" * 9999, bytes(4000), b"ab" * 6000,
              b"abcabc" * 4000, bytes(range(256)) * 50,
              ("lorem ipsum dolor sit amet " * 500).encode(), os.urandom(3000)]:
        assert bwt_decode(bwt_encode(d)) == d

def test_delta_filters_roundtrip():
    d = os.urandom(5001)  # فردي عمداً
    assert delta8_decode(delta8_encode(d)) == d
    assert xor8_decode(xor8_encode(d)) == d
    assert delta16le_decode(delta16le_encode(d)) == d
    assert delta16le_decode(delta16le_encode(b"")) == b""
    assert filters_decode(filters_encode(d)) == d

def test_zdict_roundtrip(tmp_path):
    from turboquant.advanced.zdict import self_train, pack_body, unpack_body, dict_compress, dict_decompress
    data = "".join(f'{{"id": {i}, "name": "user_{i % 50}", "active": true}}\n' for i in range(3000)).encode()
    zd = self_train(data)
    assert zd is not None
    frame = dict_compress(data, zd)
    zd2, fr2 = unpack_body(pack_body(zd, frame))
    assert dict_decompress(fr2, zd2) == data

def test_smart_select_wav_picks_delta16(tmp_path):
    import struct, math
    pcm = b"".join(struct.pack("<h", int(9000 * math.sin(i / 9))) for i in range(30000))
    sel = smart_select(pcm, "audio_wav")
    assert sel["transform"] == "delta16le", sel
    assert sel["est_ratio"] < 0.5, sel

def test_smart_select_random_is_store():
    sel = smart_select(os.urandom(60000), "generic")
    assert sel["transform"] == "none" and sel["codec"] == "store", sel

def test_advanced_csv_roundtrip_beats_or_matches(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("id,name,score\n" + "".join(f"{i},user_{i % 97},{i * 1.5}\n" for i in range(6000)), encoding="utf-8")
    std = tq.compress_lossless(str(p), str(p) + ".std.tqz", mode="balanced")
    adv = tq.compress_lossless(str(p), str(p) + ".adv.tqz", mode="balanced", advanced=True)
    assert adv["verified"] and adv["transform"] in TRANSFORMS
    assert adv["new"] <= std["new"], (std["new"], adv["new"], adv["transform"])
    r = str(p) + ".out"
    tq.decompress_lossless(str(p) + ".adv.tqz", r)
    assert sha(str(p)) == sha(r)

def test_advanced_wav_roundtrip(tmp_path):
    import struct, math, wave
    p = str(tmp_path / "s.wav")
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 12))) for i in range(24000)))
    info = tq.compress_lossless(p, p + ".tqz", mode="balanced", advanced=True)
    assert info["verified"] and info["transform"] == "delta16le", info
    tq.decompress_lossless(p + ".tqz", p + ".out.wav")
    assert sha(p) == sha(p + ".out.wav")

def test_advanced_random_uses_store(tmp_path):
    p = tmp_path / "r.bin"
    p.write_bytes(os.urandom(60000))
    info = tq.compress_lossless(str(p), str(p) + ".tqz", mode="ultra", advanced=True)
    assert info["verified"] and info["codec"] == "store", info
    assert info["new"] <= info["orig"] * 1.02
    tq.decompress_lossless(str(p) + ".tqz", str(p) + ".out")
    assert sha(str(p)) == sha(str(p) + ".out")

def test_analyze_file_report(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hello\n" * 5000, encoding="utf-8")
    rep = tq.analyze_file(str(p))
    assert rep["kind"] == "text" and rep["verdict"] == "compressible"
    assert rep["suggestion"]["transform"] in TRANSFORMS
