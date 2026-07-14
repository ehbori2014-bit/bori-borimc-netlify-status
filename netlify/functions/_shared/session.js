const crypto = require("crypto");

const COOKIE_NAME = "borimc_session";
const DEFAULT_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

function sessionSecret() {
  return process.env.BORIMC_SESSION_SECRET
    || process.env.BORIMC_REGISTRATION_SECRET
    || process.env.BORIMC_STATUS_SECRET
    || "";
}

function base64UrlJson(value) {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
}

function sign(value) {
  const secret = sessionSecret();
  if (!secret) return "";
  return crypto.createHmac("sha256", secret).update(value).digest("base64url");
}

function cookieValue(headers, name) {
  const cookie = headers.cookie || headers.Cookie || "";
  const parts = cookie.split(";").map((item) => item.trim());
  const found = parts.find((item) => item.startsWith(`${name}=`));
  return found ? decodeURIComponent(found.slice(name.length + 1)) : "";
}

function createSessionCookie(payload, maxAgeSeconds = DEFAULT_MAX_AGE_SECONDS) {
  const secret = sessionSecret();
  if (!secret) return "";

  const safePayload = {
    provider: payload.provider,
    providerUserId: payload.providerUserId,
    displayName: payload.displayName,
    email: payload.email || "",
    linkedAt: new Date().toISOString(),
    exp: Math.floor(Date.now() / 1000) + maxAgeSeconds
  };
  const encoded = base64UrlJson(safePayload);
  const signature = sign(encoded);
  return `${COOKIE_NAME}=${encodeURIComponent(`${encoded}.${signature}`)}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${maxAgeSeconds}`;
}

function readSession(headers = {}) {
  const value = cookieValue(headers, COOKIE_NAME);
  const [encoded, signature] = value.split(".");
  if (!encoded || !signature) {
    return { ok: false, authenticated: false, status: "NO_SESSION" };
  }

  const expected = sign(encoded);
  if (!expected || signature.length !== expected.length || !crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) {
    return { ok: false, authenticated: false, status: "INVALID_SESSION" };
  }

  try {
    const payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    if (!payload.exp || payload.exp < Math.floor(Date.now() / 1000)) {
      return { ok: false, authenticated: false, status: "SESSION_EXPIRED" };
    }
    return { ok: true, authenticated: true, session: payload };
  } catch {
    return { ok: false, authenticated: false, status: "INVALID_SESSION" };
  }
}

function clearSessionCookie() {
  return `${COOKIE_NAME}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0`;
}

module.exports = {
  COOKIE_NAME,
  createSessionCookie,
  readSession,
  clearSessionCookie,
  sessionSecret
};
