// Drive film.js in headless Chromium and write JPEG frames.
// usage: node render.mjs frames <start> <end> <outDir>     (frame indices, 30 fps)
//        node render.mjs stills <outDir> t1 t2 ...          (seconds)
//        node render.mjs times <times.json> <start> <end> <outDir>  (clean frames at listed film times)
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT_PATH || 'playwright');
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
const FPS = 30;
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.ttf': 'font/ttf', '.json': 'application/json' };

async function open() {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
  page.on('pageerror', e => console.error('[pageerror]', e));
  await page.route('http://film.local/**', route => {
    const p = decodeURIComponent(new URL(route.request().url()).pathname);
    const f = path.join(ROOT, p);
    if (!f.startsWith(ROOT) || !fs.existsSync(f)) return route.fulfill({ status: 404, body: 'nf' });
    route.fulfill({ status: 200, body: fs.readFileSync(f), contentType: TYPES[path.extname(f)] || 'application/octet-stream' });
  });
  await page.goto('http://film.local/src/waswaere/index.html');
  await page.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
  return { browser, page };
}
const save = (url, file) => fs.writeFileSync(file, Buffer.from(url.split(',')[1], 'base64'));

const [mode, ...rest] = process.argv.slice(2);
const { browser, page } = await open();
if (mode === 'stills') {
  const [dir, ...ts] = rest; fs.mkdirSync(dir, { recursive: true });
  if (process.env.CLEAN) await page.evaluate(() => { window.cleanFrame = true; });
  for (const t of ts) { const t0 = Date.now(); save(await page.evaluate(x => window.renderFrame(x), +t), path.join(dir, `t${(+t).toFixed(2)}.jpg`)); console.log(t, Date.now() - t0, 'ms'); }
} else if (mode === 'times') {
  const [file, a, b, dir] = rest; fs.mkdirSync(dir, { recursive: true });
  const ts = JSON.parse(fs.readFileSync(file, 'utf8'));
  await page.evaluate(() => { window.cleanFrame = true; });
  for (let i = +a; i < Math.min(+b, ts.length); i++) {
    const f = path.join(dir, `f${String(i).padStart(5, '0')}.jpg`);
    if (fs.existsSync(f)) continue;
    save(await page.evaluate(x => window.renderFrame(x), ts[i]), f);
    if (i % 30 === 0) console.log(`frame ${i}`);
  }
} else {
  const [a, b, dir] = rest; fs.mkdirSync(dir, { recursive: true });
  const t0 = Date.now();
  for (let i = +a; i < +b; i++) {
    const f = path.join(dir, `f${String(i).padStart(5, '0')}.jpg`);
    if (fs.existsSync(f)) continue;
    save(await page.evaluate(x => window.renderFrame(x), i / FPS), f);
    if (i % 30 === 0) console.log(`frame ${i} (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
  }
}
await browser.close();
