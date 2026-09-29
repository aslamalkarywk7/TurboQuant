"""POST /api/analyze — Body: file bytes → JSON {kind, entropy, suggestion}."""
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
        if len(body) == 0:
            send_json(self, {"ok": False, "error": "ملف فارغ"}, 400)
            return
        import turboquant as tq
        with tempfile.TemporaryDirectory(prefix="tqweb_") as td:
            inp = os.path.join(td, "in.bin")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                rep = tq.analyze_file(inp)
            except Exception:
                send_json(self, {"ok": False, "error": "فشل المعالجة (internal error)"}, 500)
                return
        send_json(self, {"ok": True, "kind": rep.get("kind"), "kind_ar": rep.get("kind_ar"),
                         "size": rep.get("size"), "entropy": rep.get("entropy"),
                         "verdict": rep.get("verdict"), "why": rep.get("why"),
                         "suggestion": rep.get("suggestion")})
