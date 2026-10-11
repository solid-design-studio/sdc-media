"use strict";
const crypto = require("node:crypto");
const { insertSubmission, rpc, notify, origin } = require("./_lib");

const REQUIRED = ["01.1 Project / Brand Name", "01.2 Primary Contact", "01.3 Project Location / Venue"];
const MAX_FIELDS = 400;
const MAX_KEY = 160;
const MAX_VALUE = 8000;
const MAX_TOTAL = 250000;

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "method_not_allowed" });

  const body = req.body && typeof req.body === "object" ? req.body : null;
  const answers = body && body.answers && typeof body.answers === "object" && !Array.isArray(body.answers) ? body.answers : null;
  if (!answers) return res.status(400).json({ error: "invalid_json" });

  // Honeypot: the page has no field called "website"; bots fill everything.
  if (typeof answers.website === "string" && answers.website.trim()) return res.status(200).json({ id: null });

  const keys = Object.keys(answers);
  if (keys.length > MAX_FIELDS) return res.status(400).json({ error: "too_many_fields" });
  const clean = {};
  let total = 0;
  for (const k of keys) {
    const v = answers[k];
    if (typeof v !== "string" || k.length > MAX_KEY) continue;
    const t = v.trim().slice(0, MAX_VALUE);
    total += t.length;
    if (total > MAX_TOTAL) return res.status(400).json({ error: "too_large" });
    clean[k] = t;
  }
  for (const k of REQUIRED) {
    if (!clean[k]) return res.status(400).json({ error: "required", field: k });
  }

  const token = crypto.randomBytes(24).toString("base64url");
  let row;
  try {
    row = await insertSubmission({
      project_name: clean["01.1 Project / Brand Name"] || null,
      contact: clean["01.2 Primary Contact"] || null,
      project_type: clean["01.5 Project type"] || null,
      answers: clean,
      access_token: token,
      user_agent: String(req.headers["user-agent"] || "").slice(0, 300),
    });
  } catch (err) {
    console.error("insert failed", err && err.message);
    return res.status(502).json({ error: "storage_unavailable" });
  }

  const link = origin(req) + "/s/" + row.id + "?t=" + token;
  const via = await notify(row, link);
  if (via !== "none") {
    await rpc("questionnaire_mark_notified", { p_id: row.id, p_token: token, p_via: via }).catch((err) =>
      console.error("mark notified failed", err && err.message)
    );
  } else {
    console.error("submission stored but nobody was notified (no Google credentials?)", row.id);
  }
  return res.status(200).json({ id: row.id });
};
