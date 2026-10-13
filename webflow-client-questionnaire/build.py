#!/usr/bin/env python3
"""Generate the Client Questionnaire markup, CSS, custom code and a local preview.

Outputs (in ./out):
  shell.html          -> root section inserted into the Webflow page Body (header, progress, empty form)
  step-XX.html        -> one step per PDF section, appended into the form's .cq-steps block
  nav.html            -> back/next/submit row + error line, appended after the steps
  styles.css          -> CSS passed with the shell insert (Webflow converts it to classes)
  head.html           -> page <head> custom code (Webflow form overrides + JS-driven states)
  footer.html         -> page footer custom code (stepper / conditional logic)
  preview.html        -> standalone replica of the published page for local testing
  standalone.html     -> the hosted page; also copied to ../solid-questionnaire/index.html
  fields.json         -> ordered field map used by the submission emails; also copied next to it
"""
import html
import importlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))

# python3 build.py            -> interior questionnaire (spec.py) at /interior
# python3 build.py branding   -> branding / graphic design questionnaire (spec_branding.py) at /graphic-design
# Either run also writes the landing page at / that links to both.
FORMS = {
    "interior": {
        "spec": "spec", "out": "out", "page": "interior/index.html", "fields": "fields.json",
        "path": "/interior", "card": "Interior &amp; Spatial Design",
        "blurb": "Restaurants, retail, workplaces, pop-ups, exhibitions and other spaces.",
        "title": "Client Questionnaire · Solid",
        "tag": "Client Questionnaire · Interior &amp; Spatial Design",
        "h1": 'Tell us about your <span class="cq-blue">space</span>.',
        "time": "Takes about 10–15 minutes. Answer only what applies to your project.",
        "relay": {"id": "interior", "subject": "New client questionnaire", "name": "01.1 Project / Brand Name",
                  "type": "01.5 Project type", "typeLabel": "Project type", "contact": "01.2 Primary Contact",
                  "location": "01.3 Project Location / Venue"},
    },
    "branding": {
        "spec": "spec_branding", "out": "out-branding", "page": "graphic-design/index.html", "fields": "fields-branding.json",
        "path": "/graphic-design", "card": "Branding &amp; Graphic Design",
        "blurb": "New brands, refreshes and visual identities.",
        "title": "Branding Questionnaire · Solid",
        "tag": "Client Questionnaire · Branding &amp; Graphic Design",
        "h1": 'Tell us about your <span class="cq-blue">brand</span>.',
        "time": "Takes about 5–10 minutes. Answer only what applies to your project.",
        "relay": {"id": "branding", "subject": "New branding questionnaire", "name": "00.1 Brand / Company Name",
                  "type": "01.1 Starting point", "typeLabel": "Starting point", "contact": "00.2 Primary Contact"},
    },
}
FORM_ID = sys.argv[1] if len(sys.argv) > 1 else "interior"
if FORM_ID not in FORMS:
    raise SystemExit("unknown questionnaire %r (choose from %s)" % (FORM_ID, ", ".join(FORMS)))
FORM = FORMS[FORM_ID]
_spec = importlib.import_module(FORM["spec"])
SECTIONS, INTRO = _spec.SECTIONS, _spec.INTRO
OUT = os.path.join(HERE, FORM["out"])
os.makedirs(OUT, exist_ok=True)

SITE = os.path.join(HERE, "..", "solid-questionnaire")
# Reference images live in the public "questionnaire" bucket of the Supabase project.
IMG_BASE = "https://bucsewbqwiljawcubyht.supabase.co/storage/v1/object/public/questionnaire/"


def img_url(name):
    return IMG_BASE + name


def esc(s):
    return html.escape(s, quote=True)


_uid = [0]


def uid(prefix):
    _uid[0] += 1
    return "%s-%d" % (prefix, _uid[0])


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------------------------------------------------------------- option cards

def is_unsure(label):
    return "not sure" in label.lower()


def checkbox_card(q, opt, idx):
    label = opt["label"] if isinstance(opt, dict) else opt
    img = opt.get("img") if isinstance(opt, dict) else None
    cls = "cq-opt"
    if img:
        cls += " cq-opt-img"
        if q.get("swatch"):
            cls += " cq-opt-swatch"
    elif q.get("img"):
        # options without a picture in an image question: a card under the pictures
        cls += " cq-opt-extra"
    if q.get("checklist"):
        cls += " cq-opt-check"
    elif q.get("small"):
        cls += " cq-opt-small"
    if is_unsure(label):
        cls += " cq-opt-unsure"
    cid = "cq-%s-%d" % (slug(q["id"]), idx)
    pic = ""
    if img:
        pic = '<img class="cq-opt-pic" src="%s" alt="%s" loading="lazy">' % (img_url(img), esc(label))
    # A bare checkbox inside the card: Webflow wraps it in its own label and uses the
    # input name as the visible option text.
    return ('<div class="%s" data-opt="%s">%s<input type="checkbox" id="%s" name="%s" value="Yes"></div>'
            % (cls, esc(label), pic, cid, esc(label)))


def radio_card(q, opt, idx):
    label = opt["label"] if isinstance(opt, dict) else opt
    desc = opt.get("desc") if isinstance(opt, dict) else None
    img = opt.get("img") if isinstance(opt, dict) else None
    cls = "cq-opt"
    if img:
        cls += " cq-opt-img"
    elif desc:
        cls += " cq-opt-stack"
    if is_unsure(label):
        cls += " cq-opt-unsure"
    rid = "cq-%s-%d" % (slug(q["id"]), idx)
    pic = '<img class="cq-opt-pic" src="%s" alt="%s" loading="lazy">' % (img_url(img), esc(label)) if img else ""
    inner = pic + ('<label class="w-radio cq-radio"><input type="radio" class="w-radio-input" id="%s" name="%s" value="%s">'
             '<span class="w-form-label">%s</span></label>' % (rid, esc(q["field"]), esc(label), esc(label)))
    if desc:
        inner += '<span class="cq-opt-desc">%s</span>' % esc(desc)
    return '<div class="%s" data-opt="%s">%s</div>' % (cls, esc(label), inner)


UPLOAD_ACCEPT = (".jpg,.jpeg,.png,.gif,.webp,.heic,.heif,.tif,.tiff,.svg,.pdf,.doc,.docx,.xls,.xlsx,.csv,.ppt,.pptx,"
                 ".key,.pages,.numbers,.txt,.rtf,.dwg,.dxf,.skp,.rvt,.ifc,.3dm,.ai,.psd,.indd,.eps,.zip,.rar,.7z,.mp4,.mov,.m4v")


def upload_box(q):
    """Drop zone + file list; uploaded storage paths go into one hidden field (one per line)."""
    return ('<div class="cq-upload">'
            '<label class="cq-drop"><input type="file" multiple accept="%s">'
            '<span class="cq-drop-title">Drag files here or <span class="cq-blue">browse</span></span>'
            '<span class="cq-drop-sub">Images, PDFs, drawings (DWG, SKP), Office files or ZIP · up to 50 MB each</span></label>'
            '<ul class="cq-files"></ul>'
            '<input type="hidden" name="%s" value=""></div>' % (UPLOAD_ACCEPT, esc(q["files_field"])))


