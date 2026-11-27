// Rendert audio/synth.js in Chromium (Web Audio API) und schreibt public/audio.wav
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.addScriptTag({ content: fs.readFileSync(path.join(__dirname, 'synth.js'), 'utf8') });
  const [L, R] = await p.evaluate(() => renderSoundtrack());
  await b.close();
  const n = L.length, data = Buffer.alloc(44 + n * 4);
  data.write('RIFF', 0); data.writeUInt32LE(36 + n * 4, 4); data.write('WAVEfmt ', 8);
  data.writeUInt32LE(16, 16); data.writeUInt16LE(1, 20); data.writeUInt16LE(2, 22); data.writeUInt32LE(48000, 24);
  data.writeUInt32LE(48000 * 4, 28); data.writeUInt16LE(4, 32); data.writeUInt16LE(16, 34); data.write('data', 36); data.writeUInt32LE(n * 4, 40);
  let peak = 0; for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
  const k = peak > 0.89 ? 0.89 / peak : 1;
  for (let i = 0; i < n; i++) {
    data.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i] * k)) * 32767), 44 + i * 4);
    data.writeInt16LE(Math.round(Math.max(-1, Math.min(1, R[i] * k)) * 32767), 46 + i * 4);
  }
  fs.writeFileSync(path.join(__dirname, '..', 'public', 'audio.wav'), data);
  console.log('audio.wav', (n / 48000).toFixed(2), 's, peak', peak.toFixed(3));
})();
