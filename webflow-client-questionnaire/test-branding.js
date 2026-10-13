// Playwright checks for the branding / graphic design questionnaire preview (python3 build.py branding first)
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const SHOTS = path.join(__dirname, 'shots');
fs.mkdirSync(SHOTS, { recursive: true });
const url = 'file://' + path.join(__dirname, 'out-branding', 'preview.html');

const results = [];
function check(name, ok, extra) { results.push({ name, ok: !!ok, extra }); }

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  page.on('pageerror', e => check('no page error: ' + e.message, false));
  await page.goto(url);
  await page.waitForTimeout(300);

  const vis = async () => page.$$eval('.cq-step', els => els.filter(e => !e.classList.contains('cq-skip') && !e.classList.contains('cq-hidden')).length);
  const active = async () => page.$eval('.cq-step.is-active', e => e.getAttribute('data-step'));
  const next = async () => { await page.click('[data-nav=next]'); await page.waitForTimeout(150); };
  const hidden = async id => page.$eval('.cq-q[data-q="' + id + '"]', e => !!e.closest('.cq-hidden'));

  check('js initialised', await page.$eval('.cq-page', e => e.classList.contains('cq-js')));
  check('8 steps before choosing new / existing (section 03 hidden)', (await vis()) === 8, await vis());
  await next();
  check('About You is required', (await active()) === '00');
  await page.fill('input[name="00.1 Brand / Company Name"]', 'Test Brand');
  await page.fill('input[name="00.2 Primary Contact"]', 'Jane, Founder, jane@example.com');
  await next();
  check('step 01', (await active()) === '01');
  check('01.2 hidden until existing brand', await hidden('01-2'));
  await next();
  check('starting point is required', (await active()) === '01' && await page.$eval('.cq-q[data-q="01-1"]', e => e.classList.contains('is-invalid')));
  await page.click('.cq-q[data-q="01-1"] .cq-opt[data-opt="New Brand"]'); await page.waitForTimeout(100);
  check('new brand -> 8 steps, 01.2 hidden', (await vis()) === 8 && await hidden('01-2'));
  await page.click('.cq-q[data-q="01-1"] .cq-opt[data-opt="Existing Brand"]'); await page.waitForTimeout(100);
  check('existing brand -> 9 steps, 01.2 shown', (await vis()) === 9 && !(await hidden('01-2')), await vis());
  const lf = await page.$$eval('.cq-q[data-q="01-2"] .cq-opt', els => els.map(e => e.getAttribute('data-opt') + (e.querySelector('img') ? ' +img' : '') + (e.querySelector('.cq-opt-desc') ? ' +desc' : '')));
  check('01.2 four pictures with descriptions + Not sure card', JSON.stringify(lf) === '["Refine +img +desc","Uplift +img +desc","Adapt +img +desc","Explore +img +desc","Not sure +desc"]', lf);
  check('01.2 Not sure coloured', await page.$eval('.cq-q[data-q="01-2"] .cq-opt[data-opt="Not sure"]', e => e.classList.contains('cq-opt-unsure')));
  await page.click('.cq-q[data-q="01-2"] .cq-opt[data-opt="Uplift"]');
  await page.screenshot({ path: path.join(SHOTS, 'b-01.png'), fullPage: true });
  await next();
  check('step 02', (await active()) === '02');
  await page.click('.cq-q[data-q="02-1"] .cq-opt[data-opt="The brand has evolved"]');
  await page.fill('textarea[name="02.2 What changed / what is missing"]', 'We grew into new markets.');
  await next();
  check('step 03 for existing brand', (await active()) === '03');
  await page.click('.cq-q[data-q="03-1"] .cq-opt[data-opt="Noticeable"]');
  await page.click('.cq-q[data-q="03-2"] .cq-opt[data-opt="Colours"]');
  await next();
  check('step 04', (await active()) === '04');
  const sizes = await page.$$eval('.cq-q[data-q="04-1"] .cq-opt-pic', els => [...new Set(els.map(e => Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height) + ' ' + getComputedStyle(e).objectFit))]);
  check('04.1: 20 pictures, all one 16:9 size, not cropped', (await page.$$('.cq-q[data-q="04-1"] .cq-opt-pic')).length === 20 && sizes.length === 1 && /contain/.test(sizes[0]), sizes);
  for (const o of ['Premium', 'Modern', 'Bold', 'Minimal', 'Timeless', 'Warm']) await page.click('.cq-q[data-q="04-1"] .cq-opt[data-opt="' + o + '"]');
  check('04.1 max 5', (await page.$$eval('.cq-q[data-q="04-1"] input:checked', e => e.length)) === 5 && (await page.$eval('.cq-q[data-q="04-1"] .cq-count', e => e.textContent)) === '5 of 5 selected');
  const avoidExtra = await page.$$eval('.cq-q[data-q="04-2"] .cq-options-extra .cq-opt', els => els.map(e => e.getAttribute('data-opt')));
  check('04.2: 8 pictures + Dated / Too traditional / Other cards', (await page.$$('.cq-q[data-q="04-2"] .cq-opt-pic')).length === 8 && JSON.stringify(avoidExtra) === '["Dated","Too traditional","Other"]', avoidExtra);
  for (const o of ['Generic', 'Dated', 'Too loud', 'Too serious']) await page.click('.cq-q[data-q="04-2"] .cq-opt[data-opt="' + o + '"]');
  check('04.2 max 3', (await page.$$eval('.cq-q[data-q="04-2"] input:checked', e => e.length)) === 3);
  await page.screenshot({ path: path.join(SHOTS, 'b-04.png'), fullPage: true });
  await next();
  await page.click('.cq-q[data-q="05-1"] .cq-opt[data-opt="New customers"]');
  await page.click('.cq-q[data-q="05-2"] .cq-opt[data-opt="Not sure"]');
  await next();
  check('step 06', (await active()) === '06');
  check('references follow-ups hidden', await hidden('06-1b') && await hidden('06-2'));
  await page.click('.cq-q[data-q="06-1"] .cq-opt[data-opt="Yes"]'); await page.waitForTimeout(100);
  check('Yes shows upload box + likes', !(await hidden('06-1b')) && !(await hidden('06-2')) && !!(await page.$('.cq-q[data-q="06-1b"] .cq-upload input[type=file]')));
  await page.fill('textarea[name="06.1 References — links"]', 'https://example.com/moodboard');
  await page.click('.cq-q[data-q="06-2"] .cq-opt[data-opt="Typography"]');
  await next();
  await page.click('.cq-q[data-q="07-1"] .cq-opt[data-opt="A refreshed visual identity"]');
  await page.click('.cq-q[data-q="07-2"] .cq-opt[data-opt="“It should clearly feel like an updated version of us”"]');
  await next();
  check('last step 08', (await active()) === '08' && await page.$eval('.cq-nav', e => e.classList.contains('is-last')));
  check('08.1 shown for existing brand', !(await hidden('08-1')));
  await page.click('.cq-q[data-q="08-1"] .cq-opt[data-opt="I want a noticeable refresh while keeping the brand recognisable"]');
  await page.click('.cq-btn-submit'); await page.waitForTimeout(300);
  const subs = await page.evaluate(() => window.__submissions);
  const p = subs[0] || {};
  fs.writeFileSync(path.join(SHOTS, 'b-payload.json'), JSON.stringify(p, null, 2));
  check('submitted', subs.length === 1);
  check('payload starting point', p['01.1 Starting point'] === 'Existing Brand' && p['01.2 Looking for'] === 'Uplift');
  check('payload feel', p['04.1 Brand should feel'] === 'Premium, Modern, Bold, Minimal, Timeless', p['04.1 Brand should feel']);
  check('payload not feel', p['04.2 Brand should NOT feel'] === 'Generic, Too loud, Dated', p['04.2 Brand should NOT feel']);
  check('payload expectation', p['08.1 Expectation'] === 'I want a noticeable refresh while keeping the brand recognisable');
  check('no stray option names', !Object.keys(p).some(k => ['Premium', 'Other', 'Yes', 'Colours'].includes(k)));

  // new brand path skips the existing-brand questions
  const p2 = await ctx.newPage();
  await p2.goto(url); await p2.waitForTimeout(300);
  await p2.fill('input[name="00.1 Brand / Company Name"]', 'New Co'); await p2.fill('input[name="00.2 Primary Contact"]', 'Sam');
  await p2.click('[data-nav=next]'); await p2.waitForTimeout(150);
  await p2.click('.cq-q[data-q="01-1"] .cq-opt[data-opt="New Brand"]');
  const order = [];
  for (let i = 0; i < 10; i++) { order.push(await p2.$eval('.cq-step.is-active', e => e.getAttribute('data-step'))); if (await p2.$eval('.cq-nav', e => e.classList.contains('is-last'))) break; await p2.click('[data-nav=next]'); await p2.waitForTimeout(120); }
  check('new brand skips section 03', JSON.stringify(order) === '["01","02","04","05","06","07","08"]', order);
  check('new brand hides 07.2 and 08.1', await p2.$eval('.cq-q[data-q="07-2"]', e => !!e.closest('.cq-hidden')) && await p2.$eval('.cq-q[data-q="08-1"]', e => !!e.closest('.cq-hidden')));

  const m = await (await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 })).newPage();
  await m.goto(url); await m.waitForTimeout(300);
  check('no horizontal overflow on mobile', !(await m.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)));

  await browser.close();
  const bad = results.filter(r => !r.ok);
  results.forEach(r => console.log((r.ok ? 'PASS ' : 'FAIL ') + r.name + (r.extra !== undefined ? '  [' + JSON.stringify(r.extra) + ']' : '')));
  console.log(bad.length ? bad.length + ' FAILURES' : 'ALL PASSED');
  process.exit(bad.length ? 1 : 0);
})();
