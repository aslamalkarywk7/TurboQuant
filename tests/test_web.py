"""Web console + Vercel API tests (stdlib server + api handlers)."""
import json
import os
import threading
import time
import urllib.request
from http.server import HTTPServer


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _serve(port):
    from turboquant.server import H
    srv = HTTPServer(("127.0.0.1", port), H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv


def _post(url, data, qs=""):
    req = urllib.request.Request(url + qs, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read(), dict(r.headers)


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read()


def test_health_and_ui(tmp_path):
    port = _free_port()
    srv = _serve(port)
    try:
        time.sleep(0.3)
        s, b = _get(f"http://127.0.0.1:{port}/api/health")
        assert s == 200
        j = json.loads(b.decode())
        assert j["ok"] is True and "zstd" in " ".join(j["codecs"])
        s, b = _get(f"http://127.0.0.1:{port}/")
        assert s == 200
        assert b"TurboQuant" in b  # public/index.html served
    finally:
        srv.shutdown()


def test_compress_decompress_api(tmp_path):
    port = _free_port()
    srv = _serve(port)
    try:
        time.sleep(0.3)
        raw = ("hello turboquant " * 2000).encode()
        s, blob, hdr = _post(f"http://127.0.0.1:{port}/", raw,
                             qs="")  # placeholder to warm
    except Exception:
        pass
    try:
        raw = ("hello turboquant " * 2000).encode()
        s, blob, hdr = _post(f"http://127.0.0.1:{port}/api/compress?mode=fast&filename=t.txt", raw)
        assert s == 200 and len(blob) < len(raw)
        s2, back, _ = _post(f"http://127.0.0.1:{port}/api/decompress", blob)
        assert s2 == 200 and back == raw
        # legacy compat
        s3, blob3, _ = _post(f"http://127.0.0.1:{port}/compress?mode=fast", raw)
        assert s3 == 200
    finally:
        srv.shutdown()


def test_analyze_cert_bench(tmp_path):
    port = _free_port()
    srv = _serve(port)
    try:
        time.sleep(0.3)
        raw = ("a,b,c\n1,2,3\n" * 2000).encode()
        s, b, _ = _post(f"http://127.0.0.1:{port}/api/analyze", raw)
        assert s == 200
        assert json.loads(b.decode())["ok"] is True
        s, blob, _ = _post(f"http://127.0.0.1:{port}/api/compress?mode=fast", raw)
        assert s == 200
        s, b, _ = _post(f"http://127.0.0.1:{port}/api/cert", blob)
        assert s == 200
        assert json.loads(b.decode())["verdict"] == "PASS"
        s, b, _ = _post(f"http://127.0.0.1:{port}/api/bench?modes=fast,balanced", raw)
        assert s == 200
        assert len(json.loads(b.decode())["rows"]) == 2
    finally:
        srv.shutdown()


def test_vercel_handlers_importable():
    import importlib.util
    for name in ["health", "compress", "decompress", "image", "analyze", "cert", "bench"]:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api", name + ".py")
        assert os.path.exists(p), p
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "handler")
