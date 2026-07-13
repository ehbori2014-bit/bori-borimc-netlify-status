# BoriMC Netlify Status

BoriMC 마인크래프트 서버 상태를 Netlify 기본 도메인에서 확인하는 작은 상태 페이지입니다.

학교 인터넷에서 `borimc.p-e.kr`이 차단될 수 있으므로, 브라우저는 BoriMC 도메인이나 마크 서버 포트로 직접 요청하지 않습니다. 브라우저는 Netlify 사이트의 Function만 호출하고, Netlify Function이 대신 BoriMC 웹/API/마크 서버 상태를 조회합니다.

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
      web-ping.js
      api-proxy.js
```

## 기능

- 마인크래프트 서버 온라인/오프라인 표시
- 마크 서버 핑 표시
- 접속자 수 현재/최대 표시
- 서버 버전 표시
- MOTD 표시
- BoriMC 웹서버 HTTPS 응답속도 표시
- 10초 자동 갱신
- 수동 새로고침
- 서버 주소 `borimc.p-e.kr:10259` 복사

## Netlify 배포 방법

1. GitHub에 새 저장소를 만듭니다.
2. 이 `borimc-netlify-status` 폴더 안의 파일들을 저장소 루트에 업로드합니다.
3. Netlify에서 `Add new site`를 누릅니다.
4. `Import from GitHub`를 선택합니다.
5. 방금 만든 저장소를 선택합니다.
6. Build command가 아래처럼 되어 있는지 확인합니다.

```txt
npm install && npm run build
```

7. Publish directory가 아래처럼 되어 있는지 확인합니다.

```txt
.
```

8. Deploy를 누릅니다.

처음 테스트는 Netlify가 주는 기본 `netlify.app` 주소로 하는 것을 권장합니다. 커스텀 도메인 연결은 나중에 선택사항으로 진행하면 됩니다.

## 환경 변수

Netlify에서 다음 위치로 들어갑니다.

```txt
Site settings -> Environment variables
```

설정할 값:

```txt
BORIMC_API_URL=https://borimc.p-e.kr
BORIMC_STATUS_SECRET=아주긴랜덤키
BORIMC_ADMIN_SECRET=아주긴랜덤키
```

`BORIMC_STATUS_SECRET`과 `BORIMC_ADMIN_SECRET`은 HTML, 공개 JS, README, GitHub 저장소에 실제 값을 넣으면 안 됩니다. 반드시 Netlify 환경 변수에만 넣어야 합니다.

현재 상태 페이지는 `mc-status.js`와 `web-ping.js`로 동작합니다. `api-proxy.js`는 나중에 BoriMC API와 안전하게 연결하기 위한 준비 파일입니다.

## 마크 서버 상태가 안 뜰 때

아래를 확인하세요.

- `borimc.p-e.kr:10259`가 외부 인터넷에서 접속 가능한지
- 공유기 포트포워딩에서 `10259`가 Paper 서버 컴퓨터로 연결되어 있는지
- `server.properties`에 `enable-status=true`가 켜져 있는지
- Paper 서버가 실제로 실행 중인지
- Windows 방화벽 또는 공유기 방화벽에서 `10259`가 허용되어 있는지
- Netlify Function 로그에 timeout이 뜨는지

마크 서버가 꺼져 있거나 포트가 닫혀 있으면 페이지는 정상이어도 `오프라인`으로 표시됩니다.

## 웹 응답속도가 안 뜰 때

`web-ping.js`는 먼저 아래 주소를 확인합니다.

```txt
https://borimc.p-e.kr/ping
```

이 주소가 실패하면 아래 주소를 한 번 더 확인합니다.

```txt
https://borimc.p-e.kr/
```

둘 다 실패하면 웹 응답속도는 실패로 표시됩니다.

## 학교 인터넷에서 접속이 안 될 때

이 사이트는 학교 인터넷에서 BoriMC 본 도메인이 막히는 상황을 줄이기 위해 Netlify 기본 도메인을 사용합니다.

그래도 다음 경우에는 접속이 안 될 수 있습니다.

- 학교가 Netlify 자체를 차단한 경우
- 학교 패드 MDM이 미분류 사이트를 막는 경우
- Netlify Function에서 BoriMC 서버로 접근할 수 없는 경우
- 마크 서버 포트 `10259`가 외부에서 닫힌 경우
- 학교 네트워크가 게임 서버 관련 트래픽을 넓게 차단한 경우

학교 테스트용으로는 커스텀 도메인보다 Netlify 기본 `netlify.app` 주소를 유지하는 것이 좋습니다.

## Secret 주의

Secret Key는 절대 `index.html`이나 브라우저 JS에 넣으면 안 됩니다.

안 되는 예:

```txt
index.html 안에 BORIMC_ADMIN_SECRET 작성
브라우저 JS에서 HMAC 서명 생성
GitHub README에 실제 secret 작성
```

맞는 방식:

```txt
Netlify Environment variables에 secret 저장
Netlify Function에서 process.env로 읽기
브라우저에는 결과 JSON만 반환
```

`api-proxy.js`에는 HMAC-SHA256 요청 서명 함수가 준비되어 있습니다.

사용 헤더:

```txt
X-Bori-Timestamp
X-Bori-Nonce
X-Bori-Signature
X-Bori-Key-Type
```

서명 문자열:

```txt
METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + NONCE + "\n" + BODY_SHA256
```

이 서명은 브라우저가 만들지 않고 Netlify Function에서만 만듭니다.

## 로컬 확인

HTML 모양만 보려면 `index.html`을 브라우저로 열 수 있습니다. Netlify Functions까지 로컬에서 확인하려면 Netlify CLI를 사용합니다.

```powershell
npm install
npx netlify dev
```

그 다음 브라우저에서 Netlify Dev 주소를 열면 됩니다.
