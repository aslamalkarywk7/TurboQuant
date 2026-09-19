"""lossless.py — خط الأنابيب الموحد LOSSLESS لكل أنواع الملفات.

الضمان: فك الضغط يعيد البايتات مطابقة 100% (sha256). لا يوجد أي فقد جودة — مناسب للمستندات
والصور الطبية والقانونية والتنفيذيات والنسخ الاحتياطي.

الاستراتيجية لكل نوع (detect.py):
  image      -> image_lossless (PNG/WebP-lossless + تحقق بكسل)
  office/zip -> unzip-recompress-max
  pdf        -> recompress-streams (pikepdf إن توفر)
  wav        -> FLAC إن توفر ثم dedup
  audio/video/archive مضغوط -> dedup + best-codec (بدون إعادة ترميز)
  text/csv/json/generic -> dedup + best-codec (الأقوى)

ثم: قارن (single-stream) مقابل (dedup-package) واختر الأصغر. غلّف الكل في .tqz v2.
"""
from __future__ import annotations
import hashlib
import json
import os
import struct
import tempfile

from .detect import detect_kind
from .codecs import available_codecs, compress_bytes, decompress_bytes, compress_stream, decompress_stream
from .utils import format_size, ratio_stats, ensure_parent

MAGIC = b"TQZ2"  # حاوية v2 الموحدة (تدعم single + dedup + كل codecs بما فيها brotli)
HLEN = ">I"

def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def _write_pkg(dst: str, meta: dict, body: bytes):
    ensure_parent(dst)
    head = json.dumps(meta).encode()
    tmp = dst + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(MAGIC)
            f.write(struct.pack(HLEN, len(head)))
            f.write(head)
            f.write(body)
        os.replace(tmp, dst)
    except BaseException:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise

def _read_pkg(src: str) -> tuple[dict, bytes, int]:
    from .errors import CorruptPackageError
    with open(src, "rb") as f:
        magic = f.read(4)
        if magic == b"TQZ1":
            raise CorruptPackageError("ملف TQZ1 قديم — استخدم decompress_file من turboquant.file")
        if magic != MAGIC:
            raise CorruptPackageError("ليس ملف TurboQuant v2 (.tqz)")
        try:
            (hl,) = struct.unpack(HLEN, f.read(4))
            meta = json.loads(f.read(hl).decode())
        except (struct.error, ValueError, UnicodeDecodeError) as e:
            raise CorruptPackageError(f"هيدر الحاوية تالف: {e}")
        off = 4 + 4 + hl
        body = f.read()
    return meta, body, off

def _single_compress(src: str, codec: str, mode: str, on_progress=None, cancel=None, total: int = 0) -> bytes:
    with open(src, "rb") as fin:
        import io
        buf = io.BytesIO()
        done = {"n": 0}
        def _cb(n: int):
            done["n"] += n
            if on_progress is not None:
                on_progress(done["n"], total or os.path.getsize(src), "compress")
        compress_stream(fin, buf, codec, mode, on_chunk=_cb if on_progress else None, cancel=cancel)
        return buf.getvalue()

def _try_all_single(src: str, mode: str, sample_limit: int = 8 << 20, jobs: int = 1) -> tuple[str, bytes]:
    """اختر أفضل codec على عينة (أول 8MB) ثم اضغط الكامل به — توفير وقت للملفات الضخمة."""
    with open(src, "rb") as f:
        sample = f.read(sample_limit)
    from .codecs import best_of
    best_codec, _ = best_of(sample, mode, jobs)
    return best_codec, _single_compress(src, best_codec, mode)

