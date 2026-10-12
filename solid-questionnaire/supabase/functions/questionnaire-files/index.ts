// Client file uploads for the questionnaire (Supabase project solid-hub).
// Deployed with verify_jwt off: the page is public, so access is checked here instead.
//
// POST {name, size}      -> signed upload URL for a new private object (u/<uuid>/<name>);
//                           the page PUTs the file to it directly.
// GET ?id=&t=&p=         -> 302 to a short-lived download URL, only when submission <id> with
//                           access token <t> lists object <p> in one of its "— Files" answers.
//
// The site proxies this function at /f (vercel.json), so the page calls it same-origin.
import { createClient } from "npm:@supabase/supabase-js@2.49.4";

const BUCKET = "questionnaire-uploads";
const MAX_BYTES = 50 * 1024 * 1024;
const EXTENSIONS = new Set([
  "jpg", "jpeg", "png", "gif", "webp", "heic", "heif", "tif", "tiff", "svg",
  "pdf", "doc", "docx", "xls", "xlsx", "csv", "ppt", "pptx", "key", "pages", "numbers", "txt", "rtf",
  "dwg", "dxf", "skp", "rvt", "ifc", "3dm", "ai", "psd", "indd", "eps",
  "zip", "rar", "7z", "mp4", "mov", "m4v",
]);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false },
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function notFound() {
  return new Response("This file link is not valid.", { status: 404, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}

function safeName(name: string) {
  const dot = name.lastIndexOf(".");
  const ext = name.slice(dot + 1).toLowerCase();
  const stem = name
    .slice(0, dot)
    .normalize("NFKD")
    .replace(/[^\w\- ]+/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 80);
  return (stem || "file") + "." + ext;
}

async function sign(req: Request) {
  let body: { name?: unknown; size?: unknown };
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }
  const name = String(body.name || "").trim();
  const size = Number(body.size || 0);
  const ext = name.includes(".") ? name.split(".").pop()!.toLowerCase() : "";
  if (!EXTENSIONS.has(ext)) return json({ error: "type_not_allowed" }, 400);
  if (!(size > 0) || size > MAX_BYTES) return json({ error: "too_large" }, 400);
  const path = "u/" + crypto.randomUUID() + "/" + safeName(name);
  const { data, error } = await sb.storage.from(BUCKET).createSignedUploadUrl(path);
  if (error || !data) {
    console.error("sign failed", error?.message);
    return json({ error: "sign_failed" }, 502);
  }
  return json({ path, url: data.signedUrl });
}

async function download(url: URL) {
  const id = url.searchParams.get("id") || "";
  const token = url.searchParams.get("t") || "";
  const path = url.searchParams.get("p") || "";
  if (!UUID.test(id) || token.length < 20 || !/^u\/[0-9a-f-]{36}\/[^/]+$/.test(path)) return notFound();
  const { data, error } = await sb.rpc("questionnaire_submission", { p_id: id, p_token: token });
  if (error || !Array.isArray(data) || !data.length) return notFound();
  const answers = (data[0].answers || {}) as Record<string, unknown>;
  const listed = Object.keys(answers).some(
    (k) => k.endsWith(" — Files") && String(answers[k]).split("\n").map((s) => s.trim()).includes(path),
  );
  if (!listed) return notFound();
  const { data: signed, error: err } = await sb.storage
    .from(BUCKET)
    .createSignedUrl(path, 600, { download: path.split("/").pop() });
  if (err || !signed) return notFound();
  return new Response(null, { status: 302, headers: { Location: signed.signedUrl, "Cache-Control": "no-store" } });
}

Deno.serve((req) => {
  const url = new URL(req.url);
  if (req.method === "POST") return sign(req);
  if (req.method === "GET") return download(url);
  return json({ error: "method_not_allowed" }, 405);
});
