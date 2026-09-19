# مثال: ضغط ملف كبير داخل برنامجك
import turboquant as tq

# متوازن: يستهدف ~28% من الحجم (400MB -> ~115MB للبيانات القابلة للضغط)
info = tq.compress_file("big_dataset.bin", "big_dataset.tqz", mode="balanced")
print(info)

# متطرف: أقصى ضغط lossless (400MB -> ~20MB للنصوص/البيانات المتكررة)
info2 = tq.compress_file("big_dataset.bin", "tiny.tqz", mode="extreme")
print(info2)

# هدف ثابت: حاول الوصول إلى 800KB (ينجح للصور والبيانات القابلة للضغط)
info3 = tq.compress_to_target_size("big_dataset.bin", "micro.tqz", target_bytes=800*1024)
print(info3, "hit:", info3.get("hit_target"))

# فك الضغط
out = tq.decompress_file("big_dataset.tqz", "restored.bin")
print(out)

# مجلد كامل
info4 = tq.compress_dir("./my_folder", "backup.tqz", mode="balanced")
print(info4)
