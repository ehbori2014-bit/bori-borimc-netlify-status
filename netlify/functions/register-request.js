const crypto = require("crypto");
const { readSession } = require("./_shared/session");

const DEFAULT_API_URL = "https://borimc.p-e.kr";
const DEFAULT_SITE_URL = "https://borisurvur.netlify.app";
const MAX_BODY_BYTES = 16 * 1024;
const RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify";

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
  return crypto.createHash("sha256").update(String(value || ""), "utf8").digest("hex");
}

function hmacSha256Hex(secret, value) {
  return crypto.createHmac("sha256", secret).update(String(value || ""), "utf8").digest("hex");
}

function requestIp(event) {
  const headers = event.headers || {};
  const raw = headers["x-nf-client-connection-ip"]
    || headers["X-Nf-Client-Connection-Ip"]
    || headers["client-ip"]
    || headers["Client-Ip"]
    || headers["x-forwarded-for"]
    || headers["X-Forwarded-For"]
    || "";
  return String(raw).split(",")[0].trim();
}

function hashContext(event, body) {
  const secret = process.env.BORIMC_IP_HASH_SECRET
    || process.env.BORIMC_REGISTRATION_SECRET
    || process.env.BORIMC_STATUS_SECRET
    || "borimc-development-hash-secret";
  const headers = event.headers || {};
  const ip = requestIp(event);
  const userAgent = headers["user-agent"] || headers["User-Agent"] || "";
  const deviceToken = String(body.deviceToken || "").trim();

  return {
    ipHash: hmacSha256Hex(secret, ip).slice(0, 64),
    ipPrefixHash: ip.includes(".") ? hmacSha256Hex(secret, ip.split(".").slice(0, 3).join(".")).slice(0, 64) : "",
    userAgentHash: hmacSha256Hex(secret, userAgent).slice(0, 64),
    deviceTokenHash: deviceToken ? hmacSha256Hex(secret, deviceToken).slice(0, 64) : ""
  };
}

function parseJsonBody(event) {
  const rawBody = event.isBase64Encoded
    ? Buffer.from(event.body || "", "base64").toString("utf8")
    : event.body || "";

  if (Buffer.byteLength(rawBody, "utf8") > MAX_BODY_BYTES) {
    return { error: json(413, { ok: false, status: "REQUEST_TOO_LARGE", message: "요청이 너무 큽니다." }) };
  }

  try {
    return { body: JSON.parse(rawBody || "{}") };
  } catch {
    return { error: json(400, { ok: false, status: "BAD_JSON", message: "요청 형식이 올바르지 않습니다." }) };
  }
}

function basicValidation(body) {
  const lastName = String(body.lastName || "").trim();
  const firstName = String(body.firstName || "").trim();
  const minecraftName = String(body.minecraftName || "").trim();
  const discordName = String(body.discordName || "").trim();
  const password = String(body.password || "");
  const passwordConfirm = String(body.passwordConfirm || "");
  const agreements = body.agreements || {};
  const koreanName = /^[가-힣]+$/;
  const minecraftNamePattern = /^[A-Za-z0-9_]{3,16}$/;

  if (!koreanName.test(lastName) || lastName.length < 1 || lastName.length > 2) {
    return "성은 한글 1~2글자로 입력해 주세요.";
  }
  if (!koreanName.test(firstName) || firstName.length < 1 || firstName.length > 4) {
    return "이름은 한글 1~4글자로 입력해 주세요.";
  }
  if (lastName.length + firstName.length < 2 || lastName.length + firstName.length > 5) {
    return "성+이름은 2~5글자를 권장합니다.";
  }
  if (!minecraftNamePattern.test(minecraftName)) {
    return "마크닉은 영문, 숫자, 언더바만 사용해 3~16자로 입력해 주세요.";
  }
  if (!discordName) {
    return "디스코드 닉네임을 입력해 주세요.";
  }
  if (password.length < 8 || password.length > 128) {
    return "비밀번호는 8~128자로 입력해 주세요.";
  }
  if (password !== passwordConfirm) {
    return "비밀번호 확인이 일치하지 않습니다.";
  }
  if (agreements.rules !== true || agreements.securityLogging !== true) {
    return "서버 규칙과 보안 기록 고지 동의가 필요합니다.";
  }
  return "";
}

