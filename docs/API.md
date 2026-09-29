# TurboQuant API Reference (for developers)

Base URLs:
- Production: `https://turbo-quant.vercel.app`
- Local: `http://localhost:8765` (run `python -m turboquant serve --port 8765`)

Auth: none. CORS: configurable via `TQ_CORS_ORIGIN` (default `*` for backward compat — set your domain in production).
Limits: single request ≈ 4.5MB on Vercel (`TQ_MAX_MB`, default 25 locally and on Vercel, controls the server cap). For bigger files run locally with `TQ_MAX_MB` raised.
All `POST` endpoints take **raw file bytes** as the body (`Content-Type: application/octet-stream`) unless noted.
Errors are JSON: `{"ok": false, "error": "..."}` with status `400` (bad input), `413` (over size limit), `500` (engine failure).

## `GET /api/health` — liveness + capabilities

```bash
curl https://turbo-quant.vercel.app/api/health
```

Response `200`:
```json
{"ok": true, "service": "turboquant", "version": "2.4.0",
 "codecs": ["zstd", "brotli", "gzip", "..."], "lossless_default": true,
 "endpoints": ["/api/compress", "/api/decompress", "/api/image",
               "/api/analyze", "/api/cert", "/api/bench"]}
```

## `POST /api/compress` — compress any file (lossless)

| Query param | Values | Default |
|---|---|---|
| `mode` | `fast`, `balanced`, `max`, `ultra`, `extreme` (unknown falls back to `balanced`) | `balanced` |
| `advanced` | `1` enables extra transforms (bwt/delta/filters/zdict), `0` off | `0` |
| `filename` | original name (used for the download name; or send `X-Filename` header) | `file.bin` |
| `format` | `json` returns JSON+base64 instead of binary | binary |

Binary reply (default): `.tqz` bytes + headers `X-TQ-Orig`, `X-TQ-New`, `X-TQ-Codec`, `X-TQ-Ratio`, `X-TQ-Verified` (`1`/`0`), `X-TQ-Elapsed`, `Content-Disposition: attachment; filename="….tqz"`.

JSON reply (`?format=json`): `{"ok": true, "filename", "orig", "new", "ratio", "saved_pct", "codec", "pipeline", "kind", "verified", "elapsed_s", "output_b64"}`.

```bash
curl -X POST "https://turbo-quant.vercel.app/api/compress?mode=max&filename=report.pdf" \
  --data-binary @report.pdf -o report.pdf.tqz
```

```python
import urllib.request
req = urllib.request.Request(
    "https://turbo-quant.vercel.app/api/compress?mode=max&filename=report.pdf",
    data=open("report.pdf", "rb").read(), method="POST",
    headers={"Content-Type": "application/octet-stream"})
with urllib.request.urlopen(req) as r:
    open("report.pdf.tqz", "wb").write(r.read())
    print(r.headers["X-TQ-Ratio"], r.headers["X-TQ-Verified"])
```

```js
const buf = await file.arrayBuffer();
const r = await fetch("https://turbo-quant.vercel.app/api/compress?mode=max&filename=" + encodeURIComponent(file.name), {method: "POST", body: buf});
const blob = await r.blob(); // .tqz file
```

## `POST /api/decompress` — restore a `.tqz` file

No params. Body: `.tqz` bytes. Reply: original bytes (`Content-Disposition: attachment; filename="restored.bin"`) + `X-TQ-Verified`, `X-TQ-Size`.

```bash
curl -X POST https://turbo-quant.vercel.app/api/decompress --data-binary @report.pdf.tqz -o report.pdf
```

## `POST /api/image` — photo to target size

| Query param | Values | Default |
|---|---|---|
| `target_bytes` | e.g. `819200` (800KB); invalid falls back to `819200` | `819200` |
| `mode` | same modes as compress | `balanced` |
| `fmt` | `auto` (WebP), `WEBP`, `JPEG`, `PNG`, `AVIF` | `auto` |

Reply: image bytes (`image/webp` for WebP, else `application/octet-stream`) + `X-TQ-Orig`, `X-TQ-New`, `X-TQ-Hit` (`1` = target met), `X-TQ-Quality`.
Note: files already under the target are kept as is (no quality lost) — check `X-TQ-Hit` / compare sizes.

```bash
curl -X POST "https://turbo-quant.vercel.app/api/image?target_bytes=819200&fmt=auto" \
  --data-binary @photo.jpg -o photo.tq.webp
```

## `POST /api/analyze` — file kind, entropy, suggestion

Body: any file bytes. Reply: `{"ok": true, "kind", "kind_ar", "size", "entropy", "verdict", "why", "suggestion"}`.

```bash
curl -X POST https://turbo-quant.vercel.app/api/analyze --data-binary @data.csv
```

## `POST /api/cert` — trust certificate for a `.tqz` file

Body: `.tqz` bytes. Reply: `{"ok": true, "verdict": "PASS"|..., "checks", "meta", "quality", "certificate"}` (human-readable text in `certificate`).

## `POST /api/bench` — compare modes on your file

| Query param | Values | Default |
|---|---|---|
| `modes` | comma list among `fast,balanced,max,ultra` (unknown entries ignored) | all four |
| `advanced` | `1`/`0` | `0` |

Reply: `{"ok": true, "rows": [...], "table": "..."}` — each row has `mode, codec, transform, pipeline, orig, new, ratio, saved_pct, compress_s, decompress_s, mb_s, verified`. Keep files small on Vercel (benchmark runs every mode).

```bash
curl -X POST "https://turbo-quant.vercel.app/api/bench?modes=fast,balanced" --data-binary @data.csv
```

## Python library (same engine, no server)

```python
import turboquant as tq
tq.compress_lossless("report.pdf", "report.pdf.tqz", mode="max")
tq.decompress_lossless("report.pdf.tqz", "report.pdf")
rows = tq.benchmark("data.csv", modes=["fast", "balanced", "max", "ultra"])
tq.print_benchmark(rows)
info = tq.compress_image("photo.jpg", "photo.webp", target_bytes=819200, mode="balanced", fmt="auto")
rep = tq.analyze_file("data.csv")
cert = tq.verify_package("report.pdf.tqz")
```

## Rules of thumb for integrators

1. Health-check first; read `codecs` before assuming a codec exists.
2. Always check `verified` / `X-TQ-Verified` — lossless means byte-identical or it is a bug: report it.
3. Random/encrypted/already-compressed files do not shrink (`ratio ≈ 1.0`) — detect via `/api/analyze` entropy before compressing.
4. On Vercel keep files ≤ ~4MB per request; larger files go through a local server (`TQ_MAX_MB` raises the cap locally).
5. Filenames: prefer the `filename` query param (ASCII-safe) over headers.