def picture_options(q, opts, card):
    """Same-size picture cards on a grid; options without a picture follow as cards under "Or choose"."""
    pics = [(i, o) for i, o in opts if isinstance(o, dict) and o.get("img")]
    rest = [(i, o) for i, o in opts if not (isinstance(o, dict) and o.get("img"))]
    grid = "cq-options-img"
    for flag in ("swatch", "tall", "wide"):
        if q.get(flag):
            grid += " cq-options-" + flag
    out = '<div class="%s">%s</div>' % (grid, "".join(card(q, o, i) for i, o in pics))
    if rest:
        out += ('<p class="cq-or">Or choose</p><div class="cq-options cq-options-extra%s">%s</div>'
                % (" cq-options-extra-2" if q.get("wide") else "", "".join(card(q, o, i) for i, o in rest)))
    return out


def explain_options(q):
    """(option label, field suffix, placeholder) for every option that reveals a text box."""
    out = []
    for o in q.get("options", []):
        label = o["label"] if isinstance(o, dict) else o
        if label == "Other":
            out.append(("Other", "Other", "Please specify"))
        elif isinstance(o, dict) and o.get("explain"):
            out.append((label, o["explain"], o.get("placeholder", "Please describe")))
    return out


def explain_fields(q):
    parts = []
    for label, suffix, placeholder in explain_options(q):
        name = esc(q["field"] + " — " + suffix)
        if label == "Other":
            box = '<input class="cq-input" type="text" name="%s" placeholder="%s">' % (name, esc(placeholder))
        else:
            box = '<textarea class="cq-textarea" name="%s" rows="3" placeholder="%s"></textarea>' % (name, esc(placeholder))
        parts.append('<div class="cq-other%s" data-for="%s">%s</div>' % (
            "" if label == "Other" else " cq-other-wide", esc(label), box))
    return "".join(parts)


# ---------------------------------------------------------------- questions

def question_html(q, number):
    attrs = ['class="cq-q%s"' % (" cq-q-follow" if q.get("follow") else ""),
             'data-q="%s"' % q["id"], 'data-type="%s"' % q["type"]]
    if q.get("max"):
        attrs.append('data-max="%d"' % q["max"])
    if q.get("show_if"):
        attrs.append("data-show-if='%s'" % json.dumps(q["show_if"], ensure_ascii=False).replace("'", "&#39;"))
    if q.get("checklist"):
        attrs.append('data-check="1"')
    if q.get("required") and q["type"] == "single":
        attrs.append('data-required="1"')
    parts = ['<div %s>' % " ".join(attrs)]

    num_html = '<span class="cq-qn">%d.</span>' % number if number else ""
    label_text = esc(q["label"])
    hint = q.get("hint")
    if q["type"] in ("text", "textarea", "date"):
        parts.append('<p class="cq-label">%s%s</p>' % (num_html, label_text))
    else:
        parts.append('<p class="cq-label">%s%s</p>' % (num_html, label_text))
    if q.get("note"):
        parts.append('<p class="cq-note">%s</p>' % esc(q["note"]))
    if hint or q.get("max"):
        parts.append('<p class="cq-hint"><span>%s</span><span class="cq-count"></span></p>' % esc(hint or ""))

    t = q["type"]
    if t == "text":
        parts.append('<input class="cq-input" type="text" name="%s"%s%s>' % (
            esc(q["field"]),
            ' placeholder="%s"' % esc(q["placeholder"]) if q.get("placeholder") else "",
            " required" if q.get("required") else ""))
    elif t == "textarea":
        if q.get("upload"):
            parts.append(upload_box(q))
            parts.append('<span class="cq-sublabel">%s</span>' % esc(q.get("links_label", "Links (optional)")))
        parts.append('<textarea class="cq-textarea" name="%s" rows="%d"%s></textarea>' % (
            esc(q["field"]), q.get("rows", 4),
            ' placeholder="%s"' % esc(q["placeholder"]) if q.get("placeholder") else ""))
    elif t == "date":
        parts.append('<input class="cq-input cq-input-date" type="date" name="%s">' % esc(q["field"]))
    elif t == "number_group":
        cols = []
        for sub_label, field in q["fields"]:
            itype = "text" if q.get("text") else "number"
            extra = ' placeholder="%s"' % esc(q["placeholder"]) if q.get("placeholder") else ""
            if itype == "number":
                extra += ' min="0" placeholder="0"'
            cols.append('<div class="cq-col"><span class="cq-sublabel">%s</span>'
                        '<input class="cq-input" type="%s" name="%s"%s></div>' % (esc(sub_label), itype, esc(field), extra))
        parts.append('<div class="cq-row">%s</div>' % "".join(cols))
    elif t == "single":
        opts = list(enumerate(q["options"]))
        if q.get("img"):
            parts.append(picture_options(q, opts, radio_card))
        else:
            grid = "cq-options cq-options-inline" if q.get("inline") else "cq-options"
            if q.get("stack") or any(isinstance(o, dict) and o.get("desc") for o in q["options"]):
                grid = "cq-options cq-options-1"
            parts.append('<div class="%s">%s</div>' % (grid, "".join(radio_card(q, o, i) for i, o in opts)))
        parts.append(explain_fields(q))
    elif t == "multi":
        opts = list(enumerate(q["options"]))
        if q.get("img"):
            parts.append(picture_options(q, opts, checkbox_card))
        else:
            grid = "cq-options"
            if q.get("checklist"):
                grid += " cq-options-check"
            elif q.get("compact"):
                grid += " cq-options-4"
            elif q.get("small"):
                grid += " cq-options-2"
            parts.append('<div class="%s">%s</div>' % (grid, "".join(checkbox_card(q, o, i) for i, o in opts)))
        parts.append(explain_fields(q))
        parts.append('<input type="hidden" name="%s" data-collect="%s" value="">' % (esc(q["field"]), q["id"]))
    else:
        raise SystemExit("unknown type " + t)

    if q.get("help"):
        parts.append('<p class="cq-help">%s</p>' % esc(q["help"]))
    parts.append("</div>")
    return "".join(parts)


def questions_block(questions):
    out = []
    n = 0
    for q in questions:
        if q.get("follow"):
            out.append(question_html(q, 0))
        else:
            n += 1
            out.append(question_html(q, n))
    return "".join(out)


def step_html(sec):
    attrs = ['class="cq-step"', 'data-step="%s"' % sec["num"], 'data-title="%s"' % esc(sec["title"])]
    if sec.get("conditional_section"):
        attrs.append('data-conditional="1"')
    if sec.get("show_if"):
        attrs.append("data-show-if='%s'" % json.dumps(sec["show_if"], ensure_ascii=False))
    parts = ['<div %s>' % " ".join(attrs)]
    parts.append('<div class="cq-step-head"><h2 class="cq-h2">%s</h2>' % esc(sec["title"]))
    if sec.get("intro"):
        parts.append('<p class="cq-intro">%s</p>' % esc(sec["intro"]))
    if sec.get("hint"):
        parts.append('<p class="cq-intro cq-intro-strong">%s</p>' % esc(sec["hint"]))
    if sec.get("callout"):
        head, rest = sec["callout"]
        parts.append('<p class="cq-callout"><strong>%s</strong> %s</p>' % (esc(head), esc(rest)))
    parts.append("</div>")
    if sec.get("questions"):
        parts.append(questions_block(sec["questions"]))
    for sub in sec.get("subsections", []):
        parts.append("<div class=\"cq-sub\" data-sub=\"%s\" data-show-if='%s'>" % (
            sub["key"], json.dumps(sub["show_if"], ensure_ascii=False)))
        parts.append('<div class="cq-sub-head"><h3 class="cq-h3">%s</h3>'
                     '<p class="cq-intro">%s</p></div>' % (esc(sub["title"]), esc(sub["intro"])))
        parts.append(questions_block(sub["questions"]))
        parts.append("</div>")
    parts.append("</div>")
    return "".join(parts)


