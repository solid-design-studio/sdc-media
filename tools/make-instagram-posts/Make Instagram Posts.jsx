// Make Instagram Posts
// Turns an approved presentation into designed 4:5 Instagram posts
// (1080 x 1350) in Illustrator.
//
// The presentation is treated as the source of content, not as a layout to
// copy. For every slide the script picks out what a designer would pull out of
// it: the background, each mockup or photo, each logo or graphic, and the text.
// Then it lays each piece out again on its own 1080 x 1350 artboard:
// - every mockup, photo and graphic gets its own post, whole, never cut in two
// - text is set again as one stack, at one size across the deck, aligned the
//   way it was written (left, centred, or right for Arabic)
// - a slide with one asset and a little text becomes one post, text above it
// - the slide's background (or the panel the piece sat on) carries over, so
//   every post keeps the brand colour
// - page numbers, corner logos and small slide captions are left out
// Every post gets the same margins. Posts worth a second look (a photo trimmed
// a lot, an asset that leaves a lot of empty space) are listed at the end.
//
// The presentation itself is never changed. The posts go into a new file,
// "<name> Instagram.ai", next to it, and the JPGs into a folder with the same
// name. Run the script again on the posts file to export the JPGs again after
// adjusting a post.
//
// It lives in the shared Dropbox folder and is run from there with
// File > Scripts > Other Script..., so nothing is installed and every change
// made to this file reaches everyone the next time they run it.

#target illustrator

