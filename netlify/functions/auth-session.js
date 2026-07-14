const { readSession } = require("./_shared/session");

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
  const result = readSession(event.headers || {});
  if (!result.authenticated) {
    return json(200, {
      ok: true,
      authenticated: false,
      status: result.status
    });
  }

  return json(200, {
    ok: true,
    authenticated: true,
    provider: result.session.provider,
    providerUserId: result.session.providerUserId,
    displayName: result.session.displayName,
    email: result.session.email || "",
    linkedAt: result.session.linkedAt
  });
};
