// Contact form endpoint: POST https://residentquant.com/api/contact
// Runs on our own Cloudflare account. Emails each submission with Cloudflare Email Routing.
// Deploy: cd worker && npx wrangler deploy && npx wrangler secret put TO
// Bindings:
//   MAIL  send_email binding (wrangler.toml)
//   TO    secret: the verified Email Routing destination inbox
//   FROM  var: form@residentquant.com
import { EmailMessage } from "cloudflare:email";

const ORIGINS = ["https://residentquant.com", "https://www.residentquant.com"];
const clean = (v, n = 2000) => String(v ?? "").replace(/[\r\n]+/g, " ").trim().slice(0, n);
const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json" } });

export default {
  async fetch(req, env) {
    if (req.method !== "POST") return json({ ok: false, error: "POST only" }, 405);
    if (!ORIGINS.includes(req.headers.get("origin"))) return json({ ok: false, error: "bad origin" }, 403);

    const f = await req.formData();
    if (f.get("website")) return json({ ok: true });            // honeypot: bots fill hidden fields

    const name = clean(f.get("name"), 200), email = clean(f.get("email"), 200), company = clean(f.get("company"), 200);
    if (!name || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return json({ ok: false, error: "Name and work email are required." }, 400);

    const body = [
      `Name: ${name}`, `Email: ${email}`, `Company: ${company}`,
      `Team size: ${clean(f.get("size"), 50)}`,
      `Interested in: ${f.getAll("interest").map(v => clean(v, 30)).join(", ")}`,
      `Data today: ${clean(f.get("stack"), 500)}`, "",
      String(f.get("message") ?? "").slice(0, 5000),
    ].join("\n");

    const raw = [
      `From: ResidentQuant site <${env.FROM}>`, `To: ${env.TO}`, `Reply-To: ${name} <${email}>`,
      `Subject: New lead: ${name}${company ? " at " + company : ""}`,
      `Message-ID: <${crypto.randomUUID()}@residentquant.com>`, `Date: ${new Date().toUTCString()}`,
      "MIME-Version: 1.0", "Content-Type: text/plain; charset=utf-8", "Content-Transfer-Encoding: 8bit", "", body,
    ].join("\r\n");

    try { await env.MAIL.send(new EmailMessage(env.FROM, env.TO, raw)); }
    catch (e) { return json({ ok: false, error: "send failed" }, 502); }
    return json({ ok: true });
  },
};
