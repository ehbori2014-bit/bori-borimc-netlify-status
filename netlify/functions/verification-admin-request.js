const { readSession } = require("./_shared/session");

const DEFAULT_API_URL = "https://borimc.p-e.kr";

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

exports.handler = async (event) => {
  if ((event.httpMethod || "GET").toUpperCase() !== "POST") {
    return json(405, { ok: false, status: "METHOD_NOT_ALLOWED", message: "POST 요청만 허용됩니다." });
  }

  const session = readSession(event.headers || {});
  if (!session.authenticated) {
    return json(401, {
      ok: false,
      status: "LOGIN_REQUIRED",
      message: "Discord 또는 Google 연결 후 운영진 인증 요청을 보낼 수 있습니다."
    });
  }

  const token = process.env.BORIMC_REGISTRATION_SECRET || process.env.BORIMC_STATUS_SECRET || "";
  if (!token) {
    return json(501, {
      ok: false,
      status: "VERIFICATION_API_NOT_CONFIGURED",
      message: "인증 서버 설정이 완료되면 운영진 인증 요청을 보낼 수 있습니다."
    });
  }

  const baseUrl = (process.env.BORIMC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
  let response;
  try {
    response = await fetch(`${baseUrl}/verifications/admin-request`, {
      method: "POST",
      headers: {
        "Accept": "application/json",
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": "BoriMC-Netlify-Verification/1.0"
      },
      body: JSON.stringify({
        provider: session.session.provider,
        providerUserId: session.session.providerUserId
      })
    });
  } catch {
    return json(502, {
      ok: false,
      status: "VERIFICATION_API_UNAVAILABLE",
      message: "인증 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
    });
  }

  const data = await response.json().catch(() => ({}));
  return json(response.ok ? 200 : response.status, {
    ok: response.ok && data.ok !== false,
    status: data.status || (response.ok ? "ADMIN_REVIEW_REQUESTED" : "API_ERROR"),
    message: data.message || "운영진 인증 요청을 접수했습니다."
  });
};
