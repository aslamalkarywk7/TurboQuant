# TurboQuant Container Format v2 (.tqz) — مواصفة مفتوحة لأي لغة
# الهدف: أي لغة (JS/Java/C#/Go/PHP/Rust) تقدر تكتب/تقرأ نفس الملفات بدون Python.

## 1) التخطيط العام (كل الأرقام Big-Endian)
```
[0..3]   MAGIC = "TQZ2" (0x54 0x51 0x5A 0x32)
[4..7]   header_len: uint32
[8..8+N] header: JSON UTF-8, طوله header_len
[...]    body: بايتات مضغوطة حسب header.codec
```

## 2) مثال header
```json
{
  "v": 2,
  "kind": "text",
  "codec": "zstd",
  "method": "single",
  "pre": "none",
  "transform": "bwt",
  "tparams": {},
  "orig_name": "report.pdf",
  "orig_size": 419430400,
  "sha256": "9f2c...64hex...",
  "mode": "max",
  "lossless": true,
  "advanced": true
}
```
- `transform`: `none` (افتراضي للتوافق) | `delta8` | `xor8` | `delta16le` |
  `bwt` | `pngfilter` (مع `tparams.stride`) | `zdict`.
- خط الفك: فك الـ codec أولاً، ثم عكس الـ transform، ثم تحقق `sha256`.
  (`dedup+*` لا يجتمع مع transform أبداً — القارئ يجب أن يرفض ذلك كتلف.)

## 3) قيم codec
- `"zstd"` — إطار Zstandard قياسي (الأفضل). فك الضغط بمكتبة zstd في لغتك.
- `"brotli"` — دفق brotli خام (quality 11).
- `"lzma"` — دفق `.xz` / LZMA2 (مكتبة xz في لغتك).
- `"bz2"` — دفق bzip2.
- `"gzip"` — دفق gzip.
- `"dedup+zstd"` / `"dedup+lzma"` / ... — حزمة dedup (انظر §4)، ثم فك كل chunk بنفس الـ codec.
- `"store"` — تخزين خام بلا ضغط (للبيانات العشوائية — الهوية، من v2.2.0).

كلها **lossless**: فك الضغط يجب أن يعيد `orig_size` بايت بـ `sha256` مطابق. إن لم يطابق → ملف تالف.

## 4) حزمة dedup (عندما method="dedup")
الـ body نفسه له بنية داخلية:
```
[0..3]  man_len: uint32
[4..]    manifest JSON: {"codec":"zstd","manifest":[{"sha":"...","size":123}],"order":["sha1","sha2",...]}
[...]     n_blobs: uint32
repeat n_blobs:
  [..]    sha_len: uint32, sha: bytes, data_len: uint64, data: bytes (chunk مضغوط)
```
الاستعادة: `raw = concat(decompress(store[sha]) for sha in order)`.

## 4ب) حزمة الدلتا (عندما method="delta"، من v2.3.0)
نفس إطار §4، لكن الـ manifest `{"codec":...,"order":[...]}` يحتوي **chunks الجديدة
فقط**، والهيدر يضيف `base_sha256` + `base_name` + `new_sha`. الاستعادة تتطلب ملف
الأساس: تحقق من `sha256(base) == base_sha256` أولاً (رفض عند الاختلاف)، ثم
`raw = concat(decompress(new_blobs[sha]) if sha in new else base_chunk(sha))`
وأخيراً تحقق `sha256(raw) == new_sha`. حاوية `.tqze` المشفرة موصوفة في
`turboquant/crypto.py` (MAGIC TQZE + هيدر JSON + AES-GCM).

## 5) إطار القاموس (عندما transform="zdict"، من v2.2.0)
الـ body (بعد الهيدر) له بنية داخلية:
```
[0..3]  dict_len: uint32
[4..]    zdict: بايتات القاموس (zstd dictionary)
[...]    frame: إطار zstd مضغوط بهذا القاموس (write_content_size=true)
```
الفك: اقسم الجسم، ثم `zstd_decompress(frame, dict)`، ثم تحقق `sha256`.
القارئ الذي لا يعرف `transform` أو `zdict` يجب أن يرفض الملف بخطأ واضح
(لا يفكّه جزئياً أبداً).

## 6) التوافق مع v1
- ملفات `TQZ1` القديمة: نفس الفكرة لكن header أصغر (`codec/mode/orig_name/orig_size`) وبدون sha256.
- القارئ الجديد يجب أن يقبل `TQZ1` و`TQZ2` (اكشف أول 4 بايت).

## 7) خوارزمية الضغط الموصى بها لأي لغة (lossless)
1. اقرأ الملف، احسب `sha256` واحفظه.
2. اكتشف النوع: صورة → جرّب PNG-optimize وWebP-lossless واختر الأصغر مع تحقق بكسل.
   office/zip → أعد ضغط الـ zip بمستوى أعلى. pdf → أعد ضغط streams.
   نصوص/عام → قارن (ضغط مباشر بأفضل codec) مقابل (dedup chunks ~256KB + ضغط) واختر الأصغر.
3. جرّب codecs المتاحة لديك على أول 8MB واختر الأصغر، ثم اضغط الكامل به.
4. اكتب الحاوية كما في §1. عند الفك: تحقق من `sha256`.

## 8) REST (بدون تنفيذ الفورمات)
إن لم ترد تنفيذ الفورمات: شغّل `python -m turboquant serve --port 8765` ثم:
- `POST /compress?mode=max&advanced=1` بجسم الملف الخام → يرد `.tqz`
- `POST /decompress` بجسم `.tqz` → يرد الملف الأصلي
- `GET /health`, `GET /detect?path=...`
انظر `bindings/` لأمثلة جاهزة بكل لغة.
