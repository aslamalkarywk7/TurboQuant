"""POST /api/bench?modes=fast,balanced,max,ultra&advanced=0 — Body: file bytes → JSON rows."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _tq import cors, send_json, read_body, ensure_turboquant

class handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_OPTIONS(self):
        self.send_response(200); cors(self); self.end_headers()
    def do_POST(self):
        ensure_turboquant()
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        modes = tuple(m.strip() for m in qs.get("modes", ["fast,balanced,max,ultra"])[0].split(",") if m.strip()) or ("fast", "balanced", "max", "ultra")
        modes = tuple(m for m in modes if m in ("fast", "balanced", "max", "ultra")) or ("fast", "balanced", "max", "ultra")
        advanced = qs.get("advanced", ["0"])[0] == "1"
        body = read_body(self)
        if body is None:
            send_json(self, {"ok": False, "error": "الملف أكبر من الحد (benchmark يحتاج ملف صغير على Vercel)"}, 413)
            return
        if not body:
            send_json(self, {"ok": False, "error": "ملف فارغ"}, 400)
            return
        import turboquant as tq
        with tempfile.TemporaryDirectory(prefix="tqweb_") as td:
            inp = os.path.join(td, "in.bin")
            with open(inp, "wb") as f:
                f.write(body)
            try:
                rows = tq.benchmark(inp, modes=modes, advanced=advanced)
            except Exception as e:
                send_json(self, {"ok": False, "error": str(e)[:500]}, 500)
                return
        send_json(self, {"ok": True, "rows": rows, "table": tq.format_table(rows)})
