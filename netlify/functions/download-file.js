const DOWNLOADS = {
  launcher: {
    env: "BORIMC_DOWNLOAD_LAUNCHER_URL",
    label: "BoriLauncher"
  },
  resourcepack: {
    env: "BORIMC_DOWNLOAD_RESOURCEPACK_URL",
    label: "서버 리소스팩"
  },
  pluginPack: {
    env: "BORIMC_DOWNLOAD_PLUGIN_PACK_URL",
    label: "플러그인 패키지"
  }
};

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

function cleanUrl(value) {
  const url = String(value || "").trim();
  if (!/^https:\/\//i.test(url)) return "";
  return url;
}

exports.handler = async (event) => {
  const key = String((event.queryStringParameters || {}).key || "").trim();
  const entry = DOWNLOADS[key];
  if (!entry) {
    return json(404, {
      ok: false,
      status: "DOWNLOAD_NOT_FOUND",
      message: "알 수 없는 다운로드 항목입니다."
    });
  }

  const url = cleanUrl(process.env[entry.env]);
  if (!url) {
    return json(501, {
      ok: false,
      status: "DOWNLOAD_NOT_CONFIGURED",
      message: `${entry.label} 다운로드 URL이 아직 설정되지 않았습니다.`
    });
  }

  return {
    statusCode: 302,
    headers: {
      "Cache-Control": "no-store",
      "Location": url
    },
    body: ""
  };
};
