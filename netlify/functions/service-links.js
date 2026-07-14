const DEFAULT_MAIN_SITE_URL = "https://borisurvur.netlify.app";
const DEFAULT_DISCORD_INVITE_URL = "https://discord.gg/qsdYqukFnN";

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

function cleanUrl(value, fallback = "") {
  const url = String(value || "").trim();
  if (!url) return fallback;
  if (!/^https?:\/\//i.test(url)) return fallback;
  return url;
}

exports.handler = async () => {
  const mainSiteUrl = cleanUrl(process.env.BORIMC_MAIN_SITE_URL, DEFAULT_MAIN_SITE_URL);

  return json(200, {
    checkedAt: new Date().toISOString(),
    links: {
      mainSite: {
        label: "BoriMC 공식 메인 홈페이지",
        url: mainSiteUrl,
        note: "Netlify 기준 공식 메인입니다."
      },
      backend: {
        label: "BoriMC 서버/API",
        url: cleanUrl(process.env.BORIMC_BACKEND_PUBLIC_URL, "https://borimc.p-e.kr"),
        note: "Minecraft 서버 주소와 API 백엔드 용도입니다."
      },
      discord: {
        label: "디스코드 참여",
        url: cleanUrl(process.env.BORIMC_DISCORD_INVITE_URL, DEFAULT_DISCORD_INVITE_URL),
        note: "공지, 문의, 재판/기록 확인은 디스코드에서 진행합니다."
      },
      rules: {
        label: "서버 규칙",
        url: cleanUrl(process.env.BORIMC_RULES_URL),
        note: "평화 야생 PvE 운영 규칙을 확인합니다."
      },
      community: {
        label: "커뮤니티",
        url: cleanUrl(process.env.BORIMC_COMMUNITY_URL),
        note: "공지, 자유/질문, 버그 제보, 건의, 거래, 기록보관 게시판은 디스코드에서 운영합니다."
      },
      apiProxy: {
        label: "API 프록시",
        url: "/.netlify/functions/api-proxy?path=/ping",
        configured: Boolean(process.env.BORIMC_STATUS_SECRET),
        note: "Secret은 브라우저에 노출하지 않고 Netlify Function에서만 사용합니다."
      }
    },
    integrations: {
      discordSession: "/.netlify/functions/auth-discord-start",
      googleSession: "/.netlify/functions/auth-google-start",
      verificationStatus: "/.netlify/functions/verification-status"
    }
  });
};
