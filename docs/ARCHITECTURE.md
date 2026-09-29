# ARCHITECTURE — how TurboQuant fits together

```
                 +------------------+
                 |  CLI / GUI / API |
                 | cli.py  app.py   |
                 | server.py api/*  |
                 +--------+---------+
                          |
              +-----------+-----------+
              |  turboquant/__init__  |  gateway: compress_auto / decompress_auto
              +-----------+-----------+
                          |
        +-----------------+------------------+
        |                 |                  |
  lossless.py        image.py            file.py (v1 compat)
  (v2 .tqz)      (lossy 800KB)         presets/to-size
        |
  +-----+------+----------+----------+
  |     |      |          |          |
detect codecs dedup   advanced/  handlers/
kind   best-of FastCDC entropy    image/document/audio
               chunk   bwt/delta
               store   filters/zdict
                       pipeline
        |
  +-----+------+
  |            |
limits.py    crypto.py
caps/Capped  AES-GCM .tqze
Writer       PBKDF2
```

## Layers

1. **Gateway (`__init__.py:59`):** `compress_auto` routes by extension + flags. Images + `target_bytes` → `image.py` (lossy). Everything else → `lossless.py`. Directories → `compress_dir_lossless` (tar + compress).
2. **Lossless core (`lossless.py:93`):** `detect_kind` → try `single` (best codec on 8MB sample) vs `dedup` (FastCDC ≥256KB) vs `single+adv` (if `advanced=True`, ≤64MB) → pick smallest → `_write_pkg` (atomic `tmp+os.replace`) → optional verify (`decompress` to temp + `sha256`).
3. **Container (`.tqz` v2, [FORMAT](FORMAT.md)):** `TQZ2 + uint32 header_len + JSON meta + body`. Meta has `v/kind/codec/method/pre/transform/orig_size/sha256/mode/lossless`. Body is codec bytes or dedup package. Cap: `header_len <= 10MB`.
4. **Codecs (`codecs.py`):** priority `zstd > brotli > lzma > bz2 > gzip + store`. `compress_stream/decompress_stream` are chunked (1MB). `decompress_bytes` enforces `resolve_cap` (zip-bomb guard, see [SECURITY](../SECURITY.md)).
5. **Dedup (`dedup.py` + `chunkstore.py`):** content-defined chunks (64KB–1MB, avg 256KB), `sha256` per chunk, unique blobs on SQLite temp store, manifest + blobs packed. Streaming build/restore keeps RAM ≈ largest chunk.
6. **Advanced ([ADVANCED](ADVANCED.md)):** `entropy` gate (random → `store`), `bwt` (32KB blocks), `delta8/xor8/delta16le`, `filters` (PNG predictors), `zdict` (self-trained zstd dict), `pipeline.smart_select` (race on 128KB sample). Full-file apply only ≤ `ADV_CAP=64MB`.
7. **Server ([API](API.md) + [WEB](WEB.md) + [CONFIGURATION](CONFIGURATION.md)):** stdlib `ThreadingHTTPServer` locally, Vercel functions in prod. Same routes: `POST /api/compress|decompress|image|analyze|cert|bench`, `GET /api/health`. Limits via `TQ_MAX_MB` (default 25). No auth — put behind proxy for public use.
8. **Bindings ([bindings README](../bindings/README.md)):** thin wrappers (CLI `python -m turboquant` + REST `fetch`). Native decoders (`tqz-decode.*`) handle `gzip/brotli/store + transforms` without Python; `zstd/lzma/dedup/zdict` fall back to Python.

## Key decisions (why)

- **stdlib server, no Flask:** zero-dependency deploy on Vercel/Docker, fewer CVEs.
- **Single vs dedup smallest-wins:** no heuristic guessing — measure both, ship smallest.
- **BWT kept in pure Python:** ~2x slower than C, but safety > speed for a correctness-critical path ([CHANGELOG 2.4.0](../CHANGELOG.md)).
- **`store` codec for random data:** honest `ratio≈1.0` instead of fake compression. Numbers: [PERFORMANCE](PERFORMANCE.md).
- **Atomic writes only on compress:** decompress leaves partial files on failure (documented limitation — caller must clean `dst` on `OutputLimitError`).

## Data flow examples

**Compress PDF (max):** `cli lossless` → `compress_lossless(mode=max)` → `detect=text` → `_try_all_single` (sample best = `zstd`) → `dedup` attempt → pick smaller → `_write_pkg(dst)` → verify via temp decompress.

**Serve compress:** `POST /api/compress?mode=max` → `_read_limited` (413 if > cap) → temp `in.bin` → `compress_lossless` → `X-TQ-*` headers + `.tqz` bytes.

**Decrypt:** `decrypt_bytes(.tqze)` → validate `MAGIC/HLEN<=10MB` → `PBKDF2` → `AESGCM.decrypt` → `InvalidTag` maps to `PasswordError`.