def compress_lossless(src: str, dst: str | None = None, mode: str = "balanced",
                      allow_dedup: bool = True, verify: bool = True,
                      on_progress=None, cancel=None, advanced: bool = False,
                      jobs: int = 1) -> dict:
    """اضغط أي ملف LOSSLESS — بدون أي تأثير على الجودة.

    mode: fast | balanced | max | ultra (قوة الضغط، ليس الجودة — الجودة ثابتة 100%)
    on_progress(done, total, phase): callback لشريط التقدم داخل برنامجك (اختياري).
    cancel: CancelToken لإلغاء العملية من زر داخل برنامجك (اختياري).
    advanced: True → نظام الخوارزميات المتقدمة (entropy + bwt/delta/filters/zdict
        باختيار تلقائي). ملفات ≤64MB فقط، والأكبر يرجع للمسار العادي المتدفق.
    jobs: عدد خيوط الضغط المتوازية (1 = تسلسلي، None = كل الأنوية).
    """
    if os.path.isdir(src):
        return compress_dir_lossless(src, dst, mode=mode)
    kind = detect_kind(src)
    orig = os.path.getsize(src)
    orig_sha = sha256_file(src)
    if dst is None:
        dst = src + ".tqz"

    # ضمان bit-identical: نضغط بايتات الأصل مباشرة (single vs dedup) بدون أي تحويل
    # يغيّر الحاوية. تحويلات (PNG->WebP / WAV->FLAC / zip-recompress) متاحة كدوال
    # منفصلة quality-lossless في handlers/ لمن يريدها صراحة.
    prepped = src
    pre_method = "none"

    # --- قارن single vs dedup ---
    level = {"fast": "fast", "balanced": "balanced", "max": "max",
             "ultra": "ultra", "extreme": "ultra", "micro_800k": "ultra"}.get(mode, "balanced")

    best_codec, single_body = _try_all_single(prepped, level, jobs=jobs)
    candidates = {"single": (best_codec, single_body)}

    if cancel is not None:
        cancel.check("compress")
    # إعادة الضغط مع تقدم حقيقي (الجولة النهائية بالـ codec الفائز)
    if on_progress is not None or cancel is not None:
        single_body = _single_compress(prepped, best_codec, level, on_progress, cancel, orig)
        candidates = {"single": (best_codec, single_body)}

    if allow_dedup and os.path.getsize(prepped) >= 256 * 1024:
        try:
            # بناء متدفق: blobs على SQLite مؤقت بدل RAM (يدعم الملفات الكبيرة)
            from .dedup import chunk_file_stream, build_dedup_package_stream
            res = build_dedup_package_stream(chunk_file_stream(prepped), best_codec, level, jobs)
            if res is not None:
                dbody, dinfo = res
                # وسم خاص: codec = "dedup+<codec>"
                candidates["dedup"] = (f"dedup+{best_codec}", dbody)
        except Exception as e:
            from .log import warn_or_raise
            warn_or_raise("dedup-path", e)

    # --- المسار المتقدم: تحويل ذكي قبل الترميز (ملفات ≤64MB) ---
    adv_transform, adv_tparams = "none", {}
    from .advanced.pipeline import ADV_CAP as _ADV_CAP
    if advanced and 4096 <= orig <= _ADV_CAP:
        try:
            from .advanced.pipeline import smart_select, apply_transform, SELECT_CAP
            with open(prepped, "rb") as f:
                full = f.read()
            if cancel is not None:
                cancel.check("advanced")
            sel = smart_select(full[:SELECT_CAP], kind, level)
            tid = sel["transform"]
            if tid == "none" and sel["codec"] == "store":
                adv_body, adv_codec = full, "store"  # خام: أصدق وأسرع للعشوائي
            elif tid == "zdict":
                from .advanced.zdict import self_train, pack_body, dict_compress
                from .codecs import _zstd_level
                zd = self_train(full)
                if zd is None:
                    raise ValueError("تعذّر تدريب القاموس")
                adv_body = pack_body(zd, dict_compress(full, zd, _zstd_level(level)))
                adv_codec = "zstd"
                adv_tparams = {"dict_size": len(zd)}
            else:
                from .codecs import best_of, compress_bytes
                t_full = apply_transform(full, tid, sel.get("tparams", {}))
                if cancel is not None:
                    cancel.check("advanced")
                t_sample = t_full[:SELECT_CAP] if len(t_full) > SELECT_CAP else t_full
                adv_codec, _ = best_of(t_sample, level, jobs)
                adv_body = compress_bytes(t_full, adv_codec, level)
                adv_tparams = sel.get("tparams", {})
            adv_transform = tid
            candidates["single+adv"] = (adv_codec, adv_body)
            if on_progress is not None:
                on_progress(orig, orig, "advanced")
        except Exception as e:
            from .log import warn_or_raise
            warn_or_raise("advanced-path", e)
            adv_transform, adv_tparams = "none", {}

    # اختر الأصغر
    method = min(candidates, key=lambda k: len(candidates[k][1]))
    codec, body = candidates[method]
    if method != "single+adv":
        adv_transform, adv_tparams = "none", {}

    meta = {"v": 2, "kind": kind, "codec": codec, "method": method,
            "pre": pre_method, "transform": adv_transform, "tparams": adv_tparams,
            "orig_name": os.path.basename(src),
            "orig_size": orig, "sha256": orig_sha, "mode": mode, "lossless": True,
            "advanced": bool(method == "single+adv")}
    _write_pkg(dst, meta, body)

    new = os.path.getsize(dst)
    if verify:
        # تحقق فوري: فك في ملف مؤقت حقيقي وقارن sha256 (بدون mktemp المهجورة)
        with tempfile.NamedTemporaryFile(suffix="_tqverify", delete=False) as tf:
            chk = tf.name
        try:
            decompress_lossless(dst, chk, max_output_bytes=orig + 1)
            got = sha256_file(chk)
            if got != orig_sha:
                from .errors import VerificationError
                raise VerificationError(f"فشل التحقق lossless! {got} != {orig_sha}")
        finally:
            try:
                os.remove(chk)
            except OSError:
                pass
    info = ratio_stats(orig, new)
    info.update({"output": dst, "kind": kind, "codec": codec, "pipeline": method,
                 "pre": pre_method, "transform": adv_transform, "tparams": adv_tparams,
                 "lossless": True, "verified": verify,
                 "sha256": orig_sha[:16] + "…",
                 "orig_h": format_size(orig), "new_h": format_size(new)})
    return info

