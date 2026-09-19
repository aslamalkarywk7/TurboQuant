# PERFORMANCE — جدول أداء حقيقي (مقاس فعلياً، وليس تقديرات)

الجهاز: Windows + Python 3.12 | `turboquant 2.1.0` | codecs: zstd,brotli,lzma,bz2,gzip
الأمر: `python -m turboquant bench <file>` (يقيس ضغط + فك + تحقق sha256).
التاريخ: 2026-09-14. كل الصفوف `verified=True` أي **بايت مطابق 100% بدون فقد جودة**.

## text 1.37MB
```
mode      codec         ratio   saved%  comp_s  MB/s    verified
fast      brotli        0.0002  99.98   0.991   1.39    True
balanced  brotli        0.0002  99.98   0.951   1.44    True
max       brotli        0.0002  99.98   1.015   1.35    True
ultra     brotli        0.0002  99.98   1.015   1.35    True
```

## csv 546KB
```
mode      codec         ratio   saved%  comp_s  MB/s    verified
fast      brotli        0.0005  99.95   0.381   1.40    True
balanced  brotli        0.0005  99.95   0.384   1.39    True
max       brotli        0.0005  99.95   0.628   0.85    True
ultra     brotli        0.0005  99.95   0.465   1.15    True
```

## json 31KB
```
mode      codec         ratio   saved%  comp_s  MB/s    verified
fast      brotli        0.0086  99.14   0.011   2.78    True
balanced  brotli        0.0087  99.13   0.017   1.75    True
max       zstd          0.0085  99.15   0.037   0.83    True
ultra     zstd          0.0085  99.15   0.397   0.08    True
```

## repeat-binary 1.53MB
```
mode      codec         ratio   saved%  comp_s  MB/s    verified
fast      brotli        0.0002  99.98   1.158   1.32    True
balanced  brotli        0.0002  99.98   1.045   1.46    True
max       brotli        0.0002  99.98   1.133   1.35    True
ultra     brotli        0.0002  99.98   1.098   1.39    True
```

## random 1MB (بيانات عشوائية — الصدق هنا)
```
mode      codec         ratio   saved%  comp_s  MB/s    verified
fast      brotli        1.0002  -0.02   0.718   1.39    True
balanced  brotli        1.0002  -0.02   0.842   1.19    True
max       brotli        1.0002  -0.02   2.843   0.35    True
ultra     brotli        1.0002  -0.02   2.812   0.36    True
```

## كيف تقرأ الجدول (للمطورين)
- البيانات المتكررة (نصوص/csv/json): توفير 99%+ طبيعي ومتوقع (400م -> 20م ممكن هنا).
- البيانات العشوائية/المشفرة/المضغوطة أصلاً (MP4/ZIP): لا تنضغط (`ratio≈1.0`) — **وهذا صدق وليس فشلاً**، والجودة تبقى 100%.
- `fast` للسرعة، `balanced` للاستخدام اليومي، `max/ultra` لأقصى توفير على حساب الوقت.
- أعد القياس على ملفك: `python -m turboquant bench data.bin`

## مقارنة مع المنافسين (tq-balanced ضد gzip -9 و zstd -9)

الجهاز: Windows + Python 3.12 | التاريخ: 2026-09-19 | كل الصفوف verified=True.

```
file         tool         size      ratio   comp_s  verified
text-1MB     tq-balanced  431       0.0004  0.821   True
text-1MB     gzip-9       3668      0.0035  0.016   True
text-1MB     zstd-9       1170      0.0011  0.004   True
random-256KB tq-balanced  262453    1.0012  0.294   True
random-256KB gzip-9       262242    1.0004  0.017   True
random-256KB zstd-9       262159    1.0001  0.001   True
```

الخلاصة الصادقة: على النصوص المتكررة يتفوق tq بالنسبة بفضل إزالة التكرار، لكنه أبطأ في الضغط من gzip/zstd. وعلى البيانات العشوائية يتساوى الجميع عند ratio≈1.0 (لا شيء يُضغط) — والجودة تبقى 100% دائماً.
