// A small stand-in for Illustrator's scripting DOM, enough to run
// Make Instagram Posts.jsx and Check Instagram Posts.jsx end to end in Node.
//
// It is strict where Illustrator is strict (a clipping path must be the top
// item of its group, resize keeps proportions only if asked), and it gives the
// posts file a different origin from the presentation, so copies land offset
// exactly as they would when duplicated between two real documents.
// It cannot tell us how Illustrator draws effects, masks or fonts.

const fs = require("fs");
const path = require("path");

let uid = 0;

// ---------- Page items ----------
class Item {
    constructor(typename, props) {
        this.typename = typename;
        this.parent = null;
        this.hidden = false;
        this.locked = false;
        this.opacity = 100;
        this.blendingMode = "normal";
        this.id = ++uid;
        Object.assign(this, props || {});
    }
    get layer() { let p = this.parent; while (p && p.typename !== "Layer") p = p.parent; return p; }
    get document() { let p = this.parent; while (p && !(p instanceof Document)) p = p.parent; return p; }
    get geometricBounds() { return this.bounds(); }
    get visibleBounds() { return this.bounds(); }
    bounds() { return this.b.slice(); }
    shiftBy(dx, dy) { this.b = [this.b[0] + dx, this.b[1] + dy, this.b[2] + dx, this.b[3] + dy]; }
    scaleBy(f, ox, oy) { const b = this.b; this.b = [ox + (b[0] - ox) * f, oy + (b[1] - oy) * f, ox + (b[2] - ox) * f, oy + (b[3] - oy) * f]; }
    translate(dx, dy) { this.shiftBy(dx, dy); }
    resize(sx, sy, a, b, c, d, lw, about) {
        if (sx !== sy) throw new Error("resize: non-uniform scale " + sx + " " + sy);
        if (!(sx > 0) || !isFinite(sx)) throw new Error("resize: bad scale " + sx);
        if (about !== "CENTER") throw new Error("resize: expected Transformation.CENTER");
        const g = this.geometricBounds;
        this.scaleBy(sx / 100, (g[0] + g[2]) / 2, (g[1] + g[3]) / 2);
    }
    clone() {
        const c = Object.create(Object.getPrototypeOf(this));
        Object.assign(c, this);
        c.id = ++uid;
        c.parent = null;
        if (this.b) c.b = this.b.slice();
        if (this.kids) { c.kids = this.kids.map(k => { const kc = k.clone(); kc.parent = c; return kc; }); }
        return c;
    }
    duplicate(rel, placement) {
        if (!rel || !rel.kids) throw new Error("duplicate: target is not a container");
        const c = this.clone();
        const from = this.document, to = rel.document || rel;
        if (from && to && from !== to) c.shiftBy(to.origin[0] - from.origin[0], to.origin[1] - from.origin[1]);
        insert(rel, c, placement);
        if (from) from.touchedBy.push("duplicate (read only)");
        return c;
    }
    remove() { detach(this); }
    move(rel, placement) { detach(this); insert(rel, this, placement); }
}

function insert(container, item, placement) {
    item.parent = container;
    if (placement === "PLACEATEND") container.kids.push(item);
    else if (placement === "PLACEATBEGINNING") container.kids.unshift(item);
    else throw new Error("unknown placement " + placement);
    markDirty(container);
}
function detach(item) {
    const p = item.parent;
    if (!p) return;
    const i = p.kids.indexOf(item);
    if (i >= 0) p.kids.splice(i, 1);
    item.parent = null;
    markDirty(p);
}
function markDirty(node) {
    while (node && !(node instanceof Document)) node = node.parent;
    if (node) { node.saved = false; node.changes++; }
}

class Leaf extends Item {}

