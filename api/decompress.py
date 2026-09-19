"""POST /api/decompress — Body: .tqz bytes → Returns: original file bytes."""
from http.server import BaseHTTPRequestHandler
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
        body = read_body(self)
        if body is None:
            send_json(self, {"ok": False, "error": "الملف أكبر من الحد"}, 413)
            return
        if not body:
            send_json(self, {"ok": False, "error": "ملف فارغ"}, 400)
            return
        import turboquant as tq
        with tempfile.TemporaryDirectory(prefix="tqweb_") as td:
            inp = os.path.join(td, "in.tqz")
            out = os.path.join(td, "out.bin")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                info = tq.decompress_auto(inp, out)
            except Exception as e:
                send_json(self, {"ok": False, "error": str(e)[:500]}, 400)
                return
            with open(info.get("output", out), "rb") as f:
                blob = f.read()
        send_bytes(self, blob, "restored.bin", "application/octet-stream",
                   {"X-TQ-Verified": "1" if info.get("verified") else "0",
                    "X-TQ-Size": len(blob)})
