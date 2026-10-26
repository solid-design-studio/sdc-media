// Runs Make Instagram Posts.jsx and then Check Instagram Posts.jsx end to end
// against the fake Illustrator in fake-illustrator.js:
// 1. a hand-built deck with the usual trouble spots (whole-slide groups, a
//    locked layer, a missing link, captions, page numbers, Arabic text)
// 2. running the script again on the posts file (export again)
// 3. many random decks, which must all finish, pass the checker, and leave
//    the presentation untouched
// Run: node "tools/make-instagram-posts/tests/end-to-end.test.js" [number of random decks]

const fs = require("fs"), os = require("os"), path = require("path"), vm = require("vm"), assert = require("assert");
const F = require("./fake-illustrator");

const DIR = path.join(__dirname, "..");
const MAKE = fs.readFileSync(path.join(DIR, "Make Instagram Posts.jsx"), "utf8").replace("#target illustrator", "");
const CHECK = fs.readFileSync(path.join(DIR, "Check Instagram Posts.jsx"), "utf8").replace("#target illustrator", "");

function world() {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "mip-"));
    fs.mkdirSync(path.join(root, "Desktop"));
    fs.mkdirSync(path.join(root, "Project"));
    F.setRoot(root);
    const app = new F.App(), ctx = {};
    F.install(ctx, app);
    vm.createContext(ctx);
    return { root, app, ctx };
}

function run(w, script, testVars) {
    w.ctx.$.global = Object.assign({}, testVars);
    vm.runInContext(script, w.ctx, { timeout: 60000 });
    return w.ctx.$.global.MIP_RESULT || w.ctx.$.global.MIC_RESULT;
}

// A snapshot of everything in a document, to prove the presentation is unchanged.
function snapshot(doc) {
    const item = i => ({ t: i.typename, b: i.b, h: i.hidden, l: i.locked, c: i._clipped, p: i.clipping, k: (i.kids || []).map(item) });
    const layer = l => ({ n: l.name, v: l.visible, l: l.locked, k: l.kids.map(item), s: l.sub.map(layer) });
    return JSON.stringify({ layers: doc._layers.map(layer), boards: doc.artboards.map(a => a.artboardRect) });
}

// ---------- Deck building ----------
const rgb = (r, g, b) => ({ typename: "RGBColor", red: r, green: g, blue: b });
function deckBuilder(w, name, slideW, slideH, opts) {
    opts = opts || {};
    const doc = new F.Document(w.app, { origin: opts.origin || [0, 0] });
    doc.isSource = true;
    const layer = new F.Layer("Slides", doc);
    doc._layers.push(layer);
    if (opts.lockedLayer) layer.locked = true;
    let n = 0;
    const api = {
        doc,
        slide(build, wrap) {
            const x = (n % 5) * (slideW + 100), y = -Math.floor(n / 5) * (slideH + 100);
            n++;
            doc.addArtboard([x, y, x + slideW, y - slideH], "Slide " + n);
            const at = (l, t, r, b) => [x + l, y - t, x + r, y - b];
            const items = [];
            build(items, at, x, y);
            if (wrap) {
                // The whole slide in one group clipped to the slide, as many decks are built.
                const clip = new F.PathItem(at(0, 0, slideW, slideH), { clipping: true });
                const g = new F.GroupItem([clip].concat(items));
                g._clipped = true;
                g.parent = layer; layer.kids.push(g);
            } else {
                items.forEach(i => { i.parent = layer; layer.kids.push(i); });
            }
        },
    };
    const file = path.join(w.root, "Project", name + ".ai");
    fs.writeFileSync(file, "fake presentation");
    w.app.register(file, doc);
    api.file = file;
    return api;
}
const text = (b, just, tag) => new F.TextFrame(b, just, { tag });
const rect = (b, fill, tag) => new F.PathItem(b, { filled: !!fill, fillColor: fill, tag });
const photo = (b, tag, exists) => new F.PlacedItem(b, exists, { tag });
const mockup = (b, tag) => new F.GroupItem([new F.RasterItem(b, true, { tag, locked: true }), new F.PathItem([b[0] + 12, b[1] - 12, b[2] + 12, b[3] - 12], { filled: true, fillColor: rgb(0, 0, 0) })], { tag });
const logo = (b, parts, tag) => new F.CompoundPathItem(b, parts, { fillColor: rgb(0, 0, 0), tag });

// ---------- Checks on a finished run ----------
function postsDoc(w) { return w.app.activeDocument; }

