const minecraft = require("minecraft-server-util");

const HOST = process.env.BORIMC_MC_HOST || "borimc.p-e.kr";
const PORT = Number(process.env.BORIMC_MC_PORT || "10259");
const TIMEOUT_MS = Number(process.env.BORIMC_MC_TIMEOUT_MS || "5000");
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

function cleanError(error) {
  const raw = String(error && (error.code || error.message) ? (error.code || error.message) : "connection failed");
  const message = raw.toLowerCase();
  if (message.includes("timeout") || message.includes("timed out")) return "connection timeout";
  if (message.includes("refused")) return "connection refused";
  if (message.includes("notfound") || message.includes("enotfound")) return "host not found";
  return "server did not respond";
}

function statusFromError(error) {
  const message = cleanError(error);
  if (message === "host not found") return "UNKNOWN";
  return "OFFLINE";
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

async function pingWebApi() {
  const baseUrl = (process.env.BORIMC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const startedAt = Date.now();

  try {
    const response = await fetch(`${baseUrl}/ping`, {
      method: "GET",
      signal: controller.signal,
      headers: {
        "Accept": "application/json",
        "User-Agent": "BoriMC-Netlify-Server-Status/1.0"
      }
    });
    return {
      ok: response.ok,
      responseMs: Date.now() - startedAt,
      statusCode: response.status
    };
  } catch {
    return {
      ok: false,
      responseMs: Date.now() - startedAt,
      statusCode: 0
    };
  } finally {
    clearTimeout(timeout);
  }
}

exports.handler = async () => {
  const checkedAt = new Date().toISOString();
  const status = minecraft.status || (minecraft.default && minecraft.default.status);
  const web = await pingWebApi();

  if (typeof status !== "function") {
    return json(200, {
      ok: false,
      online: false,
      status: "UNKNOWN",
      host: HOST,
      port: PORT,
      players: { online: 0, max: 0 },
      ping: null,
      version: "",
      motd: "",
      web,
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
      ok: true,
      online: true,
      status: "ONLINE",
      host: HOST,
      port: PORT,
      ping,
      players: {
        online: result.players && typeof result.players.online === "number" ? result.players.online : 0,
        max: result.players && typeof result.players.max === "number" ? result.players.max : 0
      },
      version: versionText(result.version),
      motd: motdText(result.motd),
      web,
      checkedAt
    });
  } catch (error) {
    return json(200, {
      ok: true,
      online: false,
      status: statusFromError(error),
      host: HOST,
      port: PORT,
      players: { online: 0, max: 0 },
      ping: null,
      version: "",
      motd: "",
      web,
      error: cleanError(error),
      checkedAt
    });
  }
};
