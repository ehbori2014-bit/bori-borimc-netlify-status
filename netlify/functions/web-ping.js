const DEFAULT_API_URL = "https://borimc.p-e.kr";
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

function cleanError(error) {
  const message = String(error && error.message ? error.message : "request failed");
  if (message.toLowerCase().includes("abort") || message.toLowerCase().includes("timeout")) {
    return "timeout";
  }
  if (message.toLowerCase().includes("fetch failed")) {
    return "fetch failed";
  }
  return "request failed";
}

async function timedFetch(target) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const startedAt = Date.now();

  try {
    const response = await fetch(target, {
      method: "GET",
      signal: controller.signal,
      headers: {
        "User-Agent": "BoriMC-Netlify-Status/1.0"
      }
    });

    return {
      ok: response.ok,
      target,
      responseMs: Date.now() - startedAt,
      status: response.status,
      checkedAt: new Date().toISOString()
    };
  } finally {
    clearTimeout(timeout);
  }
}

exports.handler = async () => {
  const baseUrl = (process.env.BORIMC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
  const targets = [
    `${baseUrl}/ping`,
    `${baseUrl}/`
  ];
  let lastError = "request failed";

  for (const target of targets) {
    try {
      const result = await timedFetch(target);
      if (result.ok) {
        return json(200, result);
      }
      lastError = `http ${result.status}`;
    } catch (error) {
      lastError = cleanError(error);
    }
  }

  return json(200, {
    ok: false,
    target: targets[0],
    error: lastError,
    checkedAt: new Date().toISOString()
  });
};
