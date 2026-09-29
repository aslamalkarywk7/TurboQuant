# GLOSSARY

| Term | Meaning |
|---|---|
| Lossless | `decompress(compress(x)) == x` byte-identical, `sha256` verified. Default. |
| Lossy | Quality changed to hit size (images/media only, explicit opt-in). |
| Codec | Byte encoder: `zstd/brotli/lzma/bz2/gzip/store`. All lossless. |
| Transform | Pre-codec bytes reshaping: `none/delta8/xor8/delta16le/bwt/pngfilter/zdict`. All lossless + reversible. |
| Dedup | FastCDC chunks + `sha256`, unique stored once. `method=dedup`, `codec=dedup+<codec>`. |
| `.tqz` | v2 container: `TQZ2 + header_len + JSON meta + body`. Spec `docs/FORMAT.md`. |
| `.tqze` | Encrypted `.tqz`: `TQZE + header + AES-256-GCM`. Needs password. |
| `.tdelta.tqz` | Delta vs base file (new chunks only). |
| FastCDC | Content-defined chunking (avg 256KB). Like Borg/Restic. |
| Entropy | Shannon bits/byte. `≤6.5` compressible, `≥7.6` random → `store`. |
| `store` | Raw codec (no compression) for random data. Honest `ratio≈1.0`. |
| Verify | `sha256` check on decompress. `verified=True` or `VerificationError`. |
| Cert | `verify_package()` + `format_certificate()` → `PASS/FAIL` for users. |
| Bench | `benchmark()` compares `fast/balanced/max/ultra` on your file. |
| `hit_target` | Whether output met `target_bytes` (images). `False` = honest incompressible. |
