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
| AI 플랫폼 챌린지 감시 | Artlist·Higgsfield 등 **후보만 수집** → 사람 확인 | ✅ 정상 |

⚠ **위비티는 Cloudflare가 데이터센터 IP를 차단해 GitHub Actions에서 실패합니다.** 지역 차단이 아니라 봇 차단이라 프록시 없이는 우회가 어렵습니다. 로컬(집 IP)에서 실행하면 정상 동작하고 5~10건이 더 붙으니, 가끔 로컬에서 한 번 돌려 커밋하면 좋습니다. 실패해도 경고만 남기고 나머지 소스로 진행합니다.

Higgsfield는 JSON-LD가 실제 페이지와 어긋나(2026-08-04 기준 영화제 일정이 7/16~7/30으로 실제와 다름) 자동 수집에서 뺐습니다. 값은 `data/manual.global.json`에 있습니다.

Devpost는 `search=ai` 로 열려 있는 대회를 받아오되, **상금 $1,000 이상 · 초대 전용 아님**만 남깁니다. 상금이 달러가 아닌 대회(₹ 등)는 환산하지 않고 건너뜁니다.

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

먼저 `--dry-run` 으로 몇 건이 잡히는지 보고 넣는 편이 안전합니다.

## 안전장치

수집이 깨졌을 때 멀쩡한 데이터를 덮어쓰지 않도록:

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