function allowedHostnames() {
  const expected = process.env.RECAPTCHA_EXPECTED_HOSTNAME || "borisurvur.netlify.app";
  return new Set(
    expected
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean)
      .concat(["localhost"])
  );
}

async function verifyRecaptchaV2(token, ip) {
  const secret = process.env.RECAPTCHA_SECRET_KEY || "";
  if (!secret) {
    return { ok: false, status: "RECAPTCHA_NOT_CONFIGURED" };
  }

  const body = new URLSearchParams();
  body.set("secret", secret);
  body.set("response", token);
  if (ip) body.set("remoteip", ip);

  const response = await fetch(RECAPTCHA_VERIFY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });

  const data = await response.json();
  if (data.success !== true) {
    return { ok: false, status: "RECAPTCHA_FAILED", evidence: data };
  }

  const hostname = String(data.hostname || "").toLowerCase();
  if (hostname && !allowedHostnames().has(hostname)) {
    return { ok: false, status: "RECAPTCHA_HOSTNAME_MISMATCH", evidence: { hostname } };
  }

  return {
    ok: true,
    evidence: {
      hostname,
      score: data.score,
      action: data.action
    }
  };
}

async function verifyRecaptchaV3(token, ip) {
  const result = await verifyRecaptchaV2(token, ip);
  if (!result.ok) return result;
  const minScore = Number(process.env.RECAPTCHA_MIN_SCORE || "0.5");
  const expectedAction = process.env.RECAPTCHA_EXPECTED_ACTION || "register";
  const score = Number(result.evidence.score || 0);
  const action = String(result.evidence.action || "");

  if (action && action !== expectedAction) {
    return { ok: false, status: "RECAPTCHA_ACTION_MISMATCH", evidence: result.evidence };
  }
  if (score && score < minScore) {
    return { ok: false, status: "RECAPTCHA_LOW_SCORE", evidence: result.evidence };
  }
  return result;
}

async function verifyCaptcha(token, ip) {
  const version = (process.env.RECAPTCHA_VERSION || "v2").toLowerCase();
  if (version === "v3") {
    return verifyRecaptchaV3(token, ip);
  }
  return verifyRecaptchaV2(token, ip);
}

