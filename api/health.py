"""GET /api/health — فحص حيوية + قدرات (يعمل على Vercel ومحلياً)."""
from http.server import BaseHTTPRequestHandler
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _tq import cors, send_json, ensure_turboquant

class handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_OPTIONS(self):
        self.send_response(200); cors(self); self.end_headers()
    def do_GET(self):
        ensure_turboquant()
        try:
            import turboquant as tq
            codecs = tq.available_codecs()
            ver = getattr(tq, "__version__", "2.4.0")
        except Exception as e:
            send_json(self, {"ok": False, "error": str(e)[:300]}, 500)
            return
        send_json(self, {"ok": True, "service": "turboquant", "version": ver,
                         "codecs": codecs, "lossless_default": True,
                         "endpoints": ["/api/compress", "/api/decompress", "/api/image",
                                       "/api/analyze", "/api/cert", "/api/bench"]})
