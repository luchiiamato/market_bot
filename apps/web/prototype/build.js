// Vercel build step for the static prototype.
//
// The frontend is plain HTML/CSS/JS with no framework, so the "build" is
// a single rewrite: take the value of MARKET_BOT_API_BASE from the Vercel
// environment and stamp it into config.js. The browser then reads
// window.MARKET_BOT_API_BASE before app.js boots.
//
// If the env var is missing we still write the file (empty string) so the
// site doesn't 404 on /config.js. app.js falls back gracefully to
// window.location.origin in that case.

const fs = require("fs");
const path = require("path");

const apiBase = (process.env.MARKET_BOT_API_BASE || "").trim().replace(/\/$/, "");

const lines = [
  "// Generated at Vercel build time. Do not edit by hand.",
  `window.MARKET_BOT_API_BASE = ${JSON.stringify(apiBase)};`,
  "",
];

const target = path.join(__dirname, "config.js");
fs.writeFileSync(target, lines.join("\n"), "utf8");

console.log(`[build] wrote ${target} with MARKET_BOT_API_BASE=${apiBase || "(empty — will fall back to same origin)"}`);
