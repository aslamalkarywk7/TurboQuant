#!/usr/bin/env node
/**
 * tqz-decode.mjs — مفكك TurboQuant أصلي بلغة JS (بدون Python).
 * يدعم: method=single + codecs (gzip/brotli/store) + transforms
 * (none/delta8/xor8/delta16le/pngfilter/bwt). الباقي → خطأ واضح.
 * node ≥ 18. الاستخدام: node tqz-decode.mjs in.tqz out.bin
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync, brotliDecompressSync } from 'node:zlib';
import { createHash } from 'node:crypto';

export function parseTqz(buf) {
  if (buf.subarray(0, 4).toString() !== 'TQZ2') throw new Error('not a TQZ2 file');
  const hl = buf.readUInt32BE(4);
  const meta = JSON.parse(buf.subarray(8, 8 + hl).toString('utf8'));
  return { meta, body: buf.subarray(8 + hl) };
}

export function codecDecode(body, codec) {
  if (codec === 'gzip') return gunzipSync(body);
  if (codec === 'brotli') return brotliDecompressSync(body);
  if (codec === 'store') return Buffer.from(body);
  throw new Error(`codec '${codec}' needs Python (use CLI/REST): zstd/lzma/bz2/dedup/zdict`);
}

function paeth(a, b, c) {
  const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
  return (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
}

export function invertTransform(data, tid, tp = {}) {
  if (!tid || tid === 'none') return data;
  const n = data.length;
  if (tid === 'delta8' || tid === 'xor8') {
    const out = Buffer.allocUnsafe(n);
    if (!n) return out;
    out[0] = data[0];
    for (let i = 1; i < n; i++) out[i] = tid === 'delta8' ? (data[i] + out[i - 1]) & 0xff : data[i] ^ out[i - 1];
    return out;
  }
  if (tid === 'delta16le') {
    if (!n) return Buffer.alloc(0);
    const pad = data[0], raw = data.subarray(1);
    const m = raw.length >> 1, out = Buffer.allocUnsafe(raw.length);
    let acc = raw.readInt16LE(0);
    out.writeInt16LE(acc, 0);
    for (let i = 1; i < m; i++) { acc = ((acc + raw.readInt16LE(i * 2) + 32768) % 65536) - 32768; out.writeInt16LE(acc, i * 2); }
    return out.subarray(0, out.length - pad);
  }
  if (tid === 'pngfilter') {
    const origLen = data.readUInt32BE(0), stride = data.readUInt16BE(4), nrows = data.readUInt32BE(6);
    let off = 10;
    const out = [];
    let prev = Buffer.alloc(stride);
    for (let r = 0; r < nrows; r++) {
      const f = data[off]; const row = data.subarray(off + 1, off + 1 + stride); off += 1 + stride;
      const cur = Buffer.allocUnsafe(stride);
      for (let i = 0; i < stride; i++) {
        const a = i ? cur[i - 1] : 0, b = prev[i], c = i ? prev[i - 1] : 0;
        cur[i] = f === 0 ? row[i] : f === 1 ? (row[i] + a) & 0xff : f === 2 ? (row[i] + b) & 0xff
          : f === 3 ? (row[i] + ((a + b) >> 1)) & 0xff : (row[i] + paeth(a, b, c)) & 0xff;
      }
      out.push(cur); prev = cur;
    }
    return Buffer.concat(out).subarray(0, origLen);
  }
  if (tid === 'bwt') {
    const nblocks = data.readUInt32BE(0);
    let off = 4; const parts = [];
    for (let k = 0; k < nblocks; k++) {
      const blen = data.readUInt32BE(off), primary = data.readUInt32BE(off + 4); off += 8;
      const last = data.subarray(off, off + blen); off += blen;
      const cnt = new Array(256).fill(0);
      for (const b of last) cnt[b]++;
      const start = new Array(256); let s = 0;
      for (let c = 0; c < 256; c++) { start[c] = s; s += cnt[c]; }
      const occ = new Array(256).fill(0), lf = new Array(blen);
      for (let i = 0; i < blen; i++) { lf[i] = start[last[i]] + occ[last[i]]++; }
      const blk = Buffer.allocUnsafe(blen);
      let j = primary;
      for (let i = blen - 1; i >= 0; i--) { blk[i] = last[j]; j = lf[j]; }
      parts.push(blk);
    }
    return Buffer.concat(parts);
  }
  throw new Error(`transform '${tid}' needs Python`);
}

export function decodeFile(src, dst) {
  const { meta, body } = parseTqz(readFileSync(src));
  if ((meta.method || 'single') !== 'single') throw new Error(`method '${meta.method}' needs Python`);
  const raw = invertTransform(codecDecode(body, meta.codec || 'gzip'), meta.transform, meta.tparams);
  if (raw.length !== meta.orig_size) throw new Error(`size mismatch ${raw.length} != ${meta.orig_size}`);
  const sha = createHash('sha256').update(raw).digest('hex');
  if (sha !== meta.sha256) throw new Error('sha256 mismatch — corrupt file');
  if (dst) writeFileSync(dst, raw);
  return { output: dst, size: raw.length, codec: meta.codec, transform: meta.transform || 'none', verified: true };
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/'))) {
  const [, , src, dst] = process.argv;
  if (!src || !dst) { console.error('usage: node tqz-decode.mjs in.tqz out'); process.exit(2); }
  console.log(JSON.stringify(decodeFile(src, dst)));
}
