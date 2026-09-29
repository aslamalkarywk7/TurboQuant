# Contributing to TurboQuant

Thank you for contributing. This project keeps a stable API since 2.x: `compress / decompress / detect / benchmark / verify`.

## 1. Setup

```bash
git clone https://github.com/aslamalkarywk7/TurboQuant.git
cd TurboQuant
pip install -e ".[max,secure]" pytest
pytest tests -q -rs
```

Extras:

- `.[max]` — `zstandard`, `brotli` (recommended)
- `.[full]` — `+ pikepdf`, `soundfile` (PDF/audio)
- `.[secure]` — `cryptography` (`.tqze` encryption)
- `.[dev]` — `pytest`, `build`, `twine`

Node smoke: `node -e "require('./bindings/turboquant.js')"`

## 2. What to work on

- [ROADMAP](docs/ROADMAP.md) — accepted direction + non-goals
- Issues labeled `good first issue` / `help wanted`
- Docs fixes are welcome without prior discussion

## 3. Code rules

- Lossless guarantee is sacred: `decompress(compress(x)) == x` byte-identical + `sha256` verified. Any PR breaking this is rejected.
- Public names in `turboquant/__init__.py` are stable since 2.x. Do not rename. Add new functions, do not change signatures.
- No new runtime dependencies in `dependencies` (keep base = `Pillow` only). Optional deps go to `max/full/secure`.
- Server (`turboquant/server.py`, `api/*`) is stdlib-only. No Flask/FastAPI.
- Errors: raise typed errors from `turboquant/errors.py` (`CorruptPackageError`, `VerificationError`, `OutputLimitError`, `PasswordError`). Never leak paths to HTTP clients — use generic messages, log details with `turboquant.log.logger`.
- Security: validate `header_len` caps (`10MB`), sanitize filenames (`sanitize_filename`), keep `CappedWriter` on all decompress paths.

## 4. Tests

```bash
pytest tests -q -rs          # must be green
python -m turboquant bench <file>   # manual ratio check
python -m turboquant cert out.tqz   # must be PASS
```

- New codec/transform: add round-trip test (`compress -> decompress -> sha256`) + corrupt-input test (truncated header must raise `CorruptPackageError`, not `struct.error`).
- New API route: add case in `tests/test_web.py` + update [API](docs/API.md).
- New binding: update matrix in [bindings README](bindings/README.md).

CI runs `3.9–3.12` on Ubuntu with `.[max,secure]`. Skipped crypto tests are a bug — do not add module-level `skipif`, scope skips to single tests.

## 5. Pull requests

- One PR = one change. Include: what, why, `file:line` evidence, test output.
- Update docs in same PR: [README](README.md) + [docs](docs/README.md) + [CHANGELOG](CHANGELOG.md) (Unreleased section).
- PR template checklist must be ticked (tests, docs, no new base deps, security considered).

## 6. Commit + version

- Commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:` prefix.
- Version lives in 3 places and must match (`tests/test_versions.py` enforces): `turboquant/__init__.py:__version__`, `pyproject.toml:version`, `package.json:version`.
- Release: `git tag vX.Y.Z && git push origin vX.Y.Z` — `.github/workflows/release.yml` publishes to PyPI (trusted publishing). See [PUBLISHING](docs/PUBLISHING.md).

## 7. Conduct

By contributing you agree to [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md). Report issues to maintainers privately first if security-related — see [SECURITY](SECURITY.md).
