// Renders every on-screen line as a transparent 1920x1080 PNG (Chromium handles Arabic shaping and kashida).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const fontDir = path.join(__dirname, 'node_modules/@fontsource');
const plex = w => `file://${fontDir}/ibm-plex-sans-arabic/files/ibm-plex-sans-arabic-arabic-${w}-normal.woff2`;
const plexLat = w => `file://${fontDir}/ibm-plex-sans-arabic/files/ibm-plex-sans-arabic-latin-${w}-normal.woff2`;
const corm = w => `file://${fontDir}/cormorant-garamond/files/cormorant-garamond-latin-${w}-normal.woff2`;

const css = `
@font-face{font-family:Plex;font-weight:200;src:url(${plex(200)})}
@font-face{font-family:Plex;font-weight:300;src:url(${plex(300)})}
@font-face{font-family:Plex;font-weight:500;src:url(${plex(500)})}
@font-face{font-family:PlexL;font-weight:300;src:url(${plexLat(300)})}
@font-face{font-family:Corm;font-weight:400;src:url(${corm(400)})}
html,body{margin:0;width:1920px;height:1080px;background:transparent;overflow:hidden}
.c{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column}
.line{font-family:Plex;font-weight:300;color:#F3EADC;font-size:64px;direction:rtl;letter-spacing:0;
  text-shadow:0 2px 30px rgba(20,12,6,.55)}
.big{font-size:96px;font-weight:200}
.logo{font-family:Plex;font-weight:500;font-size:190px;color:#F3EADC;direction:rtl;line-height:1}
.lat{font-family:Corm;font-size:44px;letter-spacing:22px;color:#E9DCC6;margin-top:28px;padding-left:22px}
.tag{position:absolute;font-family:PlexL;font-weight:300;font-size:22px;color:rgba(243,234,220,.55);letter-spacing:2px}
.chap{position:absolute;font-family:Plex;font-weight:300;font-size:24px;color:rgba(243,234,220,.6);direction:rtl}
.ph{font-family:PlexL;font-weight:300;font-size:20px;letter-spacing:3px;color:rgba(243,234,220,.5);margin-top:40px}
`;

const k = n => 'السالفة أعـ' + 'ـ'.repeat(n) + 'مـ' + 'ـ'.repeat(n) + 'ق';
const items = {
  t1: `<div class="c"><div class="line">مو كل شيء يبان من أول نظرة</div></div>`,
  t2: `<div class="c"><div class="line big">للأصل أثر</div></div>`,
  t3: `<div class="c"><div class="line">وفي التفاصيل اللي يصنع الفرق</div></div>`,
  t5: `<div class="c"><div class="line">أشياء كثيرة تسبق لحظة بسيطة</div></div>`,
  t6: `<div class="c"><div class="line">السالفة ما بدت اليوم</div></div>`,
  t7: `<div class="c"><div class="line">لكن اليوم، نشوف السالفة الأعـــــمـــــق</div></div>`,
  logo: `<div class="c"><div class="logo">سويل</div><div class="lat">SOIL</div><div class="ph">LOGO PLACEHOLDER</div></div>`,
  close1: `<div class="c" style="top:-120px"><div class="logo" style="font-size:120px">سويل.</div></div>`,
  close2: `<div class="c" style="top:120px"><div class="line" style="font-size:52px">من التربة.. إلى كوب يليق بذائقتك.</div></div>`,
  tag: `<div class="tag" style="left:56px;top:44px">SOIL HERO FILM  /  PRELIMINARY MOCKUP</div>`,
  label: `<div class="c"><div class="logo" style="font-size:150px;color:#3b2a1e">سويل</div><div class="lat" style="color:#3b2a1e;font-size:34px">SOIL ROASTERY</div></div>`,
};
for (let n = 0; n <= 14; n++) items['t4_' + n] = `<div class="line big" id="kk" style="position:absolute;top:50%;transform:translateY(-50%);right:RIGHTPX">${k(n)}</div>`;
const chaps = {
  ch1: 'المشهد الأول | ما لا نعرفه', ch2: 'المشهد الثاني | ما يصنع الفرق', ch3: 'المشهد الثالث | ما اعتدناه',
  ch4: 'المشهد الرابع | الكشف', ch5: 'المشهد الختامي',
};
for (const [id, t] of Object.entries(chaps)) items[id] = `<div class="chap" style="right:56px;top:40px">${t}</div>`;

(async () => {
  const out = path.join(__dirname, 'text');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  // anchor the kashida line so the start of the phrase stays still while the word stretches
  await page.setContent(`<html><head><meta charset="utf-8"><style>${css}</style></head><body>${items['t4_14'].replace('RIGHTPX','0px')}</body></html>`);
  await page.evaluate(() => document.fonts.ready);
  const w14 = await page.evaluate(() => document.getElementById('kk').getBoundingClientRect().width);
  for (let n = 0; n <= 14; n++) items['t4_' + n] = items['t4_' + n].replace('RIGHTPX', Math.round((1920 - w14) / 2) + 'px');
  for (const [id, html] of Object.entries(items)) {
    await page.setContent(`<html><head><meta charset="utf-8"><style>${css}</style></head><body>${html}</body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(out, id + '.png'), omitBackground: true });
  }
  await browser.close();
  console.log(Object.keys(items).length, 'text frames');
})();
