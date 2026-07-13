const minecraft = require("minecraft-server-util");

const HOST = "borimc.p-e.kr";
const PORT = 10259;
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
  const message = String(error && (error.code || error.message) ? (error.code || error.message) : "connection failed");
  if (message.toLowerCase().includes("timeout") || message.toLowerCase().includes("timed out")) {
    return "connection timeout";
  }
  if (message.toLowerCase().includes("refused")) {
    return "connection refused";
  }
  if (message.toLowerCase().includes("notfound") || message.toLowerCase().includes("enotfound")) {
    return "host not found";
  }
  return "server did not respond";
}

function motdText(motd) {
  if (!motd) return "";
  if (typeof motd === "string") return motd;
  if (typeof motd.clean === "string") return motd.clean;
  if (Array.isArray(motd.clean)) return motd.clean.join(" ");
  if (typeof motd.raw === "string") return motd.raw;
  return "";
}

function versionText(version) {
  if (!version) return "";
  if (typeof version === "string") return version;
  return version.name || version.version || "";
}

exports.handler = async () => {
  const checkedAt = new Date().toISOString();
  const status = minecraft.status || (minecraft.default && minecraft.default.status);

  if (typeof status !== "function") {
    return json(200, {
      online: false,
      host: HOST,
      port: PORT,
      error: "minecraft status library unavailable",
      checkedAt
    });
  }

  const startedAt = Date.now();

  try {
    const result = await status(HOST, PORT, {
      timeout: TIMEOUT_MS,
      enableSRV: false
    });

    const ping = typeof result.roundTripLatency === "number"
      ? result.roundTripLatency
      : Date.now() - startedAt;

    return json(200, {
      online: true,
      host: HOST,
      port: PORT,
      ping,
      players: {
        online: result.players && typeof result.players.online === "number" ? result.players.online : 0,
        max: result.players && typeof result.players.max === "number" ? result.players.max : 0
      },
      version: versionText(result.version),
      motd: motdText(result.motd),
      checkedAt
    });
  } catch (error) {
    return json(200, {
      online: false,
      host: HOST,
      port: PORT,
      error: cleanError(error),
      checkedAt
    });
  }
};
