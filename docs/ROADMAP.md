# ROADMAP — where TurboQuant is going

## Current: 2.4.x (stable)

Lossless core + dedup + advanced transforms + encryption + delta + parallel + media + REST + bindings. API frozen since 2.x.

## Next (accepted)

- [ ] Streaming decompress for `dedup+advanced` without full-body RAM (today `BytesIO` holds full frame)
- [ ] `OutputLimitError` cleanup: remove partial `dst` on failure (today only compress side is atomic)
- [ ] Progress double-compress removal (`lossless.py:124-132` compresses twice when `on_progress` set)
- [ ] Per-byte CDC loop in C / `memoryview` (today pure Python, slow on GB files)
- [ ] `pip-audit` + lockfiles + Dependabot in CI
- [ ] Windows CI matrix (today Ubuntu-only, but [PERFORMANCE](PERFORMANCE.md) targets Windows)
- [x] `package.json` repo URL unification (done — canonical `aslamalkarywk7/TurboQuant`)

## Non-goals (will not do)

- Lossy for non-images (quality promise).
- Server-side auth/rate-limit built-in (use reverse proxy — stdlib server stays lean).
- New base dependencies (base stays `Pillow`-only).
- Breaking renames of `compress/decompress/detect/benchmark/verify`.

## Proposing

Open a feature Issue with: use case, why `modes/advanced/jobs` do not solve it, sample file type/size. Docs PRs need no proposal.
