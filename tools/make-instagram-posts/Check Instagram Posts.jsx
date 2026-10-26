// Check Instagram Posts
// Checks a posts file made by Make Instagram Posts, and the JPGs next to it,
// so a person only has to judge the design, not count pixels.
//
// Open "<name> Instagram.ai" in Illustrator, then run this with
// File > Scripts > Other Script... It changes nothing. It checks:
// - every artboard is 1080 x 1350, and every post has its own layer
// - every post shows something, and its artwork stays inside its artboard
// - every asset sits inside the margins, unless it fills the post edge to edge
// - no linked image is missing
// - there is one JPG per post, each at the post size for its ppi
//   (4500 x 5625 at 300 ppi), marked with that ppi
// The result shows in a message and is saved as "<name> check.txt" next to
// the posts file.

#target illustrator

(function () {

    var POST_W = 1080, POST_H = 1350, MARGIN = 90, TOL = 1;
    var POSTS_LAYER = "Instagram posts";
    var TEST = $.global.MIC_TEST || null;

    function rectFromBounds(bd) { return { l: bd[0], t: bd[1], r: bd[2], b: bd[3] }; }
    function rw(r) { return r.r - r.l; }
    function rh(r) { return r.t - r.b; }
    function inside(a, outer, tol) {
        return a.l >= outer.l - tol && a.r <= outer.r + tol && a.t <= outer.t + tol && a.b >= outer.b - tol;
    }
    function fills(a, outer, tol) {
        return a.l <= outer.l + tol && a.r >= outer.r - tol && a.t >= outer.t - tol && a.b <= outer.b + tol;
    }
    function isClipPath(item) {
        if (item.typename === "PathItem") return item.clipping;
        if (item.typename === "CompoundPathItem") return item.pathItems.length > 0 && item.pathItems[0].clipping;
        return false;
    }
    // A clipped group shows only what is inside its clip path.
    function shownRect(item) {
        if (item.typename === "GroupItem" && item.clipped) {
            for (var i = 0; i < item.pageItems.length; i++) {
                if (isClipPath(item.pageItems[i])) return rectFromBounds(item.pageItems[i].geometricBounds);
            }
        }
        return rectFromBounds(item.visibleBounds);
    }

    // Width, height and ppi of a JPG, read from its header bytes (a string of
    // char codes 0 to 255). Returns null if it is not a JPG.
    function jpegInfo(bytes) {
        function at(i) { return bytes.charCodeAt(i); }
        function u16(i) { return at(i) * 256 + at(i + 1); }
        if (bytes.length < 4 || at(0) !== 0xFF || at(1) !== 0xD8) return null;
        var info = { width: 0, height: 0, ppi: 0 }, off = 2;
        while (off + 4 <= bytes.length) {
            if (at(off) !== 0xFF) return info.width ? info : null;
            var m = at(off + 1);
            if (m === 0xFF) { off++; continue; }
            var len = u16(off + 2);
            if (m === 0xE0 && bytes.substr(off + 4, 5) === "JFIF\x00") {
                var units = at(off + 11), dens = u16(off + 12);
                info.ppi = units === 1 ? dens : (units === 2 ? Math.round(dens * 2.54) : 0);
            }
            if (m >= 0xC0 && m <= 0xCF && m !== 0xC4 && m !== 0xC8 && m !== 0xCC) {
                info.height = u16(off + 5);
                info.width = u16(off + 7);
                return info;
            }
            off += 2 + len;
        }
        return info.width ? info : null;
    }

    function readHead(file) {
        file.encoding = "BINARY";
        if (!file.open("r")) return "";
        var s = file.read(512 * 1024);
        file.close();
        return s;
    }

    function checkDoc(doc) {
        var fails = [], warns = [], i, k;
        var top = null;
        for (i = 0; i < doc.layers.length; i++) if (doc.layers[i].name === POSTS_LAYER) top = doc.layers[i];
        if (!top) return { fails: ["This is not a posts file: there is no \"" + POSTS_LAYER + "\" layer."], warns: [], count: 0 };

        var layers = {};
        for (i = 0; i < top.layers.length; i++) layers[top.layers[i].name] = top.layers[i];

        for (i = 0; i < doc.artboards.length; i++) {
            var ab = doc.artboards[i], name = ab.name, r = rectFromBounds(ab.artboardRect);
            if (Math.abs(rw(r) - POST_W) > 0.5 || Math.abs(rh(r) - POST_H) > 0.5) {
                fails.push(name + ": artboard is " + Math.round(rw(r)) + " x " + Math.round(rh(r)) + ", not 1080 x 1350");
            }
            var layer = layers[name];
            if (!layer) { fails.push(name + ": has no layer of its own"); continue; }
            if (!layer.pageItems.length) { fails.push(name + ": is empty"); continue; }
            var safe = { l: r.l + MARGIN, t: r.t - MARGIN, r: r.r - MARGIN, b: r.b + MARGIN };
            for (k = 0; k < layer.pageItems.length; k++) {
                var post = layer.pageItems[k], shown = shownRect(post);
                if (!inside(shown, r, TOL)) fails.push(name + ": artwork reaches past the artboard edge");
                if (post.typename !== "GroupItem") continue;
                // Inside the post: the background first, then one group per asset or text block.
                var pieces = 0;
                for (var j = 0; j < post.pageItems.length; j++) {
                    var p = post.pageItems[j];
                    if (isClipPath(p) || p.typename !== "GroupItem") continue;
                    var pr = shownRect(p);
                    if (fills(pr, r, TOL)) continue; // a background or a photo filling the post
                    pieces++;
                    if (!inside(pr, r, TOL)) fails.push(name + ": an asset is cut by the artboard edge");
                    else if (!inside(pr, safe, TOL)) warns.push(name + ": an asset sits inside the " + MARGIN + " px margin");
                }
                if (!pieces && post.pageItems.length < 3) warns.push(name + ": only a background, no asset or text");
            }
        }
        for (i = 0; i < doc.placedItems.length; i++) {
            var ok = false;
            try { ok = doc.placedItems[i].file.exists; } catch (e) {}
            if (!ok) { fails.push("A linked image is missing (" + (i + 1) + " of " + doc.placedItems.length + " links)"); break; }
        }
        return { fails: fails, warns: warns, count: doc.artboards.length };
    }

    function checkJpgs(folder, count, fails, warns) {
        if (!folder || !folder.exists) { fails.push("No JPG folder found next to the posts file"); return ""; }
        var files = folder.getFiles("*.jpg"), sizes = {};
        if (files.length !== count) fails.push(files.length + " JPGs for " + count + " posts");
        for (var i = 0; i < files.length; i++) {
            var n = File.decode(files[i].name), info = jpegInfo(readHead(files[i]));
            if (!info) { fails.push(n + ": not a readable JPG"); continue; }
            var ppi = info.ppi || 72, w = Math.round(POST_W * ppi / 72), h = Math.round(POST_H * ppi / 72);
            if (Math.abs(info.width - w) > 1 || Math.abs(info.height - h) > 1) {
                fails.push(n + ": " + info.width + " x " + info.height + " px, expected " + w + " x " + h + " at " + ppi + " ppi");
            }
            if (!info.ppi) warns.push(n + ": no ppi marked in the file");
            var key = info.width + " x " + info.height + " px, " + (info.ppi || "no") + " ppi";
            sizes[key] = (sizes[key] || 0) + 1;
        }
        var out = [];
        for (var s in sizes) out.push(sizes[s] + " at " + s);
        return out.join(", ");
    }

    function run() {
        if (!app.documents.length) { alert("Open the posts file first, then run Check Instagram Posts again."); return "no document"; }
        var doc = app.activeDocument, file = null;
        try { file = doc.fullName; } catch (e) {}
        var res = checkDoc(doc), jpgs = "";
        if (file && res.count) {
            var base = File.decode(file.name).replace(/\.[^\.]+$/, "");
            var folder = TEST && TEST.jpgFolder ? TEST.jpgFolder : Folder(file.parent + "/" + base);
            jpgs = checkJpgs(folder, res.count, res.fails, res.warns);
        }
        var lines = [res.fails.length ? "FAILED: " + res.fails.length + " problem(s)" : "PASSED: " + res.count + " posts"];
        if (jpgs) lines.push("JPGs: " + jpgs);
        if (res.fails.length) lines.push("", "Problems:", res.fails.join("\n"));
        if (res.warns.length) lines.push("", "Worth a look:", res.warns.join("\n"));
        var report = lines.join("\n");
        if (file) {
            var out = File(file.parent + "/" + File.decode(file.name).replace(/\.[^\.]+$/, "") + " check.txt");
            out.encoding = "UTF-8";
            if (out.open("w")) { out.write(report); out.close(); }
        }
        if (!TEST) alert(report.length > 1500 ? report.substring(0, 1500) + "\n\n(The full list is in the check.txt file.)" : report);
        return report;
    }

    if (TEST && TEST.library) { $.global.MIC_LIB = { jpegInfo: jpegInfo }; return; }
    var oldCoords = app.coordinateSystem, result;
    app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM;
    try { result = run(); } catch (err) { result = "Error: " + err.message + " (line " + err.line + ")"; if (!TEST) alert("Check Instagram Posts stopped: " + err.message); }
    finally { app.coordinateSystem = oldCoords; }
    $.global.MIC_RESULT = result;
    return result;
})();
