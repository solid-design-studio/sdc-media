"use strict";
/* Shared helpers for the questionnaire site's serverless functions. */
const fieldsFile = require("../fields.json");

const SUPABASE_URL = process.env.SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY || "";

function sbHeaders(extra) {
  return Object.assign(
    {
      apikey: SUPABASE_ANON_KEY,
      Authorization: "Bearer " + SUPABASE_ANON_KEY,
      "Content-Type": "application/json",
    },
    extra || {}
  );
}

async function sbFetch(path, init) {
  const res = await fetch(SUPABASE_URL + path, init);
  const text = await res.text();
  if (!res.ok) throw new Error("Supabase " + res.status + " on " + path + ": " + text.slice(0, 300));
  return text ? JSON.parse(text) : null;
}

/**
 * Insert one submission through the security-definer function, so the site
 * needs no table privileges at all. Returns the row's id and timestamp.
 */
async function insertSubmission(row) {
  const rows = await sbFetch("/rest/v1/rpc/questionnaire_submit", {
    method: "POST",
    headers: sbHeaders(),
    body: JSON.stringify({
      p_project_name: row.project_name,
      p_contact: row.contact,
      p_project_type: row.project_type,
      p_answers: row.answers,
      p_access_token: row.access_token,
      p_user_agent: row.user_agent,
    }),
  });
  const r = Array.isArray(rows) ? rows[0] : rows;
  if (!r || !r.id) throw new Error("questionnaire_submit returned no id");
  return Object.assign({}, row, { id: r.id, created_at: r.created_at });
}

async function rpc(name, args) {
  return sbFetch("/rest/v1/rpc/" + name, {
    method: "POST",
    headers: sbHeaders(),
    body: JSON.stringify(args),
  });
}

/** The questionnaire's questions in order, with section titles. */
const FIELDS = fieldsFile.fields;
const SECTIONS = fieldsFile.sections;
const FIELD_BY_KEY = new Map(FIELDS.map((f) => [f.key, f]));

/** Answers grouped by section, in questionnaire order; empty answers left out. */
function groupAnswers(answers) {
  const groups = [];
  const seen = new Set();
  for (const sec of SECTIONS) {
    const items = [];
    for (const f of FIELDS) {
      if (f.section !== sec.code) continue;
      const v = answers[f.key];
      seen.add(f.key);
      if (typeof v === "string" && v.trim()) items.push({ label: f.label, value: v.trim() });
    }
    if (items.length) groups.push({ code: sec.code, title: sec.title, items });
  }
  // Anything the page sent that the map does not know (should not happen; kept rather than dropped).
  const extra = Object.keys(answers)
    .filter((k) => !seen.has(k) && typeof answers[k] === "string" && answers[k].trim())
    .map((k) => ({ label: k, value: answers[k].trim() }));
  if (extra.length) groups.push({ code: "", title: "Other fields", items: extra });
  return groups;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function summaryLine(answers) {
  const name = (answers["01.1 Project / Brand Name"] || "").trim() || "Untitled project";
  const type = (answers["01.5 Project type"] || "").trim();
  return type ? name + " (" + type + ")" : name;
}

function formatText(sub, link) {
  const lines = [];
  lines.push("New client questionnaire: " + summaryLine(sub.answers));
  lines.push("Received " + new Date(sub.created_at).toUTCString().replace("GMT", "UTC"));
  if (link) lines.push("Open the full submission: " + link);
  for (const g of groupAnswers(sub.answers)) {
    lines.push("");
    lines.push("== " + (g.code ? g.code + " " : "") + g.title + " ==");
    for (const it of g.items) {
      const multi = it.value.indexOf("\n") >= 0;
      lines.push(multi ? it.label + ":\n" + it.value : it.label + ": " + it.value);
    }
  }
  return lines.join("\n");
}

const PAGE_CSS = `
*{box-sizing:border-box}body{margin:0;background:#FAFAFA;color:#111;font:15px/1.5 "Neue Montreal",Arial,sans-serif;-webkit-font-smoothing:antialiased}
@font-face{font-family:"Neue Montreal";src:url("/fonts/NeueMontreal-Regular.woff2") format("woff2");font-weight:400;font-display:swap}
@font-face{font-family:"Neue Montreal";src:url("/fonts/NeueMontreal-Medium.woff2") format("woff2");font-weight:500;font-display:swap}
@font-face{font-family:"Neue Montreal";src:url("/fonts/NeueMontreal-Bold.woff2") format("woff2");font-weight:700;font-display:swap}
.bar{background:#111;height:64px;display:flex;align-items:center;padding:0 32px}.bar img{height:22px;display:block}
.wrap{max-width:880px;margin:0 auto;padding:56px 28px 96px}
.kicker{font:700 11px/1.4 "IBM Plex Sans",sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#888;margin:0 0 12px}
h1{font:700 34px/1.15 "IBM Plex Sans",sans-serif;margin:0 0 8px}h2{font:700 20px/1.2 "IBM Plex Sans",sans-serif;margin:40px 0 14px;padding-top:24px;border-top:1px solid #E6E6E6}
.meta{color:#666;margin:0 0 8px}
dl{margin:0}dt{font-weight:500;color:#111;margin:14px 0 2px}dd{margin:0;color:#333;white-space:pre-wrap}
table{width:100%;border-collapse:collapse;margin-top:24px}th,td{text-align:left;padding:12px 10px;border-bottom:1px solid #E6E6E6;vertical-align:top}th{font:700 11px/1.4 "IBM Plex Sans",sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#888}
a{color:#2B36FF}.pill{display:inline-block;background:#F0F0F0;border-radius:100px;padding:2px 10px;font-size:12px}
@media(max-width:600px){.wrap{padding:36px 20px 72px}h1{font-size:26px}}
`;

function page(title, body) {
  return (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>' +
    escapeHtml(title) +
    ' · Solid</title><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;700&display=swap" rel="stylesheet"><style>' +
    PAGE_CSS +
    '</style></head><body><div class="bar"><img src="/solid-logo.svg" alt="Solid"></div><div class="wrap">' +
    body +
    "</div></body></html>"
  );
}

function formatHtml(sub) {
  let out = '<p class="kicker">Client questionnaire · Interior &amp; Spatial Design</p>';
  out += "<h1>" + escapeHtml(summaryLine(sub.answers)) + "</h1>";
  out += '<p class="meta">Received ' + escapeHtml(new Date(sub.created_at).toUTCString().replace("GMT", "UTC")) + "</p>";
  for (const g of groupAnswers(sub.answers)) {
    out += "<h2>" + escapeHtml((g.code ? g.code + " · " : "") + g.title) + "</h2><dl>";
    for (const it of g.items) out += "<dt>" + escapeHtml(it.label) + "</dt><dd>" + escapeHtml(it.value) + "</dd>";
    out += "</dl>";
  }
  return out;
}

/* ---------------- Google (optional): Gmail first, Calendar invite as fallback ---------------- */

function googleConfigured() {
  return Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET && process.env.GOOGLE_REFRESH_TOKEN);
}

