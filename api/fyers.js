// Vercel serverless function: thin proxy to the FYERS API v3.
//
//   GET  /api/fyers?action=config      -> { clientId, redirectUri, loginUrl }
//   POST /api/fyers?action=token       -> exchanges an auth_code for an access token ({ auth_code } in the body)
//   GET  /api/fyers?action=history&symbol=NSE:SBIN-EQ&from=YYYY-MM-DD&to=YYYY-MM-DD
//                                       -> daily candles; the caller's access token goes in the x-fyers-token header
//
// Environment variables (set in the Vercel project):
//   FYERS_CLIENT_ID      app ID from myapi.fyers.in, e.g. ABCD1234-100
//   FYERS_SECRET_KEY     app secret (never sent to the browser)
//   FYERS_REDIRECT_URI   optional; defaults to https://<this site>/ and must match the FYERS app setting
//
// Access tokens are never stored here: the browser keeps its own and sends it with each history request.

const crypto = require("crypto");

const API = "https://api-t1.fyers.in/api/v3";
const DATA = "https://api-t1.fyers.in/data";

const SYMBOL_RE = /^[A-Z0-9:&_.\-]{3,60}$/i;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function send(res, status, body) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(body));
}

function readBody(req) {
  if (req.body && typeof req.body === "object") return Promise.resolve(req.body);
  if (typeof req.body === "string") {
    try { return Promise.resolve(JSON.parse(req.body)); } catch (e) { return Promise.resolve({}); }
  }
  return new Promise((resolve) => {
    let raw = "";
    req.on("data", (c) => { raw += c; });
    req.on("end", () => { try { resolve(JSON.parse(raw || "{}")); } catch (e) { resolve({}); } });
    req.on("error", () => resolve({}));
  });
}

function siteOrigin(req) {
  const host = req.headers["x-forwarded-host"] || req.headers.host || "localhost";
  const proto = req.headers["x-forwarded-proto"] || "https";
  return `${proto}://${host}`;
}

module.exports = async function handler(req, res) {
  try {
    const url = new URL(req.url, "http://localhost");
    const action = url.searchParams.get("action");
    const clientId = process.env.FYERS_CLIENT_ID;
    const secret = process.env.FYERS_SECRET_KEY;

    if (action === "config") {
      if (!clientId || !secret) {
        return send(res, 500, { error: "FYERS_CLIENT_ID and FYERS_SECRET_KEY are not set on this site yet." });
      }
      const redirectUri = process.env.FYERS_REDIRECT_URI || siteOrigin(req) + "/";
      const params = new URLSearchParams({
        client_id: clientId,
        redirect_uri: redirectUri,
        response_type: "code",
        state: "mvo",
      });
      return send(res, 200, { clientId, redirectUri, loginUrl: `${API}/generate-authcode?${params}` });
    }

    if (action === "token") {
      if (req.method !== "POST") return send(res, 405, { error: "Use POST." });
      if (!clientId || !secret) return send(res, 500, { error: "FYERS credentials are not set on this site yet." });
      const body = await readBody(req);
      const code = String(body.auth_code || "").trim();
      if (!code) return send(res, 400, { error: "Missing auth_code." });
      const appIdHash = crypto.createHash("sha256").update(`${clientId}:${secret}`).digest("hex");
      const r = await fetch(`${API}/validate-authcode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ grant_type: "authorization_code", appIdHash, code }),
      });
      const j = await r.json().catch(() => ({}));
      if (!j.access_token) return send(res, 400, { error: j.message || "FYERS did not return a token." });
      return send(res, 200, { clientId, accessToken: j.access_token });
    }

    if (action === "history") {
      const token = req.headers["x-fyers-token"];
      if (!clientId) return send(res, 500, { error: "FYERS_CLIENT_ID is not set on this site yet." });
      if (!token) return send(res, 401, { error: "Missing token. Log in with FYERS first." });
      const symbol = url.searchParams.get("symbol") || "";
      const from = url.searchParams.get("from") || "";
      const to = url.searchParams.get("to") || "";
      if (!SYMBOL_RE.test(symbol)) return send(res, 400, { error: "Invalid symbol." });
      if (!DATE_RE.test(from) || !DATE_RE.test(to)) return send(res, 400, { error: "Dates must be YYYY-MM-DD." });
      const params = new URLSearchParams({
        symbol,
        resolution: "1D",
        date_format: "1",
        range_from: from,
        range_to: to,
        cont_flag: "1",
      });
      const r = await fetch(`${DATA}/history?${params}`, {
        headers: {
          Authorization: `${clientId}:${token}`,
          "Content-Type": "application/json",
          version: "3",
        },
      });
      const text = await r.text();
      let json;
      try { json = JSON.parse(text); } catch (e) { return send(res, 502, { error: `FYERS returned a non-JSON reply (HTTP ${r.status}).` }); }
      return send(res, 200, json);
    }

    return send(res, 404, { error: "Unknown action." });
  } catch (e) {
    return send(res, 500, { error: "Server error: " + (e && e.message ? e.message : String(e)) });
  }
};