# ---------------------------------------------------------------- shell / nav

def shell_html():
    intro = "".join('<p class="cq-lead">%s</p>' % esc(p) for p in INTRO)
    return (
        '<section class="cq-page" id="client-questionnaire"><div class="cq-wrap">'
        '<header class="cq-head">'
        '<p class="cq-tag">%s</p>'
        '<h1 class="cq-h1">%s</h1>' % (FORM["tag"], FORM["h1"])
        + intro +
        '<p class="cq-note">%s</p>' % esc(FORM["time"]) +
        '</header>'
        '<div class="cq-progress"><div class="cq-progress-top">'
        '<span class="cq-progress-label" data-cq-step-label="1">Step 1 of %d</span>'
        '<span class="cq-progress-title" data-cq-step-title="1">%s</span></div>' % (len(SECTIONS), esc(SECTIONS[0]["title"])) +
        '<div class="cq-bar"><div class="cq-bar-fill" data-cq-bar="1"></div></div></div>'
        '<form class="cq-form" name="Client Questionnaire" data-name="Client Questionnaire" method="post">'
        '<div class="cq-steps"></div>'
        '</form>'
        '<p class="cq-foot">© Solid Design Studio</p>'
        '</div></section>'
    )


def nav_html():
    return (
        '<div class="cq-nav"><a href="#" class="cq-btn cq-btn-ghost" data-nav="back">Back</a>'
        '<div class="cq-nav-right"><a href="#" class="cq-btn" data-nav="next">Next section</a>'
        '<input type="submit" class="cq-btn cq-btn-submit" value="Submit questionnaire"></div></div>'
        '<p class="cq-error" data-cq-error="1">Please complete the highlighted fields before continuing.</p>'
    )


# ---------------------------------------------------------------- CSS

IBM = "'Ibm Plex Sans', sans-serif"
NM = "'Neue Montreal', sans-serif"

