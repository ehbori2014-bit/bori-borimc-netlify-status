const { clearSessionCookie } = require("./_shared/session");

exports.handler = async () => ({
  statusCode: 200,
  headers: {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Set-Cookie": clearSessionCookie()
  },
  body: JSON.stringify({
    ok: true,
    authenticated: false,
    message: "연결 세션을 해제했습니다."
  })
});
