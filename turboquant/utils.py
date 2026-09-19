"""Utilities: size formatting + stats."""
from __future__ import annotations
import os

def format_size(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"

def file_size(path: str) -> int:
    return os.path.getsize(path)

def ratio_stats(orig: int, new: int) -> dict:
    if orig <= 0:
        return {"orig": 0, "new": new, "ratio": 0.0, "saved_pct": 0.0}
    ratio = new / orig
    saved = (1 - ratio) * 100
    return {"orig": orig, "new": new, "ratio": round(ratio, 4), "saved_pct": round(saved, 2)}

def ensure_parent(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
