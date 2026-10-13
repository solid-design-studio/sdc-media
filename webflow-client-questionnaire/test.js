// Playwright checks for the questionnaire preview (stepper, limits, conditionals, payload)
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const OUT = path.join(__dirname, 'out');
const SHOTS = path.join(__dirname, 'shots');
fs.mkdirSync(SHOTS, { recursive: true });
const url = 'file://' + path.join(OUT, 'preview.html');

const results = [];
function check(name, ok, extra) { results.push({ name, ok: !!ok, extra }); }

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  page.on('pageerror', e => check('no page error: ' + e.message, false));
  await page.goto(url);
  await page.waitForTimeout(300);

  const vis = async () => page.$$eval('.cq-step', els => els.filter(e => !e.classList.contains('cq-skip')).length);
  const active = async () => page.$eval('.cq-step.is-active', e => e.getAttribute('data-step'));
  const stepLabel = async () => page.$eval('[data-cq-step-label]', e => e.textContent);

  check('js initialised (cq-js)', await page.$eval('.cq-page', e => e.classList.contains('cq-js')));
  check('11 visible steps initially (Section 08 hidden until a matching project type is chosen)', (await vis()) === 11, await vis());
  check('step 01 active', (await active()) === '01');
  await page.screenshot({ path: path.join(SHOTS, 'd-01.png'), fullPage: true });

  // Next without required -> error
  await page.click('[data-nav=next]');
  await page.waitForTimeout(200);
  check('blocked on required fields', (await active()) === '01' && await page.$eval('[data-cq-error]', e => e.classList.contains('is-on')));
  await page.screenshot({ path: path.join(SHOTS, 'd-01-error.png'), fullPage: false });

  await page.fill('input[name="01.1 Project / Brand Name"]', 'Test Café');
  await page.fill('input[name="01.2 Primary Contact"]', 'Jane Doe, Owner');
  await page.fill('input[name="01.3 Project Location / Venue"]', 'Riyadh');
  await page.click('.cq-q[data-q="01-4"] .cq-opt[data-opt="Interior Design"]');
  await page.click('.cq-q[data-q="01-4"] .cq-opt[data-opt="Other"]');
  await page.waitForTimeout(100);
  check('other field revealed (01-4)', await page.$eval('.cq-q[data-q="01-4"] .cq-other', e => e.classList.contains('is-on')));
  await page.fill('.cq-q[data-q="01-4"] .cq-other input', 'Acoustic design');
  await page.click('.cq-q[data-q="01-5"] .cq-opt[data-opt="F&B / Restaurant / Café"]');
  await page.waitForTimeout(100);
  check('card selected class', await page.$eval('.cq-q[data-q="01-4"] .cq-opt[data-opt="Interior Design"]', e => e.classList.contains('is-selected')));
  check('compiled 01-4', (await page.$eval('input[name="01.4 Looking for from Solid"]', e => e.value)) === 'Interior Design, Other: Acoustic design', await page.$eval('input[name="01.4 Looking for from Solid"]', e => e.value));

  await page.click('[data-nav=next]');
  await page.waitForTimeout(200);
  check('moved to step 02', (await active()) === '02');
  // max 3 goals
  const goals = ['Improve functionality', 'Launching a new brand', 'Improve customer / visitor experience', 'Strengthen the brand presence'];
  for (const g of goals) { await page.click('.cq-q[data-q="02-2"] .cq-opt[data-opt="' + g + '"]'); await page.waitForTimeout(50); }
  const checkedGoals = await page.$$eval('.cq-q[data-q="02-2"] input:checked', els => els.length);
  check('max 3 enforced', checkedGoals === 3, checkedGoals);
  check('4th option disabled', await page.$eval('.cq-q[data-q="02-2"] .cq-opt[data-opt="Strengthen the brand presence"]', e => e.classList.contains('is-disabled')));
  check('counter text', (await page.$eval('.cq-q[data-q="02-2"] .cq-count', e => e.textContent)) === '3 of 3 selected');
  await page.screenshot({ path: path.join(SHOTS, 'd-02.png'), fullPage: true });

  await page.click('[data-nav=next]'); await page.waitForTimeout(150);
  await page.click('.cq-q[data-q="03-1"] .cq-opt[data-opt="Noticeable Transformation"]');
  await page.screenshot({ path: path.join(SHOTS, 'd-03.png'), fullPage: true });
  await page.click('[data-nav=next]'); await page.waitForTimeout(150);
  check('step 04', (await active()) === '04');
  check('04-2b hidden initially', await page.$eval('.cq-q[data-q="04-2b"]', e => e.classList.contains('cq-hidden')));
  await page.click('.cq-q[data-q="04-2"] .cq-opt[data-opt="Yes"]'); await page.waitForTimeout(100);
  check('04-2b shown after Yes', !(await page.$eval('.cq-q[data-q="04-2b"]', e => e.classList.contains('cq-hidden'))));
  await page.fill('textarea[name="04.2 New audience — who"]', 'Tourists and families');
  await page.click('.cq-q[data-q="04-2"] .cq-opt[data-opt="No"]'); await page.waitForTimeout(100);
  check('04-2b hidden + cleared after No', (await page.$eval('.cq-q[data-q="04-2b"]', e => e.classList.contains('cq-hidden'))) && (await page.$eval('textarea[name="04.2 New audience — who"]', e => e.value)) === '');
  await page.click('.cq-q[data-q="04-2"] .cq-opt[data-opt="Yes"]'); await page.waitForTimeout(100);
  await page.fill('textarea[name="04.2 New audience — who"]', 'Tourists');
  await page.screenshot({ path: path.join(SHOTS, 'd-04.png'), fullPage: true });

  await page.click('[data-nav=next]'); await page.waitForTimeout(150);
  await page.click('.cq-q[data-q="05-3"] .cq-opt[data-opt="Modern Luxury"]');
  await page.click('.cq-q[data-q="05-3"] .cq-opt[data-opt="Warm Minimalism"]');
  check('no picture placeholders', (await page.$$('.cq-opt-nopic')).length === 0);
  const ticks = await page.$$eval('.cq-q[data-q="05-3"] .cq-options-extra .cq-opt', els => els.map(e => e.getAttribute('data-opt') + (e.querySelector('img') ? ' +img' : '')));
  check('05-3 extra option cards under "Or choose"', JSON.stringify(ticks) === '["A blend of different directions","Not sure — open to exploration"]' && !!(await page.$('.cq-q[data-q="05-3"] .cq-or')), ticks);
  const unsure = await page.$$eval('.cq-opt-unsure', els => els.map(e => e.getAttribute('data-opt')));
  check('every Not sure option is coloured', unsure.length === 14 && unsure.every(t => /not sure/i.test(t)), unsure.length);
  check('Not sure colour differs', (await page.$eval('.cq-q[data-q="05-3"] .cq-opt-unsure', e => getComputedStyle(e).backgroundColor)) !== (await page.$eval('.cq-q[data-q="05-3"] .cq-options-extra .cq-opt:not(.cq-opt-unsure)', e => getComputedStyle(e).backgroundColor)));
  check('traditional has a picture', !!(await page.$('.cq-q[data-q="05-3"] .cq-opt-img[data-opt="Traditional / Heritage-inspired"] img')));
  const fit = await page.$$eval('.cq-q[data-q="05-3"] .cq-opt-pic, .cq-q[data-q="06-3"] .cq-opt-pic', els => [...new Set(els.map(e => getComputedStyle(e).objectFit))]);
  check('pictures fitted whole, not cropped', JSON.stringify(fit) === '["contain"]', fit);
  const sizes = await page.$$eval('.cq-q[data-q="05-3"] .cq-opt-pic', els => [...new Set(els.map(e => Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height)))]);
  check('05-3 pictures all one size', sizes.length === 1, sizes);
  check('blend box hidden first', !(await page.$eval('.cq-other[data-for="A blend of different directions"]', e => e.classList.contains('is-on'))));
  await page.click('.cq-q[data-q="05-3"] .cq-opt[data-opt="A blend of different directions"]');
  check('blend box shown', await page.$eval('.cq-other[data-for="A blend of different directions"]', e => e.classList.contains('is-on')));
  await page.fill('textarea[name="05.3 Creative direction — Blend"]', 'Warm minimal with heritage arches');
  await page.screenshot({ path: path.join(SHOTS, 'd-05.png'), fullPage: true });
  await page.click('[data-nav=next]'); await page.waitForTimeout(150);
  check('step 06', (await active()) === '06');
  check('06-7 hidden until refs', await page.$eval('.cq-q[data-q="06-7"]', e => e.classList.contains('cq-hidden')));
  await page.click('.cq-q[data-q="06-5"] .cq-opt[data-opt="Yes"]'); await page.waitForTimeout(100);
  check('06-5b + 06-7 shown', !(await page.$eval('.cq-q[data-q="06-5b"]', e => e.classList.contains('cq-hidden'))) && !(await page.$eval('.cq-q[data-q="06-7"]', e => e.classList.contains('cq-hidden'))));
  await page.click('.cq-q[data-q="06-1"] .cq-opt[data-opt="Warm neutrals"]');
  const ticks6 = await page.$$eval('.cq-q[data-q="06-1"] .cq-options-extra .cq-opt', els => els.map(e => e.getAttribute('data-opt')));
  check('06-1 Other / Not sure are option cards', JSON.stringify(ticks6) === '["Other","Not sure"]', ticks6);
  check('06-5b has an upload box', !!(await page.$('.cq-q[data-q="06-5b"] .cq-upload input[type=file]')) && !!(await page.$('.cq-q[data-q="06-5b"] input[type=hidden][name="06.5 Visual references — Files"]')));
  await page.click('.cq-q[data-q="06-1"] .cq-opt[data-opt="Other"]');
  check('06-1 other box shown', await page.$eval('.cq-q[data-q="06-1"] .cq-other[data-for="Other"]', e => e.classList.contains('is-on')));
  await page.fill('input[name="06.1 Colour direction — Other"]', 'Sage green');
  await page.click('.cq-q[data-q="06-3"] .cq-opt[data-opt="Terrazzo"]');
  await page.screenshot({ path: path.join(SHOTS, 'd-06.png'), fullPage: true });
  await page.click('[data-nav=next]'); await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(SHOTS, 'd-07.png'), fullPage: true });
  await page.click('[data-nav=next]'); await page.waitForTimeout(150);
  check('step 08 reached (F&B)', (await active()) === '08');
  const subsVisible = await page.$$eval('.cq-sub', els => els.filter(e => !e.classList.contains('cq-hidden')).map(e => e.getAttribute('data-sub')));
  check('only sub A visible', JSON.stringify(subsVisible) === '["A"]', subsVisible);
  await page.click('.cq-q[data-q="08A-1"] .cq-opt[data-opt="Café"]');
  await page.fill('input[name="08A.3 Seating — Indoor"]', '40');
  await page.click('.cq-q[data-q="08A-4"] .cq-opt[data-opt="Coffee Bar"]');
  await page.screenshot({ path: path.join(SHOTS, 'd-08.png'), fullPage: true });
  for (const n of ['09', '10', '11', '12']) { await page.click('[data-nav=next]'); await page.waitForTimeout(150); await page.screenshot({ path: path.join(SHOTS, 'd-' + n + '.png'), fullPage: true }); }
  check('last step 12', (await active()) === '12');
  await page.click('[data-nav=back]'); await page.waitForTimeout(150);
  check('page 11 callout', /Tick every item you can send us/.test(await page.$eval('.cq-step.is-active .cq-callout', e => e.textContent)));
  check('checklist count starts at 0 of 6', (await page.$eval('.cq-q[data-q="11-1"] .cq-count', e => e.textContent)) === '0 of 6 ticked');
  await page.click('.cq-q[data-q="11-1"] .cq-opt[data-opt="Logo Files"]');
  check('checklist count updates', (await page.$eval('.cq-q[data-q="11-1"] .cq-count', e => e.textContent)) === '1 of 6 ticked');
  check('page 11 upload box', !!(await page.$('.cq-q[data-q="11-4"] .cq-upload')));
  await page.screenshot({ path: path.join(SHOTS, 'd-11.png'), fullPage: true });
  await page.click('[data-nav=next]'); await page.waitForTimeout(150);
  check('submit visible on last', await page.$eval('.cq-nav', e => e.classList.contains('is-last')));
  await page.click('.cq-q[data-q="12-1"] .cq-opt[data-opt="The experience feels memorable"]');
  await page.fill('textarea[name="12.2 Anything else"]', 'Nothing else.');

  // submit
  await page.click('.cq-btn-submit'); await page.waitForTimeout(300);
  const subs = await page.evaluate(() => window.__submissions);
  check('submitted once', subs.length === 1, subs.length);
  const payload = subs[0] || {};
  fs.writeFileSync(path.join(SHOTS, 'payload.json'), JSON.stringify(payload, null, 2));
  check('payload has 01.4 compiled', payload['01.4 Looking for from Solid'] === 'Interior Design, Other: Acoustic design');
  check('payload 01.5 radio', payload['01.5 Project type'] === 'F&B / Restaurant / Café', payload['01.5 Project type']);
  check('payload 02.2 goals', payload['02.2 Main goals'] === 'Improve functionality, Launching a new brand, Improve customer / visitor experience', payload['02.2 Main goals']);
  check('payload 03.1', payload['03.1 Level of change'] === 'Noticeable Transformation');
  check('payload 05.3', payload['05.3 Creative direction'] === 'Warm Minimalism, Modern Luxury, A blend of different directions: Warm minimal with heritage arches', payload['05.3 Creative direction']);
  check('payload 06.1 other', payload['06.1 Colour direction'] === 'Warm neutrals, Other: Sage green', payload['06.1 Colour direction']);
  check('payload 08A.1', payload['08A.1 F&B concept'] === 'Café');
  check('payload 08A.3 indoor', payload['08A.3 Seating — Indoor'] === '40');
  check('payload 08A.4', payload['08A.4 Zones required'] === 'Coffee Bar');
  check('payload 11.1 checklist', payload['11.1 Handover — Brand & Creative'] === 'Logo Files', payload['11.1 Handover — Brand & Creative']);
  check('no stray option names', !Object.keys(payload).some(k => ['Interior Design', 'Other', 'Yes', 'Café'].includes(k)), Object.keys(payload).filter(k => k.length < 12));
  await page.screenshot({ path: path.join(SHOTS, 'd-done.png'), fullPage: false });

  // Project type change hides step 08 entirely
  const page2 = await ctx.newPage();
  await page2.goto(url); await page2.waitForTimeout(300);
  await page2.click('.cq-q[data-q="01-5"] .cq-opt[data-opt="Workplace / Office"]'); await page2.waitForTimeout(100);
  const vis2 = await page2.$$eval('.cq-step', els => els.filter(e => !e.classList.contains('cq-skip')).length);
  check('workplace -> 11 steps (08 skipped)', vis2 === 11, vis2);
  await page2.click('.cq-q[data-q="01-5"] .cq-opt[data-opt="Event / Temporary Space"]'); await page2.waitForTimeout(100);
  const subs2 = await page2.$$eval('.cq-sub', els => els.filter(e => !e.classList.contains('cq-hidden')).map(e => e.getAttribute('data-sub')));
  check('event -> sub C', JSON.stringify(subs2) === '["C"]', subs2);
  // Enter key in text input goes next (after required filled) rather than submitting
  await page2.fill('input[name="01.1 Project / Brand Name"]', 'X');
  await page2.fill('input[name="01.2 Primary Contact"]', 'Y');
  await page2.fill('input[name="01.3 Project Location / Venue"]', 'Z');
  await page2.press('input[name="01.3 Project Location / Venue"]', 'Enter'); await page2.waitForTimeout(150);
  check('enter advances, no submit', (await page2.$eval('.cq-step.is-active', e => e.getAttribute('data-step'))) === '02' && (await page2.evaluate(() => window.__submissions.length)) === 0);

  // mobile screenshots
  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const mp = await mctx.newPage();
  await mp.goto(url); await mp.waitForTimeout(300);
  await mp.screenshot({ path: path.join(SHOTS, 'm-01.png'), fullPage: true });
  await mp.fill('input[name="01.1 Project / Brand Name"]', 'X'); await mp.fill('input[name="01.2 Primary Contact"]', 'Y'); await mp.fill('input[name="01.3 Project Location / Venue"]', 'Z');
  for (let i = 0; i < 4; i++) { await mp.click('[data-nav=next]'); await mp.waitForTimeout(150); }
  await mp.screenshot({ path: path.join(SHOTS, 'm-05.png'), fullPage: true });
  const overflow = await mp.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  check('no horizontal overflow on mobile', !overflow);

  await browser.close();
  const bad = results.filter(r => !r.ok);
  results.forEach(r => console.log((r.ok ? 'PASS ' : 'FAIL ') + r.name + (r.extra !== undefined ? '  [' + JSON.stringify(r.extra) + ']' : '')));
  console.log(bad.length ? bad.length + ' FAILURES' : 'ALL PASSED');
  process.exit(bad.length ? 1 : 0);
})();