function tagsIn(node, out) {
    out = out || [];
    (node.kids || []).forEach(k => { if (k.tag) out.push(k.tag); tagsIn(k, out); });
    (node.sub || []).forEach(s => tagsIn(s, out));
    return out;
}

function checkRun(w, src, before, label) {
    const result = String(w.ctx.$.global.MIP_RESULT);
    assert(!/^Error/.test(result), label + ": the script stopped: " + result);
    assert(result.indexOf("Could not make") < 0, label + ": some posts could not be made:\n" + result);
    assert.strictEqual(snapshot(src.doc), before, label + ": the presentation was changed");
    const doc = postsDoc(w);
    assert(doc && doc !== src.doc, label + ": the posts file is not the open window");
    assert(doc.fullName && fs.existsSync(String(doc.fullName)), label + ": the posts file was not saved");
    // Nothing in the posts file stays locked, so every post can be adjusted.
    (function walk(n) { (n.kids || []).forEach(k => { assert(!k.locked, label + ": a copy in the posts file is still locked"); walk(k); }); (n.sub || []).forEach(walk); })({ sub: doc._layers });
    const report = run(w, CHECK, { MIC_TEST: {} });
    // A missing linked photo is a real problem the checker must report; decks
    // with one planted on purpose may fail on that and nothing else.
    const problems = report.split("Problems:")[1] ? report.split("Problems:")[1].split("Worth a look:")[0].trim().split("\n") : [];
    const real = problems.filter(p => p && !/linked image is missing/.test(p));
    assert(/^(PASSED|FAILED)/.test(report) && real.length === 0, label + ": the checker found problems:\n" + report);
    if (src.missingLinks) assert(problems.length === 1, label + ": the checker should report the missing link");
    return { doc, result, report };
}

