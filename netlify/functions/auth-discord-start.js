const crypto = require("crypto");

const DEFAULT_SITE_URL = "https://borisurvur.netlify.app";

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

exports.handler = async () => {
  const clientId = process.env.DISCORD_CLIENT_ID || "";
  if (!clientId) {
    return json(500, {
      ok: false,
      status: "DISCORD_OAUTH_NOT_CONFIGURED",
      message: "Discord OAuth 설정이 아직 완료되지 않았습니다."
    });
  }

  const siteUrl = (process.env.BORIMC_NETLIFY_SITE_URL || DEFAULT_SITE_URL).replace(/\/+$/, "");
  const redirectUri = process.env.DISCORD_REDIRECT_URI || `${siteUrl}/.netlify/functions/auth-discord-callback`;
  const state = crypto.randomBytes(24).toString("hex");
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "identify",
    state
  });

  return {
    statusCode: 302,
    headers: {
      "Cache-Control": "no-store",
      "Location": `https://discord.com/api/oauth2/authorize?${params.toString()}`,
      "Set-Cookie": `borimc_discord_oauth_state=${state}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=600`
    },
    body: ""
  };
};
