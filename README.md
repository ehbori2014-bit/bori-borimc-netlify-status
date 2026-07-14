# BoriMC Netlify Main

`borisurvur.netlify.app`을 BoriMC 공식 메인 홈페이지로 쓰는 Netlify 프로젝트입니다.

`borimc.p-e.kr`은 메인 홈페이지가 아니라 Minecraft 서버 주소, API 서버, 백엔드 용도로 사용합니다. 브라우저는 `borimc.p-e.kr` 또는 `borimc.p-e.kr:10259`로 직접 `fetch`하지 않고 Netlify Function만 호출합니다.

## 포함 파일

```txt
borimc-netlify-status/
  index.html
  package.json
  netlify.toml
  README.md
  netlify/
    functions/
      mc-status.js
      server-status.js
      web-ping.js
      register.js
      register-request.js
      public-config.js
      auth-discord-start.js
      auth-discord-callback.js
      auth-google-start.js
      auth-google-callback.js
      auth-session.js
      auth-logout.js
      verification-status.js
      verification-minecraft-code.js
      verification-admin-request.js
      api-proxy.js
      download-file.js
      service-links.js
      _shared/session.js
```

## 현재 기능

- BoriMC 공식 메인 홈페이지 UI
- 밝음/어둠 테마
- 서버 주소 복사
- 기존 메인 홈페이지 흐름 이전: 운영 허브, 가입/인증, 서버 규칙, 게임 가이드, 커뮤니티 게시판 안내
- 실시간 서버 상태 카드
- 상단 미니 상태 바
- 학교망 체크 카드
- 가입/인증 폼
- 커뮤니티 게시판 허브: 공지, 자유/질문, 버그 제보, 건의, 거래/모집, 기록보관
- Google reCAPTCHA v2 체크박스
- Netlify Function 기반 가입 중계
- Discord/Google OAuth 연결 후 HttpOnly 세션 확인
- Minecraft 인증 코드/운영진 인증 요청 Function 연결
- Netlify Function 기반 다운로드 allowlist 중계
- Secret/Webhook/Token 브라우저 노출 방지

## 가입 흐름

```txt
사용자 브라우저
-> reCAPTCHA 체크
-> /.netlify/functions/register
-> Google reCAPTCHA 서버 검증
-> BoriMC API /registrations
-> DB 저장/자동 승인/정지/밴/보안 이벤트 기록
-> 결과 반환
```

브라우저는 기본 입력 검사만 합니다. 최종 자동 승인, 가입정지, 밴, 경고 판정은 서버 DB 기준으로 처리합니다. 비밀번호는 API 서버에서 해시로만 저장하고 원문은 저장하지 않습니다.

## 운영 Function 경로

- `/.netlify/functions/server-status`: Minecraft 서버 상태와 BoriMC 웹/API 응답 확인
- `/.netlify/functions/register`: 가입 신청, reCAPTCHA 검증, BoriMC API 중계
- `/.netlify/functions/auth-session`: Discord/Google 연결 세션 확인
- `/.netlify/functions/auth-logout`: 연결 세션 해제
- `/.netlify/functions/verification-status`: 가입/인증 상태 확인
- `/.netlify/functions/verification-minecraft-code`: Minecraft `/인증 <코드>`용 코드 발급 중계
- `/.netlify/functions/verification-admin-request`: 운영진 인증 요청 중계

## Netlify 환경 변수

Netlify에서 다음 위치로 들어갑니다.

```txt
Site settings -> Environment variables
```

설정할 값:

```env
BORIMC_NETLIFY_SITE_URL=https://borisurvur.netlify.app
BORIMC_API_URL=https://borimc.p-e.kr
BORIMC_MC_HOST=borimc.p-e.kr
BORIMC_MC_PORT=10259
BORIMC_STATUS_SECRET=여기에_긴_상태조회_시크릿
BORIMC_REGISTRATION_SECRET=여기에_긴_가입중계_시크릿
BORIMC_ADMIN_SECRET=여기에_긴_관리자_시크릿
BORIMC_IP_HASH_SECRET=여기에_긴_IP해시_시크릿
BORIMC_SESSION_SECRET=여기에_긴_세션서명_시크릿
BORIMC_DISCORD_INVITE_URL=https://discord.gg/qsdYqukFnN
BORIMC_COMMUNITY_URL=https://discord.gg/qsdYqukFnN

BORIMC_DOWNLOAD_LAUNCHER_URL=https://예시가_아닌_실제_런처_URL
BORIMC_DOWNLOAD_RESOURCEPACK_URL=https://예시가_아닌_실제_리소스팩_URL
BORIMC_DOWNLOAD_PLUGIN_PACK_URL=https://예시가_아닌_실제_플러그인팩_URL

RECAPTCHA_SITE_KEY=여기에_사이트키
RECAPTCHA_SECRET_KEY=여기에_시크릿키
RECAPTCHA_VERSION=v2
RECAPTCHA_EXPECTED_HOSTNAME=borisurvur.netlify.app

DISCORD_CLIENT_ID=여기에_Discord_Client_ID
DISCORD_CLIENT_SECRET=여기에_Discord_Client_Secret
DISCORD_REDIRECT_URI=https://borisurvur.netlify.app/.netlify/functions/auth-discord-callback

GOOGLE_CLIENT_ID=여기에_Google_Client_ID
GOOGLE_CLIENT_SECRET=여기에_Google_Client_Secret
GOOGLE_REDIRECT_URI=https://borisurvur.netlify.app/.netlify/functions/auth-google-callback
```

