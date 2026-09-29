# Third-party notices

TurboQuant is MIT (`LICENSE`). Base install pulls:

- `Pillow` (HPND) — image lossless/lossy
- `zstandard` (BSD) — `zstd` codec (optional `max`)
- `brotli` (MIT) — `brotli` codec (optional `max`)
- `cryptography` (Apache-2.0/BSD) — `.tqze` AES-GCM (optional `secure`)
- `pikepdf` (MPL-2.0) — PDF recompress (optional `full`)
- `soundfile` (LGPL-2.1) — WAV handling (optional `full`)

External binaries (not bundled): `ffmpeg` (GPL/LGPL depending on build) for video/audio lossy.

Check exact versions in your lockfile. No vendored code.
