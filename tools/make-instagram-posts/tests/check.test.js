// Checks the JPG reader in Check Instagram Posts.jsx and the 300 ppi tag
// written by Make Instagram Posts.jsx, on real JPGs from this repo.
// Run: node "tools/make-instagram-posts/tests/check.test.js"
const fs = require("fs"), path = require("path"), assert = require("assert");
const dir = path.join(__dirname, "..");
global.$ = { global: { MIC_TEST: { library: true }, MIP_TEST: { library: true } } };
global.BlendModes = { NORMAL: "normal" };
eval(fs.readFileSync(path.join(dir, "Check Instagram Posts.jsx"), "utf8").replace("#target illustrator", ""));
eval(fs.readFileSync(path.join(dir, "Make Instagram Posts.jsx"), "utf8").replace("#target illustrator", ""));
const { jpegInfo } = $.global.MIC_LIB, { jfifPatch } = $.global.MIP_LIB;
const bin = b => b.toString("latin1");

const root = path.join(dir, "..", "..");
const samples = fs.readdirSync(root).filter(d => /^(ig|li)-/.test(d)).map(d => path.join(root, d, "1.jpg"));
const truth = JSON.parse(require("child_process").execFileSync("python3", ["-c",
    "import sys,json\nfrom PIL import Image\nprint(json.dumps([[*Image.open(p).size, (Image.open(p).info.get('dpi') or (0,))[0]] for p in sys.argv[1:]]))", ...samples]).toString());
samples.forEach((p, i) => {
    const info = jpegInfo(bin(fs.readFileSync(p)));
    assert.deepStrictEqual([info.width, info.height], truth[i].slice(0, 2), p);
});
console.log("Read the size of " + samples.length + " real JPGs correctly.");

// Tag one as 300 ppi the way the export does, then read it back.
let b = bin(fs.readFileSync(samples[0]));
const plan = jfifPatch(b.substring(0, 20), 300);
b = plan.offset >= 0 ? b.substring(0, plan.offset) + plan.bytes + b.substring(plan.offset + plan.bytes.length)
    : b.substring(0, 2) + plan.insert + b.substring(2);
const out = path.join(require("os").tmpdir(), "mip-300ppi.jpg");
fs.writeFileSync(out, Buffer.from(b, "latin1"));
assert.strictEqual(jpegInfo(b).ppi, 300);
const pil = require("child_process").execFileSync("python3", ["-c", "import sys\nfrom PIL import Image\nim=Image.open(sys.argv[1]); im.load(); print(round(im.info['dpi'][0]), im.size[0])", out]).toString().trim();
assert.strictEqual(pil.split(" ")[0], "300");
console.log("300 ppi tag reads back as 300 ppi, and the image still opens (" + (plan.offset >= 0 ? "patched" : "inserted") + " header).");
