# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 2.4.x | Yes — security fixes |
| < 2.4 | No — upgrade |

Version triple must match: `turboquant/__init__.py`, `pyproject.toml`, `package.json` ([test_versions.py](tests/test_versions.py)).

## Report a vulnerability

- **Do not open a public issue for vulnerabilities.**
- Open a GitHub Security Advisory (preferred) or contact the maintainer privately with: affected version, repro file/PoC, `file:line`, impact.
- Expect acknowledgment within 72h. Fix + [CHANGELOG](CHANGELOG.md) entry + release tag. Credit on request.

## Security boundaries (what we guarantee)

- **Lossless integrity:** `decompress_lossless` verifies `sha256`. Mismatch raises `VerificationError`, never silent corruption.
- **Decompression bombs:** all network/file decompress paths enforce caps (`turboquant/limits.py:resolve_cap`, default `max(1GB, 100000x compressed)`). `decompress_bytes(codec, max_output_bytes=...)` and `CappedWriter` must wrap every new path.
- **Header caps:** `.tqz` header `<= 10MB` (`turboquant/lossless.py:_read_pkg`), `.tqze` header `<= 10MB` (`turboquant/crypto.py:decrypt_bytes`), dedup manifest `<= 100MB` (`turboquant/dedup.py`). Larger `hl/mlen` = `CorruptPackageError`.
- **No auth by design:** HTTP API has no login. Do not expose `serve` to the public internet without a reverse proxy (auth + rate-limit + TLS). `TQ_CORS_ORIGIN` restricts browsers, it is not access control.
- **No server-side path access:** `GET /detect?path=` is disabled (`410`). Only `POST` with body bytes is allowed.
- **Crypto:** `.tqze` = AES-256-GCM + PBKDF2-SHA256 (200k iters). Wrong password / tamper raises `PasswordError`. `TURBOQUANT_PASSWORD` via env, never CLI flag in production (leaks in `ps`/history).

## Hardening checklist (deployment) — details: [CONFIGURATION](docs/CONFIGURATION.md)

1. Set `TQ_MAX_MB=25` (default), lower for public demos. Never raise blindly — old local default was huge before hardening fix.
2. Set `TQ_CORS_ORIGIN=https://your-domain` (default `*` for compat).
3. Bind `TQ_HOST=127.0.0.1` for local-only; reverse proxy for public.
4. Run Docker as `app` (already in `Dockerfile:USER app`) + `HEALTHCHECK /api/health`.
5. Keep `cryptography>=41`, `Pillow>=10.0` patched. No version pins in repo — pin in your lockfile + run `pip-audit`.
6. Never commit `.env`, `*.pem`, `*.key` (already in [.gitignore](.gitignore)).

## Out of scope

- DoS via `bench` CPU cost on a public endpoint without rate-limit (documented — put it behind auth/limits).
- Security of `ffmpeg`/`pikepdf`/`soundfile` binaries themselves.
- Client-side `public/index.html` XSS via malicious filenames (mitigated with `textContent`, but CSP headers are still required — already sent by server).
