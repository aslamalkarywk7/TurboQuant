"""CLI v2: python -m turboquant ... (يدعم كل الملفات lossless + صور lossy)."""
from __future__ import annotations
import argparse
import sys

def _parse_size(s: str) -> int:
    s = s.strip().upper().replace(" ", "")
    mult = 1
    for suf, m in (("TB", 1024**4), ("GB", 1024**3), ("MB", 1024**2), ("KB", 1024),
                   ("T", 1024**4), ("G", 1024**3), ("M", 1024**2), ("K", 1024), ("B", 1)):
        if s.endswith(suf):
            mult = m
            s = s[: -len(suf)]
            break
    return int(float(s) * mult)

MODES = ["fast", "balanced", "max", "ultra", "extreme", "micro_800k"]

def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="turboquant", description="TurboQuant v2 - ضغط lossless لكل الملفات بدون فقد جودة")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("lossless", help="ضغط أي ملف/مجلد LOSSLESS بدون فقد جودة (موصى به)")
    a.add_argument("src")
    a.add_argument("-o", "--out", default=None)
    a.add_argument("--mode", default="balanced", choices=["fast", "balanced", "max", "ultra"])
    a.add_argument("--no-verify", action="store_true", help="تخطي التحقق sha256")
    a.add_argument("--progress", action="store_true", help="شريط تقدم")
    a.add_argument("--advanced", action="store_true", help="نظام الخوارزميات المتقدمة (bwt/delta/filters/zdict)")
    a.add_argument("--jobs", default="1", help="خيوط الضغط المتوازية (1 أو all)")

    b = sub.add_parser("image", help="ضغط صورة lossy إلى حجم مستهدف (افتراضي 800KB) — يغيّر الجودة")
    b.add_argument("src")
    b.add_argument("-o", "--out", default=None)
    b.add_argument("--target", default="800KB")
    b.add_argument("--mode", default="balanced", choices=["fast", "balanced", "extreme", "micro_800k"])
    b.add_argument("--format", default="auto", choices=["auto", "WEBP", "JPEG", "PNG", "AVIF"])

    c = sub.add_parser("file", help="(v1) ضغط ملف عام إلى .tqz")
    c.add_argument("src")
    c.add_argument("-o", "--out", default=None)
    c.add_argument("--mode", default="balanced", choices=["fast", "balanced", "extreme", "micro_800k"])
    c.add_argument("--codec", default="auto", choices=["auto", "zstd", "lzma", "bz2", "gzip", "brotli"])

    d = sub.add_parser("to-size", help="اضغط صورة لحجم مستهدف")
    d.add_argument("src")
    d.add_argument("-o", "--out", default=None)
    d.add_argument("--target", default="800KB")

    e = sub.add_parser("decompress", help="فك ضغط .tqz (v1+v2 تلقائياً)")
    e.add_argument("src")
    e.add_argument("-o", "--out", default=None)
    e.add_argument("--progress", action="store_true", help="شريط تقدم")
    e.add_argument("--max-gb", type=float, default=None, help="سقف الإخراج بالجيجا (حماية المتفجرات)")

    f = sub.add_parser("auto", help="اكتشاف تلقائي لكل الأنواع")
    f.add_argument("src")
    f.add_argument("-o", "--out", default=None)
    f.add_argument("--mode", default="balanced", choices=MODES)
    f.add_argument("--target", default=None)
    f.add_argument("--lossy", action="store_true", help="اسمح بـ lossy للصور")
    f.add_argument("--advanced", action="store_true", help="نظام الخوارزميات المتقدمة")

    g = sub.add_parser("detect", help="اكتشاف نوع الملف وخط الأنابيب المقترح")
    g.add_argument("src")

    h = sub.add_parser("serve", help="خادم HTTP صغير لتستخدمه أي لغة (REST)")
    h.add_argument("--port", type=int, default=8765)

    i = sub.add_parser("bench", help="قياس حقيقي: قارن الأوضاع على ملفك")
    i.add_argument("src")
    i.add_argument("--modes", default="fast,balanced,max,ultra")
    i.add_argument("--advanced", action="store_true", help="قياس المسار المتقدم أيضاً")
    i.add_argument("--jobs", default="1", help="خيوط الضغط المتوازية (1 أو all)")

    an = sub.add_parser("analyze", help="تحليل ملف: إنتروبيا + التحويل المقترح (بدون ضغط)")
    an.add_argument("src")

    j = sub.add_parser("cert", help="شهادة ثقة: تحقق + تقرير لملف .tqz")
    j.add_argument("src")

    e1 = sub.add_parser("encrypt", help="تشفير AES-256-GCM بكلمة سر → .tqze")
    e1.add_argument("src")
    e1.add_argument("-o", "--out", default=None)
    e1.add_argument("--password", default=None, help="أو TURBOQUANT_PASSWORD أو إدخال تفاعلي")

    d1 = sub.add_parser("decrypt", help="فك تشفير .tqze")
    d1.add_argument("src")
    d1.add_argument("-o", "--out", default=None)
    d1.add_argument("--password", default=None)

    dl = sub.add_parser("delta", help="دلتا تزايدية: فروق NEW عن BASE فقط")
    dl.add_argument("base")
    dl.add_argument("new")
    dl.add_argument("-o", "--out", default=None)
    dl.add_argument("--mode", default="balanced", choices=["fast", "balanced", "max", "ultra"])
    dl.add_argument("--jobs", default="1")

    ap = sub.add_parser("apply-delta", help="تركيب الدلتا على الأساس → النسخة الجديدة")
    ap.add_argument("base")
    ap.add_argument("delta")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--max-gb", type=float, default=None, help="سقف الإخراج بالجيجا")

    vv = sub.add_parser("video", help="ضغط فيديو lossy عبر ffmpeg (يتطلب ffmpeg)")
    vv.add_argument("src")
    vv.add_argument("-o", "--out", default=None)
    vv.add_argument("--target", default=None, help="مثال: 20MB")
    vv.add_argument("--preset", default="720p", choices=["original", "720p", "480p", "hevc"])

    au = sub.add_parser("audio", help="ضغط صوت lossy عبر ffmpeg (يتطلب ffmpeg)")
    au.add_argument("src")
    au.add_argument("-o", "--out", default=None)
    au.add_argument("--target", default=None, help="مثال: 5MB")
    au.add_argument("--codec", default="libopus", choices=["libopus", "libmp3lame"])

    args = p.parse_args(argv)
    import turboquant as tq

    def _jobs(v: str):
        return None if str(v).lower() == "all" else int(v)

    def _password(v: str | None) -> str:
        import os, getpass
        return v or os.environ.get("TURBOQUANT_PASSWORD") or getpass.getpass("كلمة السر: ")

    def _cap_gb(v: float | None) -> int | None:
        return None if v is None else int(v * 1024 ** 3)

    if args.cmd == "lossless":
        bar = tq.make_text_bar() if args.progress else None
        info = tq.compress_lossless(args.src, args.out, mode=args.mode, verify=not args.no_verify,
                                    on_progress=bar, advanced=args.advanced, jobs=_jobs(args.jobs))
    elif args.cmd == "image":
        info = tq.compress_image(args.src, args.out, target_bytes=_parse_size(args.target), mode=args.mode, fmt=args.format)
    elif args.cmd == "file":
        info = tq.compress_file(args.src, args.out, mode=args.mode, codec=args.codec)
    elif args.cmd == "to-size":
        info = tq.compress_to_target_size(args.src, args.out, target_bytes=_parse_size(args.target))
    elif args.cmd == "decompress":
        bar = tq.make_text_bar() if args.progress else None
        info = tq.decompress_auto(args.src, args.out, on_progress=bar,
                                  max_output_bytes=_cap_gb(args.max_gb))
    elif args.cmd == "auto":
        tb = _parse_size(args.target) if args.target else None
        info = tq.compress_auto(args.src, args.out, mode=args.mode, target_bytes=tb,
                                lossless=False if args.lossy else None, advanced=args.advanced)
    elif args.cmd == "detect":
        from turboquant import detect_kind, suggest_pipeline
        info = {"kind": detect_kind(args.src), "pipeline": suggest_pipeline(detect_kind(args.src))}
    elif args.cmd == "serve":
        from .server import serve
        serve(args.port)
        return 0
    elif args.cmd == "bench":
        rows = tq.benchmark(args.src, modes=tuple(m.strip() for m in args.modes.split(",") if m.strip()),
                            advanced=args.advanced, jobs=_jobs(args.jobs))
        tq.print_benchmark(rows)
        return 0
    elif args.cmd == "encrypt":
        print(tq.encrypt_file(args.src, args.out, _password(args.password)))
        return 0
    elif args.cmd == "decrypt":
        print(tq.decrypt_file(args.src, args.out, _password(args.password)))
        return 0
    elif args.cmd == "delta":
        print(tq.create_delta(args.base, args.new, args.out, mode=args.mode, jobs=_jobs(args.jobs)))
        return 0
    elif args.cmd == "apply-delta":
        print(tq.apply_delta(args.base, args.delta, args.out,
                             max_output_bytes=_cap_gb(args.max_gb)))
        return 0
    elif args.cmd == "video":
        print(tq.compress_video(args.src, args.out,
                                target_bytes=_parse_size(args.target) if args.target else None,
                                preset=args.preset))
        return 0
    elif args.cmd == "audio":
        print(tq.compress_audio(args.src, args.out,
                                target_bytes=_parse_size(args.target) if args.target else None,
                                codec=args.codec))
        return 0
    elif args.cmd == "analyze":
        import json
        print(json.dumps(tq.analyze_file(args.src), ensure_ascii=False, indent=2))
        return 0
    elif args.cmd == "cert":
        from .cert import verify_package, format_certificate
        print(format_certificate(verify_package(args.src)))
        return 0
    print(info)
    if isinstance(info, dict) and info.get("hit_target") is False:
        print("تنبيه: لم يتحقق الحجم المستهدف lossless (البيانات غير قابلة للضغط أكثر).", file=sys.stderr)
    if isinstance(info, dict) and info.get("verified") is False:
        print("خطأ: فشل التحقق من السلامة!", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