def decompress_lossless(src: str, dst: str | None = None, on_progress=None, cancel=None,
                        max_output_bytes: int | None = None) -> dict:
    """فك ضغط .tqz v2 مع تحقق sha256 — يعيد البايتات مطابقة 100%.

    max_output_bytes: سقف الإخراج (حماية قنابل فك الضغط). None → تلقائي
        (100_000× حجم الحاوية، بحد أدنى 1GB). يُحسب sha أثناء الكتابة
        (لا قراءة ثانية للملف).
    """
    import hashlib as _hl
    from .errors import UnsupportedCodecError, VerificationError, CorruptPackageError, OutputLimitError
    from .progress import CancelledError
    from .limits import CappedWriter, resolve_cap
    meta, body, _ = _read_pkg(src)
    if dst is None:
        d = os.path.dirname(os.path.abspath(src))
        # basename فقط — حماية من path traversal في حاويات خبيثة
        safe_name = os.path.basename(meta.get("orig_name") or (os.path.basename(src) + ".out"))
        dst = os.path.join(d, safe_name or (os.path.basename(src) + ".out"))
        if os.path.abspath(dst) == os.path.abspath(src):
            dst += ".out"
    ensure_parent(dst)
    codec = meta.get("codec", "lzma")
    transform = meta.get("transform", "none") or "none"
    tparams = meta.get("tparams", {}) or {}
    if transform not in ("none", "delta8", "xor8", "delta16le", "bwt", "pngfilter", "zdict"):
        raise UnsupportedCodecError(f"تحويل غير معروف في الحاوية: {transform}")
    cap = resolve_cap(max_output_bytes, len(body))
    total = meta.get("orig_size", 0) or len(body)
    hasher = _hl.sha256()
    if cancel is not None:
        cancel.check("decompress")
    with open(dst, "wb") as raw_out:
        out = CappedWriter(raw_out, cap, hasher)
        try:
            if codec.startswith("dedup+"):
                if transform != "none":
                    raise UnsupportedCodecError("حاوية تالفة: تحويل مع dedup غير مدعوم")
                from .dedup import restore_dedup_package_to
                done = {"n": 0}
                def _cb(n: int):
                    done["n"] += n
                    if on_progress is not None:
                        on_progress(min(done["n"], total), total, "decompress")
                    if cancel is not None:
                        cancel.check("decompress")
                restore_dedup_package_to(body, out, on_chunk=_cb if (on_progress or cancel) else None)
                if on_progress is not None:
                    on_progress(total, total, "decompress")
            elif transform == "zdict":
                from .advanced.zdict import unpack_body, dict_decompress
                zd, frame = unpack_body(body)
                raw = dict_decompress(frame, zd)
                out.write(raw)
                if on_progress is not None:
                    on_progress(total, total, "decompress")
            elif transform != "none":
                import io
                buf = io.BytesIO()
                decompress_stream(io.BytesIO(body), buf, codec)
                from .advanced.pipeline import invert_transform
                out.write(invert_transform(buf.getvalue(), transform, tparams))
                if on_progress is not None:
                    on_progress(total, total, "decompress")
            else:
                import io
                done = {"n": 0}
                def _cb2(n: int):
                    done["n"] += n
                    if on_progress is not None:
                        on_progress(min(done["n"], total), total, "decompress")
                decompress_stream(io.BytesIO(body), out, codec,
                                  on_chunk=_cb2 if on_progress else None, cancel=cancel)
                if on_progress is not None:
                    on_progress(total, total, "decompress")
        except (CorruptPackageError, UnsupportedCodecError, VerificationError,
                OutputLimitError, CancelledError):
            raise
        except Exception as e:
            raise CorruptPackageError(
                f"فك الترميز فشل — حاوية تالفة على الأرجح ({type(e).__name__})")
    # تحقق من البصمة المحسوبة أثناء الكتابة (لا قراءة ثانية)
    exp = meta.get("sha256")
    got = hasher.hexdigest()
    ok = (exp == got) if exp else None
    if exp and not ok:
        raise VerificationError(f"ملف تالف: sha256 {got} != {exp}")
    return {"output": dst, "kind": meta.get("kind"), "codec": codec,
            "verified": ok, "size": os.path.getsize(dst), "size_h": format_size(os.path.getsize(dst))}

