"""handlers/audio.py — صوت lossless.

- WAV/AIFF خام -> FLAC إن توفر المحول (ffmpeg أو soundfile)، وإلا generic dedup.
- مضغوط أصلاً (mp3/ogg/...) -> لا إعادة ترميز (أي إعادة = فقد أو تضخم). نستخدم dedup فقط.
"""
from __future__ import annotations
import os
import shutil
import subprocess

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def wav_to_flac_lossless(src: str, dst: str | None = None) -> dict:
    from ..utils import ratio_stats, format_size, ensure_parent
    if dst is None:
        dst = os.path.splitext(src)[0] + ".flac"
    ensure_parent(dst)
    # 1) ffmpeg إن توفر (الأفضل والأسرع)
    if _have("ffmpeg"):
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-c:a", "flac",
                            "-compression_level", "12", dst], capture_output=True)
        if r.returncode == 0 and os.path.exists(dst):
            orig, new = os.path.getsize(src), os.path.getsize(dst)
            info = ratio_stats(orig, new)
            info.update({"output": dst, "method": "wav->flac(ffmpeg)", "lossless": True,
                         "orig_h": format_size(orig), "new_h": format_size(new)})
            return info
    # 2) soundfile إن توفر
    try:
        import soundfile as sf  # type: ignore
        data, sr = sf.read(src, always_2d=True)
        sf.write(dst, data, sr, format="FLAC", compression_level=8)
        orig, new = os.path.getsize(src), os.path.getsize(dst)
        info = ratio_stats(orig, new)
        info.update({"output": dst, "method": "wav->flac(soundfile)", "lossless": True,
                     "orig_h": format_size(orig), "new_h": format_size(new)})
        return info
    except Exception:
        pass
    # 3) fallback: لا تحويل — أعد التغليف generic (المتصل سيطبق dedup+codec)
    raise RuntimeError("لا يوجد محول FLAC (ثبّت ffmpeg). سيُستخدم المسار العام dedup.")