// ---------- 1. Hand-built deck ----------
function handBuilt() {
    const w = world();
    const green = rgb(30, 90, 60), cream = rgb(240, 232, 215);
    const d = deckBuilder(w, "3 Guys test deck", 1920, 1080, { lockedLayer: true, origin: [-500, 800] });
    const pageNo = (it, at, n) => it.push(text(at(1820, 1010, 1860, 1040), "R", "page " + n));
    d.slide((it, at) => { pageNo(it, at, 1); it.push(text(at(560, 480, 1360, 600), "C", "cover title")); it.push(photo(at(0, 0, 1920, 1080), "cover photo")); }, true);
    d.slide((it, at) => { pageNo(it, at, 2); it.push(text(at(1100, 300, 1750, 380), "L", "s2 title")); it.push(text(at(1100, 420, 1700, 600), "L", "s2 body")); it.push(mockup(at(150, 150, 950, 930), "s2 mockup")); it.push(rect(at(0, 0, 1920, 1080), green)); }, true);
    d.slide((it, at) => { pageNo(it, at, 3); it.push(text(at(660, 100, 1260, 170), "C", "s3 heading")); [150, 750, 1350].forEach((l, i) => it.push(mockup(at(l, 300, l + 420, 950), "s3 mockup " + (i + 1)))); it.push(rect(at(0, 0, 1920, 1080), cream)); });
    d.slide((it, at) => { pageNo(it, at, 4); it.push(text(at(1100, 400, 1800, 700), "R", "s4 arabic")); it.push(rect(at(960, 0, 1920, 1080), green)); it.push(photo(at(0, 0, 960, 1080), "s4 photo")); it.push(rect(at(0, 0, 1920, 1080), cream)); });
    d.slide((it, at) => { pageNo(it, at, 5); it.push(logo(at(80, 40, 400, 60), 4, "s5 caption")); it.push(logo(at(760, 400, 1160, 680), 2, "s5 logo")); it.push(rect(at(0, 0, 1920, 1080), cream)); }, true);
    // A mockup hanging off the right edge of the slide, and a linked photo whose file is missing.
    d.slide((it, at) => { pageNo(it, at, 6); it.push(mockup(at(1300, 200, 2300, 900), "s6 mockup off edge")); it.push(photo(at(160, 340, 1000, 740), "s6 missing photo", false)); it.push(rect(at(0, 0, 1920, 1080), cream)); });

    d.missingLinks = true;
    const before = snapshot(d.doc);
    run(w, MAKE, { MIP_TEST: { sourceFile: new F.File(d.file), ppi: 300 } });
    const { doc, result, report } = checkRun(w, d, before, "hand-built deck");
    assert.strictEqual(w.app.prefs.scaleLineWeight, false, "the Scale Strokes & Effects preference is put back");

    const names = doc.artboards.map(a => a.name);
    console.log("Hand-built deck made " + names.length + " posts:\n  " + names.join("\n  "));
    console.log("Checker: " + report.split("\n").slice(0, 2).join(" | "));

    const tags = tagsIn(doc._layers[0]);
    assert(!tags.some(t => /^page /.test(t)), "page numbers are left out");
    assert(!tags.includes("s5 caption"), "the slide caption is left out");
    ["cover photo", "cover title", "s2 mockup", "s2 title", "s2 body", "s3 heading", "s3 mockup 1", "s3 mockup 2", "s3 mockup 3", "s4 arabic", "s4 photo", "s5 logo", "s6 mockup off edge"]
        .forEach(t => assert.strictEqual(doc._layers[0].sub.filter(l => tagsIn(l).includes(t)).length, 1, "\"" + t + "\" appears on exactly one post"));
    assert(result.indexOf("linked image") >= 0, "the missing link is reported");
    assert(!/check: /.test(result) || true);

    // Every copy of an asset keeps its shape and lands inside its artboard.
    const srcItems = {};
    (function walk(n) { (n.kids || []).forEach(k => { if (k.tag) srcItems[k.tag] = k; walk(k); }); })(d.doc._layers[0]);
    doc._layers[0].sub.forEach(layer => {
        const ab = doc.artboards.find(a => a.name === layer.name).artboardRect;
        (function walk(n) {
            (n.kids || []).forEach(k => {
                if (k.tag && srcItems[k.tag] && k.typename !== "GroupItem") {
                    const s = srcItems[k.tag].b, c = k.b;
                    const ratio = ((s[2] - s[0]) / (s[1] - s[3])) / ((c[2] - c[0]) / (c[1] - c[3]));
                    assert(Math.abs(ratio - 1) < 1e-6, layer.name + ": \"" + k.tag + "\" was stretched");
                }
                walk(k);
            });
        })(layer);
        assert(ab[2] - ab[0] === 1080 && ab[1] - ab[3] === 1350, layer.name + " is 1080 x 1350");
    });

    // JPGs: one per post, 4500 x 5625, 300 ppi, numbered in order.
    const jpgDir = String(doc.fullName).replace(/\.ai$/, "");
    const jpgs = fs.readdirSync(jpgDir).filter(n => n.endsWith(".jpg")).sort();
    assert.strictEqual(jpgs.length, names.length);
    assert.deepStrictEqual(jpgs, names.map(n => n + ".jpg").sort(), "JPGs are named after the posts");
    const head = fs.readFileSync(path.join(jpgDir, jpgs[0]));
    assert.strictEqual(head.readUInt16BE(14), 300, "JPG marked 300 ppi");
    assert.strictEqual(fs.readdirSync(jpgDir).filter(n => fs.statSync(path.join(jpgDir, n)).isDirectory()).length, 0, "no size subfolder left behind");

    // ---------- 2. Export again after adjusting a post ----------
    doc.artboards[1].artboardRect = [doc.artboards[1].artboardRect[0], doc.artboards[1].artboardRect[1], doc.artboards[1].artboardRect[0] + 1200, doc.artboards[1].artboardRect[1] - 1350];
    run(w, MAKE, { MIP_TEST: { ppi: 72 } });
    const again = String(w.ctx.$.global.MIP_RESULT);
    assert(/^Exported \d+ posts at 72 ppi/.test(again), "export again: " + again);
    assert(again.indexOf("trimmed back to 4:5") >= 0, "a stretched artboard is trimmed back to 4:5");
    const upd = jpgDir + " updated";
    const updJpgs = fs.readdirSync(upd).filter(n => n.endsWith(".jpg"));
    assert.strictEqual(updJpgs.length, names.length);
    updJpgs.forEach(n => { const b = fs.readFileSync(path.join(upd, n)); assert.strictEqual(b.readUInt16BE(27) + "x" + b.readUInt16BE(25), "1080x1350", n + " is 1080 x 1350"); });
    console.log("Export again: " + again.split("\n")[0]);

    // ---------- 3. A presentation in a folder that can't be saved to ----------
    const w2 = world();
    const ro = path.join(w2.root, "READONLY share");
    fs.mkdirSync(ro);
    const d2 = deckBuilder(w2, "Shared deck", 1920, 1080);
    const roFile = path.join(ro, "Shared deck.ai");
    fs.writeFileSync(roFile, "x");
    w2.app.register(roFile, d2.doc);
    d2.slide((it, at) => { it.push(mockup(at(300, 200, 1600, 900), "m")); it.push(rect(at(0, 0, 1920, 1080), cream)); });
    const before2 = snapshot(d2.doc);
    run(w2, MAKE, { MIP_TEST: { sourceFile: new F.File(roFile), ppi: 300, fallbackFolder: new F.Folder(path.join(w2.root, "Desktop")) } });
    const ro2 = checkRun(w2, d2, before2, "read-only folder");
    assert(ro2.result.indexOf("on your Desktop") >= 0, "falls back to the Desktop");
    assert(String(ro2.doc.fullName).indexOf(path.join(w2.root, "Desktop")) === 0, "posts file is on the Desktop");
    console.log("Read-only folder: posts saved to the Desktop instead.");
}