let cachedToken = null;
async function accessToken() {
  if (cachedToken && cachedToken.expiresAt > Date.now() + 60000) return cachedToken.value;
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: process.env.GOOGLE_CLIENT_ID,
      client_secret: process.env.GOOGLE_CLIENT_SECRET,
      refresh_token: process.env.GOOGLE_REFRESH_TOKEN,
      grant_type: "refresh_token",
    }),
  });
  if (!res.ok) throw new Error("Google token refresh failed: " + (await res.text()).slice(0, 200));
  const body = await res.json();
  cachedToken = { value: body.access_token, expiresAt: Date.now() + body.expires_in * 1000 };
  return cachedToken.value;
}

async function googleCall(url, init) {
  const res = await fetch(url, Object.assign({}, init, {
    headers: Object.assign({ Authorization: "Bearer " + (await accessToken()), "Content-Type": "application/json" }, (init && init.headers) || {}),
  }));
  if (!res.ok) {
    const err = new Error("Google " + res.status + ": " + (await res.text()).slice(0, 300));
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function base64url(s) {
  return Buffer.from(s, "utf8").toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Needs the gmail.send scope on the refresh token. */
async function sendMail({ to, subject, text }) {
  const raw = [
    "To: " + to.join(", "),
    "Subject: =?UTF-8?B?" + Buffer.from(subject, "utf8").toString("base64") + "?=",
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: base64",
    "",
    Buffer.from(text, "utf8").toString("base64"),
  ].join("\r\n");
  return googleCall("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", {
    method: "POST",
    body: JSON.stringify({ raw: base64url(raw) }),
  });
}

/** Works with the calendar-only grant: an all-day entry on hello@'s calendar; Google emails the invitees. */
async function createNoticeEvent({ summary, description, attendees }) {
  const day = new Date().toISOString().slice(0, 10);
  const next = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  return googleCall("https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=all", {
    method: "POST",
    body: JSON.stringify({
      summary,
      description,
      start: { date: day },
      end: { date: next },
      attendees: attendees.map((email) => ({ email })),
      reminders: { useDefault: false, overrides: [{ method: "email", minutes: 0 }] },
    }),
  });
}

function list(env, fallback) {
  return (process.env[env] || fallback).split(",").map((s) => s.trim()).filter(Boolean);
}

/** Returns how the team was told: "email", "calendar" or "none". Never throws. */
async function notify(sub, link) {
  if (!googleConfigured()) return "none";
  const subject = "New client questionnaire: " + summaryLine(sub.answers);
  const text = formatText(sub, link);
  try {
    await sendMail({ to: list("NOTIFY_TO", "fatimah@solid2017.com,hello@solid2017.com"), subject, text });
    return "email";
  } catch (err) {
    console.error("gmail send failed, trying a calendar invite", err && err.message);
  }
  try {
    await createNoticeEvent({
      summary: subject,
      description: text,
      attendees: list("CALENDAR_INVITEES", "fatimah@solid2017.com,design@solid2017.com"),
    });
    return "calendar";
  } catch (err) {
    console.error("calendar notice failed", err && err.message);
    return "none";
  }
}

function origin(req) {
  if (process.env.PUBLIC_ORIGIN) return process.env.PUBLIC_ORIGIN.replace(/\/$/, "");
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  return "https://" + host;
}

module.exports = { insertSubmission, rpc, groupAnswers, formatText, formatHtml, page, escapeHtml, summaryLine, notify, origin, FIELD_BY_KEY };
