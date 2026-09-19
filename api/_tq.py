"""Shared helpers for Vercel Python serverless (BaseHTTPRequestHandler pattern).

Vercel runs each api/*.py as an isolated function. Import via:
  import os, sys
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
  sys.path.insert(0, os.path.dirname(__file__))
  from _tq import cors, send_json, read_body, ensure_turboquant
"""
from __future__ import annotations
import json
import os
import sys

MAX_MB_DEFAULT = 25  # Vercel payload hard-limit ≈ 4.5MB; local server allows more

def ensure_turboquant():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    if root not in sys.path:
        sys.path.insert(0, root)

def max_mb() -> int:
    try:
        return int(os.environ.get("TQ_MAX_MB", str(MAX_MB_DEFAULT)))
    except ValueError:
        return MAX_MB_DEFAULT

def cors(h):
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type, X-Filename")
    h.send_header("Access-Control-Expose-Headers", "*")

def send_json(h, obj: dict, status: int = 200):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(data)))
    cors(h)
    h.end_headers()
    h.wfile.write(data)

def send_bytes(h, data: bytes, filename: str = "file.bin",
               ctype: str = "application/octet-stream", extra: dict | None = None):
    h.send_response(200)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(data)))
    h.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    for k, v in (extra or {}).items():
        h.send_header(k, str(v))
    cors(h)
    h.end_headers()
    h.wfile.write(data)

def read_body(h, limit: int | None = None):
    """Read Content-Length body in chunks. Returns bytes or None if over limit."""
    try:
        length = int(h.headers.get("Content-Length", 0))
    except (ValueError, TypeError):
        length = 0
    cap = (limit if limit else max_mb() * 1024 * 1024)
    if length > cap:
        # drain to keep connection clean, then signal overflow
        left = length
        while left > 0:
            blk = h.rfile.read(min(1 << 20, left))
            if not blk:
                break
            left -= len(blk)
        return None
    body = bytearray()
    remaining = length
    while remaining > 0:
        blk = h.rfile.read(min(1 << 20, remaining))
        if not blk:
            break
        body += blk
        remaining -= len(blk)
        if len(body) > cap:
            # drain rest
            while remaining > 0:
                blk = h.rfile.read(min(1 << 20, remaining))
                if not blk:
                    break
                remaining -= len(blk)
            return None
    return bytes(body)
