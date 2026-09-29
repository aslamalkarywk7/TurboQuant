# CONFIGURATION — env vars, flags, precedence

## Environment variables

| Var | Default | Used in | Effect |
|---|---|---|---|
| `TQ_MAX_MB` | `25` | `server.py:_read_limited`, `api/_tq.py:max_mb` | Max request body MB. Over-limit → `413`. Raise locally for big files: `TQ_MAX_MB=200 python -m turboquant serve`. Vercel hard cap ≈4.5MB regardless. |
| `TQ_HOST` | `0.0.0.0` | `server.py:serve` | Bind address. `127.0.0.1` for local-only. Docker/Render need `0.0.0.0`. |
| `PORT` | `8765` | `server.py:serve`, `Dockerfile`, `render.yaml` | Port. Render injects `$PORT` dynamically. |
| `TQ_CORS_ORIGIN` | `*` | `server.py`, `api/_tq.py` | `Access-Control-Allow-Origin`. Set `https://your-domain` in production. `*` is compat, not security. |
| `TQ_DEBUG` | `0` | `turboquant/log.py` | `1` = verbose tracebacks on server. Never enable publicly (leaks paths). |
| `TURBOQUANT_PASSWORD` | — | `cli.py` encrypt/decrypt | Password for `.tqze` when `--password` not passed. Prefer env over flag (flag leaks in `ps`). |

## CLI flags (selection)

| Command | Key flags |
|---|---|
| `lossless src -o out.tqz` | `--mode fast\|balanced\|max\|ultra`, `--advanced`, `--jobs 1\|all`, `--progress`, `--no-verify` |
| `decompress src -o out` | `--progress`, `--max-gb <float>` (output cap) |
| `image src -o out.webp` | `--target 800KB`, `--mode`, `--format auto\|WEBP\|JPEG\|PNG\|AVIF` |
| `serve` | `--port 8765` (`$PORT` wins if set) |
| `bench src` | `--modes fast,balanced,max,ultra`, `--advanced` |
| `encrypt/decrypt` | `--password` or `TURBOQUANT_PASSWORD` env |
| `delta v1 v2 -o v2.tdelta.tqz` | — |

Size suffixes for `--target`: `KB/MB/GB` (`cli.py:_parse_size`).

## Precedence

`CLI flag > env var > default`. Example: `--port 9000` beats `$PORT`; `$PORT` beats `8765`.

## Production recipe

```bash
TQ_MAX_MB=25 TQ_CORS_ORIGIN=https://app.example.com TQ_HOST=0.0.0.0 PORT=8765 \
  python -m turboquant serve --port 8765
```

Docker (`Dockerfile` already `USER app` + `HEALTHCHECK`):

```bash
docker build -t turboquant .
docker run -p 8765:8765 -e TQ_CORS_ORIGIN=https://app.example.com turboquant
```
