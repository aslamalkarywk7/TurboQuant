"""media.py — ضغط lossy للفيديو والصوت عبر ffmpeg (مكمل صور 800KB).

الفلسفة نفسها: بحث ثنائي على الجودة (CRF/bitrate) للوصول لحجم مستهدف،
وإلا أقوى preset يحقق أصغر حجم. يتطلب ffmpeg في PATH وإلا خطأ واضح.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess

def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None

def _need_ffmpeg():
    if not have_ffmpeg():
        raise RuntimeError("يتطلب ffmpeg في PATH (https://ffmpeg.org/download.html)")

def probe(path: str) -> dict:
    """معلومات الوسائط (ffprobe إن وجد وإلا تحليل ffmpeg -i)."""
    if shutil.which("ffprobe"):
        r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                            "-show_format", "-show_streams", path],
                           capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            return json.loads(r.stdout or "{}")
    _need_ffmpeg()
    r = subprocess.run(["ffmpeg", "-i", path], capture_output=True, text=True, timeout=60)
    return {"stderr_tail": (r.stderr or "")[-2000:]}

VIDEO_PRESETS = {
    # (scale, codec, extra)
    "original": (None, "libx264", ["-preset", "slow", "-crf", "{crf}", "-pix_fmt", "yuv420p"]),
    "720p": ("1280:720", "libx264", ["-preset", "medium", "-crf", "{crf}", "-pix_fmt", "yuv420p"]),
    "480p": ("854:480", "libx264", ["-preset", "medium", "-crf", "{crf}", "-pix_fmt", "yuv420p"]),
    "hevc": (None, "libx265", ["-preset", "medium", "-crf", "{crf}", "-pix_fmt", "yuv420p"]),
}
AUDIO_LADDER = ["128k", "96k", "64k", "48k", "32k", "24k"]

def _run(cmd: list[str], timeout: int = 3600):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg فشل: " + (r.stderr or "")[-1500:])
    return r

def compress_video(src: str, dst: str | None = None, target_bytes: int | None = None,
                   preset: str = "720p", min_crf: int = 18, max_crf: int = 38,
                   timeout: int = 3600) -> dict:
    """اضغط فيديو lossy. بهدف حجمي → بحث CRF، وإلا CRF=26 مباشرة."""
    from .utils import format_size, ratio_stats, ensure_parent
    _need_ffmpeg()
    if preset not in VIDEO_PRESETS:
        raise ValueError(f"preset غير معروف: {preset} (المتاح: {list(VIDEO_PRESETS)})")
    scale, vcodec, extra = VIDEO_PRESETS[preset]
    if dst is None:
        dst = os.path.splitext(src)[0] + ".tq.mp4"
    ensure_parent(dst)
    orig = os.path.getsize(src)

    def _try(crf: int, out: str) -> int:
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", src]
        if scale:
            cmd += ["-vf", f"scale={scale}:force_original_aspect_ratio=decrease"]
        cmd += ["-c:v", vcodec] + [a.format(crf=crf) for a in extra] + ["-c:a", "aac", "-b:a", "96k", out]
        _run(cmd, timeout)
        return os.path.getsize(out)

    tmps: list[str] = []  # ملفات مؤقتة نملكها نحن فقط (لا مسح بالـ glob أبداً)
    def _track(p: str) -> str:
        if p not in tmps:
            tmps.append(p)
        return p
    def _cleanup(keep: str | None = None):
        for p in tmps:
            if p != keep and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
    if target_bytes is None:
        _try(26, dst)
        chosen = {"crf": 26, "preset": preset}
    else:
        try:
            lo, hi, best, best_crf = min_crf, max_crf, None, max_crf
            while lo <= hi:
                mid = (lo + hi) // 2
                tmp = _track(dst + ".crf%d.tmp.mp4" % mid)
                try:
                    sz = _try(mid, tmp)
                except RuntimeError:
                    hi = mid - 1
                    continue
                if sz <= target_bytes:
                    best, best_crf, hi = tmp, mid, mid - 1  # جرّب جودة أعلى (CRF أقل)
                else:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                    lo = mid + 1
            if best is None:  # حتى أقصى ضغط فوق الهدف → خذ أصغر ما يمكن
                best = _track(dst + ".crf%d.tmp.mp4" % max_crf)
                if not os.path.exists(best):
                    _try(max_crf, best)
                best_crf = max_crf
            os.replace(best, dst)
            _cleanup(keep=best)
        except Exception:
            _cleanup()
            raise
        chosen = {"crf": best_crf, "preset": preset}
    new = os.path.getsize(dst)
    info = ratio_stats(orig, new)
    info.update({"output": dst, "kind": "video", "lossy": True, "settings": chosen,
                 "target_bytes": target_bytes, "hit_target": (new <= target_bytes) if target_bytes else None,
                 "orig_h": format_size(orig), "new_h": format_size(new)})
    return info

def compress_audio(src: str, dst: str | None = None, target_bytes: int | None = None,
                   codec: str = "libopus", timeout: int = 3600) -> dict:
    """اضغط صوت lossy (opus/mp3) بسلم bitrate للوصول للهدف."""
    from .utils import format_size, ratio_stats, ensure_parent
    _need_ffmpeg()
    ext = ".ogg" if codec == "libopus" else ".mp3"
    if dst is None:
        dst = os.path.splitext(src)[0] + ".tq" + ext
    ensure_parent(dst)
    orig = os.path.getsize(src)

    def _try(br: str, out: str) -> int:
        _run(["ffmpeg", "-y", "-v", "error", "-i", src, "-c:a", codec, "-b:a", br, out], timeout)
        return os.path.getsize(out)

    ladder = AUDIO_LADDER
    tmps: list[str] = []
    def _cleanup(keep: str | None = None):
        for p in tmps:
            if p != keep and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
    if target_bytes is None:
        _try("96k", dst)
        chosen = {"bitrate": "96k", "codec": codec}
    else:
        try:
            best, chosen = None, {"bitrate": ladder[-1], "codec": codec}
            for br in ladder:  # من الأعلى جودة للأدنى: أول ما يحقق الهدف توقف
                tmp = dst + f".{br}.tmp{ext}"
                if tmp not in tmps:
                    tmps.append(tmp)
                sz = _try(br, tmp)
                if sz <= target_bytes:
                    best = tmp
                    chosen = {"bitrate": br, "codec": codec}
                    break
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            if best is None:
                best = dst + f".{ladder[-1]}.tmp{ext}"
                if best not in tmps:
                    tmps.append(best)
                if not os.path.exists(best):
                    _try(ladder[-1], best)
            os.replace(best, dst)
            _cleanup(keep=best)
        except Exception:
            _cleanup()
            raise
    new = os.path.getsize(dst)
    info = ratio_stats(orig, new)
    info.update({"output": dst, "kind": "audio", "lossy": True, "settings": chosen,
                 "target_bytes": target_bytes, "hit_target": (new <= target_bytes) if target_bytes else None,
                 "orig_h": format_size(orig), "new_h": format_size(new)})
    return info
