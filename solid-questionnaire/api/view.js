"use strict";
const { rpc, formatHtml, page } = require("./_lib");

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

module.exports = async (req, res) => {
  const url = new URL(req.url, "https://x");
  const id = url.searchParams.get("id") || "";
  const token = url.searchParams.get("t") || "";
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.setHeader("Cache-Control", "private, no-store");
  if (!UUID.test(id) || token.length < 20) {
    return res.status(404).end(page("Not found", "<h1>Not found</h1><p class=\"meta\">This link is not valid.</p>"));
  }
  let rows;
  try {
    rows = await rpc("questionnaire_submission", { p_id: id, p_token: token });
  } catch (err) {
    console.error("view failed", err && err.message);
    return res.status(502).end(page("Unavailable", "<h1>Temporarily unavailable</h1><p class=\"meta\">Please try again in a moment.</p>"));
  }
  if (!rows || !rows.length) {
    return res.status(404).end(page("Not found", "<h1>Not found</h1><p class=\"meta\">This link is not valid.</p>"));
  }
  return res.status(200).end(page("Questionnaire · " + (rows[0].project_name || "Submission"), formatHtml(rows[0], token)));
};