class PathItem extends Leaf {
    constructor(b, props) { super("PathItem", Object.assign({ b, filled: false, stroked: false, clipping: false, guides: false, pathPoints: { length: 4 } }, props)); }
}
class CompoundPathItem extends Leaf {
    constructor(b, parts, props) {
        super("CompoundPathItem", Object.assign({ b }, props));
        this.pathItems = Array.from({ length: parts }, () => ({ filled: true, clipping: false, fillColor: props && props.fillColor }));
    }
}
class TextFrame extends Leaf {
    constructor(b, just, props) { super("TextFrame", Object.assign({ b, textRange: { paragraphAttributes: { justification: just || "L" } } }, props)); }
}
class PlacedItem extends Leaf {
    constructor(b, exists, props) { super("PlacedItem", Object.assign({ b, file: { exists: exists !== false } }, props)); }
}
class RasterItem extends Leaf {
    constructor(b, transparent, props) { super("RasterItem", Object.assign({ b, transparent: !!transparent }, props)); }
}

// Containers keep children top of the stack first, like Illustrator.
const containerMixin = {
    get pageItems() { return this.kids; },
    get groupItems() {
        const self = this, list = this.kids.filter(k => k.typename === "GroupItem");
        list.add = () => { const g = new GroupItem([]); insert(self, g, "PLACEATBEGINNING"); return g; };
        return list;
    },
    get pathItems() {
        const self = this, list = this.kids.filter(k => k.typename === "PathItem");
        list.rectangle = (top, left, w, h) => {
            if (!(w > 0 && h > 0)) throw new Error("rectangle: bad size " + w + " x " + h);
            const p = new PathItem([left, top, left + w, top - h], { filled: true, stroked: true });
            insert(self, p, "PLACEATBEGINNING");
            return p;
        };
        return list;
    },
    get textFrames() { return this.kids.filter(k => k.typename === "TextFrame"); },
};

class GroupItem extends Item {
    constructor(kids, props) {
        super("GroupItem", props);
        this.kids = [];
        this._clipped = false;
        kids.forEach(k => { k.parent = this; this.kids.push(k); });
    }
    get clipped() { return this._clipped; }
    set clipped(v) {
        if (v) {
            const top = this.kids[0];
            if (!top || top.typename !== "PathItem" || !top.clipping) throw new Error("clipped: the top item of the group must be a clipping path");
        }
        this._clipped = v;
    }
    bounds() {
        if (this._clipped) return this.kids[0].bounds();
        let u = null;
        this.kids.forEach(k => {
            if (k.hidden) return;
            const v = k.bounds();
            u = u ? [Math.min(u[0], v[0]), Math.max(u[1], v[1]), Math.max(u[2], v[2]), Math.min(u[3], v[3])] : v;
        });
        if (!u) return [0, 0, 0, 0];
        return u;
    }
    shiftBy(dx, dy) { this.kids.forEach(k => k.shiftBy(dx, dy)); }
    scaleBy(f, ox, oy) { this.kids.forEach(k => k.scaleBy(f, ox, oy)); }
}
Object.defineProperties(GroupItem.prototype, Object.getOwnPropertyDescriptors(containerMixin));

class Layer {
    constructor(name, parent) {
        this.typename = "Layer";
        this.name = name;
        this.parent = parent;
        this.visible = true;
        this.locked = false;
        this.kids = [];
        this.sub = [];
    }
    get document() { let p = this.parent; while (p && !(p instanceof Document)) p = p.parent; return p; }
    get layers() {
        const self = this, list = this.sub.slice();
        list.add = () => { const l = new Layer("Layer", self); self.sub.unshift(l); markDirty(self); return l; };
        return list;
    }
    move(rel, placement) {
        const from = this.parent.sub || this.parent._layers;
        from.splice(from.indexOf(this), 1);
        const to = rel.sub;
        if (placement === "PLACEATEND") to.push(this); else to.unshift(this);
        this.parent = rel;
    }
}
Object.defineProperties(Layer.prototype, Object.getOwnPropertyDescriptors(containerMixin));

// ---------- Files ----------
let ROOT = null;
function setRoot(dir) { ROOT = dir; }

