# Webflow Client Questionnaire (solid2017 site)

Source files for the **Client Questionnaire — Interior & Spatial Design** landing page
built on the solid2017 Webflow site from the "Client questionnaire V2 — Sep 2026" PDF.

The page itself lives in Webflow; this folder is the generator, the custom code that is
on the page, and a local test harness so the questionnaire can be regenerated or audited.

## Where it is in Webflow

| Item | Value |
| --- | --- |
| Site | solid2017 (site id `69f71feb8625d5d8995832eb`) |
| Page | Pages → **Client Questionnaire**, slug `/client-questionnaire` (page id `6acb3b750a11a8c2c2a86c75`) |
| State | **Draft, unpublished**. Untick *Draft* in page settings and publish when ready. |
| Form name | `Client Questionnaire — Interior & Spatial Design` (submissions appear under Forms with this name) |
| Custom code | Page settings → Custom code. `out/head.html` is the *Head* block, `out/footer.html` is the *Before </body>* block. |

Nothing else on the site was touched: no existing page, component, style or asset was
edited. All new classes are prefixed `cq-`; all new assets are the questionnaire images.

## What the page does

* 12 sections as a stepper (one section per step) with progress bar and Back / Next / Submit.
* Required-field validation per step, "Other" reveal fields, max-select limits with counters.
* Conditional follow-ups (04.2b, 06.4b, 06.5b, 06.6b, 06.7) shown only after "Yes".
* Section 08 (Project-specific) shows only the sub-section matching the project type chosen in
  01.5 (F&B → A, Retail → B, Pop-up / Activation & Event / Temporary space → C,
  Cultural / Art / Exhibition → D) and is skipped entirely for other project types.
* Multi-select answers are compiled into one hidden field per question so each submission
  arrives in Webflow Forms as readable columns, e.g. `01.4 Looking for from Solid`,
  `05.3 Creative direction`, `08B.2 Retail focus`.
* File uploads are collected as "upload or share links" text fields (native Webflow file
  upload needs a Business plan; not enabled).

## Files

| File | Purpose |
| --- | --- |
| `spec.py` | The questionnaire content: every section, question, option, help text, limits, images and conditional rules. Edit this to change wording or options. |
| `build.py` | Generates the Webflow HTML/CSS, the page custom code and a standalone preview into `out/`. |
| `assets.json` | Image file name → Webflow asset id (uploaded to the site's Assets panel). |
| `test.js` | Playwright checks against `out/preview.html`: stepper, validation, limits, conditionals, Section 08 routing, submit payload, keyboard, mobile overflow. |
| `out/` | Generated output. `head.html` and `footer.html` are what is on the Webflow page. |

## Regenerate / test locally

```bash
python3 build.py          # writes out/
node test.js              # needs playwright; uses the Chromium at /opt/pw-browsers/chromium
```

To change the page in Webflow after editing `spec.py`: rebuild, then re-insert the affected
`out/step-XX.html` block (or update the custom code from `out/head.html` / `out/footer.html`)
with the Webflow Designer or the Webflow MCP tools. Steps are self-contained `<section class="cq-step">`
blocks inside `form.cq-form > .cq-steps`.

## Notes for review

* Creative-direction and colour-direction cards use Aisha's Dropbox reference images.
  The **Monochromatic** colour swatch was generated (no reference supplied) and the supplied
  *Futuristic* palette is not used by any option.
* Question numbers are sequential per section (the PDF numbering was inconsistent); the PDF
  order and wording are kept.
