"""crypto.py — تشفير AES-256-GCM بكلمة سر (طبقة فوق أي حاوية .tqz).

التصميم: نضغط أولاً (lossless يحافظ على النسبة)، ثم نشفّر بايتات الحاوية كاملة.
الناتج `.tqze`: MAGIC TQZE + هيدر JSON (salt/nonce/iters) + ciphertext + tag مدمج.
فك التشفير يتحقق من السلامة تلقائياً (GCM): باسورد خطأ أو عبث → خطأ صريح.

يتطلب: pip install "turboquant[secure]" (حزمة cryptography).
"""
from __future__ import annotations
import base64
import json
import os
import struct

MAGIC = b"TQZE"
HLEN = ">I"
_SALT_N = 16
_NONCE_N = 12
_ITERS = 200_000

def _need_crypto():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        return AESGCM, PBKDF2HMAC, hashes
    except ImportError:
        raise RuntimeError('التشفير يتطلب: pip install "turboquant[secure]"')

def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()

def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode())

def encrypt_bytes(plain: bytes, password: str, iters: int = _ITERS) -> bytes:
    AESGCM, PBKDF2HMAC, hashes = _need_crypto()
    if not password:
        raise ValueError("كلمة السر فارغة")
    salt = os.urandom(_SALT_N)
    nonce = os.urandom(_NONCE_N)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iters)
    ct = AESGCM(kdf.derive(password.encode("utf-8"))).encrypt(nonce, plain, None)
    head = json.dumps({"v": 1, "kdf": "pbkdf2-sha256", "iters": iters,
                       "salt": _b64(salt), "nonce": _b64(nonce)}).encode()
    return MAGIC + struct.pack(HLEN, len(head)) + head + ct

def decrypt_bytes(blob: bytes, password: str) -> bytes:
    from cryptography.exceptions import InvalidTag
    from .errors import PasswordError, CorruptPackageError
    AESGCM, PBKDF2HMAC, hashes = _need_crypto()
    if len(blob) < 8 or blob[:4] != MAGIC:
        raise CorruptPackageError("ليس ملف TurboQuant مشفراً (.tqze)")
    try:
        (hl,) = struct.unpack_from(HLEN, blob, 4)
        # Header is tiny JSON (salt/nonce/iters); cap to stop huge-allocation DoS.
        if hl < 2 or hl > 10 * 1024 * 1024:
            raise CorruptPackageError("هيدر الحاوية المشفرة تالف (طول غير منطقي)")
        if len(blob) < 8 + hl:
            raise CorruptPackageError("حاوية مشفرة مقطوعة (truncated)")
        meta = json.loads(blob[8:8 + hl].decode())
        ct = blob[8 + hl:]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                         salt=_unb64(meta["salt"]), iterations=int(meta["iters"]))
        return AESGCM(kdf.derive(password.encode("utf-8"))).decrypt(_unb64(meta["nonce"]), ct, None)
    except InvalidTag as e:
        raise PasswordError("كلمة السر خطأ أو الملف تعرّض للعبث") from e
    except KeyError as e:
        raise CorruptPackageError("حاوية مشفرة تالفة (هيدر)") from e
    except (struct.error, ValueError, UnicodeDecodeError) as e:
        # ValueError covers b64/int() failures; keep PasswordError for auth failures only.
        # Heuristic: truncated/garbage header -> corrupt; GCM tag failure already handled above.
        raise CorruptPackageError(f"حاوية مشفرة تالفة: {type(e).__name__}") from e

def encrypt_file(src: str, dst: str | None = None, password: str = "") -> dict:
    """شفّر أي ملف (عادة .tqz بعد ضغطه) → .tqze."""
    from .utils import format_size, ensure_parent
    if dst is None:
        dst = src + ".tqze"
    ensure_parent(dst)
    with open(src, "rb") as f:
        blob = encrypt_bytes(f.read(), password)
    with open(dst, "wb") as f:
        f.write(blob)
    return {"output": dst, "orig": os.path.getsize(src), "new": os.path.getsize(dst),
            "orig_h": format_size(os.path.getsize(src)), "new_h": format_size(len(blob)),
            "cipher": "AES-256-GCM/pbkdf2-sha256"}

def decrypt_file(src: str, dst: str | None = None, password: str = "") -> dict:
    """فك تشفير .tqze → الملف الأصلي (يفشل بصوت عالٍ عند العبث)."""
    from .utils import ensure_parent, format_size
    if dst is None:
        dst = src[:-5] if src.endswith(".tqze") else src + ".out"
    ensure_parent(dst)
    with open(src, "rb") as f:
        plain = decrypt_bytes(f.read(), password)
    with open(dst, "wb") as f:
        f.write(plain)
    return {"output": dst, "size": os.path.getsize(dst), "size_h": format_size(os.path.getsize(dst))}
