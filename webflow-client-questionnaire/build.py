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
"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec import SECTIONS, INTRO  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

ASSETS = json.load(open(os.path.join(HERE, "assets.json")))


def img_url(name):
    aid = ASSETS["ids"].get(name)
    if not aid or aid == "PENDING":
        raise SystemExit("missing asset id for %s" % name)
    return ASSETS["base"] + aid + "_" + name


def esc(s):
    return html.escape(s, quote=True)


_uid = [0]


def uid(prefix):
    _uid[0] += 1
    return "%s-%d" % (prefix, _uid[0])


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------------------------------------------------------------- option cards

def checkbox_card(q, opt, idx):
    label = opt["label"] if isinstance(opt, dict) else opt
    img = opt.get("img") if isinstance(opt, dict) else None
    cls = "cq-opt"
    if q.get("img"):
        cls += " cq-opt-img"
        if q.get("swatch"):
            cls += " cq-opt-swatch"
    if q.get("small"):
        cls += " cq-opt-small"
    cid = "cq-%s-%d" % (slug(q["id"]), idx)
    pic = ""
    if img:
        pic = '<img class="cq-opt-pic" src="%s" alt="%s">' % (img_url(img), esc(label))
    elif q.get("img"):
        pic = '<div class="cq-opt-nopic"></div>'
    # A bare checkbox inside the card: Webflow wraps it in its own label and uses the
    # input name as the visible option text.
    return ('<div class="%s" data-opt="%s">%s<input type="checkbox" id="%s" name="%s" value="Yes"></div>'
            % (cls, esc(label), pic, cid, esc(label)))


def radio_card(q, opt, idx):
    label = opt["label"] if isinstance(opt, dict) else opt
    desc = opt.get("desc") if isinstance(opt, dict) else None
    cls = "cq-opt"
    if desc:
        cls += " cq-opt-stack"
    rid = "cq-%s-%d" % (slug(q["id"]), idx)
    inner = ('<label class="w-radio cq-radio"><input type="radio" class="w-radio-input" id="%s" name="%s" value="%s">'
             '<span class="w-form-label">%s</span></label>' % (rid, esc(q["field"]), esc(label), esc(label)))
    if desc:
        inner += '<span class="cq-opt-desc">%s</span>' % esc(desc)
    return '<div class="%s" data-opt="%s">%s</div>' % (cls, esc(label), inner)


def other_field(q):
    return ('<div class="cq-other"><input class="cq-input" type="text" name="%s" placeholder="Please specify">'
            '</div>' % esc(q["field"] + " — Other"))


def has_other(q):
    for o in q.get("options", []):
        if (o["label"] if isinstance(o, dict) else o) == "Other":
            return True
    return False


# ---------------------------------------------------------------- questions

