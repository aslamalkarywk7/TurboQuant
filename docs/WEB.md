# TurboQuant Web Console — تحكم حر + Vercel

واجهة ويب تفاعلية (عربية RTL) تستخدم **كامل قوة** المشروع: lossless + صور 800KB + فك + تحليل + شهادة + benchmark.

## التشغيل المحلي (كامل القوة — بلا حدود Vercel)

```bash
pip install -e ".[max]"
python -m turboquant serve --port 8765
# افتح: http://localhost:8765/
```

المسارات المحلية (نفسها على Vercel):

| المسار | الوصف |
|---|---|
| `GET /` | لوحة التحكم `public/index.html` |
| `GET /api/health` | فحص + codecs |
| `POST /api/compress?mode=max&advanced=0&filename=x.pdf` | ضغط → binary `.tqz` (أو `&format=json` → JSON+base64) |
| `POST /api/decompress` | فك → الملف الأصلي |
| `POST /api/image?target_bytes=819200&mode=balanced&fmt=auto` | صور 800KB |
| `POST /api/analyze` | JSON إنتروبيا + اقتراح |
| `POST /api/cert` | شهادة PASS/FAIL |
| `POST /api/bench?modes=fast,balanced,max,ultra` | مقارنة الأوضاع |

Legacy للتوافق: `POST /compress`, `POST /decompress`, `GET /health`, `GET /detect`.

مثال curl:

```bash
curl -X POST --data-binary @report.pdf "http://localhost:8765/api/compress?mode=max&filename=report.pdf" -o report.tqz
curl -X POST --data-binary @report.tqz "http://localhost:8765/api/decompress" -o report.pdf
curl -X POST --data-binary @data.csv "http://localhost:8765/api/analyze"
```

## النشر على Vercel (خطوتان)

1. ارفع المجلد إلى GitHub (يشمل `public/`, `api/`, `vercel.json`, `requirements.txt`, `runtime.txt`).
2. في Vercel: `New Project → Import` ثم `Deploy`. أو:
```bash
npm i -g vercel
vercel --prod
```

ملاحظات Vercel:
- حد الطلب الواحد ≈ **4.5MB** (قيد المنصة). الواجهة تنبه لهذا. للملفات الكبيرة شغّل محلياً أو ارفع `TQ_MAX_MB`.
- `vercel.json` يضبط `maxDuration=60` و `memory=1024` لدوال `api/*.py`.
- المتغير الاختياري `TQ_MAX_MB` (افتراضي 25) يتحكم بسقف الرفع داخل الدالة.
- `ffmpeg` غير متوفر على Vercel → مسارات الفيديو/الصوت lossy المعتمدة عليه تعطي خطأ واضح؛ كل مسارات lossless + صور 800KB تعمل بكامل القوة.

## البنية

```
public/index.html   ← لوحة تحكم حرة (لا build step، تعمل هنا وعلى Vercel)
api/
  _tq.py            ← CORS + قراءة body محدودة + إرسال (مشترك)
  health.py / compress.py / decompress.py / image.py / analyze.py / cert.py / bench.py
turboquant/server.py← يخدم public/ + نفس مسارات /api/* محلياً (+ legacy)
vercel.json         ← rewrites + functions config
runtime.txt         ← python-3.12
tests/test_web.py   ← تغطية UI + API + استيراد handlers
```