CSS = """
.cq-page { background-color: #FAFAFA; padding: 72px 28px 96px; font-family: %(nm)s; color: #111111; }
.cq-wrap { max-width: 880px; margin: 0 auto; }
.cq-head { margin-bottom: 36px; padding-bottom: 36px; border-bottom: 1px solid #DDDDDD; }
.cq-tag { font-family: %(ibm)s; font-size: 11px; line-height: 1.4; letter-spacing: 0.22em; text-transform: uppercase; color: #999999; margin: 0 0 16px; }
.cq-h1 { font-family: %(ibm)s; font-weight: 700; font-size: 56px; line-height: 1.05; letter-spacing: -0.01em; color: #111111; margin: 0 0 24px; }
.cq-blue { color: #2B36FF; }
.cq-lead { font-size: 17px; line-height: 1.55; color: #111111; max-width: 680px; margin: 0 0 12px; }
.cq-meta { display: inline-block; margin-top: 16px; padding: 7px 10px; background-color: #F0F0F0; border-radius: 4px; font-family: %(ibm)s; font-weight: 700; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #111111; }
.cq-progress { position: sticky; top: 0; z-index: 5; background-color: #FAFAFA; padding: 18px 0 14px; margin-bottom: 28px; border-bottom: 1px solid #DDDDDD; }
.cq-progress-top { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; margin-bottom: 10px; }
.cq-progress-label { font-family: %(ibm)s; font-weight: 700; font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; color: #111111; }
.cq-progress-title { font-size: 13px; color: #999999; text-align: right; }
.cq-bar { height: 4px; background-color: #E6E6E6; border-radius: 2px; overflow: hidden; }
.cq-bar-fill { height: 4px; width: 8%%; background-color: #2B36FF; border-radius: 2px; transition: width 300ms ease; }
.cq-form { margin: 0; }
.cq-steps { margin: 0; }
.cq-step { padding-top: 8px; margin-bottom: 40px; }
.cq-step-head { margin-bottom: 36px; }
.cq-step-num { display: block; font-family: %(ibm)s; font-weight: 700; font-size: 64px; line-height: 1; color: #111111; margin-bottom: 14px; }
.cq-h2 { font-family: %(ibm)s; font-weight: 700; font-size: 34px; line-height: 1.15; color: #111111; margin: 0 0 10px; }
.cq-h3 { font-family: %(ibm)s; font-weight: 700; font-size: 24px; line-height: 1.2; color: #111111; margin: 0 0 8px; }
.cq-intro { font-size: 15px; line-height: 1.5; color: #999999; margin: 0 0 6px; }
.cq-intro.cq-intro-strong { color: #111111; }
.cq-sub { margin-top: 48px; padding-top: 32px; border-top: 1px solid #DDDDDD; }
.cq-sub-head { margin-bottom: 28px; }
.cq-q { margin-bottom: 44px; }
.cq-q.cq-q-follow { margin-top: -24px; padding: 16px 0 0 20px; border-left: 3px solid #E8FF00; }
.cq-label { font-family: %(ibm)s; font-weight: 700; font-size: 18px; line-height: 1.3; color: #111111; margin: 0 0 8px; }
.cq-qn { color: #999999; margin-right: 8px; }
.cq-note { font-size: 14px; line-height: 1.5; color: #999999; margin: -2px 0 10px; max-width: 680px; }
.cq-hint { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; font-size: 13px; color: #999999; margin: 0 0 14px; }
.cq-count { font-family: %(ibm)s; font-weight: 700; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: #111111; white-space: nowrap; }
.cq-help { font-size: 13px; line-height: 1.5; color: #999999; margin: 10px 0 0; }
.cq-input { width: 100%%; height: 50px; padding: 0 16px; border: 1px solid #111111; border-radius: 6px; background-color: #FFFFFF; font-family: %(nm)s; font-size: 16px; color: #111111; margin: 0; }
.cq-input:focus { border-color: #2B36FF; outline-style: none; }
.cq-textarea { width: 100%%; min-height: 120px; padding: 14px 16px; border: 1px solid #111111; border-radius: 6px; background-color: #FFFFFF; font-family: %(nm)s; font-size: 16px; line-height: 1.5; color: #111111; margin: 0; resize: vertical; }
.cq-textarea:focus { border-color: #2B36FF; outline-style: none; }
.cq-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.cq-sublabel { display: block; font-size: 13px; color: #999999; margin-bottom: 6px; }
.cq-options { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.cq-options.cq-options-4 { grid-template-columns: repeat(4, 1fr); }
.cq-options.cq-options-2 { grid-template-columns: repeat(2, 1fr); }
.cq-options.cq-options-1 { grid-template-columns: 1fr; }
.cq-options-img { display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px 16px; }
.cq-options-img.cq-options-swatch { grid-template-columns: repeat(4, 1fr); gap: 24px 20px; }
.cq-options-img.cq-options-wide { grid-template-columns: repeat(2, 1fr); gap: 28px 20px; }
.cq-or { font-family: %(ibm)s; font-weight: 700; font-size: 11px; line-height: 1.4; letter-spacing: 0.16em; text-transform: uppercase; color: #999999; margin: 32px 0 12px; }
.cq-options.cq-options-extra { grid-template-columns: repeat(3, 1fr); gap: 8px 16px; }
.cq-options.cq-options-extra.cq-options-extra-2 { grid-template-columns: repeat(2, 1fr); gap: 8px 20px; }
.cq-options.cq-options-check { grid-template-columns: repeat(2, 1fr); gap: 0 32px; padding: 0 20px; background-color: #FFFFFF; border: 1px solid #DDDDDD; border-radius: 8px; overflow: hidden; }
.cq-options.cq-options-inline { display: flex; flex-wrap: wrap; gap: 8px; }
.cq-opt { display: flex; align-items: center; min-height: 54px; padding: 12px 16px; background-color: #F0F0F0; border: 1px solid #F0F0F0; border-radius: 6px; cursor: pointer; transition: border-color 150ms ease, background-color 150ms ease; }
.cq-opt:hover { border-color: #111111; }
.cq-opt.is-selected { background-color: #E8FF00; border-color: #E8FF00; }
.cq-opt.is-disabled { opacity: 0.45; cursor: not-allowed; }
.cq-opt.cq-opt-img { flex-direction: column; align-items: stretch; min-height: 0; padding: 0; gap: 10px; background-color: transparent; border: 0; border-radius: 0; }
.cq-opt.cq-opt-img.is-selected { background-color: transparent; }
.cq-opt.cq-opt-unsure { background-color: #E6E8FF; border-color: #E6E8FF; }
.cq-opt.cq-opt-unsure:hover { border-color: #2B36FF; }
.cq-opt.cq-opt-unsure.is-selected { background-color: #2B36FF; border-color: #2B36FF; }
.cq-opt.cq-opt-check { min-height: 0; padding: 14px 0; margin-bottom: -1px; background-color: transparent; border: 0; border-bottom: 1px solid #EEEEEE; border-radius: 0; }
.cq-opt.cq-opt-check:hover { border-color: #EEEEEE; }
.cq-opt.cq-opt-check.is-selected { background-color: transparent; }
.cq-callout { max-width: 680px; margin: 18px 0 0; padding: 16px 18px; background-color: #FFFFFF; border: 1px solid #DDDDDD; border-left: 4px solid #2B36FF; border-radius: 6px; font-size: 15px; line-height: 1.5; color: #111111; }
.cq-upload { margin: 4px 0 18px; }
.cq-drop { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; padding: 24px 16px; background-color: #FFFFFF; border: 1px dashed #AAAAAA; border-radius: 8px; text-align: center; cursor: pointer; overflow: hidden; transition: border-color 150ms ease, background-color 150ms ease; }
.cq-drop:hover { border-color: #2B36FF; background-color: #F5F6FF; }
.cq-drop.is-over { border-color: #2B36FF; background-color: #F5F6FF; }
.cq-drop-title { font-size: 15px; font-weight: 500; color: #111111; }
.cq-drop-sub { font-size: 13px; line-height: 1.4; color: #999999; }
.cq-files { list-style-type: none; margin: 0; padding: 0; }
.cq-file { display: flex; align-items: center; gap: 12px; margin-top: 6px; padding: 10px 12px; background-color: #F0F0F0; border-radius: 6px; font-size: 14px; color: #111111; }
.cq-file-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cq-file-state { font-size: 12px; color: #999999; white-space: nowrap; }
.cq-file-x { padding: 0 4px; border: 0; background-color: transparent; font-size: 20px; line-height: 1; color: #555555; cursor: pointer; }
.cq-opt.cq-opt-stack { flex-direction: column; align-items: stretch; padding: 16px 18px; }
.cq-opt.cq-opt-small { min-height: 48px; padding: 10px 14px; }
.cq-opt-pic { display: block; width: 100%%; height: auto; aspect-ratio: 3 / 4; object-fit: contain; background-color: #F0F0F0; border-radius: 6px; outline: 3px solid transparent; outline-offset: 3px; transition: outline-color 150ms ease, opacity 150ms ease; }
.cq-opt-desc { display: block; font-size: 13px; line-height: 1.45; color: #555555; margin-top: 6px; padding-left: 30px; }
.cq-other { margin-top: 10px; max-width: 420px; }
.cq-other.cq-other-wide { max-width: 560px; }
.cq-nav { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 8px; padding-top: 28px; border-top: 1px solid #DDDDDD; }
.cq-nav-right { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.cq-btn { display: inline-flex; align-items: center; justify-content: center; height: 48px; padding: 0 28px; border: 1px solid #111111; border-radius: 100px; background-color: #111111; color: #FFFFFF; font-family: %(nm)s; font-size: 12px; font-weight: 500; line-height: 1; letter-spacing: 0.08em; text-transform: uppercase; text-decoration: none; cursor: pointer; white-space: nowrap; transition: background-color 200ms ease, color 200ms ease, border-color 200ms ease; }
.cq-btn:hover { background-color: #2B36FF; border-color: #2B36FF; color: #FFFFFF; }
.cq-btn.cq-btn-ghost { background-color: transparent; color: #111111; }
.cq-btn.cq-btn-ghost:hover { background-color: #111111; color: #FFFFFF; border-color: #111111; }
.cq-btn.cq-btn-submit { background-color: #2B36FF; border-color: #2B36FF; }
.cq-btn.cq-btn-submit:hover { background-color: #111111; border-color: #111111; }
.cq-error { display: none; margin: 14px 0 0; padding: 10px 14px; background-color: #E8FF00; color: #111111; font-size: 14px; font-weight: 500; border-radius: 4px; }
.cq-foot { margin: 28px 0 0; font-size: 12px; color: #999999; }
@media screen and (max-width: 991px) {
  .cq-h1 { font-size: 44px; }
  .cq-options { grid-template-columns: repeat(2, 1fr); }
  .cq-options.cq-options-4 { grid-template-columns: repeat(3, 1fr); }
}
@media screen and (max-width: 767px) {
  .cq-page { padding: 48px 20px 72px; }
  .cq-h1 { font-size: 36px; }
  .cq-h2 { font-size: 28px; }
  .cq-step-num { font-size: 48px; }
  .cq-options { grid-template-columns: 1fr; }
  .cq-options.cq-options-4 { grid-template-columns: repeat(2, 1fr); }
  .cq-options.cq-options-2 { grid-template-columns: 1fr; }
  .cq-options-img { grid-template-columns: repeat(2, 1fr); gap: 22px 12px; }
  .cq-options-img.cq-options-swatch { grid-template-columns: repeat(3, 1fr); gap: 20px 12px; }
  .cq-options.cq-options-extra { grid-template-columns: repeat(2, 1fr); gap: 8px 12px; }
  .cq-options.cq-options-check { grid-template-columns: 1fr; padding: 0 16px; }
  .cq-row { grid-template-columns: 1fr; }
  .cq-nav { flex-wrap: wrap; }
  .cq-progress-title { display: none; }
}
@media screen and (max-width: 479px) {
  .cq-options.cq-options-4 { grid-template-columns: 1fr; }
  .cq-options-img.cq-options-swatch { grid-template-columns: repeat(2, 1fr); }
  .cq-options.cq-options-extra { grid-template-columns: 1fr; }
  .cq-options.cq-options-extra.cq-options-extra-2 { grid-template-columns: 1fr; }
  .cq-options-img.cq-options-wide { grid-template-columns: 1fr; }
  .cq-btn { padding: 0 20px; }
}
""" % {"ibm": IBM, "nm": NM}

