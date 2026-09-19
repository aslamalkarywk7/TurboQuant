"""server.py — خادم HTTP مصغّر (stdlib فقط) + واجهة ويب حرة + API متوافق مع Vercel.

التشغيل المحلي (كامل القوة — بلا حد 4.5MB الخاص بـ Vercel):
    python -m turboquant serve --port 8765
    → افتح http://localhost:8765/  (لوحة التحكم في public/index.html)

على Vercel: نفس المسارات تعمل كـ serverless عبر api/*.py:
    POST /api/compress?mode=max&advanced=0&filename=x.pdf  → .tqz binary (أو ?format=json)
    POST /api/decompress                                   → الملف الأصلي
    POST /api/image?target_bytes=819200&mode=balanced&fmt=auto
    POST /api/analyze  → JSON {kind, entropy, suggestion}
    POST /api/cert     → JSON certificate
    POST /api/bench    → JSON rows
    GET  /api/health   → {ok, codecs, version}

Legacy (للتوافق): POST /compress , POST /decompress , GET /health , GET /detect
"""
from __future__ import annotations
import base64
import mimetypes
import tempfile
import time
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(ROOT, "public")


def _cors(h: BaseHTTPRequestHandler):
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type, X-Filename")
    h.send_header("Access-Control-Expose-Headers", "*")


