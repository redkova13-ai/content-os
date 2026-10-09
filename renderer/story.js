// Stories renderer: JSON [{file, photo, focus?, label, text}] -> PNG 1080x1920.
// Full-bleed photo, dark gradient at the bottom, teaser text. No Instagram-only wording:
// stories are auto-reposted to VK and Telegram.
// Usage: node story.js spec.json out_dir
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

const CHROME = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const NM = path.join(__dirname, 'node_modules/@fontsource');
const PHOTO_DIR = process.env.PHOTO_DIR || '/mnt/project-files/photo-bank/ACTIVE';
const font = (pkg, w) => `<link rel="stylesheet" href="file://${NM}/${pkg}/${w}.css">`;
const FONTS = [font('lora', 600), font('inter', 500), font('inter', 600)].join('');
const photoUrl = id => 'file://' + path.join(PHOTO_DIR, fs.readdirSync(PHOTO_DIR).find(x => x.startsWith(id + '_')));
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

const html = s => `<!doctype html><meta charset="utf-8">${FONTS}<style>
*{margin:0;box-sizing:border-box}body{width:1080px;height:1920px;overflow:hidden;background:#121214}
.ph{position:absolute;inset:0;background:url('${photoUrl(s.photo)}') ${(s.focus || [50, 25]).join('% ')}%/cover no-repeat}
.g{position:absolute;inset:0;background:linear-gradient(180deg,rgba(18,18,20,0) 35%,rgba(18,18,20,.82) 62%,rgba(18,18,20,.95) 100%)}
.box{position:absolute;left:90px;right:90px;bottom:330px;color:#F5F5F4}
.l{font:600 30px Inter;letter-spacing:4px;text-transform:uppercase;color:#E9C9A8;margin-bottom:34px}
.t{font:600 58px/1.25 Lora}
.s{position:absolute;left:90px;bottom:200px;font:500 30px Inter;color:#C9CACE}
</style><div class="ph"></div><div class="g"></div>
<div class="box"><div class="l">${esc(s.label)}</div><div class="t">${esc(s.text)}</div></div>
<div class="s">Татьяна Иргисцева · психолог, сексолог</div>`;

(async () => {
  const [specPath, outDir] = process.argv.slice(2);
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  fs.mkdirSync(outDir, { recursive: true });
  const b = await chromium.launch({ executablePath: CHROME });
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  for (const s of spec) {
    const tmp = path.join(outDir, '_s.html');
    fs.writeFileSync(tmp, html(s));
    await p.goto('file://' + tmp);
    await p.evaluate(() => document.fonts.ready);
    await p.evaluate(() => new Promise(r => { const i = new Image(); i.onload = i.onerror = r; i.src = getComputedStyle(document.querySelector('.ph')).backgroundImage.slice(5, -2); }));
    await p.waitForTimeout(150);
    await p.screenshot({ path: path.join(outDir, s.file) });
    fs.unlinkSync(tmp);
    console.log(s.file);
  }
  await b.close();
})();
