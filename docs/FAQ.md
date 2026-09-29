# FAQ — every question answered once

## Concepts

**Lossless vs lossy?**
Lossless (`compress_lossless`, default) returns bytes identical + `sha256` verified. Lossy (`compress_image`, `compress_video/audio`) changes quality to hit a size target — only for images/media with explicit opt-in.

**Why didn't my MP4/ZIP shrink?**
Already-compressed/encrypted/random data has `ratio≈1.0`. This is honesty, not failure. Check `POST /api/analyze` entropy first. Quality stays 100%.

**Which mode?**
`fast` (speed) → `balanced` (daily) → `max`/`ultra` (smallest, slower). Strength only, quality always 100% in lossless.

**What is `advanced=True`?**
Extra transforms (`bwt/delta/filters/zdict` + entropy gate). Files ≤64MB only, slower, sometimes smaller. Try `bench --advanced` on your file.

**What is dedup?**
FastCDC chunks (~256KB avg) + `sha256`. Repeated chunks stored once (logs, VMs, DBs, copies). Automatic: `single` vs `dedup` smallest-wins.

## Files & format

**What is `.tqz`? `.tqze`? `.tdelta.tqz`?**
`.tqz` = v2 container (`TQZ2 + header + body`, open spec [FORMAT](FORMAT.md)). `.tqze` = encrypted `.tqz` (AES-256-GCM, see [FEATURES](FEATURES.md#1-encryption-tqze-aes-256-gcm)). `.tdelta.tqz` = delta vs base file (see [FEATURES](FEATURES.md#2-incremental-delta-tdeltatqz)).

**Is the format open?**
Yes. [FORMAT](FORMAT.md) + native decoders in [bindings](../bindings/README.md) (JS/Java/Go/C#). Unknown `transform/codec` must be rejected, never partially decoded.

**How do I verify?**
`python -m turboquant cert file.tqz` or `verify_package()` → `PASS/FAIL` + `format_certificate()`. Always check `verified` / `X-TQ-Verified`. Details: [API](API.md) headers, [TROUBLESHOOTING](TROUBLESHOOTING.md) cert errors.

## API & server

**Limits?**
`TQ_MAX_MB=25` default (local + Vercel). Vercel hard ≈4.5MB per request. For bigger files run locally with raised `TQ_MAX_MB`. Over-limit → `413`.

**No auth?**
By design. Do not expose `serve` publicly without reverse proxy (auth + rate-limit + TLS). `bench` is CPU-heavy — never public unauthenticated.

**CORS?**
`TQ_CORS_ORIGIN` (default `*`). Set your domain in prod.

**Why `410` on `GET /detect?path=`?**
Arbitrary server-path oracle, removed for security. Use `POST /api/analyze` with bytes.

**Headers?**
Compress binary: `X-TQ-Orig/New/Codec/Ratio/Verified/Elapsed`. Decompress: `X-TQ-Verified/Size`. Image: `X-TQ-Orig/New/Hit/Quality`. Health: `{ok, service, version, codecs, lossless_default, endpoints}`.

## Encryption & delta

**How does encryption work?**
`encrypt_file(.tqz, password)` → `.tqze` (PBKDF2 200k + AES-GCM). Wrong password/tamper → `PasswordError`. Use `TURBOQUANT_PASSWORD` env, not `--password` in prod.

**Delta?**
`create_delta(v1, v2)` stores new chunks only. `apply_delta(v1, delta, v2)` verifies `base_sha256` then `new_sha`.

## Bindings

**Do I need Python for JS/Java/Go/C#?**
CLI/REST wrappers need Python once. Native decoders (`tqz-decode.*`) work without Python for `gzip/brotli/store + transforms`; `zstd/lzma/dedup/zdict` need Python (matrix in [bindings README](../bindings/README.md)). Full flow: [ARCHITECTURE](ARCHITECTURE.md#layers).

**Repo URL mismatch?**
Canonical: `github.com/aslamalkarywk7/TurboQuant` (`pyproject.toml`). Legacy `package.json` URL already unified to canonical.

## Install & versions

**Which extra?**
`.[max]` (zstd/brotli, recommended), `.[full]` (+PDF/audio), `.[secure]` (crypto), base = `Pillow` only.

**Python/Node?**
Python `>=3.10` (CI `3.10–3.12`), Node `>=18` for bindings.

**Version triple?**
`__init__.__version__` = `pyproject.version` = `package.json.version` (enforced by `test_versions.py`).
