"""chunkstore.py — مخزن chunks مُعنوَن بالمحتوى على SQLite.

لماذا SQLite (وليس dict في الذاكرة)؟
- حزم الملفات الكبيرة كانت تضع كل الـ blobs المضغوطة في RAM (مئات MB).
- SQLite من stdlib: ACID + فهرس PRIMARY KEY + ملف واحد + WAL — بلا سيرفر ولا اعتماديات.
- الواجهة مجردة (ChunkBackend): يمكن لاحقاً توصيل LMDB/S3/Postgres دون لمس المستهلكين.

الاستخدام:
    with temp_store() as store:      # ملف مؤقت يُمسح تلقائياً
        store.put(sha, blob)
        blob = store.get(sha)        # KeyError لو غائب
"""
from __future__ import annotations
import os
import sqlite3
import tempfile

SCHEMA = "CREATE TABLE IF NOT EXISTS blobs(sha TEXT PRIMARY KEY, data BLOB NOT NULL)"

class ChunkBackend:
    def put(self, sha: str, data: bytes) -> None: raise NotImplementedError
    def get(self, sha: str) -> bytes: raise NotImplementedError
    def contains(self, sha: str) -> bool: raise NotImplementedError
    def __len__(self) -> int: raise NotImplementedError
    def close(self) -> None: raise NotImplementedError

class SQLiteChunkStore(ChunkBackend):
    """مخزن SQLite. path=None → ذاكرة (للصغير). fast=True → إعدادات مؤقتة سريعة."""

    def __init__(self, path: str | None = None, fast: bool = True):
        self._path = path
        self._con = sqlite3.connect(path or ":memory:")
        if fast:
            self._con.execute("PRAGMA journal_mode=OFF")
            self._con.execute("PRAGMA synchronous=OFF")
        elif path:
            self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute(SCHEMA)
        self._con.commit()
        self._pending: list[tuple[str, bytes]] = []

    def put(self, sha: str, data: bytes) -> None:
        self._pending.append((sha, bytes(data)))
        if len(self._pending) >= 64:
            self.flush()

    def put_many(self, items) -> None:
        for sha, data in items:
            self.put(sha, data)
        self.flush()

    def flush(self) -> None:
        if self._pending:
            self._con.executemany("INSERT OR IGNORE INTO blobs(sha, data) VALUES(?, ?)", self._pending)
            self._con.commit()
            self._pending = []

    def get(self, sha: str) -> bytes:
        self.flush()
        row = self._con.execute("SELECT data FROM blobs WHERE sha=?", (sha,)).fetchone()
        if row is None:
            raise KeyError(sha)
        return row[0]

    def contains(self, sha: str) -> bool:
        self.flush()
        return self._con.execute("SELECT 1 FROM blobs WHERE sha=?", (sha,)).fetchone() is not None

    def __len__(self) -> int:
        self.flush()
        return self._con.execute("SELECT COUNT(*) FROM blobs").fetchone()[0]

    def close(self) -> None:
        try:
            self.flush()
        finally:
            self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False

class temp_store:
    """مخزن مؤقت على ملف (لا RAM للـ blobs) يُمسح تلقائياً."""

    def __init__(self):
        self._dir = None
        self.store = None

    def __enter__(self) -> SQLiteChunkStore:
        self._dir = tempfile.mkdtemp(prefix="tq_chunks_")
        self.store = SQLiteChunkStore(os.path.join(self._dir, "chunks.db"))
        return self.store

    def __exit__(self, *a):
        try:
            if self.store is not None:
                self.store.close()
        finally:
            import shutil
            if self._dir and os.path.isdir(self._dir):
                shutil.rmtree(self._dir, ignore_errors=True)
        return False