def optimize_lossless(src: str, dst: str | None = None) -> dict:
    """تحويل quality-lossless اختياري (قد يغيّر الحاوية، الجودة 100%).

    - صورة -> PNG-optimize / WebP-lossless (بكسل مطابق، تحقق بكسل ببكسل)
    - office/zip -> إعادة ضغط max (نفس المحتوى الداخلي)
    - pdf -> إعادة ضغط streams (pikepdf)
    - wav -> FLAC (نفس العينات)
    ملاحظة: الناتج ليس bit-identical للملف الأصلي (حاوية مختلفة) لكن الجودة
    مطابقة تماماً. استخدم compress_lossless عندما تريد بايت مطابق.
    """
    import os
    kind = detect_kind(src)
    if kind == "image":
        from .handlers.image_lossless import compress_image_lossless
        return compress_image_lossless(src, dst)
    if kind in ("office", "archive"):
        from .handlers.document import recompress_zip_lossless
        return recompress_zip_lossless(src, dst or (src + ".opt.zip"))
    if kind == "pdf":
        from .handlers.document import recompress_pdf_lossless
        return recompress_pdf_lossless(src, dst or (src + ".opt.pdf"))
    if kind == "audio_wav":
        from .handlers.audio import wav_to_flac_lossless
        return wav_to_flac_lossless(src, dst)
    # generic: لا تحويل آمن للحاوية -> أعد التغليف bit-identical
    return compress_lossless(src, dst)

def compress_dir_lossless(src_dir: str, dst: str | None = None, mode: str = "balanced",
                        on_progress=None, cancel=None) -> dict:
    import tarfile
    if dst is None:
        dst = src_dir.rstrip("/\\") + ".tqz"
    tmp_tar = dst + ".tar.tmp"
    with tarfile.open(tmp_tar, "w", format=tarfile.PAX_FORMAT) as tar:
        tar.add(src_dir, arcname=os.path.basename(src_dir.rstrip("/\\")))
    try:
        info = compress_lossless(tmp_tar, dst, mode=mode, on_progress=on_progress, cancel=cancel)
        info["src_dir"] = src_dir
        return info
    finally:
        try:
            os.remove(tmp_tar)
        except OSError:
            pass
