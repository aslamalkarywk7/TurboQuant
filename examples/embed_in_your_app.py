# كيف تدمج TurboQuant داخل برنامج ضغط صور/ملفات خاص بك
"""
انسخ هذا النمط في برنامجك:
"""
import os
import turboquant as tq

def my_compress_button(input_path: str) -> dict:
    """دالة زر 'اضغط' في واجهتك."""
    size = os.path.getsize(input_path)
    ext = os.path.splitext(input_path)[1].lower()

    # صور: دائماً إلى <= 800KB
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"):
        # تحكم المستخدم: quality slider -> mode
        # slider 0-33 extreme, 34-70 balanced, 71-100 fast
        return tq.compress_image(input_path, None, target_bytes=800*1024, mode="balanced")

    # ملفات كبيرة: خياران للمستخدم
    # "متوازن (400 -> 115)" و "أقصى (400 -> 20)"
    if size > 50 * 1024 * 1024:
        return tq.compress_file(input_path, None, mode="balanced")

    # تلقائي لأي شيء
    return tq.compress_auto(input_path, None, mode="balanced")


if __name__ == "__main__":
    print("استدعِ my_compress_button(path) من واجهتك الرسومية (Tkinter/PyQt) أو API.")
