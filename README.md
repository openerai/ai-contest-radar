# AI 공모전 레이더

**🔗 https://openerai.github.io/ai-contest-radar/** — 매주 월요일 아침 자동 갱신

로컬에서 `index.html`을 더블클릭해도 똑같이 열립니다(빌드·서버 불필요). 상단 네비게이션으로 국내↔해외를 오갑니다.

| 파일 | 내용 |
|---|---|
| `index.html` | 🇰🇷 **국내** AI 공모전 |
| `global.html` | 🌍 **해외** 플랫폼 챌린지 · AI 영화제 |
| `data/kr.js`, `data/global.js` | 자동 생성 데이터 (직접 수정 금지) |
| `data/manual.*.json` | 사람이 관리하는 보정값 — **여기를 고치세요** |
| `scripts/update_contests.py` | 수집기 |
| `.github/workflows/update.yml` | 주 1회 자동 갱신 |

---

# 🔄 자동 갱신

## D-day와 목록은 갱신 주기가 다릅니다

**D-day는 항상 정확합니다.** 데이터에는 마감일(`2026-08-31`)만 저장되고, D-day는 페이지를 열 때마다 `new Date()`로 그 자리에서 계산됩니다. 내일 열면 D-27이 D-26이 되고, 21일·7일 경계를 지나면 색이 초록→주황→빨강으로 바뀌며, 마감된 항목은 목록에서 빠집니다. **여기엔 아무 작업도 필요 없습니다.**

**갱신이 필요한 건 목록 자체입니다.** 새로 열린 공모전은 수집을 다시 해야 들어옵니다. 그래서 GitHub Actions가 매주 월요일 06:00(KST)에 재수집합니다.

페이지 상단 배너가 이 격차를 보여줍니다 — 10일 지나면 주황, 21일 지나면 빨강으로 경고합니다.

## 수동 실행

```bash
python scripts/update_contests.py
```

GitHub에서 즉시 돌리려면 Actions 탭 → "공모전 데이터 주간 갱신" → Run workflow.

## 수집 소스