function Folder(p) {
    if (!(this instanceof Folder)) return new Folder(p);
    this.fsName = String(p);
}
Folder.prototype.toString = function () { return this.fsName; };
Object.defineProperties(Folder.prototype, {
    exists: { get() { return fs.existsSync(this.fsName) && fs.statSync(this.fsName).isDirectory(); } },
    name: { get() { return encodeURIComponent(path.basename(this.fsName)); } },
    parent: { get() { return new Folder(path.dirname(this.fsName)); } },
});
Folder.prototype.create = function () {
    if (this.fsName.indexOf("READONLY") >= 0) return false;
    fs.mkdirSync(this.fsName, { recursive: true });
    return true;
};
Folder.prototype.remove = function () { try { fs.rmdirSync(this.fsName); return true; } catch (e) { return false; } };
Folder.prototype.getFiles = function (mask) {
    if (!this.exists) return [];
    return fs.readdirSync(this.fsName).sort().map(n => {
        const full = path.join(this.fsName, n);
        return fs.statSync(full).isDirectory() ? new Folder(full) : new File(full);
    }).filter(f => {
        if (typeof mask === "function") return mask(f);
        if (typeof mask === "string") return f instanceof File && new RegExp("^" + mask.replace(".", "\\.").replace("*", ".*") + "$", "i").test(path.basename(f.fsName));
        return true;
    });
};
Object.defineProperty(Folder, "desktop", { get() { return new Folder(path.join(ROOT, "Desktop")); } });

function File(p) {
    if (!(this instanceof File)) return new File(p);
    this.fsName = String(p);
    this.encoding = "UTF-8";
    this.buf = null;
    this.pos = 0;
}
File.decode = s => decodeURIComponent(s);
File.prototype.toString = function () { return this.fsName; };
Object.defineProperties(File.prototype, {
    exists: { get() { return fs.existsSync(this.fsName); } },
    name: { get() { return encodeURIComponent(path.basename(this.fsName)); } },
    parent: { get() { return new Folder(path.dirname(this.fsName)); } },
});
File.prototype.open = function (mode) {
    if (mode === "r" || mode === "e") {
        if (!this.exists) return false;
        this.buf = fs.readFileSync(this.fsName);
    } else if (mode === "w") {
        if (!fs.existsSync(path.dirname(this.fsName))) return false;
        this.buf = Buffer.alloc(0);
    } else throw new Error("File.open: unknown mode " + mode);
    this.mode = mode;
    this.pos = 0;
    return true;
};
File.prototype.read = function (n) {
    const end = n === undefined ? this.buf.length : Math.min(this.buf.length, this.pos + n);
    const out = this.buf.slice(this.pos, end);
    this.pos = end;
    return this.encoding === "BINARY" ? out.toString("latin1") : out.toString("utf8");
};
File.prototype.seek = function (n) { this.pos = n; return true; };
File.prototype.write = function (s) {
    if (this.mode === "r") throw new Error("File.write: opened read only");
    const bytes = Buffer.from(s, this.encoding === "BINARY" ? "latin1" : "utf8");
    const end = this.pos + bytes.length;
    if (end > this.buf.length) { const nb = Buffer.alloc(end); this.buf.copy(nb); this.buf = nb; }
    bytes.copy(this.buf, this.pos);
    this.pos = end;
    return true;
};
File.prototype.close = function () {
    if (this.buf && (this.mode === "w" || this.mode === "e")) fs.writeFileSync(this.fsName, this.buf);
    this.buf = null;
    return true;
};
File.prototype.copy = function (dest) { fs.copyFileSync(this.fsName, String(dest)); return true; };
File.prototype.remove = function () { fs.unlinkSync(this.fsName); return true; };

// ---------- Documents ----------
function jpegBytes(w, h) {
    const b = [0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00,
        0xFF, 0xC0, 0x00, 0x11, 0x08, (h >> 8) & 255, h & 255, (w >> 8) & 255, w & 255, 0x03, 1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1, 0xFF, 0xD9];
    return Buffer.from(b);
}

