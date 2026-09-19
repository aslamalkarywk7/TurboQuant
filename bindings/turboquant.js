/**
 * TurboQuant binding for Node.js — استخدم مكتبة Python من JavaScript.
 * يعمل بطريقتين:
 *  1) CLI مباشر (الأفضل — يدعم كل codecs: zstd/lzma/brotli/dedup): python -m turboquant
 *  2) REST: python -m turboquant serve --port 8765
 *
 * npm: لا يحتاج أي dependency (يستخدم child_process + fs فقط).
 * مثال:
 *   const tq = require('./turboquant');
 *   await tq.compressLossless('report.pdf', 'report.tqz', 'max');
 *   await tq.decompress('report.tqz', 'report.pdf');
 *   console.log(tq.detectLocal('a.png')); // تخمين سريع بالامتداد
 */
const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

function run(cmd, args) {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, { maxBuffer: 64 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) return reject(new Error(stderr || err.message));
      resolve(stdout.trim());
    });
  });
}

function py() { return process.env.TURBOQUANT_PY || 'python'; }

async function compressLossless(src, dst, mode = 'balanced') {
  dst = dst || (src + '.tqz');
  const out = await run(py(), ['-m', 'turboquant', 'lossless', src, '-o', dst, '--mode', mode]);
  return { output: dst, info: out };
}

async function compressImage(src, dst, target = '800KB', mode = 'balanced') {
  const out = await run(py(), ['-m', 'turboquant', 'image', src, '-o', dst || '', '--target', target, '--mode', mode]);
  return { info: out };
}

async function decompress(src, dst) {
  const args = ['-m', 'turboquant', 'decompress', src];
  if (dst) args.push('-o', dst);
  const out = await run(py(), args);
  return { info: out };
}

async function compressViaRest(file, mode = 'max', port = 8765) {
  // POST /compress — يعيد .tqz (يستخدم fetch المدمج في Node 18+)
  const data = fs.readFileSync(file);
  const res = await fetch(`http://127.0.0.1:${port}/compress?mode=${mode}`, { method: 'POST', body: data });
  if (!res.ok) throw new Error('server error ' + res.status);
  const buf = Buffer.from(await res.arrayBuffer());
  const out = file + '.tqz';
  fs.writeFileSync(out, buf);
  return { output: out, bytes: buf.length };
}

function detectLocal(p) {
  const ext = path.extname(p).toLowerCase();
  if (['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'].includes(ext)) return 'image';
  if (['.pdf'].includes(ext)) return 'pdf';
  if (['.docx', '.xlsx', '.pptx'].includes(ext)) return 'office';
  if (['.txt', '.log', '.csv', '.json'].includes(ext)) return 'text';
  if (['.wav'].includes(ext)) return 'audio_wav';
  if (['.mp4', '.mkv'].includes(ext)) return 'video';
  return 'generic';
}

module.exports = { compressLossless, compressImage, decompress, compressViaRest, detectLocal };
