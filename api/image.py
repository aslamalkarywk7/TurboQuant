"""POST /api/image?target_bytes=819200&mode=balanced&fmt=auto — Body: image bytes → webp/jpg."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _tq import cors, send_json, send_bytes, read_body, ensure_turboquant

class handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_OPTIONS(self):
        self.send_response(200); cors(self); self.end_headers()
    def do_POST(self):
        ensure_turboquant()
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        try:
            target = int(qs.get("target_bytes", ["819200"])[0])
        except ValueError:
            target = 819200
        mode = (qs.get("mode", ["balanced"])[0] or "balanced")
        fmt = (qs.get("fmt", ["auto"])[0] or "auto")
        body = read_body(self)
        if body is None:
            send_json(self, {"ok": False, "error": "الصورة أكبر من الحد"}, 413)
            return
        if not body:
            send_json(self, {"ok": False, "error": "صورة فارغة"}, 400)
            return
        import turboquant as tq
        with tempfile.TemporaryDirectory(prefix="tqweb_") as td:
            inp = os.path.join(td, "in.img")
            out = os.path.join(td, "out.webp")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                info = tq.compress_image(inp, out, target_bytes=target, mode=mode, fmt=fmt)
            except Exception as e:
                send_json(self, {"ok": False, "error": str(e)[:500]}, 400)
                return
            with open(info.get("output", out), "rb") as f:
                blob = f.read()
        ctype = "image/webp" if info.get("format", "WEBP") == "WEBP" else "application/octet-stream"
        send_bytes(self, blob, "image.tq.webp", ctype,
                   {"X-TQ-Orig": info.get("orig", 0), "X-TQ-New": info.get("new", 0),
                    "X-TQ-Hit": "1" if info.get("hit_target") else "0",
                    "X-TQ-Quality": info.get("quality", 0)})