class Document {
    constructor(app, opts) {
        this.app = app;
        this._layers = [];
        this.artboards = [];
        this.origin = opts.origin || [0, 0];
        this.documentColorSpace = opts.colorSpace || "RGB";
        this.rasterEffectSettings = { resolution: 72 };
        this.fullName = opts.file || null;
        this.saved = true;
        this.changes = 0;
        this.touchedBy = [];
        this.closed = false;
    }
    get layers() {
        const self = this, list = this._layers.slice();
        list.add = () => { const l = new Layer("Layer", self); self._layers.unshift(l); self.saved = false; self.changes++; return l; };
        return list;
    }
    get placedItems() {
        const out = [];
        const walk = n => (n.kids || []).forEach(k => { if (k.typename === "PlacedItem") out.push(k); walk(k); });
        const walkLayer = l => { walk(l); l.sub.forEach(walkLayer); };
        this._layers.forEach(walkLayer);
        return out;
    }
    addArtboard(rect, name) {
        const doc = this;
        const ab = {
            name: name || "Artboard " + (this.artboards.length + 1),
            _rect: rect.slice(),
            get artboardRect() { return this._rect.slice(); },
            set artboardRect(r) { this._rect = r.slice(); doc.saved = false; doc.changes++; },
        };
        this.artboards.push(ab);
        return ab;
    }
    saveAs(file) {
        if (String(file).indexOf("READONLY") >= 0) throw new Error("saveAs: folder is read only");
        fs.writeFileSync(String(file), "fake ai file");
        this.fullName = new File(String(file));
        this.saved = true;
    }
    save() {
        if (!this.fullName) throw new Error("save: never saved");
        if (this.isSource) throw new Error("save: the presentation must never be saved");
        this.saved = true;
    }
    close() { this.closed = true; this.app.forget(this); }
    activate() { this.app.activeDocument = this; }
    exportForScreens(folder, type, opts, what) {
        if (type !== "SE_JPEG100") throw new Error("exportForScreens: unexpected type " + type);
        if (opts.scaleType !== "SCALEBYFACTOR") throw new Error("exportForScreens: unexpected scale type");
        const f = opts.scaleTypeValue, sub = path.join(folder.fsName, f + "x");
        fs.mkdirSync(sub, { recursive: true });
        String(what.artboards).split(",").forEach(n => {
            const ab = this.artboards[Number(n) - 1];
            if (!ab) throw new Error("exportForScreens: no artboard " + n);
            const r = ab.artboardRect;
            fs.writeFileSync(path.join(sub, ab.name + ".jpg"), jpegBytes(Math.round((r[2] - r[0]) * f), Math.round((r[1] - r[3]) * f)));
        });
        fs.writeFileSync(path.join(sub, ".DS_Store"), "finder");   // Finder drops these into new folders
    }
}

