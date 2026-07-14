const DEFAULT_SITE_URL = "https://borisurvur.netlify.app";
const { createSessionCookie } = require("./_shared/session");

function cookieValue(headers, name) {
  const cookie = headers.cookie || headers.Cookie || "";
  const parts = cookie.split(";").map((item) => item.trim());
  const found = parts.find((item) => item.startsWith(`${name}=`));
  return found ? decodeURIComponent(found.slice(name.length + 1)) : "";
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function html(statusCode, title, message, cookies = []) {
  const safeTitle = escapeHtml(title);
  const safeMessage = escapeHtml(message);
  return {
    statusCode,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store"
    },
    multiValueHeaders: {
      "Set-Cookie": [
        "borimc_discord_oauth_state=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0",
        ...cookies
      ].filter(Boolean)
    },
    body: `<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="2; url=/#register"><title>${safeTitle}</title><body style="font-family:system-ui;padding:32px;line-height:1.6"><h1>${safeTitle}</h1><p>${safeMessage}</p><p><a href="/#register">가입/인증 화면으로 돌아가기</a></p></body></html>`
  };
}

exports.handler = async (event) => {
  const params = event.queryStringParameters || {};
  const code = params.code || "";
  const state = params.state || "";
  const expectedState = cookieValue(event.headers || {}, "borimc_discord_oauth_state");

  if (!code || !state || !expectedState || state !== expectedState) {
    return html(400, "Discord 연결 실패", "요청이 만료되었거나 올바르지 않습니다. 다시 시도해 주세요.");
  }

  const clientId = process.env.DISCORD_CLIENT_ID || "";
  const clientSecret = process.env.DISCORD_CLIENT_SECRET || "";
    if (!clientId || !clientSecret) {
    return html(500, "Discord 연결 확인 불가", "현재 Discord 연결을 처리할 수 없습니다. 운영진에게 알려 주세요.");
  }

  const siteUrl = (process.env.BORIMC_NETLIFY_SITE_URL || DEFAULT_SITE_URL).replace(/\/+$/, "");
  const redirectUri = process.env.DISCORD_REDIRECT_URI || `${siteUrl}/.netlify/functions/auth-discord-callback`;
  const body = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri
  });

  try {
    const tokenResponse = await fetch("https://discord.com/api/oauth2/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body
    });
    const tokenData = await tokenResponse.json();
    if (!tokenResponse.ok || !tokenData.access_token) {
      return html(400, "Discord 연결 실패", "Discord 인증을 완료하지 못했습니다.");
    }

    const userResponse = await fetch("https://discord.com/api/users/@me", {
      headers: { "Authorization": `Bearer ${tokenData.access_token}` }
    });
    const user = await userResponse.json();
    if (!userResponse.ok || !user.id) {
      return html(400, "Discord 연결 실패", "Discord 사용자 정보를 확인하지 못했습니다.");
    }

    const displayName = user.global_name || user.username || user.id;
    const sessionCookie = createSessionCookie({
      provider: "discord",
      providerUserId: user.id,
      displayName
    });
    if (!sessionCookie) {
      return html(500, "Discord 연결 확인 불가", "세션 설정이 완료되지 않았습니다. 운영진에게 알려 주세요.");
    }

    return html(200, "Discord 연결 완료", `Discord 계정 ${displayName} 연결이 확인되었습니다. 가입/인증 화면으로 이동합니다.`, [sessionCookie]);
  } catch {
    return html(500, "Discord 연결 실패", "Discord 연결 처리 중 오류가 발생했습니다.");
  }
};
