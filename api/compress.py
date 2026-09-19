"""POST /api/compress?mode=max&advanced=0&filename=x.pdf
Body: raw file bytes. Returns: binary .tqz (default) or JSON with base64 (?format=json).
Works on Vercel (handler) and locally via turboquant.server.
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import base64, os, sys, tempfile, time
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
        mode = (qs.get("mode", ["balanced"])[0] or "balanced").lower()
        advanced = qs.get("advanced", ["0"])[0] == "1"
        filename = qs.get("filename", [self.headers.get("X-Filename", "file.bin")])[0]
        as_json = qs.get("format", ["bin"])[0] == "json"
        if mode not in ("fast", "balanced", "max", "ultra", "extreme"):
            mode = "balanced"
        body = read_body(self)
        if body is None:
            send_json(self, {"ok": False, "error": "الملف أكبر من الحد (جرّب محلياً أو ملف ≤4MB على Vercel)"}, 413)
            return
        if not body:
            send_json(self, {"ok": False, "error": "ملف فارغ أو بلا body"}, 400)
            return
        import turboquant as tq
        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="tqweb_") as td:
            inp = os.path.join(td, "in.bin")
            out = os.path.join(td, "out.tqz")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                info = tq.compress_lossless(inp, out, mode=mode, advanced=advanced)
            except Exception as e:
                send_json(self, {"ok": False, "error": str(e)[:500]}, 500)
                return
            with open(out, "rb") as f:
                blob = f.read()
        elapsed = round(time.perf_counter() - t0, 3)
        safe = (os.path.basename(filename) or "file.bin") + ".tqz"
        if as_json:
            send_json(self, {"ok": True, "filename": safe, "orig": info.get("orig"),
                             "new": info.get("new"), "ratio": info.get("ratio"),
                             "saved_pct": info.get("saved_pct"), "codec": info.get("codec"),
                             "pipeline": info.get("pipeline"), "kind": info.get("kind"),
                             "verified": info.get("verified"), "elapsed_s": elapsed,
                             "output_b64": base64.b64encode(blob).decode()})
            return
        send_bytes(self, blob, safe, "application/octet-stream",
                   {"X-TQ-Orig": info.get("orig", 0), "X-TQ-New": info.get("new", 0),
                    "X-TQ-Codec": info.get("codec", ""), "X-TQ-Ratio": info.get("ratio", 0),
                    "X-TQ-Verified": "1" if info.get("verified") else "0",
                    "X-TQ-Elapsed": elapsed})
