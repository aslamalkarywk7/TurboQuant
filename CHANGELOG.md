# CHANGELOG — سجل الإصدارات (API مستقر من 2.x)

## Unreleased — hardening + community docs
- أمان: `ThreadingHTTPServer` + ربط `0.0.0.0`، تعطيل `GET /detect?path=` (كان oracle)، سقف هيدر `10MB` في `lossless/crypto/dedup`، `decompress_bytes` بسقف، تعقيم أسماء الملفات، رسائل خطأ عامة + هيدرات `nosniff/DENY/no-referrer`، توحيد `TQ_MAX_MB=25`.
- نشر: `Dockerfile` غير-root + `HEALTHCHECK` + `.dockerignore`، `release.yml` جديد، `ci.yml` يشمل `[secure]`، إسقاط `3.9` (الحد الأدنى `3.10` مثل Pillow 14/pytest 8)، إصلاح `package.json` repo URL.
- مجتمع: `CONTRIBUTING` + `CODE_OF_CONDUCT` + `SECURITY` + `SUPPORT` + `CITATION.cff` + `THIRD-PARTY-NOTICES` + قوالب Issue/PR + `docs/` (`ARCHITECTURE/CONFIGURATION/FAQ/TROUBLESHOOTING/FEATURES/ROADMAP/GLOSSARY/PROJECT-CHECKLIST/README` hub).

## 2.4.0 (2026-09-14) — إصلاح العيوب + قاعدة بيانات chunks
- مخزن chunks على SQLite (`chunkstore.py`, واجهة Backend مجردة): بناء dedup/delta
  متدفق بذاكرة محدودة (دفعات متوازية ≤16)، وإصلاح التعقيد التربيعي O(n²) بمجموعة set.
- حماية قنابل فك الضغط (`limits.py`): سقف تلقائي + `max_output_bytes` في كل مسارات
  الفك + `--max-gb` في CLI، وsha يُحسب أثناء الكتابة (لا قراءة ثانية).
- هرم أخطاء موحد (`errors.py`, متوافق مع ValueError/RuntimeError) + سجل `turboquant`
  الصامت + `TQ_DEBUG=1` بدل الابتلاع الصامت (29 موضعاً).
- إصلاحات: تسريب `bench` (سياق مؤقت)، `mktemp` المهجورة، مخلفات tmp عند الإلغاء،
  تنظيف media بقائمة متتبعة، `gui` في الـ wheel، `*.mjs` في الـ sdist، brotli-v1
  متدفق، تقدم/إلغاء لمسار v1، خادم بحد حجم (413) وأخطاء آمنة، `.gitignore`.
- قرار موثق: إبقاء BWT الكامل (السلامة فوق ~2x سرعة) — انظر `bwt.py`.
- اختبارات `test_fixes.py` (16) + `test_versions.py` (اتساق الإصدارات الثلاثة).

## 2.3.0 (2026-09-14) — الأولوية: نسبة ضغط أعلى
- تشفير AES-256-GCM بكلمة سر (`.tqze`, PBKDF2, إضافي `secure`) + أوامر `encrypt/decrypt`.
- نسخ تزايدية `delta/apply-delta`: فروق الملف فقط عن الأساس (chunks مُعاد استخدامها لا تُخزَّن).
- ضغط متوازي `--jobs`/`jobs=all` (codecs + chunks concurrently، نفس البايتات).
- فيديو/صوت lossy عبر ffmpeg (`video`/`audio` ببحث CRF/bitrate لهدف حجمي).
- مفككات أصلية بلا Python: JS (18/18) وC# (18/18) وJava (12/12) وGo (12/12) — مُختبرة فعلياً.
- نشر رسمي: workflow إصدار (pytest → build → PyPI/npm) + `docs/PUBLISHING.md`.

## 2.2.0 (2026-09-14)
- نظام الخوارزميات المتقدمة `turboquant/advanced/` (كله lossless + sha256):
  بوابة الإنتروبيا + BWT بأسلوب bzip2 + فروقات delta8/xor8/delta16le +
  مرشحات PNG التنبؤية + قواميس zstd ذاتية + منسق ذكي يختار الفائز تلقائياً.
- codec التخزين الخام `store` للبيانات العشوائية (أسرع وأصدق من ضغط وهمي).
- `compress_lossless(..., advanced=True)` + `analyze_file()` + أوامر `analyze` و`--advanced`.
- توثيق الفورمات: حقل `transform` + إطار القاموس (§5 و§8 في `docs/FORMAT.md`).

## 2.1.0 (2026-09-14)
- وضع المطور: `on_progress` + `cancel` + `benchmark()` + أمر `bench` + `--progress` في CLI.
- شهادة ثقة: `verify_package()` + أمر `cert` + جدول أداء حقيقي `docs/PERFORMANCE.md`.
- نشر بنقرة: PyPI metadata كاملة + `package.json` + سكربتات `scripts/install` + CI للنشر.
- إضافات: واجهة `turboquant-gui` + `Dockerfile` + أمثلة لكل لغة.
- ضمان API: أسماء `compress/decompress/detect` ثابتة في كل اللغات من 2.x.

## 2.0.0
- خط أنابيب lossless موحد لكل الملفات (bit-identical + sha256).
- `detect.py` + `codecs.py` (zstd/brotli/lzma/bz2/gzip) + `dedup.py` (FastCDC).
- handlers اختيارية quality-lossless + خادم REST + bindings (JS/Java/C#/Go).

## 1.0.0
- ضغط صور lossy لهدف حجمي (800KB) + حاوية .tqz v1.
