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
  return json(200, {
    siteUrl: process.env.BORIMC_NETLIFY_SITE_URL || "https://borisurvur.netlify.app",
    recaptchaSiteKey: process.env.RECAPTCHA_SITE_KEY || "",
    recaptchaVersion: process.env.RECAPTCHA_VERSION || "v2",
    registrationConfigured: Boolean(process.env.RECAPTCHA_SITE_KEY && process.env.RECAPTCHA_SECRET_KEY && process.env.BORIMC_REGISTRATION_SECRET),
    sessionConfigured: Boolean(process.env.BORIMC_SESSION_SECRET || process.env.BORIMC_REGISTRATION_SECRET || process.env.BORIMC_STATUS_SECRET),
    oauth: {
      discord: Boolean(process.env.DISCORD_CLIENT_ID && process.env.DISCORD_CLIENT_SECRET),
      google: Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET)
    },
    downloads: {
      launcher: Boolean(process.env.BORIMC_DOWNLOAD_LAUNCHER_URL),
      resourcepack: Boolean(process.env.BORIMC_DOWNLOAD_RESOURCEPACK_URL),
      pluginPack: Boolean(process.env.BORIMC_DOWNLOAD_PLUGIN_PACK_URL)
    }
  });
};