# Rules that need descendant selectors (Webflow classes can't express them) live in the page head.
HEAD_CSS = """<style>
.cq-opt .w-checkbox,.cq-opt .w-radio{display:flex;align-items:center;gap:12px;margin:0;padding:0;width:100%;cursor:pointer;min-height:0}
.cq-opt .w-checkbox-input,.cq-opt .w-radio-input{float:none;margin:0;width:18px;height:18px;flex:none;accent-color:#2B36FF;cursor:pointer}
.cq-opt .w-form-label{font-family:"Neue Montreal",sans-serif;font-size:15px;line-height:1.35;font-weight:500;color:#111111;cursor:pointer;display:block;margin:0}
.cq-opt.cq-opt-img .w-checkbox{align-items:flex-start}
.cq-opt.cq-opt-small .w-form-label{font-size:14px}
.cq-options-tall .cq-opt-pic{aspect-ratio:2/3}
.cq-options-wide .cq-opt-pic{aspect-ratio:16/9}
.cq-opt.cq-opt-img .cq-opt-desc{margin-top:-4px}
.cq-q.is-invalid .cq-label{color:#2B36FF}
.cq-q.is-invalid .cq-opt{border-color:#2B36FF}
.cq-opt.cq-opt-swatch .cq-opt-pic{aspect-ratio:auto;background-color:transparent}
.cq-opt.cq-opt-img:hover .cq-opt-pic{opacity:.85}
.cq-opt.cq-opt-img.is-selected .cq-opt-pic{outline-color:#2B36FF;opacity:1}
.cq-opt.cq-opt-img.is-selected .w-form-label,.cq-opt.cq-opt-check.is-selected .w-form-label{font-weight:700}
.cq-opt.cq-opt-unsure .w-form-label{color:#2B36FF}
.cq-opt.cq-opt-unsure.is-selected .w-form-label{color:#FFFFFF}
.cq-opt.cq-opt-unsure.is-selected .w-checkbox-input,.cq-opt.cq-opt-unsure.is-selected .w-radio-input{accent-color:#111111}
.cq-opt.cq-opt-check .w-checkbox-input{width:20px;height:20px}
.cq-opt.cq-opt-check:hover .w-form-label{text-decoration:underline;text-underline-offset:3px}
.cq-q[data-check] .cq-count{color:#2B36FF}
.cq-drop input[type=file]{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}
.cq-file.is-done .cq-file-state{color:#111111}
.cq-file.is-done .cq-file-state::before{content:"✓ "}
.cq-file.is-err{background:#FDE8E8}.cq-file.is-err .cq-file-state{color:#8A1C1C}
.cq-callout strong{font-weight:700}
.cq-js .cq-step{display:none}
.cq-js .cq-step.is-active{display:block}
.cq-js .cq-hidden{display:none!important}
.cq-js .cq-other{display:none}
.cq-js .cq-other.is-on{display:block}
.cq-js .cq-btn-submit,.cq-js [data-nav]{display:none}
.cq-js .cq-nav.is-last .cq-btn-submit{display:inline-flex}
.cq-js .cq-nav.has-next [data-nav=next]{display:inline-flex}
.cq-js .cq-nav.has-back [data-nav=back]{display:inline-flex}
.cq-js .cq-error.is-on{display:block}
.cq-input.is-invalid,.cq-textarea.is-invalid{border-color:#2B36FF;border-width:2px}
.cq-page .w-form-done{display:none;background:#E8FF00;color:#111111;padding:40px;border-radius:6px;text-align:left;font-family:"Ibm Plex Sans",sans-serif;font-weight:700;font-size:22px;line-height:1.35}
.cq-page .w-form-fail{display:none;background:#F0F0F0;color:#111111;padding:16px;border-radius:6px;margin-top:16px;text-align:left}
.cq-page input[type=date]{-webkit-appearance:none;appearance:none}
</style>"""

# ---------------------------------------------------------------- JS

