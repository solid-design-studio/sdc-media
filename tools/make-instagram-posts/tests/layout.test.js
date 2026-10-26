// Checks the layout logic of Make Instagram Posts.jsx without Illustrator.
// Builds a mock six-slide deck, plans the posts, and checks the rules:
// every post is 1080 x 1350, every asset is whole and inside the margins,
// nothing is stretched, page numbers and slide captions are left out.
// Run: node "tools/make-instagram-posts/tests/layout.test.js"

const fs = require("fs");
const path = require("path");
const assert = require("assert");

global.$ = { global: { MIP_TEST: { library: true } } };
global.BlendModes = { NORMAL: "normal" };
global.Justification = { LEFT: "L", CENTER: "C", RIGHT: "R", FULLJUSTIFYLASTLINECENTER: "FC", FULLJUSTIFYLASTLINERIGHT: "FR" };
const src = fs.readFileSync(path.join(__dirname, "..", "Make Instagram Posts.jsx"), "utf8").replace("#target illustrator", "");
eval(src);
const L = $.global.MIP_LIB;

// ---------- Mock Illustrator items ----------
function base(typename, l, t, r, b, extra) {
    return Object.assign({ typename, visibleBounds: [l, t, r, b], geometricBounds: [l, t, r, b], hidden: false,
        opacity: 100, blendingMode: "normal", pageItems: [], clipped: false, clipping: false }, extra || {});
}
const rgb = (r, g, b) => ({ typename: "RGBColor", red: r, green: g, blue: b });
const rect = (l, t, r, b, fill) => base("PathItem", l, t, r, b, { filled: !!fill, fillColor: fill, pathPoints: { length: 4 } });
const photo = (l, t, r, b) => base("PlacedItem", l, t, r, b);
const raster = (l, t, r, b) => base("RasterItem", l, t, r, b, { transparent: true });
const text = (l, t, r, b, just) => base("TextFrame", l, t, r, b, { textRange: { paragraphAttributes: { justification: just || "L" } } });
const group = (kids) => {
    let u = null;
    kids.forEach(k => { const v = k.visibleBounds; u = u ? [Math.min(u[0], v[0]), Math.max(u[1], v[1]), Math.max(u[2], v[2]), Math.min(u[3], v[3])] : v.slice(); });
    return base("GroupItem", u[0], u[1], u[2], u[3], { pageItems: kids });
};
const compound = (l, t, r, b, parts) => base("CompoundPathItem", l, t, r, b, { pathItems: Array.from({ length: parts }, () => ({ filled: true, fillColor: rgb(0, 0, 0), clipping: false })) });
// A device mockup: a cut-out screen render plus its shadow.
const mockup = (l, t, r, b) => group([raster(l, t, r, b), rect(l + 10, t - 10, r + 10, b - 10, rgb(0, 0, 0))]);

// ---------- Mock deck: six 1920 x 1080 slides side by side ----------
const W = 1920, H = 1080, green = rgb(30, 90, 60), cream = rgb(240, 232, 215);
const slides = [];
function slide(i, build) {
    const x = i * 2000, items = [];
    const at = (l, t, r, b) => [x + l, -t, x + r, -b];      // slide coordinates, y down
    build(items, at);
    // Page number in the bottom right corner of every slide.
    items.unshift(text(...at(1820, 1010, 1860, 1040)));
    slides.push({ ab: { l: x, t: 0, r: x + W, b: -H }, items });
}
// 1 Cover: full-bleed photo with a centred title.
slide(0, (it, at) => { it.push(text(...at(560, 480, 1360, 600), "C")); it.push(photo(...at(0, 0, 1920, 1080))); });
// 2 One mockup on the left, title and body text on the right.
slide(1, (it, at) => { it.push(text(...at(1100, 300, 1750, 380))); it.push(text(...at(1100, 420, 1700, 600))); it.push(mockup(...at(150, 150, 950, 930))); it.push(rect(...at(0, 0, 1920, 1080), green)); });
// 3 Three mockups in a row under a heading.
slide(2, (it, at) => { it.push(text(...at(660, 100, 1260, 170), "C")); [150, 750, 1350].forEach(l => it.push(mockup(...at(l, 300, l + 420, 950)))); it.push(rect(...at(0, 0, 1920, 1080), cream)); });
// 4 Photo on the left half, Arabic text on a green panel on the right.
slide(3, (it, at) => { it.push(text(...at(1100, 400, 1800, 700), "R")); it.push(rect(...at(960, 0, 1920, 1080), green)); it.push(photo(...at(0, 0, 960, 1080))); it.push(rect(...at(0, 0, 1920, 1080), cream)); });
// 5 Logo slide with a small caption at the top.
slide(4, (it, at) => { it.push(compound(...at(80, 40, 400, 60), 4)); it.push(compound(...at(760, 400, 1160, 680), 2)); it.push(rect(...at(0, 0, 1920, 1080), cream)); });
// 6 A wide banner photo on its own.
slide(5, (it, at) => { it.push(photo(...at(160, 340, 1760, 740))); it.push(rect(...at(0, 0, 1920, 1080), cream)); });

