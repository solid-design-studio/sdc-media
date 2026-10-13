"use strict";
const { rpc, page, escapeHtml, FORMS, formOf } = require("./_lib");

module.exports = async (req, res) => {
  const url = new URL(req.url, "https://x");
  const key = url.searchParams.get("key") || "";
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.setHeader("Cache-Control", "private, no-store");
  if (key.length < 20) {
    return res.status(404).end(page("Not found", "<h1>Not found</h1><p class=\"meta\">This link is not valid.</p>"));
  }
  let rows;
  try {
    rows = await rpc("questionnaire_inbox", { p_key: key });
  } catch (err) {
    console.error("inbox failed", err && err.message);
    return res.status(502).end(page("Unavailable", "<h1>Temporarily unavailable</h1><p class=\"meta\">Please try again in a moment.</p>"));
  }
  if (!rows) rows = [];
  let body = '<p class="kicker">Client questionnaire · Team inbox</p><h1>Submissions</h1><p class="meta">' +
    rows.length + (rows.length === 1 ? " submission" : " submissions") + ", newest first. Keep this link within the team.</p>";
  if (!rows.length) {
    body += "<p>No submissions yet.</p>";
  } else {
    body += "<table><thead><tr><th>Received</th><th>Project</th><th>Questionnaire</th><th>Contact</th><th>Type</th><th>Notified</th></tr></thead><tbody>";
    for (const r of rows) {
      const link = "/s/" + r.id + "?t=" + encodeURIComponent(r.access_token);
      body +=
        "<tr><td>" + escapeHtml(new Date(r.created_at).toISOString().slice(0, 16).replace("T", " ")) + " UTC</td>" +
        '<td><a href="' + link + '">' + escapeHtml(r.project_name || "Untitled") + "</a></td>" +
        "<td>" + escapeHtml(FORMS[formOf(r.answers)].label) + "</td>" +
        "<td>" + escapeHtml(r.contact || "") + "</td>" +
        "<td>" + escapeHtml(r.project_type || "") + "</td>" +
        '<td><span class="pill">' + escapeHtml(r.notified_via || "none") + "</span></td></tr>";
    }
    body += "</tbody></table>";
  }
  return res.status(200).end(page("Questionnaire inbox", body));
};
