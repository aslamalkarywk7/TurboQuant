# bindings/README — كيف تستخدم TurboQuant من أي لغة؟

## الطريقة 1: CLI (الأسهل — تعمل فوراً)
ثبّت المكتبة مرة واحدة:
```bash
pip install -e /path/to/TurboQuant
# أو: pip install tqz
```
ثم من أي لغة نفّذ أمر النظام (أمثلة جاهزة بجانب هذا الملف):
- `bindings/turboquant.js` (Node) — `compressLossless/decompress/compressViaRest`
- `bindings/TurboQuant.java` (Java) — نفس الدوال عبر ProcessBuilder
- `bindings/TurboQuant.cs` (C#) — عبر Process + HttpClient
- `bindings/turboquant.go` (Go) — عبر os/exec + net/http

```bash
python -m turboquant lossless report.pdf -o report.tqz --mode max
python -m turboquant decompress report.tqz -o report.pdf
python -m turboquant detect report.pdf
```

## الطريقة 2: REST (للميكروسيرفسز)
```bash
python -m turboquant serve --port 8765
curl -X POST --data-binary @report.pdf "http://localhost:8765/compress?mode=max" -o report.tqz
curl -X POST --data-binary @report.tqz "http://localhost:8765/decompress" -o report.pdf
```
أي لغة فيها HTTP (PHP/Ruby/Rust/PHP...) تستخدمه مباشرة بدون أي مكتبة.

## الطريقة 3: مفككات أصلية (بدون Python إطلاقاً)
ملفات جاهزة ومُختبرة تفك `method=single` مباشرة:
- `bindings/tqz-decode.mjs` (Node ≥ 18): `node tqz-decode.mjs in.tqz out`
- `bindings/TqzDecode.java` (JDK فقط): `javac TqzDecode.java && java TqzDecode in.tqz out`
- `bindings/tqzdecode.go` (stdlib): `go run tqzdecode.go in.tqz out`
- `bindings/TqzDecode.cs` (.NET فقط): `[TqzDecode]::Decode("in.tqz", "out")`

مصفوفة الدعم (تفاصيل الفورمات `docs/FORMAT.md`):

| المفكك | gzip | brotli | store | none/delta/xor/filters/bwt | zstd/lzma/dedup/zdict |
|---|---|---|---|---|---|
| JS | ✅ | ✅ | ✅ | ✅ | يحتاج Python |
| C# | ✅ | ✅ | ✅ | ✅ | يحتاج Python |
| Java | ✅ | ❌ | ✅ | ✅ | يحتاج Python |
| Go | ✅ | ❌ | ✅ | ✅ | يحتاج Python |

كل المفككات تتحقق من `orig_size` و`sha256` وترفض الملف التالف بصوت عالٍ.

## الطريقة 4: تنفيذ الفورمات أصلياً (الأسرع — بدون Python)
اقرأ `docs/FORMAT.md`: بنية `.tqz` مفتوحة (MAGIC + JSON header + body).
نفّذها بلغتك باستخدام مكتبة zstd/lzma/brotli المتاحة لديك + تحقق sha256.