def _json(h: BaseHTTPRequestHandler, obj: dict, status: int = 200):
    import json as _j
    data = _j.dumps(obj, ensure_ascii=False).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(data)))
    _cors(h)
    h.end_headers()
    h.wfile.write(data)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        _cors(self)
        self.end_headers()

    def _send_file(self, path: str, name: str = "file.tqz",
                   ctype: str = "application/octet-stream", extra: dict | None = None):
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        for k, v in (extra or {}).items():
            self.send_header(k, str(v))
        _cors(self)
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, rel: str) -> bool:
        # حماية traversal: فقط داخل PUBLIC_DIR
        safe = os.path.normpath(rel).lstrip("/\\")
        full = os.path.abspath(os.path.join(PUBLIC_DIR, safe))
        if not full.startswith(os.path.abspath(PUBLIC_DIR)):
            return False
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.exists(full):
            return False
        ctype, _ = mimetypes.guess_type(full)
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            return False
        self.send_response(200)
        self.send_header("Content-Type", (ctype or "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        _cors(self)
        self.end_headers()
        self.wfile.write(data)
        return True

    def do_POST(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        path = u.path.rstrip("/") or "/"
        # توحيد: /compress ≡ /api/compress (نفس الشيء للتوافق)
        route = path
        if route in ("/compress", "/api/compress.py", "/api/compress"):
            return self._api_compress(qs)
        if route in ("/decompress", "/api/decompress.py", "/api/decompress"):
            return self._api_decompress(qs)
        if route in ("/api/image", "/api/image.py"):
            return self._api_image(qs)
        if route in ("/api/analyze", "/api/analyze.py"):
            return self._api_analyze(qs)
        if route in ("/api/cert", "/api/cert.py"):
            return self._api_cert(qs)
        if route in ("/api/bench", "/api/bench.py"):
            return self._api_bench(qs)
        self.send_response(404)
        _cors(self)
        self.end_headers()

    # ---------- helpers ----------
    def _read_limited(self):
        try:
            max_mb = int(os.environ.get("TQ_MAX_MB", "4096"))
        except ValueError:
            max_mb = 4096
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0

        def _reject(drain: int = 0):
            try:
                left = drain
                while left > 0:
                    blk = self.rfile.read(min(1 << 20, left))
                    if not blk:
                        break
                    left -= len(blk)
            except Exception:
                pass
            try:
                self.send_response(413)
                self.send_header("Content-Length", "2")
                _cors(self)
                self.end_headers()
                self.wfile.write(b"[]")
            except (BrokenPipeError, ConnectionResetError):
                pass
            return None

        if length > max_mb * 1024 * 1024:
            return _reject(drain=length)
        body = bytearray()
        remaining = length
        while remaining > 0:
            blk = self.rfile.read(min(1 << 20, remaining))
            if not blk:
                break
            body += blk
            remaining -= len(blk)
            if len(body) > max_mb * 1024 * 1024:
                _reject(drain=remaining)
                return None
        return bytes(body)

    def _api_compress(self, qs):
        mode = (qs.get("mode", ["balanced"])[0] or "balanced").lower()
        advanced = qs.get("advanced", ["0"])[0] == "1"
        filename = qs.get("filename", [self.headers.get("X-Filename", "file.bin")])[0]
        as_json = qs.get("format", ["bin"])[0] == "json"
        if mode not in ("fast", "balanced", "max", "ultra", "extreme"):
            mode = "balanced"
        body = self._read_limited()
        if body is None:
            return  # 413 already sent
        if not body:
            return _json(self, {"ok": False, "error": "ملف فارغ"}, 400)
        import turboquant as tq
        from turboquant.log import logger
        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "in.bin")
            out = os.path.join(td, "out.tqz")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                info = tq.compress_lossless(inp, out, mode=mode, advanced=advanced)
            except Exception as e:
                logger.warning("compress failed: %r", e, exc_info=True)
                return _json(self, {"ok": False, "error": str(e)[:500]}, 500)
            with open(out, "rb") as f:
                blob = f.read()
        elapsed = round(time.perf_counter() - t0, 3)
        safe = (os.path.basename(filename) or "file.bin") + ".tqz"
        if as_json:
            return _json(self, {"ok": True, "filename": safe, "orig": info.get("orig"),
                                "new": info.get("new"), "ratio": info.get("ratio"),
                                "saved_pct": info.get("saved_pct"), "codec": info.get("codec"),
                                "pipeline": info.get("pipeline"), "kind": info.get("kind"),
                                "verified": info.get("verified"), "elapsed_s": elapsed,
                                "output_b64": base64.b64encode(blob).decode()})
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
        self.send_header("X-TQ-Orig", str(info.get("orig", 0)))
        self.send_header("X-TQ-New", str(info.get("new", 0)))
        self.send_header("X-TQ-Codec", str(info.get("codec", "")))
        self.send_header("X-TQ-Verified", "1" if info.get("verified") else "0")
        _cors(self)
        self.end_headers()
        self.wfile.write(blob)

    def _api_decompress(self, qs):
        body = self._read_limited()
        if body is None:
            return
        if not body:
            return _json(self, {"ok": False, "error": "ملف فارغ"}, 400)
        import turboquant as tq
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "in.tqz")
            out = os.path.join(td, "out.bin")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                info = tq.decompress_auto(inp, out)
            except Exception as e:
                return _json(self, {"ok": False, "error": str(e)[:500]}, 400)
            with open(info.get("output", out), "rb") as f:
                blob = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Content-Disposition", 'attachment; filename="restored.bin"')
        self.send_header("X-TQ-Verified", "1" if info.get("verified") else "0")
        _cors(self)
        self.end_headers()
        self.wfile.write(blob)

    def _api_image(self, qs):
        try:
            target = int(qs.get("target_bytes", ["819200"])[0])
        except ValueError:
            target = 819200
        mode = qs.get("mode", ["balanced"])[0] or "balanced"
        fmt = qs.get("fmt", ["auto"])[0] or "auto"
        body = self._read_limited()
        if body is None:
            return
        if not body:
            return _json(self, {"ok": False, "error": "صورة فارغة"}, 400)
        import turboquant as tq
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "in.img")
            out = os.path.join(td, "out.webp")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                info = tq.compress_image(inp, out, target_bytes=target, mode=mode, fmt=fmt)
            except Exception as e:
                return _json(self, {"ok": False, "error": str(e)[:500]}, 400)
            with open(info.get("output", out), "rb") as f:
                blob = f.read()
        ctype = "image/webp" if info.get("format", "WEBP") == "WEBP" else "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Content-Disposition", 'attachment; filename="image.tq.webp"')
        self.send_header("X-TQ-Orig", str(info.get("orig", 0)))
        self.send_header("X-TQ-New", str(info.get("new", 0)))
        _cors(self)
        self.end_headers()
        self.wfile.write(blob)

    def _api_analyze(self, qs):
        body = self._read_limited()
        if body is None:
            return
        if not body:
            return _json(self, {"ok": False, "error": "ملف فارغ"}, 400)
        import turboquant as tq
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "in.bin")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                rep = tq.analyze_file(inp)
            except Exception as e:
                return _json(self, {"ok": False, "error": str(e)[:500]}, 500)
        return _json(self, {"ok": True, "kind": rep.get("kind"), "kind_ar": rep.get("kind_ar"),
                            "size": rep.get("size"), "entropy": rep.get("entropy"),
                            "verdict": rep.get("verdict"), "why": rep.get("why"),
                            "suggestion": rep.get("suggestion")})

    def _api_cert(self, qs):
        body = self._read_limited()
        if body is None:
            return
        if not body:
            return _json(self, {"ok": False, "error": "ملف فارغ"}, 400)
        import turboquant as tq
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "in.tqz")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                cert = tq.verify_package(inp)
            except Exception as e:
                return _json(self, {"ok": False, "error": str(e)[:500]}, 500)
        return _json(self, {"ok": True, "verdict": cert.get("verdict"), "checks": cert.get("checks"),
                            "meta": cert.get("meta"), "quality": cert.get("quality"),
                            "certificate": tq.format_certificate(cert)})

    def _api_bench(self, qs):
        modes = tuple(m.strip() for m in qs.get("modes", ["fast,balanced,max,ultra"])[0].split(",") if m.strip()) or ("fast", "balanced", "max", "ultra")
        modes = tuple(m for m in modes if m in ("fast", "balanced", "max", "ultra")) or ("fast", "balanced", "max", "ultra")
        advanced = qs.get("advanced", ["0"])[0] == "1"
        body = self._read_limited()
        if body is None:
            return
        if not body:
            return _json(self, {"ok": False, "error": "ملف فارغ"}, 400)
        import turboquant as tq
        with tempfile.TemporaryDirectory() as td:
            inp = os.path.join(td, "in.bin")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                rows = tq.benchmark(inp, modes=modes, advanced=advanced)
            except Exception as e:
                return _json(self, {"ok": False, "error": str(e)[:500]}, 500)
        return _json(self, {"ok": True, "rows": rows, "table": tq.format_table(rows)})

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path.rstrip("/") or "/"
        if path in ("/", "/index.html", "/app"):
            if self._serve_static("index.html"):
                return
            # fallback: public missing → رسالة إرشادية
            return _json(self, {"ok": True, "service": "turboquant",
                                "hint": "ضع الواجهة في public/index.html أو استخدم /api/*"}, 200)
        if path in ("/health", "/api/health", "/api/health.py"):
            try:
                import turboquant as tq
                return _json(self, {"ok": True, "service": "turboquant",
                                    "version": getattr(tq, "__version__", "2.4.0"),
                                    "codecs": tq.available_codecs()})
            except Exception as e:
                return _json(self, {"ok": False, "error": str(e)[:300]}, 500)
        if path in ("/detect", "/api/detect"):
            import json
            from turboquant import detect_kind, suggest_pipeline
            qs = parse_qs(u.query)
            pth = qs.get("path", [""])[0]
            try:
                k = detect_kind(pth)
                payload = {"kind": k, "pipeline": suggest_pipeline(k)}
            except Exception as e:
                payload = {"error": str(e)}
            return _json(self, payload)
        # ملفات ستاتيك (css/js/img داخل public/)
        if self._serve_static(path.lstrip("/")):
            return
        self.send_response(404)
        _cors(self)
        self.end_headers()


def serve(port: int = 8765):
    web_hint = " + Web UI http://localhost:%d/" % port if os.path.isdir(PUBLIC_DIR) else ""
    print(f"TurboQuant server on http://localhost:{port}{web_hint}  (/api/compress /api/decompress /api/image /api/analyze /api/cert /api/bench)")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