JS = r"""<script>
(function(){
function ready(f){if(document.readyState!=='loading'){f()}else{document.addEventListener('DOMContentLoaded',f)}}
ready(function(){
var wrap=document.querySelector('.cq-form');var form=wrap?(wrap.tagName==='FORM'?wrap:wrap.querySelector('form')):null;if(!form)return;
var page=form.closest('.cq-page')||document.body;page.classList.add('cq-js');
form.setAttribute('novalidate','novalidate');
var $=function(s,r){return Array.prototype.slice.call((r||form).querySelectorAll(s))};
var steps=$('.cq-step'),nav=form.querySelector('.cq-nav'),err=form.querySelector('[data-cq-error]');
var lbl=page.querySelector('[data-cq-step-label]'),ttl=page.querySelector('[data-cq-step-title]'),bar=page.querySelector('[data-cq-bar]');
var cur=0;
/* option checkboxes submit through one hidden field per question, so drop their own names */
function isMulti(q){return q.getAttribute('data-type')==='multi'||!!q.querySelector('input[data-collect]')}
$('input[type=checkbox]').filter(function(c){var q=c.closest('.cq-q');return !!(q&&isMulti(q))}).forEach(function(c){c.removeAttribute('name');c.removeAttribute('data-name');c.removeAttribute('required')});
function optText(i){var o=i.closest('.cq-opt');if(!o)return i.value||'';return (o.getAttribute('data-opt')||'').trim()||i.value||''}
function radioVal(id){var q=form.querySelector('.cq-q[data-q="'+id+'"]');if(!q)return '';var r=q.querySelector('input[type=radio]:checked');return r?r.value:''}
function evalShow(el){var c=el.getAttribute('data-show-if');if(!c)return true;try{c=JSON.parse(c)}catch(e){return true}var v=radioVal(c.q);if(c.equals!==undefined)return v===c.equals;if(c['in'])return c['in'].indexOf(v)>=0;return true}
function clearInputs(root){$('input,textarea',root).forEach(function(i){if(i.type==='checkbox'||i.type==='radio'){i.checked=false;i.disabled=false}else if(i.type!=='hidden'&&i.type!=='submit'){i.value=''}else if(i.type==='hidden'){i.value=''}});$('.cq-opt',root).forEach(function(o){o.classList.remove('is-selected','is-disabled')});$('.cq-other',root).forEach(function(o){o.classList.remove('is-on')});$('.cq-count',root).forEach(function(c){c.textContent=''});$('.cq-file',root).forEach(function(li){li.parentNode.removeChild(li)})}
function boxFor(b){return b.getAttribute('data-for')||'Other'}
function compile(q){var h=q.querySelector('input[data-collect]');if(!h)return;var vals=$('input[type=checkbox]',q).filter(function(c){return c.checked}).map(optText);$('.cq-other',q).forEach(function(b){var t=b.querySelector('input,textarea');var k=vals.indexOf(boxFor(b));if(k>=0&&t&&t.value.trim())vals[k]=vals[k]+': '+t.value.trim()});h.value=vals.join(', ')}
function refresh(q){var max=parseInt(q.getAttribute('data-max')||'0',10);var boxes=$('input[type=checkbox]',q);var n=boxes.filter(function(b){return b.checked}).length;
$('.cq-opt',q).forEach(function(o){var i=o.querySelector('input');o.classList.toggle('is-selected',!!(i&&i.checked))});
if(max){boxes.forEach(function(b){var lim=!b.checked&&n>=max;b.disabled=lim;b.closest('.cq-opt').classList.toggle('is-disabled',lim)})}
var cnt=q.querySelector('.cq-count');if(cnt)cnt.textContent=max?(n+' of '+max+' selected'):(q.hasAttribute('data-check')?(n+' of '+boxes.length+' ticked'):(n?n+' selected':''));
$('.cq-other',q).forEach(function(oth){var lab=boxFor(oth);var on=$('input:checked',q).some(function(i){return optText(i)===lab});oth.classList.toggle('is-on',on);if(!on){var t=oth.querySelector('input,textarea');if(t)t.value=''}});
if(isMulti(q))compile(q)}
function conditionals(){$('[data-show-if]').forEach(function(el){var show=evalShow(el);var hidden=el.classList.contains('cq-hidden');if(!show&&!hidden)clearInputs(el);el.classList.toggle('cq-hidden',!show)});
steps.forEach(function(s){if(!s.getAttribute('data-conditional'))return;var subs=$('.cq-sub',s);var any=subs.some(function(x){return !x.classList.contains('cq-hidden')});s.classList.toggle('cq-skip',!any)})}
function visible(){return steps.filter(function(s){return !s.classList.contains('cq-skip')&&!s.classList.contains('cq-hidden')})}
function paint(){var vs=visible();if(cur>vs.length-1)cur=vs.length-1;steps.forEach(function(s){s.classList.remove('is-active')});var s=vs[cur];s.classList.add('is-active');
if(lbl)lbl.textContent='Step '+(cur+1)+' of '+vs.length;if(ttl)ttl.textContent=s.getAttribute('data-title')||'';if(bar)bar.style.width=Math.round((cur+1)/vs.length*100)+'%';
nav.classList.toggle('has-back',cur>0);nav.classList.toggle('has-next',cur<vs.length-1);nav.classList.toggle('is-last',cur===vs.length-1);hideErr()}
function showErr(m){if(err){err.textContent=m;err.classList.add('is-on')}}
function hideErr(){if(err)err.classList.remove('is-on');$('.is-invalid').forEach(function(i){i.classList.remove('is-invalid')})}
function validate(step){var bad=$('[required]',step).filter(function(i){return !i.closest('.cq-hidden')&&!i.value.trim()});bad.forEach(function(i){i.classList.add('is-invalid')});
var badQ=$('.cq-q[data-required]',step).filter(function(q){return !q.closest('.cq-hidden')&&!q.querySelector('input:checked')});badQ.forEach(function(q){q.classList.add('is-invalid')});
if(bad.length||badQ.length){showErr(badQ.length&&!bad.length?'Please choose an option for the highlighted question before continuing.':'Please complete the highlighted fields before continuing.');if(bad.length)bad[0].focus();else badQ[0].scrollIntoView({block:'center',behavior:'smooth'});return false}return true}
function scrollTop(){var p=page.querySelector('.cq-progress')||form;var y=p.getBoundingClientRect().top+window.pageYOffset-16;window.scrollTo({top:y,behavior:'smooth'})}
function go(d){var vs=visible();if(d>0&&!validate(vs[cur]))return;cur=Math.max(0,Math.min(cur+d,vs.length-1));paint();scrollTop()}
/* file uploads: each file goes straight to private storage via /f; the hidden field keeps the stored paths */
var MAXB=50*1024*1024;
function fmtSize(b){return b>=1048576?(b/1048576).toFixed(1)+' MB':Math.max(1,Math.round(b/1024))+' KB'}
function syncUp(box){var h=box.querySelector('input[type=hidden]');if(h)h.value=$('.cq-file.is-done',box).map(function(li){return li.getAttribute('data-path')}).join('\n')}
function uploadOne(box,file){var li=document.createElement('li');li.className='cq-file is-up';
li.innerHTML='<span class="cq-file-name"></span><span class="cq-file-state">Uploading\u2026</span><button type="button" class="cq-file-x" aria-label="Remove file">\u00d7</button>';
li.querySelector('.cq-file-name').textContent=file.name+' \u00b7 '+fmtSize(file.size);box.querySelector('.cq-files').appendChild(li);var st=li.querySelector('.cq-file-state');
function fail(m){li.classList.remove('is-up');li.classList.add('is-err');st.textContent=m;syncUp(box)}
if(file.size>MAXB){fail('Too large \u2014 max 50 MB, please share a link instead');return}
fetch('/f',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:file.name,size:file.size})})
.then(function(r){return r.json().catch(function(){return {}}).then(function(j){if(!r.ok||!j.url)throw new Error(j.error||('http '+r.status));return j})})
.then(function(j){var fd=new FormData();fd.append('cacheControl','3600');fd.append('',file);return fetch(j.url,{method:'PUT',headers:{'x-upsert':'false'},body:fd}).then(function(r){if(!r.ok)throw new Error('upload '+r.status);li.setAttribute('data-path',j.path)})})
.then(function(){if(!li.parentNode)return;li.classList.remove('is-up');li.classList.add('is-done');st.textContent='Uploaded';syncUp(box)})
.catch(function(e){var m=String(e&&e.message);fail(m==='type_not_allowed'?'This file type isn\u2019t supported \u2014 try PDF, an image or ZIP':m==='too_large'?'Too large \u2014 max 50 MB, please share a link instead':'Upload failed \u2014 please try again')})}
function addFiles(box,files){Array.prototype.slice.call(files||[]).forEach(function(f){uploadOne(box,f)})}
$('.cq-drop').forEach(function(d){var box=d.closest('.cq-upload');
d.addEventListener('dragover',function(e){e.preventDefault();d.classList.add('is-over')});
d.addEventListener('dragleave',function(){d.classList.remove('is-over')});
d.addEventListener('drop',function(e){e.preventDefault();d.classList.remove('is-over');addFiles(box,e.dataTransfer&&e.dataTransfer.files)})});
form.addEventListener('change',function(e){if(e.target.type==='file'){addFiles(e.target.closest('.cq-upload'),e.target.files);e.target.value='';return}var q=e.target.closest('.cq-q');if(q&&q.classList.contains('is-invalid')&&q.querySelector('input:checked'))q.classList.remove('is-invalid');if(q)refresh(q);if(e.target.type==='radio')conditionals();if(e.target.type==='radio')paint()});
form.addEventListener('input',function(e){var q=e.target.closest('.cq-q');if(q&&e.target.closest('.cq-other'))compile(q);if(e.target.classList.contains('is-invalid')&&e.target.value.trim())e.target.classList.remove('is-invalid')});
form.addEventListener('click',function(e){var x=e.target.closest('.cq-file-x');if(x){e.preventDefault();var li=x.closest('.cq-file'),box=x.closest('.cq-upload');li.parentNode.removeChild(li);syncUp(box);return}
var b=e.target.closest('[data-nav]');if(b){e.preventDefault();go(b.getAttribute('data-nav')==='next'?1:-1);return}
var o=e.target.closest('.cq-opt');if(o&&!e.target.closest('input,label')){var i=o.querySelector('input');if(i&&!i.disabled)i.click()}});
form.addEventListener('keydown',function(e){if(e.key==='Enter'&&e.target.tagName==='INPUT'&&e.target.type!=='submit'){e.preventDefault();if(nav.classList.contains('has-next'))go(1)}});
form.addEventListener('submit',function(e){if($('.cq-file.is-up').length){e.preventDefault();e.stopImmediatePropagation();showErr('Please wait until your files have finished uploading.');return false}var vs=visible();for(var i=0;i<vs.length;i++){if(!validate(vs[i])){e.preventDefault();e.stopImmediatePropagation();cur=i;paint();scrollTop();showErr('Please complete the highlighted fields before submitting.');return false}}$('.cq-q').filter(isMulti).forEach(compile)},true);
conditionals();$('.cq-q').forEach(refresh);paint();
});
})();
</script>"""


# ---------------------------------------------------------------- preview replica

def webflowify(markup):
    """Approximate how Webflow renders the builder markup on a published page."""
    # bare checkbox inside a card -> Webflow checkbox wrapper with inline label
    def cb(m):
        attrs = m.group(1)
        name = re.search(r'name="([^"]*)"', attrs).group(1)
        return ('<label class="w-checkbox"><input type="checkbox" class="w-checkbox-input" %s data-name="%s">'
                '<span class="w-form-label">%s</span></label>' % (attrs, name, name))
    markup = re.sub(r'<input type="checkbox" ([^>]*)>', cb, markup)
    markup = markup.replace('class="w-radio cq-radio"', 'class="w-radio cq-radio"')
    return markup


