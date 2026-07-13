const crypto = require("crypto");

const DEFAULT_API_URL = "https://borimc.p-e.kr";
const ALLOWED_METHODS = new Set(["GET"]);
const ALLOWED_PATHS = new Set([
  "/ping",
  "/health",
  "/status",
  "/server-status"
]);
const TIMEOUT_MS = 5000;

function json(statusCode, body) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store"
    },
    body: JSON.stringify(body)
  };
}

function sha256Hex(value) {
  return crypto.createHash("sha256").update(value || "", "utf8").digest("hex");
}

function hmacSha256Hex(secret, value) {
  return crypto.createHmac("sha256", secret).update(value, "utf8").digest("hex");
}

function nonce() {
  return crypto.randomBytes(16).toString("hex");
}

function signedHeaders({ method, path, body, secret, keyType }) {
  const timestamp = new Date().toISOString();
  const requestNonce = nonce();
  const bodyHash = sha256Hex(body || "");
  const signingString = [
    method.toUpperCase(),
    path,
    timestamp,
    requestNonce,
    bodyHash
  ].join("\n");

  return {
    "X-Bori-Timestamp": timestamp,
    "X-Bori-Nonce": requestNonce,
    "X-Bori-Signature": hmacSha256Hex(secret, signingString),
    "X-Bori-Key-Type": keyType
  };
}

function normalizePath(rawPath) {
  const value = rawPath || "/ping";
  if (!value.startsWith("/")) {
    return `/${value}`;
  }
  return value;
}

function cleanError(error) {
  const message = String(error && error.message ? error.message : "proxy request failed");
  if (message.toLowerCase().includes("abort") || message.toLowerCase().includes("timeout")) {
    return "timeout";
  }
  return "proxy request failed";
}

exports.handler = async (event) => {
  const method = (event.httpMethod || "GET").toUpperCase();
  const path = normalizePath(event.queryStringParameters && event.queryStringParameters.path);
  const baseUrl = (process.env.BORIMC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
  const statusSecret = process.env.BORIMC_STATUS_SECRET || "";

  if (!ALLOWED_METHODS.has(method)) {
    return json(405, { ok: false, error: "method not allowed" });
  }

  if (!ALLOWED_PATHS.has(path)) {
    return json(400, { ok: false, error: "path not allowed" });
  }

  if (!statusSecret) {
    return json(500, { ok: false, error: "proxy is not configured" });
  }

  const target = `${baseUrl}${path}`;
  const body = "";
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const startedAt = Date.now();

  try {
    const response = await fetch(target, {
      method,
      signal: controller.signal,
      headers: {
        "Accept": "application/json",
        "User-Agent": "BoriMC-Netlify-Proxy/1.0",
        ...signedHeaders({
          method,
          path,
          body,
          secret: statusSecret,
          keyType: "status"
        })
      }
    });

    const contentType = response.headers.get("content-type") || "";
    const text = await response.text();
    let data = text;

    if (contentType.includes("application/json")) {
      try {
        data = JSON.parse(text);
      } catch (error) {
        data = null;
      }
    }

    return json(200, {
      ok: response.ok,
      status: response.status,
      responseMs: Date.now() - startedAt,
      data,
      checkedAt: new Date().toISOString()
    });
  } catch (error) {
    return json(200, {
      ok: false,
      error: cleanError(error),
      checkedAt: new Date().toISOString()
    });
  } finally {
    clearTimeout(timeout);
  }
};