(function () {

    // ---------- Settings: change once, applies to every project ----------
    var SETTINGS = {
        postWidth: 1080,            // post size in pixels (the artboards in the posts file)
        postHeight: 1350,
        margin: 90,                 // clear space inside every post, in post pixels
        postGap: 120,               // space between the artboards in the posts file
        exportPpi: [300, 144, 72],  // 300 ppi = 4500 x 5625 px, 72 ppi = 1080 x 1350 px
        defaultExportPpi: 300,
        textBoost: 1.5,             // text in posts, compared with simply shrinking the slide to the post width
        textOnlyBoost: 1.3,         // text alone on a post is set this much larger again
        textGap: 48,                // space between text blocks that sat apart on the slide
        assetTextGap: 72,           // space between the text and the asset when they share a post
        graphicFill: 0.66,          // a logo or small graphic alone takes up this share of the clear space
        maxPhotoTrim: 0.2,          // a photo may lose up to this share of its width or height to fill a post edge to edge
        bgTrimNote: 0.35,           // a background photo trimmed more than this is listed to check
        maxImageEnlarge: 3,         // images enlarged more than this are listed to check they are sharp
        emptyShare: 0.3,            // asset posts whose asset covers less than this share of the clear space are listed
        comboKeep: 0.72,            // one asset and its text share a post if the asset keeps this share of its size alone
        comboTextShare: 0.4,        // ... and the text takes up no more than this share of the height
        detailedParts: 400,         // artwork with more parts than this (patterns) is listed to check after scaling
        postsPerFile: 120,          // Illustrator's canvas holds about this many posts; more go into a second file
        dropSlideLabels: true,      // leave out small captions at the top of slides, like "Primary Logo Lockup"
        dropSlideFurniture: true    // leave out page numbers and corner logos that repeat on most slides
    };

    var MODES = [
        { id: "design", label: "Designed: each asset on its own post", tag: "Designed" },
        { id: "fit", label: "Whole slide, shrunk to fit", tag: "Whole" },
        { id: "bleed", label: "Whole slide, filling the post", tag: "Fill" },
        { id: "skip", label: "Skip", tag: "Skip" }
    ];

    var POSTS_LAYER = "Instagram posts";
    var TEST = $.global.MIP_TEST || null;

    // ---------- Geometry (rects use Illustrator's y-up bounds: t > b) ----------

    function rectFromBounds(bd) { return { l: bd[0], t: bd[1], r: bd[2], b: bd[3] }; }
    function rw(r) { return r.r - r.l; }
    function rh(r) { return r.t - r.b; }
    function area(r) { return rw(r) * rh(r); }
    function cx(r) { return (r.l + r.r) / 2; }
    function cy(r) { return (r.t + r.b) / 2; }
    function sized(l, t, w, h) { return { l: l, t: t, r: l + w, b: t - h }; }
    function shift(r, dx, dy) { return { l: r.l + dx, t: r.t + dy, r: r.r + dx, b: r.b + dy }; }
    function inset(r, m) { return { l: r.l + m, t: r.t - m, r: r.r - m, b: r.b + m }; }
    function grow(r, mx, my) { return { l: r.l - mx, t: r.t + my, r: r.r + mx, b: r.b - my }; }

    function overlap(a, b) {
        var l = Math.max(a.l, b.l), r = Math.min(a.r, b.r);
        var t = Math.min(a.t, b.t), bo = Math.max(a.b, b.b);
        if (r - l <= 0.5 || t - bo <= 0.5) return null;
        return { l: l, t: t, r: r, b: bo };
    }

    function union(a, b) {
        if (!a) return b;
        if (!b) return a;
        return { l: Math.min(a.l, b.l), t: Math.max(a.t, b.t), r: Math.max(a.r, b.r), b: Math.min(a.b, b.b) };
    }

    function inside(a, outer, tol) {
        return a.l >= outer.l - tol && a.r <= outer.r + tol && a.t <= outer.t + tol && a.b >= outer.b - tol;
    }

    function shareInside(a, outer) {
        var o = overlap(a, outer);
        return o ? area(o) / area(a) : 0;
    }

    // Whole post pixels, so edges stay crisp and margins line up.
    function snap(r) {
        var l = Math.round(r.l), t = Math.round(r.t);
        return { l: l, t: t, r: l + (r.r - r.l), b: t - (r.t - r.b) };
    }

    // The largest rect with the post's proportions that fits in `within`,
    // centred as close to (x, y) as the area allows.
    function postRegion(within, x, y) {
        var aspect = SETTINGS.postWidth / SETTINGS.postHeight;
        var h = rh(within), w = h * aspect;
        if (w > rw(within)) { w = rw(within); h = w / aspect; }
        var l = Math.min(Math.max(x - w / 2, within.l), within.r - w);
        var t = Math.max(Math.min(y + h / 2, within.t), within.b + h);
        return { l: l, t: t, r: l + w, b: t - h };
    }

    // A w x h piece scaled to sit whole inside `box`, centred.
    function containIn(w, h, box) {
        var s = Math.min(rw(box) / w, rh(box) / h);
        return { s: s, rect: sized(cx(box) - w * s / 2, cy(box) + h * s / 2, w * s, h * s) };
    }

    // A w x h piece scaled to cover `box` edge to edge, centred. `trim` is the
    // share of its width or height that falls outside.
    function coverOf(w, h, box) {
        var s = Math.max(rw(box) / w, rh(box) / h);
        var trim = 1 - Math.min(rw(box) / (w * s), rh(box) / (h * s));
        return { s: s, trim: trim, rect: sized(cx(box) - w * s / 2, cy(box) + h * s / 2, w * s, h * s) };
    }

    function postRect() { return { l: 0, t: 0, r: SETTINGS.postWidth, b: -SETTINGS.postHeight }; }

    // ---------- Reading the presentation ----------

    function isClipPath(item) {
        if (item.typename === "PathItem") return item.clipping;
        if (item.typename === "CompoundPathItem") return item.pathItems.length > 0 && item.pathItems[0].clipping;
        return false;
    }

    function plainBounds(item) {
        var r = rectFromBounds(item.visibleBounds);
        return rw(r) > 0 && rh(r) > 0 ? r : null;
    }

    // The part of an item you can actually see, or null if nothing shows.
    // Groups are measured from their contents: a group clipped to the whole
    // slide often holds only a small logo, and Illustrator's own bounds for
    // nested clipping can be wrong.
    function itemRect(item, depth) {
        depth = depth || 0;
        if (item.typename !== "GroupItem" || depth > 6) return plainBounds(item);
        var n = item.pageItems.length;
        if (n > 400) return plainBounds(item);
        var clip = null, content = null;
        for (var i = 0; i < n; i++) {
            var ch = item.pageItems[i];
            if (item.clipped && isClipPath(ch)) { clip = rectFromBounds(ch.geometricBounds); continue; }
            if (ch.hidden) continue;
            content = union(content, itemRect(ch, depth + 1));
        }
        if (!content) return null;
        return clip ? overlap(clip, content) : content;
    }

    // Top-level visible items, top of the stack first.
    function collectItems(doc) {
        var out = [];
        function fromLayer(layer) {
            if (!layer.visible) return;
            for (var s = 0; s < layer.layers.length; s++) fromLayer(layer.layers[s]);
            for (var i = 0; i < layer.pageItems.length; i++) {
                var it = layer.pageItems[i];
                if (it.parent.typename !== "Layer") continue;
                if (it.hidden) continue;
                if (it.typename === "PathItem" && it.guides) continue;
                var r = itemRect(it);
                if (r) out.push({ item: it, rect: r });
            }
        }
        for (var i = 0; i < doc.layers.length; i++) fromLayer(doc.layers[i]);
        return out;
    }

    // Linked images whose file can't be found show up empty in the posts.
    function missingLinks(doc) {
        var out = [];
        for (var i = 0; i < doc.placedItems.length; i++) {
            var p = doc.placedItems[i], ok = false;
            try { ok = p.file.exists; } catch (e) { ok = false; }
            if (!ok) out.push(rectFromBounds(p.geometricBounds));
        }
        return out;
    }

    function isOpaque(item) {
        try { return item.opacity >= 99 && item.blendingMode === BlendModes.NORMAL; } catch (e) { return true; }
    }

    // Presentations often wrap a whole slide, or most of it, in one group. Open
    // such groups up so the background, photos, text and logos can be told apart.
    function openSlideGroups(items, ab) {
        var W = rw(ab), H = rh(ab);
        for (var pass = 0; pass < 4; pass++) {
            var opened = false, next = [];
            for (var i = 0; i < items.length; i++) {
                var it = items[i].item, c = items[i].cover;
                var big = area(c) >= W * H * 0.5;
                if (it.typename === "GroupItem" && big && it.pageItems.length > 0 && isOpaque(it)) {
                    for (var k = 0; k < it.pageItems.length; k++) {
                        var ch = it.pageItems[k];
                        if (ch.hidden || isClipPath(ch)) continue;
                        var r = itemRect(ch), o = r ? overlap(r, ab) : null;
                        if (o) next.push({ item: ch, rect: r, cover: o });
                    }
                    opened = true;
                } else {
                    next.push(items[i]);
                }
            }
            items = next;
            if (!opened) break;
        }
        return items;
    }

    function isImageItem(item) { return item.typename === "RasterItem" || item.typename === "PlacedItem"; }

    function hasImage(item, depth) {
        if (isImageItem(item)) return true;
        if (item.typename === "GroupItem" && depth < 4) {
            var n = Math.min(item.pageItems.length, 60);
            for (var i = 0; i < n; i++) if (hasImage(item.pageItems[i], depth + 1)) return true;
        }
        return false;
    }

    function countParts(item, cap) {
        if (item.typename === "CompoundPathItem") return item.pathItems.length;
        if (item.typename !== "GroupItem") return 1;
        var n = 0;
        for (var i = 0; i < item.pageItems.length && n <= cap; i++) n += countParts(item.pageItems[i], cap - n);
        return n;
    }

    // Live text, or a group holding only live text.
    function isTextItem(item, depth) {
        if (item.typename === "TextFrame") return true;
        if (item.typename !== "GroupItem" || depth > 3) return false;
        var n = item.pageItems.length, any = false;
        if (!n || n > 80) return false;
        for (var i = 0; i < n; i++) {
            var ch = item.pageItems[i];
            if (item.clipped && isClipPath(ch)) continue;
            if (ch.hidden) continue;
            if (!isTextItem(ch, depth + 1)) return false;
            any = true;
        }
        return any;
    }

    // "text", "image" or "graphic". Outlined text is common in brand decks: a
    // thin, wide line made of many letter shapes counts as text.
    function kindOf(e, ab) {
        if (e.kind) return e.kind;
        var it = e.item, c = e.cover, H = rh(ab), k = "graphic";
        if (isTextItem(it, 0)) k = "text";
        else if (hasImage(it, 0)) k = "image";
        else if ((it.typename === "GroupItem" || it.typename === "CompoundPathItem") &&
            rh(c) <= H * 0.06 && rw(c) >= rh(c) * 3 && countParts(it, 4) >= 3) k = "text";
        e.kind = k;
        return k;
    }

    // A photo that is one plain rectangle: a raster, a linked image, or an image
    // in a rectangular mask. A cut-out with a transparent background is not one.
    function isRectImage(item) {
        if (isImageItem(item)) {
            try { if (item.typename === "RasterItem" && item.transparent) return false; } catch (e) {}
            return true;
        }
        if (item.typename !== "GroupItem" || !item.clipped || item.pageItems.length > 3) return false;
        var clip = null, images = 0;
        for (var i = 0; i < item.pageItems.length; i++) {
            var ch = item.pageItems[i];
            if (isClipPath(ch)) clip = ch;
            else if (isImageItem(ch)) images++;
            else if (!ch.hidden) return false;
        }
        return images === 1 && clip !== null && clip.typename === "PathItem" && clip.pathPoints.length === 4;
    }

    // Large plain shapes, like a coloured half-slide panel or a big brand blob,
    // are what the content sits on, not content of their own.
    function isPanel(e, ab) {
        if (kindOf(e, ab) !== "graphic") return false;
        var c = e.cover, W = rw(ab), H = rh(ab), share = area(c) / (W * H);
        if (countParts(e.item, 3) > 2 || share < 0.05) return false;
        var edges = 0;
        if (c.l - ab.l < W * 0.01) edges++;
        if (ab.r - c.r < W * 0.01) edges++;
        if (ab.t - c.t < H * 0.01) edges++;
        if (c.b - ab.b < H * 0.01) edges++;
        // A big shape in the middle of the slide is only a panel if it is a
        // plain rectangle. A big logo mark is not.
        if (edges) return true;
        return share >= 0.15 && e.item.typename === "PathItem" && e.item.pathPoints.length <= 8;
    }

    // Small captions near the top of a slide, like "Primary Logo Lockup": one
    // thin line of text (often a shape per word), with nothing beside it or
    // just below it. Returns the items that make up such captions.
    function findSlideLabels(items, ab) {
        if (!SETTINGS.dropSlideLabels) return [];
        var W = rw(ab), H = rh(ab), lines = [], i, k;
        for (i = 0; i < items.length; i++) {
            var c = items[i].cover;
            if (ab.t - c.b > H * 0.1 || rh(c) > H * 0.025) continue;
            var joined = false;
            for (k = 0; k < lines.length && !joined; k++) {
                var b = lines[k].box;
                var sameLine = Math.min(b.t, c.t) - Math.max(b.b, c.b) > 0;
                var near = c.l - b.r <= H * 0.03 && b.l - c.r <= H * 0.03;
                if (sameLine && near) { lines[k].box = union(b, c); lines[k].members.push(items[i]); joined = true; }
            }
            if (!joined) lines.push({ box: c, members: [items[i]] });
        }
        var out = [];
        for (k = 0; k < lines.length; k++) {
            var box = lines[k].box, members = lines[k].members;
            if (rh(box) > H * 0.025 || rw(box) < rh(box) * 5 || rw(box) > W * 0.4) continue;
            var zone = { l: box.l - 40, t: ab.t, r: box.r + 40, b: box.b - H * 0.06 }, alone = true;
            for (i = 0; i < items.length && alone; i++) {
                if (area(items[i].cover) > W * H * 0.35) continue;
                var mine = false;
                for (var m = 0; m < members.length; m++) if (members[m] === items[i]) mine = true;
                if (!mine && overlap(items[i].cover, zone)) alone = false;
            }
            if (alone) out = out.concat(members);
        }
        return out;
    }

    // Reads one slide: its background and the items on top of it.
    function readSlide(ab, index, allItems, missing) {
        var W = rw(ab), H = rh(ab), found = [], i, k;
        for (i = 0; i < allItems.length; i++) {
            var o = overlap(allItems[i].rect, ab);
            if (o) found.push({ item: allItems[i].item, rect: allItems[i].rect, cover: o });
        }
        found = openSlideGroups(found, ab);
        var labels = findSlideLabels(found, ab), items = [];
        for (i = 0; i < found.length; i++) {
            var isLabel = false;
            for (k = 0; k < labels.length; k++) if (labels[k] === found[i]) isLabel = true;
            if (!isLabel) items.push(found[i]);
        }
        for (i = 0; i < items.length; i++) items[i].z = i;

        var slide = { index: index, ab: ab, items: items, labels: labels, bg: null, content: items,
            panels: [], assets: [], blocks: [], mode: "design", missing: "", note: "", plan: [] };
        for (i = 0; i < missing.length; i++) {
            if (overlap(missing[i], ab)) slide.missing = "a linked image is missing from the file";
        }
        // Background: the top-most opaque item covering the whole slide.
        for (i = 0; i < items.length; i++) {
            var c = items[i].cover;
            if (rw(c) >= W * 0.98 && rh(c) >= H * 0.98 && isOpaque(items[i].item)) {
                slide.bg = items[i];
                slide.content = items.slice(0, i);
                break;
            }
        }
        return slide;
    }

    // Page numbers, footers and corner logos: small items at the edge of the
    // slide, in the same place on most slides.
    function markFurniture(slides) {
        if (!SETTINGS.dropSlideFurniture || slides.length < 3) return;
        var counts = {}, i, k, e;
        function keys(e, ab) {
            var W = rw(ab), H = rh(ab), c = e.cover;
            var q = function (v, d) { return Math.round(v / d * 200); };
            var base = e.item.typename + ":" + q(ab.t - c.t, H) + ":" + q(rh(c), H) + ":";
            var out = [base + "l" + q(c.l - ab.l, W), base + "r" + q(ab.r - c.r, W)];
            if (kindOf(e, ab) !== "text") { out[0] += ":" + q(rw(c), W); out[1] += ":" + q(rw(c), W); }
            return out;
        }
        function atEdge(e, ab) {
            var W = rw(ab), H = rh(ab), c = e.cover;
            if (area(c) >= W * H * 0.03) return false;
            return c.l - ab.l < W * 0.15 || ab.r - c.r < W * 0.15 || ab.t - c.t < H * 0.15 || c.b - ab.b < H * 0.15;
        }
        for (i = 0; i < slides.length; i++) {
            var seen = {};
            for (k = 0; k < slides[i].content.length; k++) {
                e = slides[i].content[k];
                if (!atEdge(e, slides[i].ab)) continue;
                e.keys = keys(e, slides[i].ab);
                for (var j = 0; j < 2; j++) {
                    if (seen[e.keys[j]]) continue;
                    seen[e.keys[j]] = true;
                    counts[e.keys[j]] = (counts[e.keys[j]] || 0) + 1;
                }
            }
        }
        var need = Math.max(3, Math.ceil(slides.length * 0.4));
        for (i = 0; i < slides.length; i++) {
            for (k = 0; k < slides[i].content.length; k++) {
                e = slides[i].content[k];
                if (e.keys && (counts[e.keys[0]] >= need || counts[e.keys[1]] >= need)) e.furniture = true;
            }
        }
    }

    // Groups the entries that `joins` links, directly or through each other.
    function clusterBy(list, joins) {
        var group = [], i, k;
        for (i = 0; i < list.length; i++) group.push(i);
        function root(i) { while (group[i] !== i) i = group[i]; return i; }
        for (i = 0; i < list.length; i++) {
            for (k = i + 1; k < list.length; k++) {
                if (root(i) !== root(k) && joins(list[i], list[k])) group[root(k)] = root(i);
            }
        }
        var byRoot = {}, out = [];
        for (i = 0; i < list.length; i++) {
            var r = root(i);
            if (!byRoot[r]) { byRoot[r] = []; out.push(byRoot[r]); }
            byRoot[r].push(list[i]);
        }
        return out;
    }

    function byStack(a, b) { return a.z - b.z; }

    function boxOf(members) {
        var box = null;
        for (var i = 0; i < members.length; i++) box = union(box, members[i].cover);
        return box;
    }

    function makeAsset(members, ab) {
        members.sort(byStack);
        var a = { members: members, box: boxOf(members), kind: "graphic", bleeds: false };
        var image = false;
        for (var i = 0; i < members.length; i++) if (kindOf(members[i], ab) === "image") image = true;
        if (image) a.kind = members.length === 1 && isRectImage(members[0].item) ? "photo" : "mockup";
        a.share = area(a.box) / area(ab);
        if (a.kind === "photo") {
            // Photos set edge to edge on the slide, or large ones, were placed as
            // photos and can fill a post. Smaller ones are shown whole.
            var W = rw(ab), H = rh(ab), b = a.box, edges = 0;
            if (b.l - ab.l < W * 0.01) edges++;
            if (ab.r - b.r < W * 0.01) edges++;
            if (ab.t - b.t < H * 0.01) edges++;
            if (b.b - ab.b < H * 0.01) edges++;
            a.bleeds = edges >= 2 || a.share >= 0.4;
        }
        return a;
    }

    function justification(item, depth, tally) {
        if (item.typename === "TextFrame") {
            try {
                var j = item.textRange.paragraphAttributes.justification;
                if (j === Justification.CENTER || j === Justification.FULLJUSTIFYLASTLINECENTER) tally.center++;
                else if (j === Justification.RIGHT || j === Justification.FULLJUSTIFYLASTLINERIGHT) tally.right++;
                else tally.left++;
            } catch (e) {}
            return;
        }
        if (item.typename === "GroupItem" && depth < 3) {
            for (var i = 0; i < item.pageItems.length; i++) justification(item.pageItems[i], depth + 1, tally);
        }
    }

    // Left, centre or right, as the text was set. Outlined text has no setting,
    // so it goes by where it sat on the slide.
    function blockAlign(members, box, ab) {
        var tally = { left: 0, center: 0, right: 0 };
        for (var i = 0; i < members.length; i++) justification(members[i].item, 0, tally);
        if (tally.left + tally.center + tally.right) {
            if (tally.center > tally.left && tally.center >= tally.right) return "center";
            return tally.right > tally.left ? "right" : "left";
        }
        if (Math.abs(cx(box) - cx(ab)) < rw(ab) * 0.04) return "center";
        return box.l - ab.l <= ab.r - box.r ? "left" : "right";
    }

    function readingOrder(list, ab) {
        var H = rh(ab);
        list.sort(function (a, b) {
            if (Math.abs(a.box.t - b.box.t) > H * 0.04) return b.box.t - a.box.t;
            return a.box.l - b.box.l;
        });
        return list;
    }

    // Sorts a slide's content into what goes on the posts: assets (mockups,
    // photos, graphics), text blocks, and the panels they sit on.
    function shapeSlide(slide) {
        var ab = slide.ab, W = rw(ab), H = rh(ab), A = W * H, i, k;
        var texts = [], others = [], specks = [];
        slide.panels = [];
        for (i = 0; i < slide.content.length; i++) {
            var e = slide.content[i];
            if (e.furniture) continue;
            var kind = kindOf(e, ab);
            if (kind === "text") texts.push(e);
            else if (isPanel(e, ab)) slide.panels.push(e);
            else if (area(e.cover) < A * 0.0015) specks.push(e);
            else others.push(e);
        }

        // Parts that overlap (a phone, its screen and its shadow) are one asset.
        var tol = W * 0.004;
        var groups = clusterBy(others, function (a, b) { return !!overlap(grow(a.cover, tol, tol), b.cover); });
        // Specks touching an asset belong to it. Lone specks are decoration.
        for (i = 0; i < specks.length; i++) {
            for (k = 0; k < groups.length; k++) {
                if (overlap(grow(boxOf(groups[k]), W * 0.02, W * 0.02), specks[i].cover)) { groups[k].push(specks[i]); break; }
            }
        }
        var assets = [];
        for (i = 0; i < groups.length; i++) assets.push(makeAsset(groups[i], ab));

        // One photo filling almost the whole slide is the slide's background.
        slide.designBg = null;
        if (!slide.bg || !hasImage(slide.bg.item, 0)) {
            for (i = 0; i < assets.length; i++) {
                if (assets[i].kind === "photo" && assets[i].share >= 0.85) {
                    slide.designBg = assets[i].members[0];
                    assets.splice(i, 1);
                    break;
                }
            }
        }

        // Text sitting on a mockup or photo is part of it, like a screen's copy.
        var loose = [];
        for (i = 0; i < texts.length; i++) {
            var host = null;
            for (k = 0; k < assets.length && !host; k++) {
                if (shareInside(texts[i].cover, assets[k].box) >= 0.7) host = assets[k];
            }
            if (host) host.members.push(texts[i]);
            else loose.push(texts[i]);
        }
        for (i = 0; i < assets.length; i++) assets[i] = makeAsset(assets[i].members, ab);

        // Several small pieces (icons, swatches, a row of logos) read as one set.
        var small = [], big = [];
        for (i = 0; i < assets.length; i++) (assets[i].share < 0.04 ? small : big).push(assets[i]);
        if (small.length >= 2) {
            var all = [];
            for (i = 0; i < small.length; i++) all = all.concat(small[i].members);
            var set = makeAsset(all, ab);
            set.kind = set.kind === "graphic" ? "set" : "mockup";
            big.push(set);
        } else {
            big = assets;
        }
        slide.assets = readingOrder(big, ab);

        // Lines of text close together are one block.
        var blocks = clusterBy(loose, function (a, b) { return !!overlap(grow(a.cover, W * 0.02, H * 0.035), b.cover); });
        slide.blocks = [];
        for (i = 0; i < blocks.length; i++) {
            blocks[i].sort(byStack);
            var box = boxOf(blocks[i]);
            slide.blocks.push({ members: blocks[i], box: box, align: blockAlign(blocks[i], box, ab) });
        }
        readingOrder(slide.blocks, ab);
        return slide;
    }

    // ---------- Designing the posts (geometry only, nothing is drawn yet) ----------

    // What a post sits on: the panel its content sat on, else the slide's
    // background, else white.
    function backgroundOf(slide) {
        return slide.mode === "design" && slide.designBg ? slide.designBg : slide.bg;
    }

    function surfaceFor(slide, box, R) {
        var source = null;
        if (box) {
            for (var i = 0; i < slide.panels.length && !source; i++) {
                if (shareInside(box, slide.panels[i].cover) >= 0.9) source = slide.panels[i];
            }
        }
        if (!source) source = backgroundOf(slide);
        if (!source) return { white: true };
        var c = source.cover, cover = coverOf(rw(c), rh(c), R);
        return { entry: source, fill: fillOf(source.item), from: c, to: cover.rect, trim: cover.trim,
            photo: hasImage(source.item, 0) };
    }

    function mainAlign(blocks) {
        var best = null;
        for (var i = 0; i < blocks.length; i++) if (!best || area(blocks[i].box) > area(best.box)) best = blocks[i];
        return best ? best.align : "left";
    }

    // Sets the text blocks again as one stack inside `box`, in reading order,
    // all aligned the same way. Lines that sat close keep their spacing.
    function stackTexts(blocks, scale, box, valign, slide) {
        var H = rh(slide.ab), align = mainAlign(blocks), out, total, tries;
        for (tries = 0; tries < 4; tries++) {
            out = { pieces: [], height: 0, width: 0, align: align, shrunk: false };
            var sizes = [], gaps = [], i;
            total = 0;
            for (i = 0; i < blocks.length; i++) {
                var b = blocks[i].box, s = Math.min(scale, rw(box) / rw(b));
                if (s < scale * 0.75) out.shrunk = true;
                sizes.push({ s: s, w: rw(b) * s, h: rh(b) * s });
                total += sizes[i].h;
                if (i > 0) {
                    var p = blocks[i - 1].box, g0 = p.b - b.t;
                    var stacked = Math.min(p.r, b.r) - Math.max(p.l, b.l) > 0 && g0 >= 0 && g0 <= H * 0.12;
                    var g = stacked ? Math.min(Math.max(g0 * s, 16), SETTINGS.textGap * 1.5) : SETTINGS.textGap;
                    gaps.push(g);
                    total += g;
                }
                out.width = Math.max(out.width, sizes[i].w);
            }
            if (total <= rh(box) + 0.5) break;
            scale *= rh(box) / total;
        }
        var y = valign === "top" ? box.t : (valign === "bottom" ? box.b + total : cy(box) + total / 2);
        for (i = 0; i < blocks.length; i++) {
            var z = sizes[i], x = align === "center" ? cx(box) - z.w / 2 : (align === "right" ? box.r - z.w : box.l);
            out.pieces.push({ members: blocks[i].members, clip: grow(blocks[i].box, 2, 2), from: blocks[i].box, to: sized(x, y, z.w, z.h), text: true });
            y -= z.h + (i < gaps.length ? gaps[i] : 0);
        }
        out.height = total;
        out.box = null;
        for (i = 0; i < out.pieces.length; i++) out.box = union(out.box, out.pieces[i].to);
        return out;
    }

    // Where an asset goes inside `box`: whole, as large as it fits. A photo
    // alone may fill the post edge to edge when that trims only a little.
    function placeAsset(asset, box, R, alone) {
        var b = asset.box, w = rw(b), h = rh(b);
        if (alone && asset.kind === "photo" && asset.bleeds) {
            var cover = coverOf(w, h, R);
            if (cover.trim <= SETTINGS.maxPhotoTrim) return { rect: cover.rect, s: cover.s, bleed: true, trim: cover.trim };
        }
        var target = box;
        if ((asset.kind === "graphic" || asset.kind === "set") && asset.share < 0.15) {
            var f = SETTINGS.graphicFill;
            target = sized(cx(box) - rw(box) * f / 2, cy(box) + rh(box) * f / 2, rw(box) * f, rh(box) * f);
        }
        var c = containIn(w, h, target);
        return { rect: c.rect, s: c.s, bleed: false };
    }

    function kindName(asset) {
        if (asset.kind === "graphic") return asset.share < 0.15 ? "logo" : "graphic";
        return asset.kind;
    }

    function detailed(members) {
        var parts = 0, cap = SETTINGS.detailedParts + 1;
        for (var i = 0; i < members.length && parts < cap; i++) parts += countParts(members[i].item, cap - parts);
        return parts > SETTINGS.detailedParts;
    }

    function textsBox(blocks) {
        var box = null;
        for (var i = 0; i < blocks.length; i++) box = union(box, blocks[i].box);
        return box;
    }

    // Text beside the asset (sharing some of its height), rather than above or below it.
    function sideBySide(a, b) { return Math.min(a.t, b.t) - Math.max(a.b, b.b) > 0; }

    function assetNotes(asset, place, safe) {
        var notes = [];
        var vector = asset.kind === "graphic" || asset.kind === "set";
        if (!vector && place.s > SETTINGS.maxImageEnlarge) notes.push("image enlarged a lot, check it is sharp");
        // Logos and small graphics are meant to have room around them.
        if (!place.bleed && !vector) {
            var o = overlap(place.rect, safe);
            if (!o || area(o) / area(safe) < SETTINGS.emptyShare) notes.push("a lot of empty space around the asset");
        }
        if (detailed(asset.members)) notes.push("detailed pattern was scaled, check it looks right");
        return notes;
    }

    function surfaceNotes(surface) {
        if (surface.photo && surface.trim > SETTINGS.bgTrimNote) return ["background photo trimmed a lot, check the crop"];
        return [];
    }

    // The posts the "Designed" option makes for a slide.
    function planDesigned(slide) {
        var R = postRect(), safe = inset(R, SETTINGS.margin), ab = slide.ab;
        var A = slide.assets, T = slide.blocks, posts = [], i;
        var textScale = SETTINGS.textBoost * SETTINGS.postWidth / rw(ab);

        if (!A.length && !T.length) {
            var bg = backgroundOf(slide);
            if (bg && hasImage(bg.item, 0)) {
                var sf = surfaceFor(slide, null, R);
                posts.push({ kind: "photo", surface: sf, pieces: [], notes: surfaceNotes(sf) });
            }
            return posts;
        }

        function textPost() {
            var st = stackTexts(T, textScale * SETTINGS.textOnlyBoost, safe, "center", slide);
            var sf = surfaceFor(slide, textsBox(T), R), notes = surfaceNotes(sf);
            if (st.shrunk) notes.push("a long line of text was set smaller to fit");
            return { kind: "text", surface: sf, pieces: st.pieces, notes: notes };
        }

        function assetPost(a) {
            var place = placeAsset(a, safe, R, true), sf = surfaceFor(slide, a.box, R);
            var notes = surfaceNotes(sf).concat(assetNotes(a, place, safe));
            if (place.bleed && place.trim > 0.02) notes.push("photo trimmed " + Math.round(place.trim * 100) + "% to fill the post");
            return { kind: kindName(a), surface: sf, pieces: [{ members: a.members, clip: a.box, from: a.box, to: place.rect }], notes: notes };
        }

        // One asset and a little text: one post, text above (or below, if it
        // was below on the slide), the asset as large as the space allows.
        function comboPost(a) {
            // A photo that can fill a post edge to edge gets that post to itself,
            // and text on a different panel keeps its own colour.
            if (placeAsset(a, safe, R, true).bleed) return null;
            if (surfaceFor(slide, textsBox(T), R).entry !== surfaceFor(slide, a.box, R).entry) return null;
            var measure = stackTexts(T, textScale, safe, "top", slide);
            if (measure.height > rh(safe) * SETTINGS.comboTextShare) return null;
            var solo = placeAsset(a, safe, R, false), tb = textsBox(T), gap = SETTINGS.assetTextGap;
            var textAbove = sideBySide(tb, a.box) || cy(tb) >= cy(a.box);
            var room = textAbove ? { l: safe.l, t: safe.t - measure.height - gap, r: safe.r, b: safe.b }
                : { l: safe.l, t: safe.t, r: safe.r, b: safe.b + measure.height + gap };
            if (rh(room) <= 0) return null;
            var place = placeAsset(a, room, R, false);
            if (place.s < solo.s * SETTINGS.comboKeep) return null;
            // Centre the whole composition, and line the asset up with the text.
            var ah = rh(place.rect), aw = rw(place.rect), total = measure.height + gap + ah, top = cy(safe) + total / 2;
            var ax = measure.align === "left" ? safe.l : (measure.align === "right" ? safe.r - aw : cx(safe) - aw / 2);
            var at = textAbove ? top - measure.height - gap : top;
            var tt = textAbove ? top : top - ah - gap;
            var st = stackTexts(T, textScale, { l: safe.l, t: tt, r: safe.r, b: tt - measure.height }, "top", slide);
            place.rect = sized(ax, at, aw, ah);
            var sf = surfaceFor(slide, union(tb, a.box), R);
            var notes = surfaceNotes(sf).concat(assetNotes(a, place, safe));
            if (st.shrunk) notes.push("a long line of text was set smaller to fit");
            // Text and asset together fill the clear space, so drop the empty-space note.
            for (var n = notes.length - 1; n >= 0; n--) if (notes[n].indexOf("empty space") >= 0) notes.splice(n, 1);
            var pieces = st.pieces.concat([{ members: a.members, clip: a.box, from: a.box, to: place.rect }]);
            return { kind: kindName(a) + " with text", surface: sf, pieces: pieces, notes: notes };
        }

        if (!A.length) return [textPost()];
        if (A.length === 1 && T.length) {
            var combo = comboPost(A[0]);
            if (combo) return [combo];
        }
        var tb = T.length ? textsBox(T) : null, first = A[0].box, textFirst = false;
        if (tb) {
            textFirst = sideBySide(tb, first) ? (mainAlign(T) === "right" ? tb.l > first.l : tb.l < first.l) : cy(tb) >= cy(first);
        }
        if (tb && textFirst) posts.push(textPost());
        for (i = 0; i < A.length; i++) posts.push(assetPost(A[i]));
        if (tb && !textFirst) posts.push(textPost());
        return posts;
    }

    function wholeContent(slide) {
        var out = [];
        for (var i = 0; i < slide.content.length; i++) if (!slide.content[i].furniture) out.push(slide.content[i]);
        return out;
    }

    // "Whole slide, shrunk to fit": the slide's layout as it is, centred on its
    // background inside the margins.
    function planFit(slide) {
        var R = postRect(), safe = inset(R, SETTINGS.margin), content = wholeContent(slide);
        var box = boxOf(content), sf = surfaceFor(slide, null, R);
        if (!box) return slide.bg ? [{ kind: "slide", surface: sf, pieces: [], notes: surfaceNotes(sf) }] : [];
        var c = containIn(rw(box), rh(box), safe), notes = [];
        if (c.s < 0.4 * SETTINGS.postWidth / rw(slide.ab)) notes.push("artwork gets small");
        if (detailed(content)) notes.push("detailed pattern was scaled, check it looks right");
        return [{ kind: "slide", surface: sf, pieces: [{ members: content, clip: slide.ab, from: box, to: c.rect }], notes: notes }];
    }

    // "Whole slide, filling the post": the slide as it is, trimmed at the sides.
    function planBleed(slide) {
        var R = postRect(), ab = slide.ab, content = wholeContent(slide);
        var box = boxOf(content), focus = box && area(box) < area(ab) * 0.9 ? [cx(box), cy(box)] : [cx(ab), cy(ab)];
        var region = postRegion(ab, focus[0], focus[1]);
        var members = slide.bg ? content.concat([slide.bg]) : content;
        if (!members.length) return [];
        var notes = [], trim = 1 - rw(region) / rw(ab);
        if (trim > SETTINGS.bgTrimNote) notes.push("slide trimmed " + Math.round(trim * 100) + "% at the sides, check nothing important is cut");
        return [{ kind: "slide", surface: { white: true }, pieces: [{ members: members, clip: ab, from: region, to: R }], notes: notes }];
    }

    function planFor(slide) {
        if (slide.mode === "skip") return [];
        if (slide.mode === "fit") return planFit(slide);
        if (slide.mode === "bleed") return planBleed(slide);
        return planDesigned(slide);
    }

    // ---------- Building the posts (in the new posts file) ----------

    function fillOf(item) {
        try {
            if (item.typename === "PathItem" && item.filled) return item.fillColor;
            if (item.typename === "CompoundPathItem" && item.pathItems.length && item.pathItems[0].filled) return item.pathItems[0].fillColor;
        } catch (e) {}
        return null;
    }

    function noFrame(path) { path.filled = false; path.stroked = false; return path; }

    function clipTo(group, r) {
        var clip = noFrame(group.pathItems.rectangle(r.t, r.l, rw(r), rh(r)));
        clip.move(group, ElementPlacement.PLACEATBEGINNING);
        clip.clipping = true;
        group.clipped = true;
    }

    // Copies `members` into `parent`, clipped to `clip` (slide coordinates),
    // and scales them so the slide rect `from` lands exactly on `to`.
    function placePiece(parent, members, clip, from, to) {
        var g = parent.groupItems.add(), src = null, landed = null, failed = 0;
        for (var i = 0; i < members.length; i++) {
            var d;
            try { d = members[i].item.duplicate(g, ElementPlacement.PLACEATEND); } catch (e) { failed++; continue; }
            try { d.locked = false; } catch (e2) {}
            src = union(src, members[i].rect);
            landed = union(landed, itemRect(d) || plainBounds(d));
        }
        if (!src || !landed) { g.remove(); return failed; }
        // The copies keep their place relative to each other, but the posts
        // file measures from its own origin. Find where they landed.
        var dx = landed.l - src.l, dy = landed.t - src.t;
        var c = shift(clip, dx, dy), f = shift(from, dx, dy);
        var mark = noFrame(g.pathItems.rectangle(f.t, f.l, rw(f), rh(f)));
        clipTo(g, c);
        var s = rw(to) / rw(from) * 100;
        g.resize(s, s, true, true, true, true, s, Transformation.CENTER);
        var m = rectFromBounds(mark.geometricBounds);
        g.translate(to.l - m.l, to.t - m.t);
        mark.remove();
        return failed;
    }

    function white() {
        var c = new RGBColor();
        c.red = 255; c.green = 255; c.blue = 255;
        return c;
    }

    function drawSurface(group, surface, R) {
        var rect = group.pathItems.rectangle(R.t, R.l, rw(R), rh(R));
        rect.stroked = false;
        if (surface.white) { rect.fillColor = white(); return; }
        if (surface.fill) {
            try { rect.fillColor = surface.fill; return; } catch (e) {}
        }
        // Photos, gradients and patterns: copy the real thing, scaled to cover the post.
        rect.fillColor = white();
        placePiece(group, [surface.entry], surface.from, surface.from, shift(surface.to, R.l, R.t));
    }

    function buildPost(layer, post, R) {
        var g = layer.groupItems.add(), failed = 0;
        drawSurface(g, post.surface, R);
        for (var i = 0; i < post.pieces.length; i++) {
            var p = post.pieces[i];
            failed += placePiece(g, p.members, p.clip, p.from, snap(shift(p.to, R.l, R.t)));
        }
        clipTo(g, R);
        return failed;
    }

    function pad(n) { return n < 10 ? "0" + n : "" + n; }

    // One entry per post to make, in order, named so the JPGs sort in order.
    function listPosts(slides) {
        var posts = [], n = 0;
        for (var i = 0; i < slides.length; i++) {
            var plan = slides[i].plan, used = {};
            for (var k = 0; k < plan.length; k++) {
                var kind = plan[k].kind;
                used[kind] = (used[kind] || 0) + 1;
                var count = 0;
                for (var j = 0; j < plan.length; j++) if (plan[j].kind === kind) count++;
                n++;
                plan[k].slide = slides[i];
                plan[k].name = pad(n) + " Slide " + pad(slides[i].index + 1) + " " + kind + (count > 1 ? " " + used[kind] : "");
                posts.push(plan[k]);
            }
        }
        return posts;
    }

    // ---------- Dialog ----------

    function ppiChoice(w) {
        var row = w.add("group");
        row.add("statictext", undefined, "Export JPGs at:");
        var labels = [];
        for (var i = 0; i < SETTINGS.exportPpi.length; i++) {
            var p = SETTINGS.exportPpi[i];
            labels.push(p + " ppi (" + Math.round(SETTINGS.postWidth * p / 72) + " x " + Math.round(SETTINGS.postHeight * p / 72) + " px)");
        }
        var size = row.add("dropdownlist", undefined, labels);
        size.selection = 0;
        for (i = 0; i < SETTINGS.exportPpi.length; i++) {
            if (SETTINGS.exportPpi[i] === SETTINGS.defaultExportPpi) size.selection = i;
        }
        return size;
    }

    function addButtons(w, okLabel) {
        var buttons = w.add("group");
        buttons.alignment = "right";
        buttons.add("button", undefined, "Cancel", { name: "cancel" });
        buttons.add("button", undefined, okLabel, { name: "ok" });
    }

    function modeIndex(id) {
        for (var i = 0; i < MODES.length; i++) if (MODES[i].id === id) return i;
        return 0;
    }

    function slideNotes(slide) {
        var out = [];
        if (slide.missing) out.push(slide.missing);
        for (var i = 0; i < slide.plan.length; i++) {
            for (var k = 0; k < slide.plan[i].notes.length; k++) {
                var n = slide.plan[i].notes[k], dup = false;
                for (var j = 0; j < out.length; j++) if (out[j] === n) dup = true;
                if (!dup) out.push(n);
            }
        }
        return out;
    }

    function countText(slide) {
        if (slide.mode === "skip") return "";
        var n = slide.plan.length;
        return n === 1 ? "1 post" : n + " posts";
    }

    function askPlan(docName, slides) {
        var w = new Window("dialog", "Make Instagram Posts");
        w.orientation = "column";
        w.alignChildren = ["fill", "top"];

        w.add("statictext", undefined, docName + ": " + slides.length + " slides. Your presentation stays as it is. The posts go into a new file next to it.");
        var help = w.add("panel", undefined, "Options");
        help.alignChildren = ["left", "top"];
        help.add("statictext", undefined, "Designed: every mockup, photo and logo gets its own post, whole. The text is set again, above it or on its own post.");
        help.add("statictext", undefined, "Whole slide, shrunk to fit: keeps the slide's layout, centred on its background.");
        help.add("statictext", undefined, "Whole slide, filling the post: keeps the slide's layout, trims the sides.");

        // At most 14 rows per column, so the window fits a laptop screen and the
        // buttons are never off the bottom. Long decks get more columns with
        // shorter labels. Past 84 slides there is no room to list them all, so
        // every slide gets the Designed option.
        var colCount = Math.ceil(slides.length / 14);
        var perCol = Math.ceil(slides.length / colCount);
        var compact = colCount > 2;
        var listed = slides.length <= 84;
        var labels = [];
        for (var i = 0; i < MODES.length; i++) labels.push(compact ? MODES[i].tag : MODES[i].label);

        var cols = w.add("group");
        cols.orientation = "row";
        cols.alignChildren = ["left", "top"];
        if (!listed) cols.add("statictext", undefined, "This presentation has too many slides to list. Every slide gets the Designed option, and you can adjust any post afterwards.");
        var col = null;
        function addRow(slide) {
            var row = col.add("group");
            row.add("statictext", undefined, "Slide " + (slide.index + 1)).preferredSize.width = 55;
            var d = row.add("dropdownlist", undefined, labels);
            d.selection = modeIndex(slide.mode);
            var count = row.add("statictext", undefined, countText(slide));
            count.preferredSize.width = 50;
            var note = row.add("statictext", undefined, "");
            note.preferredSize.width = compact ? 45 : 170;
            function showNotes() {
                var notes = slide.mode === "skip" ? [] : slideNotes(slide);
                note.text = notes.length ? (compact ? "check" : "check: " + notes[0] + (notes.length > 1 ? " (+" + (notes.length - 1) + ")" : "")) : "";
                note.helpTip = notes.join("\n");
                count.text = countText(slide);
            }
            showNotes();
            d.onChange = function () {
                slide.mode = MODES[d.selection.index].id;
                slide.plan = planFor(slide);
                showNotes();
            };
        }
        for (i = 0; listed && i < slides.length; i++) {
            if (i % perCol === 0) {
                col = cols.add("group");
                col.orientation = "column";
                col.alignChildren = ["left", "center"];
            }
            addRow(slides[i]);
        }

        var size = ppiChoice(w);
        addButtons(w, "Make posts");

        // Tests build the whole window and measure it, then carry on without waiting for a click.
        if (TEST) {
            if (TEST.cancel) return null;
            w.layout.layout(true);
            $.global.MIP_WINDOW = Math.round(w.preferredSize.width) + "x" + Math.round(w.preferredSize.height);
            return { ppi: TEST.ppi || 72 };
        }
        if (w.show() !== 1) return null;
        return { ppi: SETTINGS.exportPpi[size.selection.index] };
    }

    function progressWindow(total) {
        if (TEST) return { step: function () {}, close: function () {} };
        var w = new Window("palette", "Make Instagram Posts");
        var label = w.add("statictext", undefined, "Making posts...");
        label.preferredSize.width = 300;
        var bar = w.add("progressbar", undefined, 0, total);
        bar.preferredSize.width = 300;
        w.show();
        return {
            step: function (n, text) { bar.value = n; label.text = text; w.update(); },
            close: function () { w.close(); }
        };
    }

    // ---------- Output ----------

    function freeFile(folder, base, ext) {
        var f = File(folder + "/" + base + ext), n = 2;
        while (f.exists) { f = File(folder + "/" + base + " " + n + ext); n++; }
        return f;
    }

    function freeFolder(parent, base) {
        var f = Folder(parent + "/" + base), n = 2;
        while (f.exists) { f = Folder(parent + "/" + base + " " + n); n++; }
        return f;
    }

    // Writes the ppi into a JPG's header (the JFIF density), so the file reads
    // as 300 ppi in Photoshop and Finder, like Illustrator's own Export As.
    function jfifPatch(head, ppi) {
        if (head.length < 4 || head.charCodeAt(0) !== 0xFF || head.charCodeAt(1) !== 0xD8) return null;
        var hi = String.fromCharCode((ppi >> 8) & 255), lo = String.fromCharCode(ppi & 255);
        var density = "\x01" + hi + lo + hi + lo;
        if (head.charCodeAt(2) === 0xFF && head.charCodeAt(3) === 0xE0 && head.substr(6, 5) === "JFIF\x00") return { offset: 13, bytes: density };
        return { offset: -1, insert: "\xFF\xE0\x00\x10JFIF\x00\x01\x01" + density + "\x00\x00" };
    }

    function tagPpi(file, ppi) {
        try {
            file.encoding = "BINARY";
            if (!file.open("e")) return false;
            var plan = jfifPatch(file.read(20), ppi);
            if (plan && plan.offset >= 0) { file.seek(plan.offset); file.write(plan.bytes); }
            file.close();
            if (!plan || plan.offset >= 0) return !!plan;
            file.open("r");
            var all = file.read();
            file.close();
            file.open("w");
            file.write(all.substring(0, 2) + plan.insert + all.substring(2));
            file.close();
            return true;
        } catch (e) {
            try { file.close(); } catch (e2) {}
            return false;
        }
    }

    // Exports every artboard as a JPG at `ppi`. Artboards that are not 1080 px
    // wide are scaled so every JPG still comes out at the post size.
    function exportJpgs(doc, folder, ppi) {
        folder.create();
        var byScale = {}, scales = [], i;
        for (i = 0; i < doc.artboards.length; i++) {
            var r = rectFromBounds(doc.artboards[i].artboardRect);
            var f = Math.round(ppi / 72 * SETTINGS.postWidth / rw(r) * 10000) / 10000;
            if (!byScale[f]) { byScale[f] = []; scales.push(f); }
            byScale[f].push(i + 1);
        }
        for (i = 0; i < scales.length; i++) {
            var opts = new ExportForScreensOptionsJPEG();
            opts.scaleType = ExportForScreensScaleType.SCALEBYFACTOR;
            opts.scaleTypeValue = scales[i];
            try { opts.antiAliasing = AntiAliasingMethod.ARTOPTIMIZED; } catch (e0) {}
            var what = new ExportForScreensItemToExport();
            what.artboards = byScale[scales[i]].join(",");
            what.document = false;
            doc.exportForScreens(folder, ExportForScreensType.SE_JPEG100, opts, what, "");
        }
        // Illustrator puts the files in a size subfolder ("4.1667x"). Bring them up a level.
        var subs = folder.getFiles(function (x) { return x instanceof Folder; });
        for (i = 0; i < subs.length; i++) {
            var files = subs[i].getFiles("*.jpg");
            for (var k = 0; k < files.length; k++) {
                if (files[k].copy(folder.fsName + "/" + files[k].name)) files[k].remove();
            }
            subs[i].remove();
        }
        var jpgs = folder.getFiles("*.jpg"), untagged = 0;
        for (i = 0; i < jpgs.length; i++) if (!tagPpi(jpgs[i], ppi)) untagged++;
        return untagged;
    }

    // ---------- Main ----------

    function isPostsFile(doc) {
        for (var i = 0; i < doc.layers.length; i++) if (doc.layers[i].name === POSTS_LAYER) return true;
        return false;
    }

    // Run on a posts file (after adjusting posts), it exports the JPGs again
    // into a new folder.
    function exportAgain(doc, file) {
        var ppi = TEST && TEST.ppi ? TEST.ppi : SETTINGS.defaultExportPpi;
        if (!TEST) {
            app.userInteractionLevel = oldLevel;
            var w = new Window("dialog", "Make Instagram Posts");
            w.orientation = "column";
            w.alignChildren = ["fill", "top"];
            w.add("statictext", undefined, "This is a posts file. Export all " + doc.artboards.length + " posts as JPGs again?");
            var size = ppiChoice(w);
            addButtons(w, "Export");
            var ok = w.show() === 1;
            app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
            if (!ok) return "cancelled";
            ppi = SETTINGS.exportPpi[size.selection.index];
        }
        // A post resized out of the Instagram shape is trimmed back to 4:5,
        // centred inside the frame that was set, so every JPG is the post size.
        var trimmed = [], aspect = SETTINGS.postWidth / SETTINGS.postHeight;
        for (var i = 0; i < doc.artboards.length; i++) {
            var region = rectFromBounds(doc.artboards[i].artboardRect);
            if (Math.abs(rw(region) / rh(region) / aspect - 1) > 0.002) {
                region = postRegion(region, cx(region), cy(region));
                doc.artboards[i].artboardRect = [region.l, region.t, region.r, region.b];
                trimmed.push(doc.artboards[i].name);
            }
        }
        // Keep the adjusted posts: save the posts file before exporting.
        try { if (!doc.saved) doc.save(); } catch (eSave) {}
        var base = File.decode(file.name).replace(/\.[^\.]+$/, "");
        var parent = TEST && TEST.outFolder ? TEST.outFolder : file.parent, where = "next to this file";
        var folder = freeFolder(parent, base + " updated");
        if (!folder.create()) {
            folder = freeFolder(TEST && TEST.fallbackFolder ? TEST.fallbackFolder : Folder.desktop, base + " updated");
            where = "on your Desktop, because this file's folder can't be saved to";
        }
        exportJpgs(doc, folder, ppi);
        var msg = "Exported " + doc.artboards.length + " posts at " + ppi + " ppi to the folder \"" + File.decode(folder.name) + "\", " + where + ".";
        if (trimmed.length) msg += "\n\nThese posts were no longer the Instagram shape, so they were trimmed back to 4:5 inside the frame you set: " + trimmed.join(", ") + ".";
        app.userInteractionLevel = oldLevel;
        if (!TEST) alert(msg);
        return msg;
    }

    function run() {
        if (TEST && TEST.sourceFile) return makePosts(null, TEST.sourceFile);
        if (!app.documents.length) {
            app.userInteractionLevel = oldLevel;
            alert("Open the approved presentation first, then run Make Instagram Posts again.");
            return "no document";
        }
        var src = app.activeDocument, srcFile = null;
        try { srcFile = src.fullName; } catch (e) {}
        if (!srcFile || !srcFile.exists) {
            app.userInteractionLevel = oldLevel;
            alert("Save the presentation first, then run Make Instagram Posts again.");
            return "unsaved";
        }
        if (isPostsFile(src)) return exportAgain(src, srcFile);
        return makePosts(src, srcFile);
    }

    function newPostsFile(src, count) {
        var p = new DocumentPreset();
        p.width = SETTINGS.postWidth;
        p.height = SETTINGS.postHeight;
        p.units = RulerUnits.Pixels;
        p.colorMode = src.documentColorSpace;
        p.numArtboards = count;
        p.artboardLayout = DocumentArtboardLayout.GridByRow;
        p.artboardRowsOrCols = Math.max(1, Math.min(count, Math.ceil(Math.sqrt(count * 1.25))));
        p.artboardSpacing = SETTINGS.postGap;
        p.rasterResolution = DocumentRasterResolution.HighResolution;
        var doc;
        try {
            doc = app.documents.addDocument(src.documentColorSpace === DocumentColorSpace.CMYK ? "Print" : "Web", p, false);
        } catch (e0) {
            doc = app.documents.add(src.documentColorSpace, SETTINGS.postWidth, SETTINGS.postHeight, count,
                DocumentArtboardLayout.GridByRow, SETTINGS.postGap, p.artboardRowsOrCols);
        }
        // Shadows and blurs are drawn at 300 ppi, so they stay sharp in the JPGs.
        try { doc.rasterEffectSettings.resolution = 300; } catch (e) {}
        return doc;
    }

    // Builds `posts` into a new file, saves it and exports its JPGs.
    function makeFile(src, posts, outParent, fileBase, ppi, progress, done, total) {
        var doc = newPostsFile(src, posts.length), failed = [];
        var top = doc.layers[0];
        top.name = POSTS_LAYER;
        for (var i = 0; i < posts.length; i++) {
            var p = posts[i];
            progress.step(done + i, "Making " + p.name + " (" + (done + i + 1) + " of " + total + ")");
            var board = doc.artboards[i];
            board.name = p.name;
            var layer = top.layers.add();
            layer.name = p.name;
            // Posts read top to bottom in the Layers panel, in order.
            try { layer.move(top, ElementPlacement.PLACEATEND); } catch (eMove) {}
            try {
                var lost = buildPost(layer, p, rectFromBounds(board.artboardRect));
                if (lost) failed.push(p.name + " (" + lost + " item(s) could not be copied)");
            } catch (e) {
                failed.push(p.name + " (" + e.message + ")");
            }
        }
        var saveOpts = new IllustratorSaveOptions();
        saveOpts.pdfCompatible = true;
        saveOpts.embedICCProfile = true;
        var where = "next to your presentation";
        var outFile = freeFile(outParent, fileBase, ".ai");
        try { doc.saveAs(outFile, saveOpts); } catch (eSave) {}
        if (!File(outFile.fsName).exists) {
            // The presentation's folder can't be saved to, for example a folder
            // shared view-only. Save to the Desktop instead.
            outParent = TEST && TEST.fallbackFolder ? TEST.fallbackFolder : Folder.desktop;
            outFile = freeFile(outParent, fileBase, ".ai");
            try { doc.saveAs(outFile, saveOpts); } catch (eSave2) {}
            where = "on your Desktop, because the presentation's folder can't be saved to";
        }
        if (!File(outFile.fsName).exists) return { error: "save" };

        var jpgFolder = freeFolder(outParent, File.decode(outFile.name).replace(/\.[^\.]+$/, ""));
        var untagged = 0;
        try {
            untagged = exportJpgs(doc, jpgFolder, ppi);
        } catch (e5) {
            failed.push("JPG export (" + e5.message + ")");
        }
        doc.save();
        app.executeMenuCommand("fitall");
        return { doc: doc, file: outFile, folder: jpgFolder, where: where, failed: failed, untagged: untagged };
    }

    // Plans the posts from what is open, asks, then builds them in a new file.
    // The presentation is only read, never changed or saved.
    function makePosts(src, srcFile) {
        var i, k;
        var baseName = File.decode(srcFile.name).replace(/\.[^\.]+$/, "");
        var outParent = TEST && TEST.outFolder ? TEST.outFolder : srcFile.parent;
        var opened = !src;
        if (opened) src = app.open(srcFile);

        var all = collectItems(src);
        var missing = missingLinks(src);
        var slides = [];
        for (i = 0; i < src.artboards.length; i++) slides.push(readSlide(rectFromBounds(src.artboards[i].artboardRect), i, all, missing));
        markFurniture(slides);
        for (i = 0; i < slides.length; i++) {
            shapeSlide(slides[i]);
            slides[i].plan = planFor(slides[i]);
            if (!slides[i].plan.length) { slides[i].mode = "skip"; slides[i].note = "Empty"; }
        }

        if (TEST && TEST.planOnly) {
            var plan = [];
            for (i = 0; i < slides.length; i++) {
                var kinds = [];
                for (k = 0; k < slides[i].plan.length; k++) kinds.push(slides[i].plan[k].kind);
                plan.push((slides[i].index + 1) + "\t" + slides[i].mode + "\t" + kinds.join(", ") + "\t" + slideNotes(slides[i]).join("; "));
            }
            if (opened) src.close(SaveOptions.DONOTSAVECHANGES);
            return plan.join("\n");
        }

        if (TEST && TEST.modes) {
            for (i = 0; i < slides.length; i++) {
                if (TEST.modes[i + 1]) { slides[i].mode = TEST.modes[i + 1]; slides[i].plan = planFor(slides[i]); }
            }
        }
        app.userInteractionLevel = oldLevel;
        var choice = askPlan(File.decode(srcFile.name), slides);
        app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
        var posts = choice ? listPosts(slides) : [];
        if (!posts.length) {
            if (opened) src.close(SaveOptions.DONOTSAVECHANGES);
            app.userInteractionLevel = oldLevel;
            if (choice) alert("Every slide is set to Skip, so there is nothing to make.");
            return choice ? "nothing" : "cancelled";
        }

        // Illustrator's canvas holds about 120 posts, so long decks get more than one file.
        var chunks = Math.ceil(posts.length / SETTINGS.postsPerFile), results = [];
        var progress = progressWindow(posts.length);
        for (var c = 0; c < chunks; c++) {
            var part = posts.slice(c * SETTINGS.postsPerFile, (c + 1) * SETTINGS.postsPerFile);
            var fileBase = baseName + " Instagram" + (chunks > 1 ? " part " + (c + 1) : "");
            var res = makeFile(src, part, outParent, fileBase, choice.ppi, progress, c * SETTINGS.postsPerFile, posts.length);
            if (res.error) {
                progress.close();
                app.userInteractionLevel = oldLevel;
                if (!TEST) alert("Could not save the posts file. Check there is enough free space on your Mac, then run Make Instagram Posts again.");
                return "save failed";
            }
            results.push(res);
        }
        progress.close();
        if (opened) src.close(SaveOptions.DONOTSAVECHANGES);
        results[results.length - 1].doc.activate();

        var names = [], folders = [], failed = [], untagged = 0;
        for (i = 0; i < results.length; i++) {
            names.push(File.decode(results[i].file.name));
            folders.push("\"" + File.decode(results[i].folder.name) + "\"");
            failed = failed.concat(results[i].failed);
            untagged += results[i].untagged;
        }
        var checks = [];
        for (i = 0; i < posts.length; i++) {
            for (k = 0; k < posts[i].notes.length; k++) checks.push(posts[i].name + ": " + posts[i].notes[k]);
        }
        for (i = 0; i < slides.length; i++) {
            if (slides[i].mode !== "skip" && slides[i].missing) checks.push("Slide " + (slides[i].index + 1) + ": " + slides[i].missing);
        }
        var summary = "Made " + posts.length + " posts, 1080 x 1350, one asset per artboard.\n\nSaved " + names.join(" and ") +
            " and the JPGs (" + choice.ppi + " ppi) in " + folders.join(" and ") + ", " + results[0].where +
            ". Your presentation has not been changed. This window is now the posts file." +
            "\n\nTo adjust a post, double-click it to go inside, then move or scale the artwork. Run Make Instagram Posts again on this file to export the JPGs again.";
        if (checks.length) summary += "\n\nWorth a look:\n" + checks.join("\n");
        var dropped = [];
        for (i = 0; i < slides.length; i++) if (slides[i].mode !== "skip" && slides[i].labels.length) dropped.push(slides[i].index + 1);
        summary += "\n\nLeft out on purpose: page numbers and corner logos that repeat on most slides" +
            (dropped.length ? ", and the small slide captions (like \"Primary Logo Lockup\") on slides " + dropped.join(", ") : "") + ".";
        if (missing.length) summary += "\n\n" + missing.length + " linked image(s) are missing from the presentation. Relink them in Window > Links, then run this again.";
        if (untagged) summary += "\n\n" + untagged + " JPG(s) are the right size but could not be marked as " + choice.ppi + " ppi.";
        if (failed.length) summary += "\n\nCould not make:\n" + failed.join("\n");
        app.userInteractionLevel = oldLevel;
        if (!TEST) alert(summary);
        return summary;
    }

    // Tests load the layout logic on its own, without Illustrator.
    if (TEST && TEST.library) {
        $.global.MIP_LIB = {
            SETTINGS: SETTINGS, readSlide: readSlide, markFurniture: markFurniture, shapeSlide: shapeSlide,
            planFor: planFor, listPosts: listPosts, postRect: postRect, inset: inset, jfifPatch: jfifPatch,
            rw: rw, rh: rh, area: area, overlap: overlap, inside: inside
        };
        return;
    }

    var oldCoords = app.coordinateSystem;
    var oldLevel = app.userInteractionLevel;
    app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;
    app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
    var result;
    try {
        result = run();
    } catch (err) {
        result = "Error: " + err.message + " (line " + err.line + ")";
        app.userInteractionLevel = oldLevel;
        if (!TEST) alert("Make Instagram Posts stopped: " + err.message + "\n\nYour presentation has not been changed. This usually means your Mac is low on free space. Free some up, restart Illustrator, then run Make Instagram Posts again.");
    } finally {
        app.coordinateSystem = oldCoords;
        app.userInteractionLevel = oldLevel;
    }
    $.global.MIP_RESULT = result;
    return result;
})();