def preview_html(steps, shell, nav):
    body = shell.replace('<div class="cq-steps"></div>', '<div class="cq-steps">%s</div>%s' % ("".join(steps), nav))
    body = webflowify(body)
    # mimic Webflow's form wrapper and messages
    body = body.replace('<form class="cq-form"', '<div class="cq-form w-form"><form')
    body = re.sub(r' data-type="[a-z_]+"', '', body)  # Webflow drops data-type on publish
    body = body.replace('</form>', '</form><div class="w-form-done">Thank you — your questionnaire has been received. Your account manager will be in touch to confirm next steps.</div><div class="w-form-fail">Oops! Something went wrong while submitting the form.</div></div>')
    stub = """<script>
window.__submissions=[];document.addEventListener('DOMContentLoaded',function(){document.querySelector('.cq-form form').addEventListener('submit',function(e){e.preventDefault();var fd=new FormData(e.target);var o={};fd.forEach(function(v,k){o[k]=v});window.__submissions.push(o);document.querySelector('.w-form').querySelector('form').style.display='none';document.querySelector('.w-form-done').style.display='block';});});
</script>"""
    return """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Client Questionnaire preview</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>body{margin:0;font-family:'Neue Montreal',sans-serif;background:#FAFAFA;color:#333;font-size:14px;line-height:20px}*{box-sizing:border-box}
.w-checkbox,.w-radio{display:block;margin-bottom:5px;padding-left:20px}.w-checkbox-input,.w-radio-input{float:left;margin:4px 0 0 -20px;line-height:normal}.w-form-label{display:inline-block;cursor:pointer;font-weight:normal;margin-bottom:0}
.wf-nav{background:#111;height:64px;display:flex;align-items:center;padding:0 2rem;color:#fff;font-size:12px;letter-spacing:.08em;text-transform:uppercase;justify-content:space-between}
%s</style>%s%s%s</head><body>
<div class="wf-nav"><span>SOLID</span><span>Work · About · Contact</span></div>
%s
</body></html>""" % (CSS.replace("'Ibm Plex Sans'", "'IBM Plex Sans'"), HEAD_CSS, JS, stub, body)


SUBMIT_JS = """<script>
(function(){
document.addEventListener('DOMContentLoaded',function(){
var wrap=document.querySelector('.cq-form');if(!wrap)return;var form=wrap.querySelector('form');var done=wrap.querySelector('.w-form-done');var fail=wrap.querySelector('.w-form-fail');var btn=form.querySelector('.cq-btn-submit');
form.addEventListener('submit',function(e){e.preventDefault();if(btn.disabled)return;
var fd=new FormData(form);var answers={};fd.forEach(function(v,k){if(typeof v==='string')answers[k]=v});
btn.disabled=true;var label=btn.value;btn.value='Sending\\u2026';fail.style.display='none';
fetch('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({form:(window.CQ_FORM||{}).id,answers:answers})})
.then(function(r){if(!r.ok)throw new Error('http '+r.status);return r.json()})
.then(function(res){try{relay(answers,res&&res.link)}catch(e){}form.style.display='none';done.style.display='block';var p=document.querySelector('.cq-progress');if(p)p.style.display='none';window.scrollTo({top:0,behavior:'smooth'})})
.catch(function(){fail.style.display='block';btn.disabled=false;btn.value=label});
});
});
})();
</script>"""


RELAY_JS = r"""<script>
/* Emails each submission to the team through FormSubmit (formsubmit.co), approved by Solid on 12 Oct 2026.
   No keys: the first message asks design@ to click "Activate Form" once. */
function relay(answers,link){
  var to='design@solid2017.com', cc='fatimah-alamer@hotmail.com,hello@solid2017.com,aljazi@solid2017.com,banah@solid2017.com,manal@solid2017.com';
  var F=window.CQ_FORM||{};
  var name=(answers[F.name]||'Untitled project').trim();
  var type=(answers[F.type]||'').trim();
  var p={_subject:F.subject+': '+name+(type?' ('+type+')':''),_cc:cc,_template:'table',_captcha:'false','Project':name};
  p[F.typeLabel]=type;p['Contact']=answers[F.contact]||'';if(F.location)p['Location']=answers[F.location]||'';
  p['Full answers (private link)']=link||'See the team inbox';
  /* uploaded files become download links that only work with this submission's private token */
  var m=/\/s\/([0-9a-f-]{36})\?t=([A-Za-z0-9_-]+)/.exec(link||'');
  Object.keys(answers).forEach(function(k){var v=answers[k];if(typeof v!=='string'||!v.trim()||(k in p))return;v=v.trim();
    if(/ \u2014 Files$/.test(k)&&m)v=v.split('\n').map(function(f){f=f.trim();return f.split('/').pop()+' \u2014 '+location.origin+'/f?id='+m[1]+'&t='+m[2]+'&p='+encodeURIComponent(f)}).join('\n');
    p[k]=v});
  fetch('https://formsubmit.co/ajax/'+to,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(p),keepalive:true}).catch(function(){});
}
</script>"""


