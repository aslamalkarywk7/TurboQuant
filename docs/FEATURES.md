# FEATURES — encryption, delta, parallel, media, GUI

Complements [README](../README.md) quickstart and [ARCHITECTURE](ARCHITECTURE.md) layers. All examples are copy-paste. See [FAQ](FAQ.md) for concepts and [TROUBLESHOOTING](TROUBLESHOOTING.md) for errors.

## 1. Encryption (`.tqze`, AES-256-GCM)

Needs `.[secure]` (`cryptography`). Design: compress first with [lossless](../README.md#usage-python), then encrypt container bytes. See [ARCHITECTURE](ARCHITECTURE.md#layers) and [SECURITY](../SECURITY.md#security-boundaries-what-we-guarantee).

```python
import turboquant as tq
tq.compress_lossless("backup.bin", "backup.tqz", mode="max")
tq.encrypt_file("backup.tqz", password="...")   # → backup.tqz.tqze
tq.decrypt_file("backup.tqz.tqze", "backup.tqz", password="...")
```

```bash
TURBOQUANT_PASSWORD=... python -m turboquant encrypt backup.tqz
TURBOQUANT_PASSWORD=... python -m turboquant decrypt backup.tqz.tqze -o backup.tqz
```

Rules: PBKDF2-SHA256 200k iters, header `<= 10MB` ([crypto.py](../turboquant/crypto.py)). Wrong password/tamper → `PasswordError`. Never use `--password` in production (leaks in `ps`) — use `TURBOQUANT_PASSWORD` env ([CONFIGURATION](CONFIGURATION.md)).

## 2. Incremental delta (`.tdelta.tqz`)

Stores new chunks only vs base file. Format: same dedup frame + `base_sha256/base_name/new_sha` ([FORMAT](FORMAT.md#4ب-حزمة-الدلتا-عندما-methoddelta-من-v230)).

```python
import turboquant as tq
tq.create_delta("v1.bin", "v2.bin")                        # → v2.tdelta.tqz
tq.apply_delta("v1.bin", "v2.tdelta.tqz", "v2-restored.bin")
```

```bash
python -m turboquant delta v1.bin v2.bin -o v2.tdelta.tqz
python -m turboquant apply-delta v1.bin v2.tdelta.tqz -o v2.bin
```

`apply_delta` verifies `sha256(base) == base_sha256` first (`BaseMismatchError` on mismatch), then `sha256(raw) == new_sha` (`VerificationError`).

## 3. Parallel (`jobs`)

Same bytes, less time. `jobs=1` serial, `jobs=None` or `"all"` = all cores ([parallel.py](../turboquant/parallel.py)).

```python
tq.compress_lossless("big.bin", "big.tqz", mode="max", jobs=None)
```

```bash
python -m turboquant lossless big.bin -o big.tqz --mode max --jobs all
python -m turboquant bench big.bin --jobs all
```

Note: directory branch of `compress_auto` drops `jobs` (documented limitation).

## 4. Media (needs `ffmpeg`, lossy)

Images use [README](../README.md#usage-python) `compress_image`; video/audio need external `ffmpeg` binary (not on Vercel — see [WEB](WEB.md) + [TROUBLESHOOTING](TROUBLESHOOTING.md#docker--render--vercel)).

```python
tq.compress_video("film.mp4", "film.tq.mp4", target_bytes=20*1024*1024, preset="720p")
tq.compress_audio("song.wav", "song.tq.ogg", target_bytes=5*1024*1024)
```

```bash
python -m turboquant video film.mp4 --target 20MB --preset 720p
python -m turboquant audio song.wav --target 5MB
```

WAV lossless alternative without `ffmpeg`: `optimize_lossless("a.wav")` → FLAC (same samples) via `handlers/audio.py`.

## 5. Desktop GUI (`turboquant-gui`)

```bash
turboquant-gui   # drag & drop: compress / decompress / cert, progress + cancel
```

Implementation: [gui/app.py](../gui/app.py) (`tkinter`, threaded `_work` + `CancelToken`). `cert()` runs synchronously (freezes on huge `.tqz` — see [ROADMAP](ROADMAP.md)). No tests for GUI (documented gap).

## 6. Where to go next

- Server/REST: [API](API.md) + [WEB](WEB.md) + [CONFIGURATION](CONFIGURATION.md)
- Container spec for other languages: [FORMAT](FORMAT.md) + [bindings README](../bindings/README.md)
- Measured numbers: [PERFORMANCE](PERFORMANCE.md) — rerun `bench` on your file
- Advanced transforms: [ADVANCED](ADVANCED.md)
