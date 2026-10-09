// Content OS carousel renderer: JSON spec -> PNG slides 1080x1350.
// Templates T01–T03 follow templates/TEMPLATES.md (layout differs, palette is shared).
// Usage: node render.js spec.json out_dir
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

const W = 1080, H = 1350;
const CHROME = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const NM = path.join(__dirname, 'node_modules/@fontsource');
const font = (pkg, w, it) => `<link rel="stylesheet" href="file://${NM}/${pkg}/${w}${it ? '-italic' : ''}.css">`;
const FONTS = [
  font('montserrat', 500), font('montserrat', 700), font('montserrat', 800), font('montserrat', 800, true),
  font('lora', 600), font('lora', 600, true),
  font('inter', 400), font('inter', 500), font('inter', 600),
  font('inter-tight', 400), font('inter-tight', 500), font('inter-tight', 800), font('inter-tight', 900),
].join('');

const ACCENTS = { wine: '#7B1E33', indigo: '#2C3566', terracotta: '#A24F38' };
const LAYOUTS = ['cover', 'text', 'list', 'quote', 'steps', 'cta'];

const ICONS = {
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z"/>',
  bolt: '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><circle cx="17" cy="9" r="2.8"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M15.5 14.5a5 5 0 0 1 6 5"/>',
  msg: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6"/><path d="M12 16.5v.5"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  home: '<path d="M3 11 12 3l9 8"/><path d="M5 10v10h14V10"/>',
  brain: '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 3 3V4z"/><path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-3 3V4z"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  book: '<path d="M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z"/><path d="M20 4h-4a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h5z"/>',
};
const icon = (n, s = 34) => {
  if (!ICONS[n]) throw new Error(`unknown icon "${n}" (known: ${Object.keys(ICONS).join(', ')})`);
  return `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICONS[n]}</svg>`;
};

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// **bold**, *accent*, blank line = paragraph gap, newline = line break; short Russian words glued to the next one
const md = s => s == null ? '' : esc(s)
  .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\*(.+?)\*/g, '<em>$1</em>')
  .replace(/(^|[\s>«(])([а-яёА-ЯЁ]{1,2}) /g, '$1$2 ').replace(/(^|[\s>«(])([а-яёА-ЯЁ]{1,2}) /g, '$1$2 ')
  .replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');

let PHOTO_DIR = '/mnt/project-files/photo-bank/ACTIVE';
const photoUrl = id => {
  const f = fs.readdirSync(PHOTO_DIR).find(x => x.startsWith(id + '_') || x === id);
  if (!f) throw new Error(`photo ${id} not found in ACTIVE photo bank`);
  return 'file://' + path.join(PHOTO_DIR, f);
};
// photo as background: zoom = image width relative to the box, focus = [x%, y%]
const ph = (s, box, zoom = 1, focus = [50, 30]) => s.photo
  ? `background:url('${photoUrl(s.photo)}') ${(s.focus || focus)[0]}% ${(s.focus || focus)[1]}%/${(s.zoom || zoom) * 100}% auto no-repeat;`
  : 'background:#8E9299;';

/* ======================= T01 dark editorial ======================= */
const T01 = {
  css: `
.s{font-family:Montserrat;color:#F5F5F4;background:#121214}
.paper{background:#E9E8E6;color:#121214}
.pills{position:absolute;top:60px;left:70px;right:70px;display:flex;justify-content:space-between;z-index:3}
.pill{border:1.5px solid currentColor;border-radius:40px;padding:12px 28px;font:500 26px Montserrat}
.count{position:absolute;right:70px;bottom:60px;border:1.5px solid currentColor;border-radius:40px;padding:12px 26px;font:500 26px Montserrat;z-index:3}
.h1{font:800 104px/1.0 Montserrat;text-transform:uppercase;letter-spacing:-.01em}
.h1 .m{color:#CBC3BB}
.h2{font:800 60px/1.05 Montserrat;text-transform:uppercase}
.label{display:inline-block;background:var(--acc);color:#fff;font:800 italic 34px/1.15 Montserrat;text-transform:uppercase;padding:16px 30px}
.body{font:500 33px/1.5 Montserrat}.body b{font-weight:800}.body em{font-style:normal;color:var(--acc);font-weight:800}
.mono{filter:grayscale(.3)}
.li{display:flex;gap:26px;margin-bottom:30px;align-items:flex-start}
.li .n{flex:0 0 auto;font:800 italic 44px/1 Montserrat;color:var(--acc);min-width:64px}
.li .t{font:800 32px/1.25 Montserrat;text-transform:uppercase}.li .x{font:500 30px/1.4 Montserrat;margin-top:6px}
.qt{font:800 italic 58px/1.15 Montserrat;text-transform:uppercase}
`,
  pills: c => `<div class="pills" style="color:${c}"><div class="pill">психолог · сексолог</div><div class="pill">@irg_psy</div></div>`,
  cnt: (n, c) => `<div class="count" style="color:${c}">${n} ⟶</div>`,
  cover: (s, n) => `<div class="s"><div style="position:absolute;inset:0;${ph(s, 0, 1.1, [50, 0])}filter:grayscale(.35) brightness(.62) contrast(1.05)"></div>
   <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(18,18,20,.15) 0%,rgba(18,18,20,0) 30%,rgba(18,18,20,.88) 70%,#121214 100%)"></div>${T01.pills('#F5F5F4')}
   <div class="fit" style="position:absolute;left:70px;right:70px;top:560px;bottom:150px;display:flex;flex-direction:column;justify-content:flex-end">
     <div class="h1">${md(s.title)}${s.title2 ? `<br><span class="m">${md(s.title2)}</span>` : ''}</div>
     ${s.label ? `<div><div class="label" style="margin-top:40px">${md(s.label)}</div></div>` : ''}</div>${T01.cnt(n, '#F5F5F4')}</div>`,
  text: (s, n) => s.photo
    ? `<div class="s paper"><div class="mono" style="position:absolute;left:0;top:0;bottom:0;width:440px;${ph(s, 0, 2.4, [50, 40])}"></div>
       <div class="fit" style="position:absolute;left:440px;top:0;right:0;bottom:140px;padding:150px 64px 0 56px">
       ${s.heading ? `<div class="label" style="font-size:31px">${md(s.heading)}</div>` : ''}<div class="body" style="margin-top:44px;font-size:31px">${md(s.body)}</div></div>${T01.cnt(n, '#121214')}</div>`
    : `<div class="s paper">${T01.pills('#121214')}<div class="fit" style="position:absolute;left:70px;right:70px;top:190px;bottom:150px">
       ${s.heading ? `<div class="label">${md(s.heading)}</div>` : ''}<div class="body" style="margin-top:44px">${md(s.body)}</div></div>${T01.cnt(n, '#121214')}</div>`,
  list: (s, n) => `<div class="s paper">${T01.pills('#121214')}<div class="fit" style="position:absolute;left:70px;right:70px;top:190px;bottom:150px">
     ${s.heading ? `<div class="label">${md(s.heading)}</div>` : ''}${s.intro ? `<div class="body" style="margin-top:36px">${md(s.intro)}</div>` : ''}
     <div style="margin-top:44px">${s.items.map((it, i) => `<div class="li"><div class="n">${String(i + 1).padStart(2, '0')}</div><div><div class="t">${md(it.title)}</div>${it.text ? `<div class="x">${md(it.text)}</div>` : ''}</div></div>`).join('')}</div></div>${T01.cnt(n, '#121214')}</div>`,
  quote: (s, n) => `<div class="s">${s.photo ? `<div style="position:absolute;inset:0;${ph(s, 0, 1.2, [50, 20])}filter:grayscale(.5) brightness(.35)"></div>` : ''}${T01.pills('#F5F5F4')}
   <div class="fit" style="position:absolute;left:70px;right:70px;top:190px;bottom:150px;display:flex;flex-direction:column;justify-content:center">
     ${s.before ? `<div class="body" style="color:#D6D0CA">${md(s.before)}</div>` : ''}
     <div class="qt" style="margin:44px 0;border-left:10px solid var(--acc);padding-left:40px">«${md(s.quote)}»</div>
     ${s.after ? `<div class="body" style="color:#D6D0CA">${md(s.after)}</div>` : ''}</div>${T01.cnt(n, '#F5F5F4')}</div>`,
  steps: (s, n) => T01.list({ ...s, items: s.steps.map(x => (typeof x === 'string' ? { title: x } : x)), intro: s.intro }, n)
    .replace('</div></div><div class="count"', `</div>${s.note ? `<div class="body" style="margin-top:20px">${md(s.note)}</div>` : ''}</div><div class="count"`),
  cta: (s, n) => `<div class="s paper">${T01.pills('#121214')}
   <div class="fit" style="position:absolute;left:70px;right:70px;top:190px;bottom:${s.photo ? 470 : 150}px">
     ${s.heading ? `<div class="label">${md(s.heading)}</div>` : ''}<div class="body" style="margin-top:44px">${md(s.body)}</div></div>
   ${s.photo ? `<div style="position:absolute;left:0;right:0;bottom:0;height:420px;${ph(s, 0, 1.9, [40, 24])}filter:grayscale(.3) brightness(.8)"></div>` : ''}${T01.cnt(n, s.photo ? '#F5F5F4' : '#121214')}</div>`,
};

/* ======================= T02 soft expert ======================= */
const T02 = {
  css: `
.s{font-family:Inter;color:#2B2C30;background:#EEEDEB}
.num{position:absolute;top:60px;left:80px;font:500 26px Inter;letter-spacing:.06em;color:#8A7F76;z-index:3}
.h{font:600 76px/1.06 Lora;letter-spacing:-.01em}.h em{font-style:normal;color:var(--acc)}
.p{font:400 33px/1.45 Inter;color:#45464B}.p b{font-weight:600;color:#2B2C30}.p em{font-style:normal;color:var(--acc);font-weight:600}
.quote{background:#DDD7D1;border-radius:28px;padding:30px 38px;font:400 40px/1.3 Inter;color:#2B2C30}
.quote .q{font:600 80px/.5 Lora;color:var(--acc);display:block;margin:18px 0 6px}
.row{display:flex;align-items:center;gap:26px;background:#FFFFFF;border-radius:24px;padding:22px 28px;margin-bottom:16px}
.bub{flex:0 0 68px;height:68px;border-radius:50%;background:#E7E8EA;display:flex;align-items:center;justify-content:center;color:#5E524C}
.row .t{font:500 31px/1.3 Inter;color:#2B2C30}.row .t b{font-weight:600}.row .x{font:400 27px/1.35 Inter;color:#5E524C;margin-top:4px}
.sn{flex:0 0 68px;height:68px;border-radius:50%;background:var(--acc);color:#fff;display:flex;align-items:center;justify-content:center;font:600 34px Lora}
.arrow{position:absolute;right:70px;bottom:70px;width:84px;height:84px;border-radius:50%;border:2px solid currentColor;display:flex;align-items:center;justify-content:center;font:300 40px Inter}
`,
  num: (n, c) => `<div class="num"${c ? ` style="color:${c}"` : ''}>${n}</div>`,
  cover: (s, n) => `<div class="s" style="color:#F5F5F4"><div style="position:absolute;inset:0;${ph(s, 0, 1.6, [0, 18])}"></div>
   <div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(43,44,48,.86) 0%,rgba(43,44,48,.55) 45%,rgba(43,44,48,0) 75%)"></div>${T02.num(n, '#D6D0CA')}
   <div class="fit" style="position:absolute;left:80px;top:150px;width:620px;bottom:420px">
     <div class="h" style="font-size:90px;color:#F5F5F4">${md(s.title)}${s.title2 ? `<br><em style="color:#D6D0CA">${md(s.title2)}</em>` : ''}</div></div>
   ${s.label ? `<div class="p" style="position:absolute;left:80px;bottom:110px;width:500px;color:#E7E8EA">${md(s.label)}</div>` : ''}<div class="arrow">→</div></div>`,
  text: (s, n) => s.photo
    ? `<div class="s"><div style="position:absolute;right:0;top:0;bottom:0;width:440px;${ph(s, 0, 3.0, [60, 30])}"></div>${T02.num(n)}
       <div class="fit" style="position:absolute;left:80px;top:150px;width:520px;bottom:110px">${s.heading ? `<div class="h">${md(s.heading)}</div>` : ''}
       <div class="p" style="margin-top:36px">${md(s.body)}</div></div></div>`
    : `<div class="s">${T02.num(n)}<div class="fit" style="position:absolute;left:80px;right:80px;top:150px;bottom:110px">${s.heading ? `<div class="h">${md(s.heading)}</div>` : ''}
       <div class="p" style="margin-top:40px">${md(s.body)}</div></div></div>`,
  list: (s, n) => `<div class="s">${T02.num(n)}<div class="fit" style="position:absolute;left:80px;right:80px;top:150px;bottom:90px">
     ${s.heading ? `<div class="h">${md(s.heading)}</div>` : ''}${s.intro ? `<div class="p" style="margin:30px 0 0">${md(s.intro)}</div>` : ''}<div style="margin-top:40px">
     ${s.items.map(it => `<div class="row"><div class="bub">${icon(it.icon || 'check', 32)}</div><div><div class="t">${md(it.title)}</div>${it.text ? `<div class="x">${md(it.text)}</div>` : ''}</div></div>`).join('')}</div></div></div>`,
  quote: (s, n) => `<div class="s">${s.photo ? `<div style="position:absolute;right:0;top:0;bottom:0;width:440px;${ph(s, 0, 3.0, [60, 30])}"></div>` : ''}${T02.num(n)}
   <div class="fit" style="position:absolute;left:80px;top:150px;right:${s.photo ? 230 : 80}px;bottom:90px">
     ${s.heading ? `<div class="h" style="width:${s.photo ? 520 : 900}px">${md(s.heading)}</div>` : ''}
     ${s.before ? `<div class="p" style="margin-top:36px;width:${s.photo ? 500 : 900}px">${md(s.before)}</div>` : ''}
     <div class="quote" style="margin-top:44px"><span class="q">“</span>${md(s.quote)}</div>
     ${s.after ? `<div class="p" style="margin-top:44px;width:${s.photo ? 500 : 900}px">${md(s.after)}</div>` : ''}</div></div>`,
  steps: (s, n) => `<div class="s">${T02.num(n)}<div class="fit" style="position:absolute;left:80px;right:80px;top:150px;bottom:90px">
     ${s.heading ? `<div class="h">${md(s.heading)}</div>` : ''}${s.intro ? `<div class="p" style="margin-top:30px">${md(s.intro)}</div>` : ''}<div style="margin-top:40px">
     ${s.steps.map((x, i) => { const it = typeof x === 'string' ? { title: x } : x; return `<div class="row"><div class="sn">${i + 1}</div><div><div class="t">${md(it.title)}</div>${it.text ? `<div class="x">${md(it.text)}</div>` : ''}</div></div>`; }).join('')}</div>
     ${s.note ? `<div class="p" style="margin-top:30px">${md(s.note)}</div>` : ''}</div></div>`,
  cta: (s, n) => `<div class="s">${s.photo ? `<div style="position:absolute;right:0;top:0;bottom:0;width:440px;${ph(s, 0, 3.0, [60, 30])}"></div>` : ''}${T02.num(n)}
   <div class="fit" style="position:absolute;left:80px;top:150px;width:${s.photo ? 520 : 920}px;bottom:200px">${s.heading ? `<div class="h">${md(s.heading)}</div>` : ''}
     <div class="p" style="margin-top:36px">${md(s.body)}</div></div><div class="p" style="position:absolute;left:80px;bottom:80px;font-weight:500;color:#8A7F76">@irg_psy</div></div>`,
};

/* ======================= T03 system ======================= */
const T03 = {
  css: `
.s{font-family:'Inter Tight'}
.d{background:#121214;color:#F5F5F4}.l{background:#F5F5F4;color:#121214}
.soft{position:absolute;inset:0;opacity:.16;filter:blur(6px) grayscale(1)}
.top{position:absolute;top:56px;left:70px;right:70px;display:flex;align-items:center;gap:24px;font:500 18px 'Inter Tight';letter-spacing:.32em;text-transform:uppercase;opacity:.8;z-index:3}
.top .ln{flex:1;height:1.5px;background:currentColor;opacity:.4}
.top .c{width:54px;height:54px;border-radius:50%;background:currentColor;display:flex;align-items:center;justify-content:center;letter-spacing:0}
.top .c span{font:800 18px 'Inter Tight'}.d .top .c span{color:#121214}.l .top .c span{color:#F5F5F4}
.H{font:900 88px/1.0 'Inter Tight';text-transform:uppercase;letter-spacing:-.02em;word-spacing:.12em}
.hl{display:inline-block;background:var(--acc);color:#fff;padding:2px 20px 8px;border-radius:16px;margin:6px 0}
.H2{font:500 48px/1.1 'Inter Tight';text-transform:uppercase}
.P{font:400 33px/1.45 'Inter Tight'}.P b{font-weight:800}.P em{font-style:normal;color:var(--acc);font-weight:800}
.d .P em{color:#D6D0CA}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.cd{border-radius:26px;padding:30px;background:rgba(255,255,255,.88);border:1.5px solid #DCDDE0}
.ic{width:72px;height:72px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-bottom:22px;background:#E7E8EA;color:var(--acc)}
.ct{font:800 31px/1.15 'Inter Tight';text-transform:uppercase}.ct b{color:var(--acc)}
.cx{font:400 27px/1.35 'Inter Tight';margin-top:12px;opacity:.85}
.under{height:3px;width:55%;background:var(--acc);margin-top:20px;border-radius:2px}
.step{display:flex;align-items:center;gap:24px;border:1.5px solid rgba(255,255,255,.22);background:rgba(18,18,20,.55);border-radius:22px;padding:24px 30px}
.step .n{flex:0 0 52px;height:52px;border-radius:50%;background:var(--acc);color:#fff;display:flex;align-items:center;justify-content:center;font:800 26px 'Inter Tight'}
.step .t{font:800 31px/1.2 'Inter Tight';text-transform:uppercase}.step .x{font:400 27px/1.3 'Inter Tight';opacity:.8;margin-top:6px}
.down{text-align:center;font-size:30px;opacity:.6;margin:8px 0}
.box{border:1.5px solid rgba(255,255,255,.35);border-radius:20px;padding:22px 28px;background:rgba(18,18,20,.4)}
`,
  top: n => `<div class="top"><span>Татьяна · психолог, сексолог</span><span class="ln"></span><span class="c"><span>${n}</span></span></div>`,
  // title supports [[highlight]] for the accent bar
  hd: t => md(t).replace(/\[\[(.+?)\]\]/g, '<span class="hl">$1</span>'),
  cover: (s, n) => `<div class="s d"><div style="position:absolute;inset:0;${ph(s, 0, 1.45, [0, 24])}filter:brightness(.8)"></div>
   <div style="position:absolute;inset:0;background:linear-gradient(90deg,#121214 0%,rgba(18,18,20,.92) 38%,rgba(18,18,20,.35) 62%,rgba(18,18,20,0) 80%)"></div>${T03.top(n)}
   <div class="fit" style="position:absolute;left:70px;top:190px;width:870px;bottom:90px">
     <div class="H">${T03.hd(s.title)}</div>${s.title2 ? `<div class="H2" style="margin-top:22px;width:560px">${md(s.title2)}</div>` : ''}
     ${s.label ? `<div style="width:380px;height:2px;background:rgba(255,255,255,.3);margin:50px 0 36px"></div><div class="box" style="width:440px">
       <div style="font:800 38px/1.15 'Inter Tight';text-transform:uppercase">${md(s.label)}</div></div>` : ''}</div></div>`,
  text: (s, n) => `<div class="s l">${s.photo ? `<div class="soft" style="${ph(s, 0, 1.2, [50, 20])}"></div>` : ''}${T03.top(n)}
   <div class="fit" style="position:absolute;left:70px;right:70px;top:170px;bottom:90px">${s.heading ? `<div class="H" style="font-size:80px">${T03.hd(s.heading)}</div>` : ''}
     <div class="P" style="margin-top:44px">${md(s.body)}</div></div></div>`,
  list: (s, n) => `<div class="s l">${s.photo ? `<div class="soft" style="${ph(s, 0, 1.2, [50, 20])}"></div>` : ''}${T03.top(n)}
   <div class="fit" style="position:absolute;left:70px;right:70px;top:170px;bottom:80px">${s.heading ? `<div class="H" style="font-size:80px">${T03.hd(s.heading)}</div>` : ''}
     ${s.intro ? `<div class="P" style="margin-top:30px">${md(s.intro)}</div>` : ''}
     <div class="grid" style="margin-top:44px;${s.items.length % 2 || s.items.length > 4 ? 'grid-template-columns:1fr' : ''}">
     ${s.items.map((it, i) => `<div class="cd">${s.items.length <= 4 ? `<div class="ic">${icon(it.icon || 'check', 34)}</div>` : ''}<div class="ct"><b>${String(i + 1).padStart(2, '0')}.</b> ${md(it.title)}</div>${it.text ? `<div class="cx">${md(it.text)}</div>` : ''}${s.items.length <= 4 ? '<div class="under"></div>' : ''}</div>`).join('')}</div></div></div>`,
  quote: (s, n) => `<div class="s d">${s.photo ? `<div class="soft" style="${ph(s, 0, 1.2, [50, 30])}opacity:.22"></div>` : ''}${T03.top(n)}
   <div class="fit" style="position:absolute;left:70px;right:70px;top:180px;bottom:90px;display:flex;flex-direction:column;justify-content:center">
     ${s.heading ? `<div class="H" style="font-size:72px">${T03.hd(s.heading)}</div>` : ''}${s.before ? `<div class="P" style="margin-top:36px">${md(s.before)}</div>` : ''}
     <div class="box" style="margin:44px 0;font:800 50px/1.2 'Inter Tight';text-transform:uppercase;border-color:var(--acc);border-width:3px">«${md(s.quote)}»</div>
     ${s.after ? `<div class="P">${md(s.after)}</div>` : ''}</div></div>`,
  steps: (s, n) => `<div class="s d">${s.photo ? `<div class="soft" style="${ph(s, 0, 1.2, [50, 30])}opacity:.22"></div>` : ''}${T03.top(n)}
   <div class="fit" style="position:absolute;left:70px;right:70px;top:180px;bottom:80px">${s.heading ? `<div class="H" style="font-size:80px">${T03.hd(s.heading)}</div>` : ''}
     ${s.intro ? `<div class="P" style="margin-top:30px">${md(s.intro)}</div>` : ''}<div style="margin:44px 40px 0">
     ${s.steps.map((x, i) => { const it = typeof x === 'string' ? { title: x } : x; return `<div class="step"><div class="n">${i + 1}</div><div><div class="t">${md(it.title)}</div>${it.text ? `<div class="x">${md(it.text)}</div>` : ''}</div></div>`; }).join('<div class="down">↓</div>')}</div>
     ${s.note ? `<div class="P" style="margin-top:40px;opacity:.85">${md(s.note)}</div>` : ''}</div></div>`,
  cta: (s, n) => `<div class="s d">${s.photo ? `<div style="position:absolute;inset:0;${ph(s, 0, 1.45, [0, 24])}filter:brightness(.7)"></div><div style="position:absolute;inset:0;background:linear-gradient(90deg,#121214 0%,rgba(18,18,20,.9) 45%,rgba(18,18,20,.2) 80%)"></div>` : ''}${T03.top(n)}
   <div class="fit" style="position:absolute;left:70px;top:190px;width:${s.photo ? 640 : 940}px;bottom:90px">${s.heading ? `<div class="H" style="font-size:80px">${T03.hd(s.heading)}</div>` : ''}
     <div class="P" style="margin-top:44px">${md(s.body)}</div><div class="box" style="margin-top:50px;display:inline-block;font:800 30px 'Inter Tight';letter-spacing:.06em">@IRG_PSY</div></div></div>`,
};

const TEMPLATES = { T01, T02, T03 };

function validate(spec) {
  const errs = [];
  if (!TEMPLATES[spec.template]) errs.push(`TEMPLATE ID "${spec.template}" not allowed (T01/T02/T03 only)`);
  if (spec.accent && !ACCENTS[spec.accent]) errs.push(`accent "${spec.accent}" not in palette (${Object.keys(ACCENTS).join('/')})`);
  if (!Array.isArray(spec.slides) || !spec.slides.length) errs.push('no slides');
  (spec.slides || []).forEach((s, i) => {
    const at = `slide ${i + 1}`;
    if (!LAYOUTS.includes(s.layout)) errs.push(`${at}: unknown layout "${s.layout}" (allowed: ${LAYOUTS.join(', ')})`);
    if (s.layout === 'cover' && !s.title) errs.push(`${at}: cover needs title`);
    if (s.layout === 'cover' && i !== 0) errs.push(`${at}: cover must be slide 1`);
    if ((s.layout === 'text' || s.layout === 'cta') && !s.body) errs.push(`${at}: ${s.layout} needs body`);
    if (s.layout === 'list' && !(s.items && s.items.length)) errs.push(`${at}: list needs items`);
    if (s.layout === 'steps' && !(s.steps && s.steps.length)) errs.push(`${at}: steps needs steps`);
    if (s.layout === 'quote' && !s.quote) errs.push(`${at}: quote needs quote`);
    if (s.photo) try { photoUrl(s.photo); } catch (e) { errs.push(`${at}: ${e.message}`); }
  });
  return errs;
}

async function render(spec, outDir) {
  if (spec.photo_dir) PHOTO_DIR = spec.photo_dir;
  const errs = validate(spec);
  if (errs.length) throw Object.assign(new Error('BLOCKED:\n' + errs.join('\n')), { blocked: true });
  const T = TEMPLATES[spec.template];
  const acc = ACCENTS[spec.accent || { T01: 'wine', T02: 'terracotta', T03: 'indigo' }[spec.template]];
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ executablePath: CHROME });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const report = [];
  const N = spec.slides.length;
  try {
    for (let i = 0; i < N; i++) {
      const s = spec.slides[i];
      const n = spec.template === 'T02' ? `${String(i + 1).padStart(2, '0')}/${String(N).padStart(2, '0')}` : `${i + 1}/${N}`;
      const html = `<!doctype html><html><head><meta charset="utf-8">${FONTS}<style>:root{--acc:${acc}}*{box-sizing:border-box;margin:0;padding:0}
html,body{width:${W}px;height:${H}px;overflow:hidden}.s{position:relative;width:${W}px;height:${H}px;overflow:hidden}${T.css}</style></head><body>${T[s.layout](s, n)}</body></html>`;
      const tmp = path.join(outDir, `_slide.html`);
      fs.writeFileSync(tmp, html);
      await page.goto('file://' + tmp, { waitUntil: 'load' });
      await page.evaluate(() => document.fonts.ready);
      // shrink text block until it fits its box (not below 72%), report overflow otherwise
      const fit = await page.evaluate(grow => {
        const box = document.querySelector('.fit');
        if (!box) return { zoom: 1, ok: true };
        // scale an inner wrapper, so the box keeps its position and size
        const inner = document.createElement('div');
        while (box.firstChild) inner.appendChild(box.firstChild);
        box.appendChild(inner);
        const rb = box.getBoundingClientRect();
        const h = () => inner.getBoundingClientRect().height;
        const fits = () => h() <= rb.height + 2 && inner.scrollWidth <= inner.clientWidth + 2;
        let z = 1;
        const set = k => { z = +k.toFixed(2); inner.style.zoom = z; };
        while (!fits() && z > 0.72) set(z - 0.02);
        // sparse slide: grow text up to 125% while it fills less than 80% of the box
        if (z === 1 && grow) { while (z < 1.25 && h() <= rb.height * 0.8) set(z + 0.02); while (!fits() && z > 1) set(z - 0.02); }
        return { zoom: z, ok: fits() };
      }, s.layout !== 'cover');
      await page.waitForTimeout(150);
      const file = path.join(outDir, `slide_${String(i + 1).padStart(2, '0')}.png`);
      await page.screenshot({ path: file });
      fs.unlinkSync(tmp);
      report.push({ slide: i + 1, layout: s.layout, file: path.basename(file), text_scale: fit.zoom, fits: fit.ok });
    }
  } finally { await browser.close(); }
  fs.writeFileSync(path.join(outDir, 'render_report.json'), JSON.stringify({ template: spec.template, accent: spec.accent || null, slides: report }, null, 2));
  return report;
}

module.exports = { render, validate, LAYOUTS, ICONS: Object.keys(ICONS) };

if (require.main === module) {
  const [specPath, outDir] = process.argv.slice(2);
  if (!specPath || !outDir) { console.error('usage: node render.js spec.json out_dir'); process.exit(2); }
  render(JSON.parse(fs.readFileSync(specPath, 'utf8')), outDir).then(r => {
    for (const x of r) console.log(`${x.file}  ${x.layout}  scale=${x.text_scale}${x.fits ? '' : '  OVERFLOW'}`);
    process.exit(r.every(x => x.fits) ? 0 : 1);
  }).catch(e => { console.error(e.message); process.exit(e.blocked ? 3 : 1); });
}
