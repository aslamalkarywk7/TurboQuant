# نظام الخوارزميات المتقدمة — كتالوج (v2.2.0)

التفعيل: `compress_lossless(..., advanced=True)` أو `lossless --advanced`.
القاعدة: **كلها lossless** — الفك يعيد البايتات مطابقة (sha256)، والاختيار التلقائي
لا يمس الجودة أبداً، بل يختار أصغر نتيجة فقط.

## 1) بوابة الإنتروبيا (`advanced/entropy.py`)
- إنتروبيا شانون بت/بايت على عينة 1MB: `≤6.5` قابلة للضغط، `≥7.6` عشوائية.
- العشوائية → codec التخزين الخام `store` فوراً: أسرع ولا يدّعي توفيراً وهمياً.

## 2) تحويل BWT بأسلوب bzip2 (`advanced/bwt.py`)
- تجميع سياقي: المتشابه يتجاور → وليمة لـ zstd/lzma. كتل 32KB + suffix array
  بالمضاعفة O(n log n) + عكس LF-mapping بفرز عدّي.
- يفوز في: نصوص، سجلات، CSV، JSON، كود مصدري. التكلفة: CPU أعلى → للملفات المهمة.

## 3) فروقات Delta/XOR (`advanced/delta.py`)
- `delta8`: فرق بايت-بايت — متسلسلات عامة.
- `xor8`: XOR متجاور — نصوص وقوائم (البتات العليا تثبت).
- `delta16le`: فرق عينات 16-بت — WAV خام والحساسات (يقلب الموجة لأرقام حول الصفر).
- كلها نفس الطول تقريباً وبدون هيدر (عدا بايت pad في delta16le).

## 4) مرشحات PNG التنبؤية (`advanced/filters.py`)
- None/Sub/Up/Average/Paeth لكل صف + اكتشاف stride تلقائي [1..1024].
- تفوز في: صور خام، مصفوفات، جداول رقمية ملساء.

## 5) قواميس zstd الذاتية (`advanced/zdict.py`)
- تدريب قاموس من 24 شريحة من الملف نفسه → يلتقط البنية المتكررة المتباعدة
  (مفاتيح JSON، هيدرات CSV، قوالب سجلات). القاموس يُضمَّن في الحاوية.
- يتطلب `zstandard`. يُتخطى تلقائياً بدونه.

## 6) المنسق الذكي (`advanced/pipeline.py`)
- `analyze_file(path)`: تقرير (النوع + الإنتروبيا + التحويل المقترح) بدون ضغط.
- `smart_select`: سباق المرشحين على عينة 128KB بأسرع codec، والفائز يُنفَّذ كاملاً.
- المرشحون حسب النوع (بيانات مُرمَّزة كالصور/الفيديو تُستبعد لتوفير CPU).
- الحدود: ملفات ≤64MB (`ADV_CAP`)، والأكبر يرجع للمسار المتدفق العادي.
- المسار المتقدم مرشح إضافي (`single+adv`) ينافس العادي والـ dedup، والأصغر يفوز.

## أوامر
```bash
python -m turboquant analyze data.csv        # ماذا سيحدث قبل الضغط؟
python -m turboquant lossless data.csv -o d.tqz --mode max --advanced
python -m turboquant bench data.csv --advanced
```
```python
import turboquant as tq
print(tq.analyze_file("s.wav"))
tq.compress_lossless("s.wav", "s.tqz", mode="max", advanced=True)  # transform=delta16le
```