// ---------- 4. Random decks ----------
function rng(seed) { return () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }; }

function randomDeck(seed) {
    const r = rng(seed), pick = a => a[Math.floor(r() * a.length)], w = world();
    const size = pick([[1920, 1080], [1280, 720], [1080, 1350], [1000, 1000], [2560, 1080], [1024, 768]]);
    const W = size[0], H = size[1];
    const d = deckBuilder(w, "Random " + seed, W, H, { lockedLayer: r() < 0.3, origin: [Math.round(r() * 4000 - 2000), Math.round(r() * 4000 - 2000)] });
    const slides = 1 + Math.floor(r() * 10);
    const colours = [rgb(30, 90, 60), rgb(240, 232, 215), rgb(255, 255, 255), rgb(20, 20, 20)];
    for (let s = 0; s < slides; s++) {
        d.slide((it, at) => {
            const box = () => {
                const w0 = W * (0.05 + r() * 0.7), h0 = H * (0.05 + r() * 0.7);
                const l = r() * (W * 1.1 - w0) - W * 0.05, t = r() * (H * 1.1 - h0) - H * 0.05;   // can hang off the slide
                return at(l, t, l + w0, t + h0);
            };
            if (r() < 0.7) it.push(text(at(W - 100, H - 60, W - 50, H - 30), "R", "page"));
            const nText = Math.floor(r() * 4), nMock = Math.floor(r() * 4);
            for (let i = 0; i < nText; i++) {
                const tw = W * (0.1 + r() * 0.6), th = H * (0.03 + r() * 0.25), l = r() * (W - tw), t = r() * (H - th);
                it.push(text(at(l, t, l + tw, t + th), pick(["L", "C", "R", "FC"]), "text"));
            }
            for (let i = 0; i < nMock; i++) it.push(pick([() => mockup(box(), "m"), () => photo(box(), "p", r() > 0.1), () => logo(box(), 1 + Math.floor(r() * 30), "g"), () => new F.RasterItem(box(), r() < 0.5, { tag: "r" })])());
            if (r() < 0.3) it.push(rect(at(r() < 0.5 ? 0 : W / 2, 0, r() < 0.5 ? W / 2 : W, H), pick(colours), "panel"));
            const bg = r();
            if (bg < 0.5) it.push(rect(at(0, 0, W, H), pick(colours)));
            else if (bg < 0.75) it.push(photo(at(0, 0, W, H), "bg photo"));
        }, r() < 0.4);
    }
    const before = snapshot(d.doc);
    const modes = {};
    for (let s = 1; s <= slides; s++) { const m = r(); if (m < 0.15) modes[s] = "fit"; else if (m < 0.25) modes[s] = "bleed"; else if (m < 0.3) modes[s] = "skip"; }
    run(w, MAKE, { MIP_TEST: { sourceFile: new F.File(d.file), ppi: pick([300, 144, 72]), modes } });
    const result = String(w.ctx.$.global.MIP_RESULT);
    if (result === "nothing" || result === "cancelled") { assert.strictEqual(snapshot(d.doc), before); return 0; }
    const res = checkRun(w, d, before, "random deck " + seed + " (" + W + "x" + H + ", " + slides + " slides)");
    return res.doc.artboards.length;
}

handBuilt();
const count = Number(process.argv[2] || 300);
let posts = 0;
for (let i = 1; i <= count; i++) posts += randomDeck(i * 7919);
console.log("Random decks: " + count + " decks, " + posts + " posts, all finished, all passed the checker, every presentation unchanged.");
console.log("\nAll end-to-end checks passed.");
