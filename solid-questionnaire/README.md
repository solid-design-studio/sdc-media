# Solid client questionnaire (private link)

A standalone site for the Client Questionnaire (Interior & Spatial Design). It is not part of
the Solid website: clients get the link directly from their account manager.

- Hosting: Vercel project `solid-questionnaire` (team "Solid Design Studio's projects").
- Pages: `/` is a landing page linking to both; `/interior` is the Interior & Spatial questionnaire (`interior/index.html`, `fields.json`) and `/graphic-design` the
  Branding & Graphic Design one (`graphic-design/index.html`, `fields-branding.json`; `/branding` redirects there). All three are written by
  `../webflow-client-questionnaire/build.py` (`python3 build.py` / `python3 build.py branding`); never edit them by hand.
  Each page posts its id as `form`; it is stored as `_form` in the answers and picks the field map (`FORMS` in `api/_lib.js`).
- Submissions: Supabase project `solid-hub`, table `questionnaire_submissions` (insert-only for the site;
  reads go through the `questionnaire_submission` / `questionnaire_inbox` functions).
- Images: Supabase storage bucket `questionnaire` (public read; uploads only with the service key / dashboard).
- Client uploads: private bucket `questionnaire-uploads` (50 MB per file). The Supabase Edge Function
  `questionnaire-files` (source in `supabase/functions/`, deployed with JWT verification off) hands out
  signed upload URLs and, for `GET ?id=&t=&p=`, a 10-minute download link only when that submission's
  token matches and its answers list the file. The site proxies it at `/f` (`vercel.json`).
- Functions: `api/submit.js` (stores + notifies), `api/view.js` (`/s/<id>?t=<token>`, one submission),
  `api/inbox.js` (`/inbox?key=<team key>`, all submissions).

Notifications: the simplest setup is a Gmail app password for hello@ (`GMAIL_USER`, `GMAIL_APP_PASSWORD` in the Vercel project; emails go to `NOTIFY_TO`). Alternatively Google OAuth credentials in the Vercel project (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`GOOGLE_REFRESH_TOKEN`, the same OAuth client as consultation.solid2017.com). With the Gmail send scope the
team gets an email (`NOTIFY_TO`); with a calendar-only grant it gets a calendar invite instead
(`CALENDAR_INVITEES`). Without credentials, submissions are still stored and visible in the inbox.

Email: each submission is also emailed to design@ (cc fatimah-alamer@hotmail.com, hello@, aljazi@, banah@, manal@) from the page through FormSubmit (formsubmit.co, free, no keys). design@ must click "Activate Form" in FormSubmit's first email once. Approved by Solid on 12 Oct 2026.