async function sendSecurityEvent(eventPayload) {
  const baseUrl = (process.env.BORIMC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
  const token = process.env.BORIMC_REGISTRATION_SECRET || process.env.BORIMC_STATUS_SECRET || "";
  if (!token) return;

  try {
    await fetch(`${baseUrl}/registrations/security-events`, {
      method: "POST",
      headers: {
        "Accept": "application/json",
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": "BoriMC-Netlify-Registration/1.0"
      },
      body: JSON.stringify(eventPayload)
    });
  } catch {
    // Security event delivery is best-effort. Do not expose backend details to users.
  }
}

async function forwardRegistration(payload) {
  const baseUrl = (process.env.BORIMC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
  const token = process.env.BORIMC_REGISTRATION_SECRET || process.env.BORIMC_STATUS_SECRET || "";
  if (!token) {
    return json(500, {
      ok: false,
      status: "REGISTRATION_NOT_CONFIGURED",
      message: "가입 서버 설정이 아직 완료되지 않았습니다."
    });
  }

  let response;
  try {
    response = await fetch(`${baseUrl}/registrations`, {
      method: "POST",
      headers: {
        "Accept": "application/json",
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": "BoriMC-Netlify-Registration/1.0"
      },
      body: JSON.stringify(payload)
    });
  } catch {
    return json(502, {
      ok: false,
      status: "REGISTRATION_API_UNAVAILABLE",
      message: "가입 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
    });
  }

  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  return json(response.ok ? 200 : response.status, {
    ok: Boolean(data.ok),
    status: data.status || "API_ERROR",
    message: data.message || "가입 서버 응답을 확인할 수 없습니다.",
    retryAfterSeconds: data.retryAfterSeconds
  });
}

exports.handler = async (event) => {
  const method = (event.httpMethod || "GET").toUpperCase();
  const contentType = String((event.headers || {})["content-type"] || (event.headers || {})["Content-Type"] || "");

  if (method !== "POST") {
    return json(405, { ok: false, status: "METHOD_NOT_ALLOWED", message: "POST 요청만 허용됩니다." });
  }
  if (!contentType.includes("application/json")) {
    return json(415, { ok: false, status: "UNSUPPORTED_MEDIA_TYPE", message: "JSON 요청만 허용됩니다." });
  }

  const parsed = parseJsonBody(event);
  if (parsed.error) return parsed.error;
  const body = parsed.body;
  const context = hashContext(event, body);
  const ip = requestIp(event);
  const sessionResult = readSession(event.headers || {});
  const linkedSession = sessionResult.authenticated ? sessionResult.session : null;

  if (!String(body.captchaToken || "").trim()) {
    await sendSecurityEvent({
      event_type: "RECAPTCHA_MISSING",
      severity: "MEDIUM",
      ...context,
      message: "reCAPTCHA token missing",
      evidence_json: { minecraftName: body.minecraftName, discordName: body.discordName }
    });
    return json(400, {
      ok: false,
      status: "RECAPTCHA_REQUIRED",
      message: "reCAPTCHA 인증을 완료해 주세요."
    });
  }

  if (String(body.honeypot || "").trim()) {
    await sendSecurityEvent({
      event_type: "HONEYPOT_FILLED",
      severity: "HIGH",
      ...context,
      message: "Honeypot field was filled",
      evidence_json: { field: "homepage" }
    });
    return json(403, {
      ok: false,
      status: "BOT_CHECK_SUSPICIOUS",
      message: "가입 요청이 비정상으로 감지되었습니다. 잠시 후 다시 시도해 주세요."
    });
  }

  let captcha;
  try {
    captcha = await verifyCaptcha(String(body.captchaToken), ip);
  } catch {
    captcha = { ok: false, status: "RECAPTCHA_FAILED" };
  }

  if (!captcha.ok) {
    await sendSecurityEvent({
      event_type: captcha.status || "RECAPTCHA_FAILED",
      severity: captcha.status === "RECAPTCHA_HOSTNAME_MISMATCH" ? "HIGH" : "MEDIUM",
      ...context,
      message: "reCAPTCHA verification failed",
      evidence_json: captcha.evidence || {}
    });
    return json(captcha.status === "RECAPTCHA_NOT_CONFIGURED" ? 500 : 403, {
      ok: false,
      status: captcha.status || "RECAPTCHA_FAILED",
      message: captcha.status === "RECAPTCHA_NOT_CONFIGURED"
        ? "reCAPTCHA 서버 설정이 아직 완료되지 않았습니다."
        : "reCAPTCHA 인증에 실패했습니다. 다시 시도해 주세요."
    });
  }

  const validationError = basicValidation(body);
  if (validationError) {
    return json(400, { ok: false, status: "INVALID_FORM", message: validationError });
  }

  return forwardRegistration({
    lastName: String(body.lastName || "").trim(),
    firstName: String(body.firstName || "").trim(),
    minecraftName: String(body.minecraftName || "").trim(),
    discordName: String(body.discordName || "").trim(),
    password: String(body.password || ""),
    passwordConfirm: String(body.passwordConfirm || ""),
    discordId: linkedSession && linkedSession.provider === "discord" ? linkedSession.providerUserId : "",
    googleSub: linkedSession && linkedSession.provider === "google" ? linkedSession.providerUserId : "",
    googleEmail: String(body.googleEmail || (linkedSession && linkedSession.provider === "google" ? linkedSession.email : "") || "").trim(),
    agreements: body.agreements || {},
    captcha: {
      provider: "recaptcha",
      version: process.env.RECAPTCHA_VERSION || "v2",
      verified: true
    },
    requestContext: {
      ...context,
      siteUrl: process.env.BORIMC_NETLIFY_SITE_URL || DEFAULT_SITE_URL
    }
  });
};