class App {
    constructor() {
        const self = this;
        this.docs = [];
        this.coordinateSystem = "ARTBOARD";
        this.userInteractionLevel = "DISPLAYALERTS";
        this.activeDocument = null;
        this.opens = {};
        this.alerts = [];
        const prefs = this.prefs = { scaleLineWeight: false };
        this.preferences = {
            getBooleanPreference: k => !!prefs[k],
            setBooleanPreference: (k, v) => { prefs[k] = !!v; },
        };
        const docs = this.docs;
        Object.defineProperty(this, "documents", {
            get() {
                const list = docs.slice();
                list.addDocument = (preset, p) => self.newGrid(p.width, p.height, p.numArtboards, p.artboardRowsOrCols, p.artboardSpacing, p.colorMode);
                list.add = (cs, w, h, n, layout, gap, cols) => self.newGrid(w, h, n, cols, gap, cs);
                return list;
            },
        });
    }
    newGrid(w, h, n, cols, gap, cs) {
        if (!(n >= 1 && n <= 1000)) throw new Error("addDocument: bad artboard count " + n);
        const doc = new Document(this, { origin: [3137, -2211], colorSpace: cs });
        doc._layers.push(new Layer("Layer 1", doc));
        for (let i = 0; i < n; i++) {
            const c = i % cols, r = Math.floor(i / cols), l = c * (w + gap), t = -r * (h + gap);
            if (l + w > 16000 || -t + h > 16000) throw new Error("addDocument: artboards past the canvas");
            doc.addArtboard([l, t, l + w, t - h]);
        }
        this.docs.push(doc);
        this.activeDocument = doc;
        return doc;
    }
    register(file, doc) { this.opens[String(file)] = doc; }
    open(file) {
        const doc = this.opens[String(file)];
        if (!doc) throw new Error("open: no such file " + file);
        doc.fullName = new File(String(file));
        if (this.docs.indexOf(doc) < 0) this.docs.push(doc);
        this.activeDocument = doc;
        return doc;
    }
    forget(doc) {
        const i = this.docs.indexOf(doc);
        if (i >= 0) this.docs.splice(i, 1);
        if (this.activeDocument === doc) this.activeDocument = this.docs[this.docs.length - 1] || null;
    }
    executeMenuCommand() {}
}

// ---------- ScriptUI ----------
class Control {
    constructor(type, text) {
        this.type = type;
        this.text = text;
        this.kids = [];
        this.preferredSize = { width: 0, height: 0 };
        this.layout = { layout: () => { this.preferredSize = { width: 900, height: 700 }; } };
        if (type === "dropdownlist") {
            this.items = (text || []).map((t, i) => ({ text: t, index: i }));
            let sel = null;
            Object.defineProperty(this, "selection", {
                get() { return sel; },
                set(v) { sel = typeof v === "number" ? this.items[v] : v; },
            });
        }
    }
    add(type, bounds, text) { const c = new Control(type, text); this.kids.push(c); return c; }
    show() { return 1; }
    close() {}
    update() {}
}

// ---------- Globals the scripts expect ----------
function install(target, app) {
    const E = (...names) => Object.fromEntries(names.map(n => [n, n]));
    Object.assign(target, {
        app,
        $: { global: {} },
        alert: m => app.alerts.push(m),
        File, Folder,
        Window: function (type, title) { return new Control(type, title); },
        ElementPlacement: E("PLACEATBEGINNING", "PLACEATEND"),
        Transformation: E("CENTER"),
        BlendModes: { NORMAL: "normal" },
        Justification: { LEFT: "L", CENTER: "C", RIGHT: "R", FULLJUSTIFY: "F", FULLJUSTIFYLASTLINELEFT: "FL", FULLJUSTIFYLASTLINECENTER: "FC", FULLJUSTIFYLASTLINERIGHT: "FR" },
        CoordinateSystem: E("DOCUMENTCOORDINATESYSTEM", "ARTBOARDCOORDINATESYSTEM"),
        UserInteractionLevel: E("DONTDISPLAYALERTS", "DISPLAYALERTS"),
        SaveOptions: E("DONOTSAVECHANGES", "SAVECHANGES"),
        RulerUnits: E("Pixels", "Points"),
        DocumentArtboardLayout: E("GridByRow", "GridByCol"),
        DocumentRasterResolution: E("HighResolution", "ScreenResolution"),
        DocumentColorSpace: E("RGB", "CMYK"),
        ExportForScreensScaleType: E("SCALEBYFACTOR"),
        ExportForScreensType: E("SE_JPEG100"),
        AntiAliasingMethod: E("ARTOPTIMIZED"),
        DocumentPreset: function () {},
        IllustratorSaveOptions: function () {},
        ExportForScreensOptionsJPEG: function () {},
        ExportForScreensItemToExport: function () {},
        RGBColor: function () { this.typename = "RGBColor"; },
    });
}

module.exports = { App, Document, Layer, GroupItem, PathItem, CompoundPathItem, TextFrame, PlacedItem, RasterItem, File, Folder, install, setRoot };
