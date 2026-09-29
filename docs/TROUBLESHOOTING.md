# TROUBLESHOOTING — error → cause → fix. Hub: [docs/README](README.md). Concepts: [FAQ](FAQ.md). Config: [CONFIGURATION](CONFIGURATION.md).

## Python exceptions

| Error | Cause | Fix |
|---|---|---|
| `CorruptPackageError: ليس ملف TurboQuant v2` | Wrong magic (not `.tqz`) or `TQZ1` old file | Use `decompress_auto` (handles v1+v2) or `decompress_file` for v1 — spec: [FORMAT](FORMAT.md) |
| `CorruptPackageError: هيدر الحاوية تالف` | Truncated / `hl > 10MB` / garbage | Re-download, check `Content-Length`, do not hand-edit `.tqz` |
| `VerificationError: sha256 ... != ...` | Tamper / disk error / bug | Treat as corrupt, re-compress from source. If reproducible on clean files → open bug ([SUPPORT](../SUPPORT.md)) |
| `OutputLimitError: تجاوز حد الإخراج` | Zip-bomb guard tripped ([ARCHITECTURE](ARCHITECTURE.md)) | If legit huge file, pass explicit `max_output_bytes` / `--max-gb`. If from network, reject |
| `PasswordError` | Wrong password or tampered `.tqze` | Retry password, check integrity — details: [FEATURES](FEATURES.md#1-encryption-tqze-aes-256-gcm) |
| `UnsupportedCodecError` | Unknown `codec/transform` (e.g. `zdict` without `zstandard`) | Install matching extra (`.[max]`) or reject file |
| `CancelledError` | `CancelToken.cancel()` called | Expected on user cancel |
| `ModuleNotFoundError: zstandard/brotli/cryptography` | Extra not installed | `pip install -e ".[max,secure]"` ([CONTRIBUTING](../CONTRIBUTING.md)) |

## CLI

| Symptom | Fix |
|---|---|
| `lossless -o report.pdf` overwrote source | Never `-o` same path. Use `-o report.pdf.tqz` ([README](../README.md)) |
| `bench` slow on big file | Use small sample, fewer `--modes`, no `--advanced` on >64MB ([PERFORMANCE](PERFORMANCE.md)) |
| `video/audio` → `RuntimeError` / ffmpeg missing | Install `ffmpeg` binary; Vercel has no `ffmpeg` — use local/Docker ([FEATURES](FEATURES.md#4-media-needs-ffmpeg-lossy)) |
| `wav` optimize → `RuntimeError` | Needs `ffmpeg` or `soundfile`; otherwise `compress_lossless` still works |

## HTTP (`server.py` / `api/*`) — spec: [API](API.md)

| Code | Meaning | Fix |
|---|---|---|
| `400` | Empty body / bad input | Send raw bytes, check `Content-Length` |
| `410` on `/detect` | Disabled oracle | Use `POST /api/analyze` with bytes ([SECURITY](../SECURITY.md)) |
| `413` | Over `TQ_MAX_MB` (default 25) | Smaller file or raise `TQ_MAX_MB` locally; Vercel ≈4.5MB hard ([CONFIGURATION](CONFIGURATION.md)) |
| `500` + generic `فشل المعالجة` | Engine failure (details in server log, not client) | Check server log with `TQ_DEBUG=1`, retry with smaller file |

Headers missing? Local server sends same `X-TQ-*` as Vercel (parity fixed). If old version, upgrade.

## Docker / Render / Vercel

- **Container unhealthy:** `Dockerfile` binds `0.0.0.0` + `HEALTHCHECK /api/health`. If custom `serve`, ensure `TQ_HOST=0.0.0.0` and `$PORT` respected ([CONFIGURATION](CONFIGURATION.md)).
- **Render healthcheck fails:** `healthCheckPath: /api/health` needs `0.0.0.0` + `TQ_MAX_MB=25` env.
- **Vercel timeout on `bench`:** `maxDuration=60`. Keep bench files ≤4MB, fewer modes, no `advanced` on large files ([WEB](WEB.md)).
- **`ffmpeg` on Vercel:** unavailable by design — video/audio lossy return clear error.

## Debug recipe

```bash
TQ_DEBUG=1 python -m turboquant lossless big.bin -o big.tqz --mode max --progress
python -m turboquant cert big.tqz
python -m pytest tests -q -rs
```
