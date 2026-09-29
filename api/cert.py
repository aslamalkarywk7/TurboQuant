"""POST /api/cert — Body: .tqz bytes → JSON certificate (verify_package)."""
from http.server import BaseHTTPRequestHandler
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _tq import cors, send_json, read_body, ensure_turboquant, _security

class handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_OPTIONS(self):
        self.send_response(200); cors(self); _security(self); self.end_headers()
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
            with open(inp, "wb") as f:
                f.write(body)
            try:
                cert = tq.verify_package(inp)
            except Exception:
                send_json(self, {"ok": False, "error": "فشل المعالجة (internal error)"}, 500)
                return
        send_json(self, {"ok": True, "verdict": cert.get("verdict"), "checks": cert.get("checks"),
                         "meta": cert.get("meta"), "quality": cert.get("quality"),
                         "certificate": tq.format_certificate(cert)})
