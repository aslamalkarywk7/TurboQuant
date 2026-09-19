# TurboQuant v2 — مكتبة ضغط موحدة لكل الملفات 🇪🇬

## التركيب بنقرة واحدة
```bash
pip install "turboquant[max]"          # موصى به (zstd + brotli)
# Windows PowerShell: powershell -ExecutionPolicy Bypass -File scripts/install.ps1
# Linux/macOS:        sh scripts/install.sh
# من المصدر: pip install -e ".[max]" ثم pytest -q
```

## القاعدة الذهبية
- **LOSSLESS افتراضياً = بدون أي فقد جودة** (بكسل/بايت مطابق 100% + تحقق `sha256`).
- **LOSSY للصور فقط** عند طلب حجم صغير جداً (800KB) — وباختيارك الصريح.

## ضمان API المستقر (من 2.x)
نفس الأسماء في كل اللغات — بدّل اللغة بدون إعادة تعلم:
`compress / decompress / detect / benchmark / verify`
- Python: `import turboquant as tq` • Node: `bindings/turboquant.js`
- Java: `bindings/TurboQuant.java` • C#: `bindings/TurboQuant.cs` • Go: `bindings/turboquant.go`
- أي لغة أخرى: REST (`python -m turboquant serve`) أو مواصفة `docs/FORMAT.md`.

## ترتيب المكتبة الجديد
```
turboquant/
  __init__.py   -> compress_auto / decompress_auto (بوابة واحدة لكل الأنواع)
  lossless.py   -> compress_lossless / decompress_lossless (كل الملفات، sha256)
  detect.py     -> detect_kind لكل نوع + suggest_pipeline
  codecs.py     -> zstd/brotli/lzma/bz2/gzip (الكل lossless + best-of)
  dedup.py      -> إزالة التكرار FastCDC (مثل Borg/Restic) — سر التوفير الكبير
  handlers/     -> image_lossless / document (zip/pdf) / audio (wav->flac)
  image.py      -> lossy للصور فقط (800KB)
  file.py       -> حاوية v1 (متوافقة)
  server.py     -> REST لأي لغة
bindings/       -> JS / Java / C# / Go (CLI + REST) + README
docs/FORMAT.md  -> مواصفة .tqz المفتوحة لأي لغة
```

## الاستخدام (Python)
```python
import turboquant as tq

# 1) أي ملف — بدون فقد جودة (PDF/Office/CSV/JSON/PNG/WAV/EXE/...)
tq.compress_lossless("report.pdf", "report.tqz", mode="max")     # موصى به
tq.compress_lossless("data.csv", "data.tqz", mode="ultra")       # أقصى ضغط
tq.compress_lossless("photo.png", "photo.tqz")                   # بكسل مطابق
tq.decompress_lossless("report.tqz", "report.pdf")               # تحقق sha256

# 2) تلقائي ذكي لكل الأنواع
tq.compress_auto("anything.pdf")                 # -> lossless
tq.compress_auto("photo.jpg", target_bytes=800*1024, lossless=False)  # -> lossy 800KB

# 2ب) تحسين اختياري quality-lossless (يغيّر الحاوية، الجودة 100%)
tq.optimize_lossless("photo.bmp")   # -> PNG/WebP-lossless (بكسل مطابق)
tq.optimize_lossless("doc.docx")    # -> zip max (نفس المحتوى)
tq.optimize_lossless("a.wav")       # -> FLAC (نفس العينات)

# 3) صورة صغيرة جداً (lossy — يغيّر الجودة بتحكمك)
tq.compress_image("in.jpg", "out.webp", target_bytes=800*1024, mode="balanced")

# 4) أوضاع الضغط (قوة الضغط — الجودة ثابتة 100% في lossless)
# fast (أسرع) | balanced | max | ultra
# ملاحظة صدق: أرقام مثل 400م->115م أمثلة لبيانات قابلة للضغط (نصوص/متكرر)،
# وليست ضماناً — البيانات المشفرة/المضغوطة أصلاً لا تنضغط أكثر (انظر hit_target).

# 5) وضع المطور داخل برنامجك: تقدم + إلغاء + قياس
tok = tq.CancelToken()
info = tq.compress_lossless("big.bin", "big.tqz", mode="max",
                            on_progress=lambda d, t, ph: print(f"{d/t:.0%}"),
                            cancel=tok)
# من زر "إلغاء": tok.cancel()  (يرفع tq.CancelledError)
rows = tq.benchmark("data.csv", modes=["fast", "balanced", "max", "ultra"])
tq.print_benchmark(rows)

# 6) شهادة ثقة تعرضها للمستخدم
from turboquant import verify_package, format_certificate
print(format_certificate(verify_package("big.tqz")))  # verdict: PASS/FAIL
```

## الطرق المتقدمة (كلها lossless)
| الطريقة | أين تعمل | الفكرة |
|---|---|---|
| `dedup chunks` | logs/VM/نسخ/DB | FastCDC ~256KB + sha256، تخزين الفريد فقط |
| `best-codec` | كل الملفات | تجربة zstd/brotli/lzma على عينة واختيار الأصغر |
| `image-lossless` | PNG/BMP/TIFF | PNG-optimize وWebP-lossless + تحقق بكسل ببكسل |
| `zip-recompress` | docx/xlsx/zip | فك الـ zip وإعادة ضغطه max (توفير 5-20%) |
| `pdf-recompress` | PDF | إعادة ضغط streams (pikepdf) |
| `wav->flac` | صوت خام | تحويل FLAC (توفير ~50%) عبر ffmpeg |
| `sha256 verify` | الكل | فك الضغط لا يُقبل إلا بمطابقة تامة |

