# مثال: ضغط صورة إلى 800KB داخل برنامجك
import turboquant as tq

# 1) صورة -> 800KB كحد أقصى (WEBP تلقائياً)
info = tq.compress_image("input.jpg", "output.webp", target_bytes=800*1024, mode="balanced")
print(info)
# {'orig_h': '4.20 MB', 'new_h': '780.11 KB', 'saved_pct': 81.8, 'hit_target': True, ...}

# 2) وضع متطرف أصغر (~400KB)
info2 = tq.compress_image("input.jpg", "tiny.webp", target_bytes=400*1024, mode="extreme")
print(info2)

# 3) دفعة صور
res = tq.compress_images_batch(["a.jpg", "b.png"], out_dir="compressed/", target_bytes=800*1024)
print(res)
