// مثال Node — نفس أسماء الدوال في كل اللغات
// npm i turboquant  (+ pip install turboquant للطرف الثاني)
const tq = require('../bindings/turboquant.js');

(async () => {
  console.log(await tq.compressLossless('report.pdf', 'report.tqz', 'max'));
  console.log(await tq.decompress('report.tqz', 'report.pdf'));
  // أو عبر REST: await tq.compressViaRest('report.pdf', 'max', 8765);
})();
