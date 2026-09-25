# TurboQuant v2 — Unified Compression Library for Every File Type

[![CI](https://github.com/aslamalkarywk7/TurboQuant/actions/workflows/ci.yml/badge.svg)](https://github.com/aslamalkarywk7/TurboQuant/actions/workflows/ci.yml)

## One-command install
```bash
pip install "turboquant[max]"          # recommended (zstd + brotli)
# Windows PowerShell: powershell -ExecutionPolicy Bypass -File scripts/install.ps1
# Linux/macOS:        sh scripts/install.sh
# From source: pip install -e ".[max]" then pytest -q
```

## The golden rule
- **Lossless by default = zero quality loss** (bit/byte-identical + `sha256` verification).
- **Lossy for images only** when you request a tiny size (800KB) — and only with your explicit opt-in.

## Stable API guarantee (since 2.x)
Same names in every language — switch languages without relearning:
`compress / decompress / detect / benchmark / verify`
- Python: `import turboquant as tq` • Node: `bindings/turboquant.js`
- Java: `bindings/TurboQuant.java` • C#: `bindings/TurboQuant.cs` • Go: `bindings/turboquant.go`
- Any other language: REST (`python -m turboquant serve`) or the `docs/FORMAT.md` spec.

## New library layout
```
turboquant/
  __init__.py   -> compress_auto / decompress_auto (one gateway for all types)
  lossless.py   -> compress_lossless / decompress_lossless (all files, sha256)
  detect.py     -> detect_kind per type + suggest_pipeline
  codecs.py     -> zstd/brotli/lzma/bz2/gzip (all lossless + best-of)
  dedup.py      -> FastCDC deduplication (like Borg/Restic) — the big saver
  handlers/     -> image_lossless / document (zip/pdf) / audio (wav->flac)
  image.py      -> lossy for images only (800KB)
  file.py       -> v1 container (compatible)
  server.py     -> REST for any language
bindings/       -> JS / Java / C# / Go (CLI + REST) + README
docs/FORMAT.md  -> open .tqz spec for any language
```

## Usage (Python)
```python
import turboquant as tq

# 1) Any file — lossless (PDF/Office/CSV/JSON/PNG/WAV/EXE/...)
tq.compress_lossless("report.pdf", "report.tqz", mode="max")     # recommended
tq.compress_lossless("data.csv", "data.tqz", mode="ultra")       # max compression
tq.compress_lossless("photo.png", "photo.tqz")                   # pixel-identical
tq.decompress_lossless("report.tqz", "report.pdf")               # sha256 verified

# 2) Smart auto mode for every type
tq.compress_auto("anything.pdf")                 # -> lossless
tq.compress_auto("photo.jpg", target_bytes=800*1024, lossless=False)  # -> lossy 800KB

# 2b) Optional quality-lossless optimization (changes container, 100% quality)
tq.optimize_lossless("photo.bmp")   # -> PNG/WebP-lossless (pixel-identical)
tq.optimize_lossless("doc.docx")    # -> max zip (same content)
tq.optimize_lossless("a.wav")       # -> FLAC (same samples)

# 3) Tiny image (lossy — changes quality, your call)
tq.compress_image("in.jpg", "out.webp", target_bytes=800*1024, mode="balanced")

# 4) Compression modes (strength — quality stays 100% in lossless)
# fast (fastest) | balanced | max | ultra
# Honesty note: figures like 400MB->115MB are examples for compressible data
# (text/repetitive), not a guarantee — already-encrypted/compressed data barely
# shrinks further (see hit_target).

# 5) Developer mode inside your app: progress + cancel + measure
tok = tq.CancelToken()
info = tq.compress_lossless("big.bin", "big.tqz", mode="max",
                            on_progress=lambda d, t, ph: print(f"{d/t:.0%}"),
                            cancel=tok)
# From a "Cancel" button: tok.cancel()  (raises tq.CancelledError)
rows = tq.benchmark("data.csv", modes=["fast", "balanced", "max", "ultra"])
tq.print_benchmark(rows)

# 6) Trust certificate to show your users
from turboquant import verify_package, format_certificate
print(format_certificate(verify_package("big.tqz")))  # verdict: PASS/FAIL
```

## Advanced methods (all lossless)
| Method | Where it works | Idea |
|---|---|---|
| `dedup chunks` | logs/VM/copies/DB | FastCDC ~256KB + sha256, store unique only |
| `best-codec` | all files | try zstd/brotli/lzma on a sample, pick smallest |
| `image-lossless` | PNG/BMP/TIFF | PNG-optimize & WebP-lossless + pixel-by-pixel check |
| `zip-recompress` | docx/xlsx/zip | unpack zip and recompress max (5-20% saving) |
| `pdf-recompress` | PDF | recompress streams (pikepdf) |
| `wav->flac` | raw audio | FLAC conversion (~50% saving) via ffmpeg |
| `sha256 verify` | all | decompression accepted only on exact match |

> Already-compressed files (MP4/MP3/random ZIP): no magic — savings are small and `hit_target=False` honestly reports it, but **quality is never touched**.

## Real performance (actually measured — details in `docs/PERFORMANCE.md`)
| File | balanced | ultra | Verification |
|---|---|---|---|
| 1.37MB text | 99.98% saving | 99.98% | byte-identical |
| 546KB csv | 99.95% | 99.95% | byte-identical |
| 1MB random | +0.02% (honestly incompressible) | +0.02% | byte-identical |
```bash
python -m turboquant bench data.bin        # measure on your file
python -m turboquant cert out.tqz          # trust certificate
python -m turboquant lossless big.bin -o big.tqz --mode max --progress
```

## Advanced algorithm system (v2.2.0 — all lossless)
```python
import turboquant as tq
print(tq.analyze_file("data.csv"))   # entropy + suggested transform before compressing
tq.compress_lossless("data.csv", "d.tqz", mode="max", advanced=True)
tq.compress_lossless("s.wav", "s.tqz", mode="max", advanced=True)   # auto delta16le
```
```bash
python -m turboquant analyze data.csv
python -m turboquant lossless data.csv -o d.tqz --mode max --advanced
python -m turboquant bench data.csv --advanced
```
- entropy gate (raw storage for random data) • bzip2-style BWT • delta8/xor8/delta16le •
  PNG filters • self-made zstd dictionaries • orchestrator auto-picks the winner — details in `docs/ADVANCED.md`.

## License & contributing
- License: MIT (`LICENSE`) — use it freely inside commercial apps.
- History: `CHANGELOG.md` — releases since 2.x keep function names stable.

## Usage from other languages
```bash
pip install -e .
python -m turboquant lossless report.pdf -o report.pdf --mode max
python -m turboquant decompress report.pdf.tqz -o report.pdf
python -m turboquant detect report.pdf
python -m turboquant serve --port 8765   # REST for any language
```
- Node: `bindings/turboquant.js` • Java: `bindings/TurboQuant.java`
- C#: `bindings/TurboQuant.cs` • Go: `bindings/turboquant.go`
- Native decoders without Python: `tqz-decode.mjs` • `TqzDecode.java` • `tqzdecode.go` • `TqzDecode.cs`
- Open format: `docs/FORMAT.md`

## New in v2.3 (priority: higher ratios)
```python
import turboquant as tq
# Encryption: compress then AES-256-GCM
tq.encrypt_file("backup.tqz", password="...")   # → .tqze
# Incremental: only the diff of the new version against the base
tq.create_delta("v1.bin", "v2.bin")             # → far smaller than a full copy
tq.apply_delta("v1.bin", "v2.tdelta.tqz", "v2.bin")
# Parallel: same bytes, less time
tq.compress_lossless("big.bin", "big.tqz", mode="max", jobs=None)  # all cores
# Media (needs ffmpeg): video/audio to a size target like 800KB images
tq.compress_video("film.mp4", "film.tq.mp4", target_bytes=20*1024*1024, preset="720p")
tq.compress_audio("song.wav", "song.tq.ogg", target_bytes=5*1024*1024)
```
```bash
TURBOQUANT_PASSWORD=... python -m turboquant encrypt backup.tqz
python -m turboquant delta v1.bin v2.bin -o v2.tdelta.tqz
python -m turboquant lossless big.bin --jobs all
python -m turboquant video film.mp4 --target 20MB --preset 720p
```

## App integrations (5-minute merge)
```bash
turboquant-gui                                  # drag & drop UI (progress + cancel + certificate)
docker build -t turboquant . && docker run -p 8765:8765 turboquant   # ready REST
```
- Copy-ready examples: `examples/example.py` • `example.js` • `Example.java` • `example.cs` • `example.go` • `example_rest.sh`
- Publishing: `pip install turboquant[max]` / `npm i turboquant` + `scripts/install.*` scripts + CI in `.github/workflows/publish.yml`

## Install
```bash
pip install -e .               # base
pip install -e ".[max]"        # + zstd/brotli (recommended)
pip install -e ".[full]"       # + pikepdf/soundfile (PDF/audio)
pip install -e ".[secure]"     # + cryptography (encryption)
pytest -q
```