def question_html(q, number):
    attrs = ['class="cq-q%s"' % (" cq-q-follow" if q.get("follow") else ""),
             'data-q="%s"' % q["id"], 'data-type="%s"' % q["type"]]
    if q.get("max"):
        attrs.append('data-max="%d"' % q["max"])
    if q.get("show_if"):
        attrs.append("data-show-if='%s'" % json.dumps(q["show_if"], ensure_ascii=False).replace("'", "&#39;"))
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
        grid = "cq-options cq-options-inline" if q.get("inline") else "cq-options"
        if any(isinstance(o, dict) and o.get("desc") for o in q["options"]):
            grid = "cq-options cq-options-1"
        cards = "".join(radio_card(q, o, i) for i, o in enumerate(q["options"]))
        parts.append('<div class="%s">%s</div>' % (grid, cards))
        if has_other(q):
            parts.append(other_field(q))
    elif t == "multi":
        grid = "cq-options"
        if q.get("img"):
            grid += " cq-options-img"
        elif q.get("compact"):
            grid += " cq-options-4"
        elif q.get("small"):
            grid += " cq-options-2"
        cards = "".join(checkbox_card(q, o, i) for i, o in enumerate(q["options"]))
        parts.append('<div class="%s">%s</div>' % (grid, cards))
        if has_other(q):
            parts.append(other_field(q))
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
    parts = ['<div %s>' % " ".join(attrs)]
    parts.append('<div class="cq-step-head"><h2 class="cq-h2">%s</h2>' % esc(sec["title"]))
    if sec.get("intro"):
        parts.append('<p class="cq-intro">%s</p>' % esc(sec["intro"]))
    if sec.get("hint"):
        parts.append('<p class="cq-intro cq-intro-strong">%s</p>' % esc(sec["hint"]))
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
        '<p class="cq-tag">Client Questionnaire · Interior &amp; Spatial Design</p>'
        '<h1 class="cq-h1">Tell us about your <span class="cq-blue">space</span>.</h1>'
        + intro +
        '<p class="cq-note">Takes about 10–15 minutes. Answer only what applies to your project.</p>'
        '</header>'
        '<div class="cq-progress"><div class="cq-progress-top">'
        '<span class="cq-progress-label" data-cq-step-label="1">Step 1 of 12</span>'
        '<span class="cq-progress-title" data-cq-step-title="1">Project Overview</span></div>'
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
.cq-options.cq-options-img { grid-template-columns: repeat(3, 1fr); gap: 10px; }
.cq-options.cq-options-inline { display: flex; flex-wrap: wrap; gap: 8px; }
.cq-opt { display: flex; align-items: center; min-height: 54px; padding: 12px 16px; background-color: #F0F0F0; border: 1px solid #F0F0F0; border-radius: 6px; cursor: pointer; transition: border-color 150ms ease, background-color 150ms ease; }
.cq-opt:hover { border-color: #111111; }
.cq-opt.is-selected { background-color: #E8FF00; border-color: #E8FF00; }
.cq-opt.is-disabled { opacity: 0.45; cursor: not-allowed; }
.cq-opt.cq-opt-img { flex-direction: column; align-items: stretch; padding: 8px 8px 12px; gap: 10px; }
.cq-opt.cq-opt-stack { flex-direction: column; align-items: stretch; padding: 16px 18px; }
.cq-opt.cq-opt-small { min-height: 48px; padding: 10px 14px; }
.cq-opt-pic { display: block; width: 100%%; height: 160px; border-radius: 4px; object-fit: cover; }
.cq-opt-nopic { display: block; width: 100%%; height: 160px; border-radius: 4px; background-color: #E6E6E6; }
.cq-opt-desc { display: block; font-size: 13px; line-height: 1.45; color: #555555; margin-top: 6px; padding-left: 30px; }
.cq-other { margin-top: 10px; max-width: 420px; }
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
  .cq-options.cq-options-img { grid-template-columns: repeat(2, 1fr); }
}
@media screen and (max-width: 767px) {
  .cq-page { padding: 48px 20px 72px; }
  .cq-h1 { font-size: 36px; }
  .cq-h2 { font-size: 28px; }
  .cq-step-num { font-size: 48px; }
  .cq-options { grid-template-columns: 1fr; }
  .cq-options.cq-options-4 { grid-template-columns: repeat(2, 1fr); }
  .cq-options.cq-options-2 { grid-template-columns: 1fr; }
  .cq-options.cq-options-img { grid-template-columns: repeat(2, 1fr); }
  .cq-row { grid-template-columns: 1fr; }
  .cq-nav { flex-wrap: wrap; }
  .cq-progress-title { display: none; }
}
@media screen and (max-width: 479px) {
  .cq-options.cq-options-4 { grid-template-columns: 1fr; }
  .cq-options.cq-options-img { grid-template-columns: 1fr; }
  .cq-opt-pic { height: 140px; }
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
.cq-opt.cq-opt-swatch .cq-opt-pic{height:110px;object-fit:contain}
.cq-opt.cq-opt-swatch .cq-opt-nopic{height:110px}
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
$('.cq-q[data-type=multi] input[type=checkbox]').forEach(function(c){c.removeAttribute('name');c.removeAttribute('data-name');c.removeAttribute('required')});
function optText(i){var o=i.closest('.cq-opt');if(!o)return i.value||'';return (o.getAttribute('data-opt')||'').trim()||i.value||''}
function radioVal(id){var q=form.querySelector('.cq-q[data-q="'+id+'"]');if(!q)return '';var r=q.querySelector('input[type=radio]:checked');return r?r.value:''}
function evalShow(el){var c=el.getAttribute('data-show-if');if(!c)return true;try{c=JSON.parse(c)}catch(e){return true}var v=radioVal(c.q);if(c.equals!==undefined)return v===c.equals;if(c['in'])return c['in'].indexOf(v)>=0;return true}
function clearInputs(root){$('input,textarea',root).forEach(function(i){if(i.type==='checkbox'||i.type==='radio'){i.checked=false;i.disabled=false}else if(i.type!=='hidden'&&i.type!=='submit'){i.value=''}else if(i.type==='hidden'){i.value=''}});$('.cq-opt',root).forEach(function(o){o.classList.remove('is-selected','is-disabled')});$('.cq-other',root).forEach(function(o){o.classList.remove('is-on')});$('.cq-count',root).forEach(function(c){c.textContent=''})}
function compile(q){var h=q.querySelector('input[data-collect]');if(!h)return;var vals=$('input[type=checkbox]',q).filter(function(c){return c.checked}).map(optText);var o=q.querySelector('.cq-other input');var k=vals.indexOf('Other');if(k>=0&&o&&o.value.trim())vals[k]='Other: '+o.value.trim();h.value=vals.join(', ')}
function refresh(q){var max=parseInt(q.getAttribute('data-max')||'0',10);var boxes=$('input[type=checkbox]',q);var n=boxes.filter(function(b){return b.checked}).length;
$('.cq-opt',q).forEach(function(o){var i=o.querySelector('input');o.classList.toggle('is-selected',!!(i&&i.checked))});
if(max){boxes.forEach(function(b){var lim=!b.checked&&n>=max;b.disabled=lim;b.closest('.cq-opt').classList.toggle('is-disabled',lim)})}
var cnt=q.querySelector('.cq-count');if(cnt)cnt.textContent=max?(n+' of '+max+' selected'):(n?n+' selected':'');
var oth=q.querySelector('.cq-other');if(oth){var on=$('input:checked',q).some(function(i){return optText(i)==='Other'});oth.classList.toggle('is-on',on);if(!on){var t=oth.querySelector('input');if(t)t.value=''}}
if(q.getAttribute('data-type')==='multi')compile(q)}
function conditionals(){$('[data-show-if]').forEach(function(el){var show=evalShow(el);var hidden=el.classList.contains('cq-hidden');if(!show&&!hidden)clearInputs(el);el.classList.toggle('cq-hidden',!show)});
steps.forEach(function(s){if(!s.getAttribute('data-conditional'))return;var subs=$('.cq-sub',s);var any=subs.some(function(x){return !x.classList.contains('cq-hidden')});s.classList.toggle('cq-skip',!any)})}
function visible(){return steps.filter(function(s){return !s.classList.contains('cq-skip')})}
function paint(){var vs=visible();if(cur>vs.length-1)cur=vs.length-1;steps.forEach(function(s){s.classList.remove('is-active')});var s=vs[cur];s.classList.add('is-active');
if(lbl)lbl.textContent='Step '+(cur+1)+' of '+vs.length;if(ttl)ttl.textContent=s.getAttribute('data-title')||'';if(bar)bar.style.width=Math.round((cur+1)/vs.length*100)+'%';
nav.classList.toggle('has-back',cur>0);nav.classList.toggle('has-next',cur<vs.length-1);nav.classList.toggle('is-last',cur===vs.length-1);hideErr()}
function showErr(m){if(err){err.textContent=m;err.classList.add('is-on')}}
function hideErr(){if(err)err.classList.remove('is-on');$('.is-invalid').forEach(function(i){i.classList.remove('is-invalid')})}
function validate(step){var bad=$('[required]',step).filter(function(i){return !i.closest('.cq-hidden')&&!i.value.trim()});bad.forEach(function(i){i.classList.add('is-invalid')});if(bad.length){showErr('Please complete the highlighted fields before continuing.');bad[0].focus();return false}return true}
function scrollTop(){var p=page.querySelector('.cq-progress')||form;var y=p.getBoundingClientRect().top+window.pageYOffset-16;window.scrollTo({top:y,behavior:'smooth'})}
function go(d){var vs=visible();if(d>0&&!validate(vs[cur]))return;cur=Math.max(0,Math.min(cur+d,vs.length-1));paint();scrollTop()}
form.addEventListener('change',function(e){var q=e.target.closest('.cq-q');if(q)refresh(q);if(e.target.type==='radio')conditionals();if(e.target.type==='radio')paint()});
form.addEventListener('input',function(e){var q=e.target.closest('.cq-q');if(q&&e.target.closest('.cq-other'))compile(q);if(e.target.classList.contains('is-invalid')&&e.target.value.trim())e.target.classList.remove('is-invalid')});
form.addEventListener('click',function(e){var b=e.target.closest('[data-nav]');if(b){e.preventDefault();go(b.getAttribute('data-nav')==='next'?1:-1);return}
var o=e.target.closest('.cq-opt');if(o&&!e.target.closest('input,label')){var i=o.querySelector('input');if(i&&!i.disabled)i.click()}});
form.addEventListener('keydown',function(e){if(e.key==='Enter'&&e.target.tagName==='INPUT'&&e.target.type!=='submit'){e.preventDefault();if(nav.classList.contains('has-next'))go(1)}});
form.addEventListener('submit',function(e){var vs=visible();for(var i=0;i<vs.length;i++){if(!validate(vs[i])){e.preventDefault();e.stopImmediatePropagation();cur=i;paint();scrollTop();showErr('Please complete the highlighted fields before submitting.');return false}}$('.cq-q[data-type=multi]').forEach(compile)},true);
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
    print("shell %d chars, nav %d, css %d, head %d, footer %d" % (len(shell), len(nav), len(CSS), len(HEAD_CSS), len(JS)))
    for sec, s in zip(SECTIONS, steps):
        print("step %s: %d chars" % (sec["num"], len(s)))


if __name__ == "__main__":
    main()