def standalone_html(steps, shell, nav):
    """The hosted page (questionnaire.solid2017.com, project ../solid-questionnaire)."""
    body = shell.replace('<div class="cq-steps"></div>', '<div class="cq-steps">%s</div>%s' % ("".join(steps), nav))
    body = webflowify(body)
    body = body.replace('<form class="cq-form"', '<div class="cq-form w-form"><form')
    body = re.sub(r' data-type="[a-z_]+"', '', body)
    body = body.replace('</form>', '</form><div class="w-form-done"><p class="cq-done">Thank you — your questionnaire has been received. Your account manager will be in touch to confirm the next steps.</p></div><div class="w-form-fail">Something went wrong while sending your answers. Please check your connection and try again; nothing you entered has been lost.</div></div>')
    base = """body{margin:0;font-family:'Neue Montreal',Arial,sans-serif;background:#FAFAFA;color:#333;font-size:14px;line-height:20px;-webkit-font-smoothing:antialiased}*{box-sizing:border-box}
@font-face{font-family:'Neue Montreal';src:url('/fonts/NeueMontreal-Regular.woff2') format('woff2');font-weight:400;font-display:swap}
@font-face{font-family:'Neue Montreal';src:url('/fonts/NeueMontreal-Medium.woff2') format('woff2');font-weight:500;font-display:swap}
@font-face{font-family:'Neue Montreal';src:url('/fonts/NeueMontreal-Bold.woff2') format('woff2');font-weight:700;font-display:swap}
.w-checkbox,.w-radio{display:block;margin-bottom:5px;padding-left:20px}.w-checkbox-input,.w-radio-input{float:left;margin:4px 0 0 -20px;line-height:normal}.w-form-label{display:inline-block;cursor:pointer;font-weight:normal;margin-bottom:0}
.w-input,.w-button{font-family:inherit}.w-form-done,.w-form-fail{display:none}.w-form-fail{margin-top:16px;padding:14px 16px;border-radius:6px;background:#FDE8E8;color:#8A1C1C;font-size:14px;line-height:1.45}
.cq-topbar{background:#111111;height:64px;display:flex;align-items:center;padding:0 32px}.cq-topbar img{height:22px;width:auto;display:block}
@media (max-width:767px){.cq-topbar{padding:0 24px;height:60px}}
"""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title>
<meta name="robots" content="noindex,nofollow"><meta name="description" content="Solid Design Studio client questionnaire for interior and spatial design projects.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>%s%s</style><script>window.CQ_FORM=%s</script>%s%s%s%s</head><body>
<div class="cq-topbar"><a href="https://www.solid2017.com" aria-label="Solid Design Studio"><img src="/solid-logo.svg" alt="Solid"></a></div>
%s
</body></html>""" % (esc(FORM["title"]), base, CSS.replace("'Ibm Plex Sans'", "'IBM Plex Sans'"),
                       json.dumps(FORM["relay"], ensure_ascii=False), HEAD_CSS, JS, SUBMIT_JS, RELAY_JS, body)


def fields_map():
    """Ordered field map ({sections, fields}) the server uses to lay out submission emails and pages."""
    sections, fields = [], []

    def add_questions(code, title, questions):
        for q in questions:
            if q["type"] == "number_group":
                for sub_label, field in q["fields"]:
                    fields.append({"key": field, "label": "%s — %s" % (q["label"], sub_label), "section": code, "sectionTitle": title})
                continue
            fields.append({"key": q["field"], "label": q["label"], "section": code, "sectionTitle": title})
            if q.get("files_field"):
                fields.append({"key": q["files_field"], "label": "%s (uploaded files)" % q["label"],
                               "section": code, "sectionTitle": title})
            for label, suffix, _ in explain_options(q):
                fields.append({"key": q["field"] + " — " + suffix, "label": "%s (%s)" % (q["label"], label),
                               "section": code, "sectionTitle": title})

    for sec in SECTIONS:
        sections.append({"code": sec["num"], "title": sec["title"]})
        add_questions(sec["num"], sec["title"], sec.get("questions", []))
        for sub in sec.get("subsections", []):
            code, title = sec["num"] + sub["key"], "%s — %s" % (sec["title"], sub["title"])
            sections.append({"code": code, "title": title})
            add_questions(code, title, sub["questions"])
    return {"sections": sections, "fields": fields}


def landing_html():
    """questionnaire.solid2017.com/ : pick a questionnaire (links shared before /interior existed land here)."""
    cards = "".join(
        '<a class="lq-card" href="%s"><span class="lq-tag">Client Questionnaire</span><span class="lq-name">%s</span>'
        '<span class="lq-blurb">%s</span><span class="lq-go">Start &rarr;</span></a>' % (f["path"], f["card"], f["blurb"])
        for f in FORMS.values())
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Client Questionnaires · Solid</title><meta name="robots" content="noindex,nofollow">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;700&display=swap" rel="stylesheet">
<style>
@font-face{font-family:'Neue Montreal';src:url('/fonts/NeueMontreal-Regular.woff2') format('woff2');font-weight:400;font-display:swap}
@font-face{font-family:'Neue Montreal';src:url('/fonts/NeueMontreal-Medium.woff2') format('woff2');font-weight:500;font-display:swap}
*{box-sizing:border-box}body{margin:0;background:#FAFAFA;color:#111111;font-family:'Neue Montreal',Arial,sans-serif;-webkit-font-smoothing:antialiased}
.cq-topbar{background:#111111;height:64px;display:flex;align-items:center;padding:0 32px}.cq-topbar img{height:22px;width:auto;display:block}
.lq{max-width:880px;margin:0 auto;padding:72px 28px 96px}
.lq-kicker{font:700 11px/1.4 'IBM Plex Sans',sans-serif;letter-spacing:.22em;text-transform:uppercase;color:#999999;margin:0 0 16px}
.lq h1{font:700 56px/1.05 'IBM Plex Sans',sans-serif;letter-spacing:-.01em;margin:0 0 20px}.lq h1 span{color:#2B36FF}
.lq-lead{font-size:17px;line-height:1.55;max-width:620px;margin:0 0 40px}
.lq-cards{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.lq-card{display:flex;flex-direction:column;gap:10px;padding:28px;background:#FFFFFF;border:1px solid #DDDDDD;border-radius:8px;color:#111111;text-decoration:none;transition:border-color 150ms ease,box-shadow 150ms ease}
.lq-card:hover{border-color:#2B36FF;box-shadow:0 0 0 1px #2B36FF}
.lq-tag{font:700 11px/1.4 'IBM Plex Sans',sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#999999}
.lq-name{font:700 24px/1.2 'IBM Plex Sans',sans-serif}.lq-blurb{font-size:15px;line-height:1.5;color:#555555}
.lq-go{margin-top:8px;font-size:12px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:#2B36FF}
.lq-foot{margin:40px 0 0;font-size:12px;color:#999999}
@media (max-width:767px){.cq-topbar{padding:0 24px;height:60px}.lq{padding:48px 20px 72px}.lq h1{font-size:36px}.lq-cards{grid-template-columns:1fr}}
</style></head><body>
<div class="cq-topbar"><a href="https://www.solid2017.com" aria-label="Solid Design Studio"><img src="/solid-logo.svg" alt="Solid"></a></div>
<main class="lq"><p class="lq-kicker">Solid Design Studio</p><h1>Tell us about your <span>project</span>.</h1>
<p class="lq-lead">Choose the questionnaire your account manager asked you to fill in.</p>
<div class="lq-cards">%s</div><p class="lq-foot">© Solid Design Studio</p></main>
</body></html>
""" % cards


def main():
    shell = shell_html()
    nav = nav_html()
    steps = []
    for sec in SECTIONS:
        s = step_html(sec)
        steps.append(s)
        open(os.path.join(OUT, "step-%s.html" % sec["num"]), "w").write(s)
        if sec.get("subsections"):
            # large conditional section: insert the step shell first, then each subsection
            shell_only = step_html(dict(sec, subsections=[]))
            open(os.path.join(OUT, "step-%s-shell.html" % sec["num"]), "w").write(shell_only)
            for sub in sec["subsections"]:
                one = step_html(dict(sec, questions=[], subsections=[sub]))
                inner = re.search(r'(<div class="cq-sub".*</div>)</div>$', one, re.S).group(1)
                open(os.path.join(OUT, "step-%s-sub-%s.html" % (sec["num"], sub["key"])), "w").write(inner)
                print("  sub %s: %d chars" % (sub["key"], len(inner)))
    open(os.path.join(OUT, "shell.html"), "w").write(shell)
    open(os.path.join(OUT, "nav.html"), "w").write(nav)
    open(os.path.join(OUT, "styles.css"), "w").write(CSS.strip())
    open(os.path.join(OUT, "head.html"), "w").write(HEAD_CSS)
    open(os.path.join(OUT, "footer.html"), "w").write(JS)
    open(os.path.join(OUT, "preview.html"), "w").write(preview_html(steps, shell, nav))
    page = standalone_html(steps, shell, nav)
    fmap = json.dumps(fields_map(), indent=2, ensure_ascii=False) + "\n"
    open(os.path.join(OUT, "standalone.html"), "w").write(page)
    open(os.path.join(OUT, "fields.json"), "w").write(fmap)
    if os.path.isdir(SITE):
        dest = os.path.join(SITE, FORM["page"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "w").write(page)
        open(os.path.join(SITE, FORM["fields"]), "w").write(fmap)
        open(os.path.join(SITE, "index.html"), "w").write(landing_html())
    print("shell %d chars, nav %d, css %d, head %d, footer %d" % (len(shell), len(nav), len(CSS), len(HEAD_CSS), len(JS)))
    for sec, s in zip(SECTIONS, steps):
        print("step %s: %d chars" % (sec["num"], len(s)))


if __name__ == "__main__":
    main()