> ملفات مضغوطة أصلاً (MP4/MP3/ZIP عشوائي): لا سحر — التوفير صغير و`hit_target=False` بصدق، لكن **الجودة لا تمس أبداً**.

## أداء حقيقي (مقاس فعلياً — التفاصيل `docs/PERFORMANCE.md`)
| الملف | balanced | ultra | التحقق |
|---|---|---|---|
| نص 1.37MB | 99.98% توفير | 99.98% | بايت مطابق |
| csv 546KB | 99.95% | 99.95% | بايت مطابق |
| عشوائي 1MB | +0.02% (لا ينضغط بصدق) | +0.02% | بايت مطابق |
```bash
python -m turboquant bench data.bin        # قس على ملفك
python -m turboquant cert out.tqz          # شهادة الثقة
python -m turboquant lossless big.bin -o big.tqz --mode max --progress
```

## نظام الخوارزميات المتقدمة (v2.2.0 — كله lossless)
```python
import turboquant as tq
print(tq.analyze_file("data.csv"))   # إنتروبيا + التحويل المقترح قبل الضغط
tq.compress_lossless("data.csv", "d.tqz", mode="max", advanced=True)
tq.compress_lossless("s.wav", "s.tqz", mode="max", advanced=True)   # delta16le تلقائياً
```
```bash
python -m turboquant analyze data.csv
python -m turboquant lossless data.csv -o d.tqz --mode max --advanced
python -m turboquant bench data.csv --advanced
```
- entropy gate (تخزين خام للعشوائي) • BWT بأسلوب bzip2 • delta8/xor8/delta16le •
  مرشحات PNG • قواميس zstd ذاتية • منسق يختار الفائز تلقائياً — التفاصيل `docs/ADVANCED.md`.

## الترخيص والمساهمة
- الترخيص: MIT (`LICENSE`) — استخدمها داخل برامجك التجارية بحرية.
- السجل: `CHANGELOG.md` — الإصدارات من 2.x تحافظ على أسماء الدوال.

## الاستخدام من لغات أخرى
```bash
pip install -e .
python -m turboquant lossless report.pdf -o report.tqz --mode max
python -m turboquant decompress report.tqz -o report.pdf
python -m turboquant detect report.pdf
python -m turboquant serve --port 8765   # REST لأي لغة
```
- Node: `bindings/turboquant.js` • Java: `bindings/TurboQuant.java`
- C#: `bindings/TurboQuant.cs` • Go: `bindings/turboquant.go`
- مفككات أصلية بلا Python: `tqz-decode.mjs` • `TqzDecode.java` • `tqzdecode.go` • `TqzDecode.cs`
- الفورمات المفتوح: `docs/FORMAT.md`

## الجديد في v2.3 (الأولوية: نسبة أعلى)
```python
import turboquant as tq
# تشفير: ضغط ثم AES-256-GCM
tq.encrypt_file("backup.tqz", password="...")   # → .tqze
# تزايدي: فروق النسخة الجديدة فقط عن الأساس
tq.create_delta("v1.bin", "v2.bin")             # → أصغر بكثير من نسخة كاملة
tq.apply_delta("v1.bin", "v2.tdelta.tqz", "v2.bin")
# توازي: نفس البايتات، وقت أقل
tq.compress_lossless("big.bin", "big.tqz", mode="max", jobs=None)  # كل الأنوية
# وسائط (يتطلب ffmpeg): فيديو/صوت لهدف حجمي مثل صور 800KB
tq.compress_video("film.mp4", "film.tq.mp4", target_bytes=20*1024*1024, preset="720p")
tq.compress_audio("song.wav", "song.tq.ogg", target_bytes=5*1024*1024)
```
```bash
TURBOQUANT_PASSWORD=... python -m turboquant encrypt backup.tqz
python -m turboquant delta v1.bin v2.bin -o v2.tdelta.tqz
python -m turboquant lossless big.bin --jobs all
python -m turboquant video film.mp4 --target 20MB --preset 720p
```

## إضافات البرامج (5 دقائق دمج)
```bash
turboquant-gui                                  # واجهة سحب وإفلات (تقدم + إلغاء + شهادة)
docker build -t turboquant . && docker run -p 8765:8765 turboquant   # REST جاهز
```
- أمثلة جاهزة للنسخ: `examples/example.py` • `example.js` • `Example.java` • `example.cs` • `example.go` • `example_rest.sh`
- النشر: `pip install turboquant[max]` / `npm i turboquant` + سكربتات `scripts/install.*` + CI في `.github/workflows/publish.yml`

## التركيب
```bash
pip install -e .               # أساسي
pip install -e ".[max]"        # + zstd/brotli (موصى به)
pip install -e ".[full]"       # + pikepdf/soundfile (PDF/صوت)
pip install -e ".[secure]"     # + cryptography (تشفير)
pytest -q
```
