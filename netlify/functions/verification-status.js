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

async function forwardStatus(session) {
  const baseUrl = (process.env.BORIMC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
  const token = process.env.BORIMC_REGISTRATION_SECRET || process.env.BORIMC_STATUS_SECRET || "";
  if (!token) {
    return null;
  }

  const params = new URLSearchParams({
    provider: session.provider,
    providerUserId: session.providerUserId
  });
  const response = await fetch(`${baseUrl}/verifications/status?${params.toString()}`, {
    method: "GET",
    headers: {
      "Accept": "application/json",
      "Authorization": `Bearer ${token}`,
      "User-Agent": "BoriMC-Netlify-Verification/1.0"
    }
  });
  return response.json().catch(() => ({}));
}

exports.handler = async (event) => {
  const result = readSession(event.headers || {});
  if (!result.authenticated) {
    return json(401, {
      ok: false,
      authenticated: false,
      status: "LOGIN_REQUIRED",
      message: "Discord 또는 Google 연결 후 인증 상태를 확인할 수 있습니다."
    });
  }

  try {
    const backend = await forwardStatus(result.session);
    if (backend) {
      return json(200, {
        ok: backend.ok !== false,
        authenticated: true,
        status: backend.status || "PENDING_VERIFICATION",
        verificationDeadline: backend.verificationDeadline || backend.verification_deadline || "",
        methods: backend.methods || ["ADMIN", "MINECRAFT", "DISCORD"],
        message: backend.message || "인증 상태를 확인했습니다."
      });
    }
  } catch {
    // Fall back to a safe local state. Do not expose backend errors.
  }

  return json(200, {
    ok: true,
    authenticated: true,
    status: "PENDING_VERIFICATION",
    verificationDeadline: "",
    methods: ["ADMIN", "MINECRAFT", "DISCORD"],
    message: "계정 연결은 확인되었습니다. 서버 인증 완료 여부는 운영진 확인 또는 Minecraft 인증 후 갱신됩니다."
  });
};
