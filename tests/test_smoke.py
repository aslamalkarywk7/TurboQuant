import hashlib
import os
import zipfile
from PIL import Image
import turboquant as tq

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

def test_image_to_800k(tmp_path):
    p = tmp_path / "big.jpg"
    img = Image.new("RGB", (3000, 2000))
    px = img.load()
    for x in range(0, 3000, 7):
        for y in range(0, 2000, 7):
            px[x, y] = ((x * 3) % 256, (y * 5) % 256, (x + y) % 256)
    img.save(p, "JPEG", quality=95)
    out = str(tmp_path / "out.webp")
    info = tq.compress_image(str(p), out, target_bytes=800*1024, mode="balanced")
    assert os.path.exists(out)
    assert info["new"] <= 800*1024, info
    assert info["hit_target"] is True

def test_file_roundtrip(tmp_path):
    p = tmp_path / "data.bin"
    p.write_bytes((b"TurboQuant hello world! " * 5000) + os.urandom(2000))
    c = str(tmp_path / "data.tqz")
    info = tq.compress_file(str(p), c, mode="balanced")
    assert os.path.exists(c)
    assert info["new"] < info["orig"]
    r = str(tmp_path / "restored.bin")
    tq.decompress_file(c, r)
    assert open(r, "rb").read() == open(p, "rb").read()

def test_auto_dispatch(tmp_path):
    from PIL import Image as I
    p = tmp_path / "a.png"
    I.new("RGB", (1600, 1200), (10, 200, 90)).save(p)
    info = tq.compress_auto(str(p), mode="balanced")
    assert info.get("output") and os.path.exists(info["output"])

# ---- v2 lossless: كل الأنواع بدون فقد ----

def test_lossless_text_roundtrip(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_bytes(("سطر مكرر للاختبار TurboQuant 123\n" * 20000).encode("utf-8"))
    c = str(tmp_path / "notes.tqz")
    info = tq.compress_lossless(str(p), c, mode="max")
    assert info["lossless"] and info["verified"]
    assert info["new"] < info["orig"]
    r = str(tmp_path / "notes.out.txt")
    d = tq.decompress_lossless(c, r)
    assert d["verified"] is True
    assert sha(str(p)) == sha(r)

def test_lossless_csv_json(tmp_path):
    csv = tmp_path / "d.csv"
    csv.write_text("a,b,c\n" + "1,2,3\n" * 15000, encoding="utf-8")
    js = tmp_path / "d.json"
    js.write_text('{"k": "' + "x" * 500 + '", "n": 1}\n' * 3000, encoding="utf-8")
    for f in (csv, js):
        c = str(f) + ".tqz"
        info = tq.compress_lossless(str(f), c, mode="balanced")
        assert info["verified"], info
        r = str(f) + ".out"
        tq.decompress_lossless(c, r)
        assert sha(str(f)) == sha(r), f

def test_lossless_image_pixels_identical(tmp_path):
    p = tmp_path / "pic.png"
    img = Image.new("RGB", (512, 512))
    px = img.load()
    for x in range(512):
        for y in range(512):
            px[x, y] = ((x * 5) % 256, (y * 7) % 256, (x + y) % 256)
    img.save(p, "PNG")
    c = str(tmp_path / "pic.tqz")
    info = tq.compress_lossless(str(p), c, mode="balanced")
    assert info["kind"] == "image" and info["verified"]
    r = str(tmp_path / "pic.out.png")
    tq.decompress_lossless(c, r)
    a = Image.open(p).convert("RGB")
    b = Image.open(r).convert("RGB")
    assert list(a.getdata()) == list(b.getdata())

def test_lossless_office_zip_smaller_or_equal(tmp_path):
    z = tmp_path / "doc.docx"
    with zipfile.ZipFile(z, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        zf.writestr("word/document.xml", "<w:doc>" + "hello " * 20000 + "</w:doc>")
        zf.writestr("[Content_Types].xml", "<types/>" * 500)
    c = str(tmp_path / "doc.tqz")
    info = tq.compress_lossless(str(z), c, mode="max")
    assert info["verified"]
    assert info["new"] <= info["orig"] * 1.05  # bit-identical: قد يزيد هيدر بسيط لغير القابل للضغط
    r = str(tmp_path / "doc.out.docx")
    tq.decompress_lossless(c, r)
    assert sha(str(z)) == sha(r)

def test_lossless_dedup_repeated_blocks(tmp_path):
    p = tmp_path / "vm.bin"
    block = os.urandom(50000)
    with open(p, "wb") as f:
        for _ in range(40):
            f.write(block)  # تكرار كامل -> dedup يتألق
    c = str(p) + ".tqz"
    info = tq.compress_lossless(str(p), c, mode="ultra")
    assert info["verified"]
    assert info["new"] < info["orig"] * 0.5, info
    r = str(p) + ".out"
    tq.decompress_lossless(c, r)
    assert sha(str(p)) == sha(r)

def test_lossless_binary_random_honest(tmp_path):
    p = tmp_path / "rand.bin"
    p.write_bytes(os.urandom(300000))
    c = str(p) + ".tqz"
    info = tq.compress_lossless(str(p), c, mode="ultra")
    # بيانات عشوائية لا تنضغط — المهم: فك الضغط مطابق 100% (بدون فقد/تلف)
    r = str(p) + ".out"
    d = tq.decompress_lossless(c, r)
    assert d["verified"] is True
    assert sha(str(p)) == sha(r)

def test_detect_kinds(tmp_path):
    from turboquant import detect_kind
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n")
    assert detect_kind(str(f)) == "csv"
    j = tmp_path / "y.json"
    j.write_text("{}")
    assert detect_kind(str(j)) == "json"
