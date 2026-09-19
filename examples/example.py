# مثال Python — انسخه داخل برنامجك (5 دقائق دمج)
import turboquant as tq

# ضغط + تقدم + شهادة
tok = tq.CancelToken()
info = tq.compress_lossless(
    "report.pdf", "report.tqz", mode="max",
    on_progress=lambda d, t, ph: print(f"{ph} {d / t:.0%}"),
)
print(info["orig_h"], "->", info["new_h"], info["codec"], info["verified"])

from turboquant import verify_package, format_certificate
print(format_certificate(verify_package("report.tqz")))

# فك الضغط
print(tq.decompress_auto("report.tqz", "report.pdf"))

# قياس على ملفك قبل الاعتماد
tq.print_benchmark(tq.benchmark("report.pdf", modes=["fast", "balanced", "max"]))