실제 Secret 값은 GitHub, README, `index.html`, 공개 JS에 넣으면 안 됩니다. 반드시 Netlify 환경 변수 또는 BoriMC API 서버 환경 변수에만 넣습니다.

버그 제보는 독립 웹 폼이 아니라 커뮤니티의 버그 제보 게시판에서 진행합니다. 디스코드 초대 링크는 `https://discord.gg/qsdYqukFnN`입니다.

## reCAPTCHA 설정

1. Google reCAPTCHA 콘솔에서 v2 체크박스 사이트를 만듭니다.
2. 허용 도메인에 `borisurvur.netlify.app`을 추가합니다.
3. 로컬 테스트가 필요하면 `localhost`도 추가합니다.
4. Site Key는 `RECAPTCHA_SITE_KEY`에 넣습니다.
5. Secret Key는 `RECAPTCHA_SECRET_KEY`에 넣습니다.
6. 배포 후 가입 폼에 체크박스가 보이는지 확인합니다.
7. 가입 신청 시 `register-request.js`가 Google 검증 API로 token을 검증합니다.

## BoriMC API 환경 변수

API 서버에도 같은 가입 Secret을 설정해야 합니다.

```env
BORIMC_REGISTRATION_SECRET=Netlify와_같은_가입중계_시크릿
BORIMC_IP_HASH_SECRET=긴_IP해시_시크릿
```

API DB에는 다음 테이블이 추가됩니다.

- `registration_attempts`
- `registration_bans`
- `linked_accounts`
- `registration_security_events`
- `admin_accounts`

## 보안 정책

- 비밀번호는 가입 폼에서 입력받지만 원문을 저장하지 않고 API 서버에서 PBKDF2 해시로만 보관합니다.
- IP 주소 원문은 저장하지 않고 해시만 저장합니다.
- 쿠키/로컬스토리지 토큰은 보조 수단입니다.
- 쿠키 삭제만으로 정지/밴이 풀리지 않게 서버 DB 기록을 사용합니다.
- reCAPTCHA 실패, honeypot 입력, 반복 시도는 보안 이벤트로 남깁니다.
- Discord Webhook URL은 공개 HTML에 넣지 않습니다.
- Bot Token, Google Client Secret, 관리자 키는 절대 프론트에 넣지 않습니다.

## 관리자 API

관리자 API는 반드시 `BORIMC_ADMIN_SESSION_SECRET` 또는 `BORIMC_ADMIN_SECRET` 값으로 호출합니다.

- `POST /api/admin/registration-bans`: Discord ID, Minecraft UUID/닉네임, Google subject/email 기준 가입 밴 등록
- `GET /api/admin/registration-bans`: 가입 밴 목록 확인
- `POST /api/admin/registration/{ban_id}/unban`: 가입 밴 해제
- `POST /api/admin/admins`: Discord/Google/Minecraft 기준 관리자 계정 등록
- `GET /api/admin/registrations`: 가입 신청/자동 승인 기록 확인

## 학교 인터넷에서 안 될 때

다음 경우에는 Netlify 메인도 접속 또는 상태 조회가 안 될 수 있습니다.

- 학교가 Netlify 자체를 차단한 경우
- 학교 패드 MDM이 미분류 사이트를 막는 경우
- 마크 서버 포트 `10259`가 외부에서 닫힌 경우
- BoriMC API 서버가 꺼진 경우
- Netlify Function에서 BoriMC 서버로 접근할 수 없는 경우

## 배포

GitHub 저장소 루트에 이 폴더의 내용물을 올리고 Netlify에서 Import from GitHub로 연결합니다.

Build command:

```txt
npm install && npm run build
```

Publish directory:

```txt
.
```

## 로컬 확인

```powershell
npm install
npx netlify dev
```

로컬에서 reCAPTCHA를 테스트하려면 reCAPTCHA 콘솔에 `localhost`를 허용 도메인으로 추가해야 합니다.