| 소스 | 담당 | CI(GitHub 러너)에서 |
|---|---|---|
| [링커리어](https://linkareer.com/list/contest) | 국내 **주 소스** | ✅ 정상 |
| [인공지능팩토리](https://aifactory.space/ko/competition) | 국내 알고리즘 대회 | ✅ 정상 |
| [위비티](https://www.wevity.com/) | 국내 보조 | ❌ **Cloudflare 403** |
| [aifilmcontests.com](https://aifilmcontests.com/) | 해외 영화제 (sitemap→JSON-LD) | ✅ 정상 |
| [Devpost](https://devpost.com/hackathons) | 해외 AI 해커톤 (공개 JSON API) | ✅ 정상 |
| [melies.co](https://melies.co/ai-film-festivals) | 해외 AI 영화제 디렉터리 (JSON-LD) | ✅ 정상 |
| AI 플랫폼 챌린지 감시 | AI 서비스 20곳 **후보만 수집** → 사람 확인 | ✅ 정상 |

⚠ **위비티는 Cloudflare가 데이터센터 IP를 차단해 GitHub Actions에서 실패합니다.** 지역 차단이 아니라 봇 차단이라 프록시 없이는 우회가 어렵습니다. 로컬(집 IP)에서 실행하면 정상 동작하고 5~10건이 더 붙으니, 가끔 로컬에서 한 번 돌려 커밋하면 좋습니다. 실패해도 경고만 남기고 나머지 소스로 진행합니다.

Higgsfield는 JSON-LD가 실제 페이지와 어긋나(2026-08-04 기준 영화제 일정이 7/16~7/30으로 실제와 다름) 자동 수집에서 뺐습니다. 값은 `data/manual.global.json`에 있습니다.

### 해외 목록은 '만드는 대회'만 싣습니다

이 사이트가 다루는 건 **AI로 이미지·영상을 만들어 내는 공모전**입니다. AI를 쓰긴 하지만 결과물이 소프트웨어인 일반 개발 해커톤은 싣지 않습니다. 목록의 성격이 흐려지고, 영상·이미지 공모를 찾는 사람이 앱 해커톤 더미를 헤쳐야 하기 때문입니다.

두 겹으로 거릅니다.

1. **소스에서** — Devpost는 제목에 영상·이미지 단서(`film` `cinema` `video` `animation` `photo` `illustration` …)가 있는 것만 통과시킵니다. 테마 태그는 보지 않습니다. Devpost의 `Design`·`3D`는 소프트웨어 분류라서 창작 신호가 아니고, 실제로 그것 때문에 `Prometheus August AI Challenge`(테마 Design)와 `3D Websites Hackathon`이 통과했었습니다.
2. **파이프라인에서** — 새 소스를 붙였을 때 조용히 섞여 들어오는 걸 막는 그물입니다. 단 영화제 전용 소스(aifilmcontests · melies · 수동 데이터)는 이름 검사를 건너뜁니다. `Chroma Awards`·`FESTIAV`처럼 이름만으로는 창작 대회인 줄 알 수 없는 영화제가 있어서, 이름으로 거르면 진짜가 빠집니다.

이 필터로 Devpost 수집이 14건 → 1건이 됐습니다. 남은 하나는 `Agentic Cinema: The Blockbuster Hackathon`($75,000)으로, 형식은 해커톤이지만 결과물이 영상이라 **AI 필름**으로 분류합니다.

Devpost는 `search=ai` 로 열려 있는 대회를 받아오되, **상금 $1,000 이상 · 초대 전용 아님**만 남깁니다. 상금이 달러가 아닌 대회(₹ 등)는 환산하지 않고 건너뜁니다.

melies.co는 FilmFreeway가 봇을 막아 공식 페이지를 못 읽는 아시아권 AI 영화제(부산·제주·K-Culture 등)를 채워 줍니다. 다만 **디렉터리의 날짜는 마감일로 쓰지 않습니다.** 등재된 날짜가 출품 마감인지 행사 개최일인지 구분되지 않기 때문입니다 — 실제로 Reply AI Film Festival은 등재값이 9/6(행사일)인데 출품은 6/30에 이미 닫혀 있었습니다. 늦은 날짜를 마감일로 띄우면 이미 닫힌 공모에 사람을 보내게 되므로, 기간은 비고에만 적고 `⚠ 마감 확인필요` 로 표시합니다.

## AI 플랫폼 챌린지 감시 (watchtower)

Artlist Seedance 2.5 챌린지, Higgsfield Global Film Festival 같은 **업체 자체 챌린지는 공고 주기가 없습니다.** 어느 날 랜딩페이지 하나가 올라오고 3주 뒤 조용히 끝나며, 공모전 포털에도 잘 실리지 않습니다. 그래서 "목록을 긁는" 대신 **"새 URL이 생겼는지 감시"**합니다.

```bash
python scripts/watch_challenges.py            # 새 챌린지 후보 탐색
python scripts/watch_challenges.py --seed     # 첫 실행: 지금 것들을 '봤음'으로만 기록
```

작동 방식

1. `scripts/watchlist.py` 의 `PLATFORMS` 에 적힌 업체의 사이트맵·허브 페이지를 훑어 `challenge`·`contest`·`award` 류 URL을 모읍니다.
2. `data/watch.state.json` 에 없는 **새 URL만** 상세 페이지를 열어 제목·상금·마감일을 뽑습니다.
3. 결과를 `data/review.queue.json` 에 쌓습니다. **목록(data/*.js)에는 자동으로 올리지 않습니다.**
4. 사람이 URL을 열어 확인한 뒤, 같은 항목의 `draft` 를 `data/manual.global.json` 의 `extra` 로 옮기고 `update_contests.py` 를 돌립니다.

자동 등록을 하지 않는 이유는 랜딩페이지의 마감일이 "by Aug 31" 같은 산문이라 연도·시간대가 빠져 있고 카운트다운이 JS로만 그려지는 일이 흔하기 때문입니다. 신뢰도는 세 단계로 표시합니다.

| 신뢰도 | 뜻 |
|---|---|
| `high` | 마감 단서(`deadline`/`closes`) 뒤에 **연도까지** 적힌 날짜 · 또는 JSON-LD `Event.endDate` |
| `medium` | 마감 단서는 있지만 연도가 없어 추측 (`by August 26th`) |
| `low` / `none` | 단서 없음 — 사람이 직접 봐야 함 |

`high` 가 아닌 날짜는 `draft.deadline` 에 넣지 않고 `deadlineGuess` 로만 남깁니다. 틀린 D-day를 띄우는 것보다 비워 두는 편이 낫다고 봤습니다.

감시 중인 곳은 **자동 20곳**(Higgsfield · Artlist · PixVerse · PixAI · Artbreeder · CapCut/Dreamina · Runway · Krea · Luma · Vidu · LTX · Moonvalley · Recraft · Suno · Udio · Stability · Synthesia · ElevenLabs · OpenAI · Civitai) + **수동 확인 13곳**입니다.

보조 채널로 **구글 뉴스 RSS**도 봅니다. Kling·PixVerse처럼 로그인 뒤 JS로만 그려져 사이트맵으로 볼 수 없는 업체의 챌린지는 기사로만 잡히기 때문입니다(실제로 PixVerse `PixLight`, Runway 광고 공모가 이 채널로 걸렸습니다). 자동 감시가 불가능한 업체 목록은 `watchlist.MANUAL_CHECK` 에 있고 실행할 때마다 체크리스트로 출력됩니다.

GitHub Actions의 **"AI 플랫폼 챌린지 감시"** 워크플로가 주 2회(수·토 06:00 KST) 돌면서 큐를 갱신하고, 새 후보가 있으면 이슈를 열어 알립니다.

### 감시 대상 늘리기

`scripts/watchlist.py` 의 `PLATFORMS` 에 한 줄 추가하면 됩니다.

```python
{
    "brand": "새업체", "org": "새업체", "orgTier": "mid",
    "sitemaps": [("https://example.com/sitemap.xml", r"blog|news")],  # 인덱스면 하위 필터
    "hubs": [("https://example.com/contests", r"/contests/[\w\-]+$")],
    "only": r"/blog/",        # (선택) 이 경로만 후보로
    "noisy": True,            # (선택) 커뮤니티 글이 섞이는 소스 — 상금·마감이 잡힌 것만 큐에 올림
}
```

어느 사이트가 감시 가능한지는 진단 도구로 먼저 재 봅니다.

```bash
python scripts/probe_watch_targets.py                    # 기본 후보군 50여 곳
python scripts/probe_watch_targets.py krea.ai pika.art   # 특정 도메인만
```

사이트맵과 흔한 허브 경로(`/contests`, `/challenges`, `/blog` …)를 훑어 **쓸 수 있음 / 자동 감시 불가**로 갈라 줍니다. AI 서비스 절반은 로그인 뒤 JS로만 그려져 서버 HTML에 목록이 아예 없어서, 넣기 전에 재 보지 않으면 매 실행마다 요청만 쓰고 0건을 돌려받습니다. 이 진단으로 PixVerse 블로그·PixAI 공식 콘테스트·Artbreeder·CapCut을 새로 찾았고, 반대로 Midjourney·Leonardo·NightCafe·Tensor.Art는 봇 차단이라 수동 목록으로 보냈습니다.

상금이 플랫폼 크레딧인 챌린지(PixAI·Kling 계열)는 달러 파서로는 0원으로 보이므로 `N Credits` 표기를 따로 읽어 `credit` 에 담습니다.

## 지난 공모전 검수 (verifier)

마감일이 있는 대회는 날짜가 지나면 자동으로 빠집니다. 문제는 **마감일을 못 넣은 항목**입니다. `deadline: null` 이면 만료 판정에 걸리지 않아서 작년에 끝난 대회가 몇 달씩 남습니다. 실제로 OpenArt Music Video Awards(2026-01 종료), PixVerse × UN AI for Good(2026-07 종료), Runway AI Film Festival(2026-07 개최 완료)이 그렇게 목록에 남아 있었습니다.

```bash
python scripts/verify_contests.py            # 검수 → 리포트만
python scripts/verify_contests.py --apply    # 확실히 끝난 건은 목록에서 내림
python scripts/verify_contests.py --scope kr # 국내 목록 (기본은 해외)
```

목록의 모든 항목에 대해 공식 페이지를 다시 열어 판정합니다.

| 판정 | 뜻 | 자동 조치 |
|---|---|---|
| `live` | 미래 일정이 확인됨 | — |
| `ended` | 페이지의 명시 날짜가 전부 과거 · 종료 문구 · 지난 `Event.endDate` | **목록에서 내림** |
| `suspect` | 페이지는 끝난 것 같은데 우리 데이터 마감일은 미래 | 사람 확인 |
| `drift` | 페이지가 말하는 마감일이 우리 값과 다름 | 사람 확인 |
| `blocked` | 403 등으로 못 읽음 (FilmFreeway가 봇을 막습니다) | 건드리지 않음 |
| `dead` | 404 · 410 | **목록에서 내림** |
| `unknown` | JS 셸이라 본문이 안 내려옴 | 우회 확인으로 |

내린 항목은 `data/manual.*.json` 의 `block` 에 id가 들어가고 근거와 함께 `data/retired.json` 에 남습니다. 되살리려면 `block` 에서 그 줄만 지우면 됩니다.

**오판을 막는 규칙들** — 전부 실제로 한 번씩 틀린 뒤에 넣은 것입니다.

- **403은 죽은 게 아니다.** 처음엔 `requests` 실패를 전부 404로 봐서 FilmFreeway 영화제 13건을 통째로 내릴 뻔했습니다. 이제 상태 코드를 구분해 404/410만 `dead`, 403·429·5xx는 `blocked` 로 둡니다.
- **연도 없는 날짜는 미래로 읽지 않는다.** `Nov 17 - Nov 30` 같은 표기를 "가장 가까운 미래"로 채우면 작년에 끝난 페이지가 살아 있는 것처럼 보입니다. 종료 판정에는 **연도가 적힌 날짜만** 셉니다.
- **다만 그 규칙만 쓰면 반대로 틀린다.** Higgsfield 영화제는 타임라인을 `Competition closes Sep 3` 처럼 연도 없이 적습니다. 그래서 "마감 단서 뒤에 붙은 날짜"는 연도가 없어도 살아 있다는 신호로 인정합니다 — 단 페이지의 명시 날짜가 전부 과거일 때는 인정하지 않습니다(그럴 땐 연도 추정이 틀린 경우가 많습니다).
- **JSON-LD 하나만으로 내리지 않는다.** Higgsfield는 끝난 회차의 `endDate` 를 그대로 둡니다. 페이지 본문에도 남은 일정이 없을 때만 종료로 봅니다.
- **우리 데이터가 미래를 가리키면 자동으로 안 내린다.** 페이지는 끝난 것 같은데 우리 마감일이 미래면 `suspect` 로만 올립니다.

### 우회 확인

Kling·SeaArt·Vidu처럼 로그인 뒤 JS로만 그려지는 곳은 공식 페이지를 읽을 수 없습니다. 이때 제3자 기록으로 우회합니다.

- [melies.co AI 영화제 디렉터리](https://melies.co/ai-film-festivals) — JSON-LD로 20여 건의 시작·종료일을 내보냅니다. 이름이 충분히 겹칠 때만(유사도 0.8 이상 + 고유 낱말 일치) 대조합니다.
- 구글 뉴스 RSS — 대회 이름으로 기사를 찾습니다. **'수상자 발표' 기사는 종료의 직접 근거**가 됩니다.

### 화면 표시

각 공모전 상세에 **최종 확인** 날짜가 붙습니다. 14일이 넘으면 "재확인 필요"로 표시됩니다. 확인이 오래된 것 자체가 신호이기 때문입니다 — 사이트가 조용히 내려가도 목록에는 남습니다.

또 마감일 없는 단발 대회가 45일 넘게 확인되지 않으면 수집 단계에서 자동으로 빠집니다.

## 안전장치

수집이 깨졌을 때 멀쩡한 데이터를 덮어쓰지 않도록:

0. **검수 우선** — 주간 갱신은 수집 전에 `verify_contests.py --apply` 를 먼저 돌려 끝난 대회를 걷어냅니다. 검수가 실패해도 수집은 계속합니다.
1. **건수 가드** — 최종 건수가 직전 실행의 50% 미만이면 파일을 쓰지 않고 워크플로가 실패합니다. (실제로 위비티 차단 때 이게 작동해 국내 데이터를 지켰습니다)
2. **소스 격리** — 한 소스가 죽어도 나머지는 수집합니다.
3. **사람 값 우선** — `manual.*.json`의 값은 자동 수집이 덮어쓰지 못합니다.
4. **캐시 버스터** — 갱신할 때마다 `<script src="data/kr.js?v=...">` 버전이 바뀝니다. 없으면 브라우저가 옛 데이터를 캐시에서 꺼내 씁니다.
5. **HTML 이스케이프** — 수집한 제목에 `<AI 창창 아이디어 챌린지>`처럼 꺾쇠가 들어오는 실제 사례가 있어, 모든 외부 문자열을 이스케이프한 뒤 렌더합니다.

## 데이터 보정하기

자동 수집 값이 틀렸거나 부족하면 `data/manual.kr.json` / `data/manual.global.json`을 고칩니다.

```jsonc
{
  "overrides": {
    // 키는 자동 id 또는 공모전 제목 (공백·기호 무시하고 비교)
    "[NHN] 게임 X AI 해커톤 (NAN2026)": {
      "prizeTotal": 80000000,
      "topPrize": "대상 5,000만원 · 최우수 2,000만 · 우수 1,000만"
    }
  },
  "extra": [ /* 자동으로 못 잡는 항목을 통째로 추가 */ ],
  "block": [ /* 목록에서 뺄 id 또는 제목 */ ]
}
```

고친 뒤 `python scripts/update_contests.py`를 실행하거나, 그냥 커밋하면 다음 주 갱신 때 반영됩니다.

> 실제 사례: 링커리어는 NHN 해커톤 시상규모를 "3억 5000만 원"으로 싣지만 보도자료 기준 상위 3팀 총상금은 8,000만원입니다. 이런 차이를 `overrides`로 잡습니다.

## 중복 처리

같은 공모전이 여러 소스에 뜨면 정보가 충실한 쪽(정확한 상금 > 구간 상금, 링커리어 > 위비티)을 남기고 빈 필드만 다른 쪽에서 채웁니다. 제목이 같거나, 한쪽이 다른 쪽을 포함하거나(`NHN 게임 X AI 해커톤` ↔ `[NHN] 게임 X AI 해커톤 (NAN2026)`), 마감일이 같으면서 유사도 0.9 이상이면 같은 대회로 봅니다.

## 알아둘 점

- GitHub은 **60일간 커밋이 없는 저장소의 예약 워크플로를 자동 중단**합니다. 매주 갱신 커밋이 생기므로 정상 동작 중에는 문제없지만, 오래 실패가 이어지면 확인이 필요합니다.
- 워크플로 실패는 GitHub이 이메일로 알려줍니다.

---

# 🇰🇷 국내 (`index.html`)

## 기능

- **D-day 자동 계산** — 마감일만 넣으면 브라우저가 오늘 기준으로 매번 다시 계산합니다. 날짜를 손볼 필요 없음
- **필터** — D-day(7/14/30일·미정) · 상금 구간 · 중요도 등급 · 분야 · 참가대상, 모두 중복 선택 가능
- **정렬** — 마감임박순 / 상금순 / 중요도순 / 이름순
- **3가지 뷰** — 카드 · 표 · 캘린더(월별 마감일 도트, 등급별 색)
- **★ 관심 등록 / ✓ 지원완료** — localStorage 저장
- **CSV 내보내기** — 현재 필터가 적용된 목록만 (Excel 한글 깨짐 방지 BOM 포함)
- 다크/라이트 테마, 모바일 대응

## 중요도 점수 (100점)

| 항목 | 배점 | 기준 |
|---|---|---|
| 상금 규모 | 40 | 5,000만↑ 40 · 2,000만↑ 32 · 1,000만↑ 24 · 500만↑ 16 · 그 외 10 · 미공개 8 |
| 주최 위상 | 25 | 정부·공공 25 · 대기업 22 · 지자체 16 · 기타 10 |
| 참가 범위 | 20 | 전국민 20 · 대학생 14 · 전문가한정 10 · 지역/소속한정 8 |
| 부가 혜택 | 15 | 채용연계 15 · 인턴/멘토링 10 · 전시/사업화 7 · 장관상 5 |

등급: **S** 80+ / **A** 65+ / **B** 50+ / **C** 그 미만. 카드의 `상세` 버튼에서 항목별 점수를 확인할 수 있습니다.

배점을 바꾸려면 `index.html`의 `scorePrize` · `scoreHost` · `scoreWho` · `scoreBonus` 함수만 수정하면 됩니다.

## 상금 표시

위비티는 총상금을 `3천만원~1천만원` 같은 **구간**으로만 줍니다. 구간을 정확한 금액인 척 보여주면 오해를 부르므로 `1,000만원~3,000만원`처럼 범위 그대로 표시하고, 상단 "확인된 총 상금" 합계에서는 제외합니다. 링커리어는 시상규모가 정확한 금액이라 그대로 씁니다.

## ⚠ 데이터 신뢰도

**⚠ 확인필요** 배지가 붙은 항목은 상금 또는 마감일이 공고에 명시되지 않았거나 출처 간 값이 엇갈립니다. 지원 전 반드시 공식 링크에서 확인하세요. 마감 시각(자정/18시 등)도 별도 확인이 필요합니다.

### 출처

- [링커리어](https://linkareer.com/list/contest) · [위비티](https://www.wevity.com/?c=find&s=1&gub=1&cidx=20) · [인공지능팩토리](https://aifactory.space/ko/competition) · [데이콘](https://dacon.io/competitions) · [전국민 AI 경진대회](https://aichallenge4all.or.kr/competitions)
- 교차 확인용 보도: [NHN NAN 2026 (ZDNet)](https://zdnet.co.kr/view/?no=20260731140707) · [SKT 모두의 promp.T](https://news.sktelecom.com/prompt) · [대전 AI 영상 공모전](https://aikive.com/event) · [스마트축산 AI 경진대회](https://smartlivestock.co.kr/) · [임베디드SW경진대회](https://www.eswcontest.or.kr/main.php)

---

# 🌍 해외 (`global.html`)

국내와 성격이 달라 데이터 모델과 점수 체계를 따로 만들었습니다.

## 국내 페이지와 다른 점

| | 국내 | 해외 |
|---|---|---|
| 상금 | 원화 현금 | **현금(USD)과 플랫폼 크레딧을 분리 표기** — 크레딧은 현금화 불가·12개월 소멸이 흔해 점수에서 낮게 반영 |
| 주기 | 대부분 단발 | **주간·매일·월간·상시 반복**이 많음 (PixVerse 주간 현금, SeaArt·Civitai 데일리 챌린지 등) |
| 참가비 | 거의 없음 | **무료 / 플랫폼 구독 필요 / 참가비 유료**로 갈림 → 별도 필터 |
| 응모 방식 | 폼·이메일 | 플랫폼 제출 / **SNS 해시태그** / FilmFreeway |
| 마감 | KST | **ET·PT·UTC 등 현지 시간대** → 카드·표에 시간대 병기 |
| 보상 | 상금 위주 | 현금 없이 **극장 상영·배급 계약·페스티벌 노출**만인 경우 다수 → 커리어 가치를 점수화 |

## 추가 기능

- **₩ 환산 토글** — 상단 `₩ 환산` 버튼으로 원화 병기 on/off (`const FX = 1380` 상수로 환율 조정)
- **상금 유형 필터** — 💵 현금 / 🎟 크레딧·구독 / 🎬 상영·커리어
- **참가 조건 필터** — 무료 출품 / 구독 필요 / 참가비 있음 / 전세계 누구나
- **반복·상시 필터** — 단발 대회를 걸러내고 상시 수익형만 보기
- 정렬에 **현금 상금순**과 **총 상금가치순**(현금+크레딧) 분리

## 중요도 점수 (100점)

| 항목 | 배점 | 기준 |
|---|---|---|
| 현금 상금 | 35 | $500k↑ 35 · $100k↑ 32 · $25k↑ 27 · $10k↑ 22 · $5k↑ 17 · $1k↑ 12 · 그 외 8 · 없음/미공개 3 |
| 크레딧·부상 | 10 | $100k↑ 10 · $25k↑ 8 · $5k↑ 5 · 그 외 3 |
| 주최 신뢰도 | 20 | top 20 · major 15 · mid 10 · small 5 |
| 참가 용이성 | 15 | 무료 15 · 구독필요 9 · 유료 5 (업계/학생 한정이면 −5) |
| 커리어 가치 | 20 | 배급·IMAX 20 · 영화제 상영 14 · 플랫폼 피처링 8 · 로럴만 4 |

바꾸려면 `sCash` · `sCredit` · `sOrg` · `sFee` · `sCareer` 함수만 수정하면 됩니다.

## ⚠ 시간대 주의

해외 마감은 대부분 `ET`(미 동부) · `PT`(미 서부) · `UTC` 기준입니다. **KST는 ET+13~14시간, PT+16~17시간**이라 표기된 날짜의 **다음 날 오후까지**인 경우가 많습니다. 반대로 UTC+8·UTC+9 지역 대회는 한국과 거의 같으니 여유가 없습니다.

### 출처

- [Higgsfield Contests](https://higgsfield.ai/contests) · [Global Film Festival](https://higgsfield.ai/contests/higgsfield-global-film-festival) · [Adathon](https://higgsfield.ai/contests/adathon)
- [Kling AI Activity Zone](https://app.klingai.com/global/activity-zone)
- [PixVerse CPP 2.0](https://pixverse.ai/en/blog/pixverse-global-creative-partner-program-2-0) · [UN AI for Good 파트너십](https://pixverse.ai/en/blog/pixverse-partners-un-ai-for-good-global-summit-2026)
- [SeaArt Event Center](https://www.seaart.ai/event-center/activity)
- [Civitai Challenges](https://civitai.com/challenges) · [Vidu × Civitai](https://www.vidu.com/activity/2776589160456791)
- [OpenArt Music Video Awards](https://openart.ai/programs/music-video-awards)
- [Runway AI Film Festival](https://aif.runwayml.com/)
- [Artlist $250K Seedance 2.5 Challenge](https://artlist.io/lp/seedance-2-5-challenge/) — 마감 표기가 랜딩(8/31)과 블로그(8/26)로 엇갈려 이른 쪽을 채택
- [aifilmcontests.com](https://aifilmcontests.com/) — 영화제 57건 집계 (마감일·상금 대부분 여기서 확인)
- [Devpost](https://devpost.com/hackathons) — AI 해커톤 (공개 API)
- [melies.co/ai-film-festivals](https://melies.co/ai-film-festivals)