const all = [];
slides.forEach(s => s.items.forEach(item => all.push({ item, rect: L.rw ? { l: item.visibleBounds[0], t: item.visibleBounds[1], r: item.visibleBounds[2], b: item.visibleBounds[3] } : null })));
const read = slides.map((s, i) => L.readSlide(s.ab, i, all, []));
L.markFurniture(read);
read.forEach(s => { L.shapeSlide(s); s.plan = L.planFor(s); });
const posts = L.listPosts(read);

// ---------- Report ----------
const R = L.postRect(), safe = L.inset(R, L.SETTINGS.margin);
console.log("Posts:");
posts.forEach(p => console.log("  " + p.name + (p.notes.length ? "   [check: " + p.notes.join("; ") + "]" : "")));

// ---------- Rules ----------
assert.strictEqual(L.rw(R), 1080); assert.strictEqual(L.rh(R), 1350);
let pageNumbers = 0;
posts.forEach(p => {
    p.pieces.forEach(piece => {
        // Never stretched.
        const a1 = L.rw(piece.from) / L.rh(piece.from), a2 = L.rw(piece.to) / L.rh(piece.to);
        assert(Math.abs(a1 / a2 - 1) < 1e-6, p.name + ": piece stretched");
        // Whole and inside the margins, unless it is a photo filling the post edge to edge.
        const bleed = L.rw(piece.to) >= 1080 - 0.5 && L.rh(piece.to) >= 1350 - 0.5;
        if (!bleed) assert(L.inside(piece.to, safe, 0.5), p.name + ": piece outside the margins " + JSON.stringify(piece.to));
        // Assets are shown whole: the clip holds everything that was visible.
        piece.members.forEach(m => { if (m.item.typename === "TextFrame" && m.cover.l - read[p.slide.index].ab.l > 1800) pageNumbers++; });
    });
});
assert.strictEqual(pageNumbers, 0, "page numbers should be left out");

const names = posts.map(p => p.name.replace(/^\d+ /, ""));
assert(names.includes("Slide 01 text"), "cover becomes a text post on its photo");
assert.strictEqual(posts.find(p => p.name.includes("Slide 01")).surface.photo, true, "cover keeps its photo");
assert(names.some(n => n.startsWith("Slide 02 mockup")), "slide 2 mockup has a post");
assert.strictEqual(names.filter(n => /^Slide 03 mockup \d/.test(n)).length, 3, "slide 3: each mockup on its own post");
assert(names.includes("Slide 03 text"), "slide 3 heading on its own post");
assert(names.indexOf("Slide 03 text") < names.indexOf("Slide 03 mockup 1"), "slide 3 heading comes before the mockups");
const s4photo = posts.find(p => p.name.endsWith("Slide 04 photo"));
assert(s4photo && L.rw(s4photo.pieces[0].to) >= 1080, "slide 4 photo fills its post");
const s4text = posts.find(p => p.name.endsWith("Slide 04 text"));
assert(s4text && s4text.surface.fill === green, "slide 4 text sits on its green panel");
assert(Math.abs(s4text.pieces[0].to.r - safe.r) < 0.5, "Arabic text is right aligned to the margin");
const logo = posts.find(p => p.name.endsWith("Slide 05 logo"));
assert(logo, "slide 5 logo has a post");
assert(read[4].labels.length === 1, "slide 5 caption is left out");
assert(Math.abs(L.rw(logo.pieces[0].to) - L.rw(safe) * L.SETTINGS.graphicFill) < 1, "logo takes the set share of the width");
const banner = posts.find(p => p.name.endsWith("Slide 06 photo"));
assert(banner && banner.notes.some(n => n.includes("empty space")), "wide banner is flagged for empty space");

// JPG ppi header.
const jfif = "\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x48\x00\x48\x00\x00";
const patch = L.jfifPatch(jfif, 300);
assert.strictEqual(patch.offset, 13);
assert.deepStrictEqual([...patch.bytes].map(c => c.charCodeAt(0)), [1, 1, 44, 1, 44]);
const noJfif = L.jfifPatch("\xFF\xD8\xFF\xE1\x00\x10Exif\x00\x00", 300);
assert.strictEqual(noJfif.offset, -1); assert.strictEqual(noJfif.insert.length, 18);

console.log("\nAll layout checks passed.");

if (process.argv.includes("--show")) posts.forEach(p => console.log(p.name, JSON.stringify(p.pieces.map(x => ({ l: Math.round(x.to.l), t: Math.round(-x.to.t), w: Math.round(L.rw(x.to)), h: Math.round(L.rh(x.to)) })))));
