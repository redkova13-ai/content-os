const { chromium } = require('/home/user/content-os/renderer/node_modules/playwright-core');
const NM='/home/user/content-os/renderer/node_modules/@fontsource';
const [cover,out,label,text]=process.argv.slice(2);
(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome'});
const p=await b.newPage({viewport:{width:1080,height:1920}});
const fs=require('fs');fs.writeFileSync(out+'.html',`<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="file://${NM}/inter/600.css"><link rel="stylesheet" href="file://${NM}/inter/700.css"><style>
*{margin:0}body{width:1080px;height:1920px;overflow:hidden;background:#121214;position:relative}
.bg{position:absolute;inset:-80px;background:url('file://${cover}') center/cover;filter:blur(40px) brightness(.45)}
.l{position:absolute;left:60px;top:250px;font:600 36px Inter;letter-spacing:2px;text-transform:uppercase;color:#F5F5F4}
.c{position:absolute;left:60px;top:330px;width:960px;border-radius:24px;box-shadow:0 20px 60px rgba(0,0,0,.5)}
.t{position:absolute;left:60px;right:60px;top:1560px;font:700 50px/1.25 Inter;color:#F5F5F4}</style>
<div class="bg"></div><div class="l">${label}</div><img class="c" src="file://${cover}"><div class="t">${text}</div>`);await p.goto('file://'+out+'.html',{waitUntil:'networkidle'});
await p.screenshot({path:out});await b.close();})();
