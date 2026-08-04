# AI 공모전 레이더

각각 더블클릭하면 바로 열리는 단일 파일 페이지입니다. 빌드·서버 불필요. 상단 네비게이션으로 서로 오갈 수 있습니다.

| 파일 | 내용 |
|---|---|
| `index.html` | 🇰🇷 **국내** AI 공모전 24건 |
| `global.html` | 🌍 **해외** 플랫폼 챌린지 · AI 영화제 54건 |

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

## 데이터 수정

`index.html` 안의 `const CONTESTS = [ ... ]` 배열 하나만 고치면 됩니다.

```js
{
  id: 'unique-key',              // 중복 불가 (즐겨찾기 저장 키)
  title: '공모전 이름',
  host: '주최기관', hostType: '정부·공공',   // 정부·공공 | 대기업 | 지자체 | 기타
  cat: '해커톤·개발',                        // 자유롭게 추가 가능, 필터 칩이 자동 생성됨
  deadline: '2026-09-30',        // 모르면 null → "일정 미정"으로 표시
  prizeTotal: 30000000,          // 원 단위 숫자, 모르면 null
  topPrize: '대상 1,000만원',
  who: '만 19세 이상 누구나', whoType: '전국민',  // 전국민 | 대학생 | 전문가한정 | 지역·소속한정
  bonus: ['채용연계'],            // 중요도 점수에 반영됨
  note: '비고',
  url: 'https://...',
  tags: ['해커톤'],
  verify: ['prize']              // 'prize' | 'deadline' → ⚠ 확인필요 배지
}
```

## ⚠ 데이터 신뢰도

2026년 8월 4일 기준 웹 조사 결과입니다. **⚠ 확인필요** 배지가 붙은 항목은 상금 또는 마감일이 공고에 명시되지 않았거나, 위비티 목록의 D-day에서 역산한 값입니다. 지원 전 반드시 공식 링크에서 확인하세요. 마감 시각도 자정/18시 등으로 갈리니 별도 확인이 필요합니다.

### 확인된 항목 (공고·보도자료 교차 확인)

| 공모전 | 마감 | 총상금 |
|---|---|---|
| NHN 게임 X AI 해커톤 (NAN 2026) | 8/10 | 8,000만원 |
| SKT 모두의 promp.T | 8/10 | 1,000만원 상당 |
| 제2회 매일유업 대학생 AI 영상 공모전 | 8/17 | 1,200만원 |
| 2026 대전 AI 영상 공모전 | 8/18 | 4,800만원 |
| 제4회 전북청년 AI·빅데이터 경진대회 | 8/28 17:00 | 미공개 |
| 제4회 스마트축산 AI 경진대회 | 8/31 | 2,300만원 |
| 제24회 임베디드SW경진대회 (자유공모) | 9/3 | 최대 3,000만원 |
| 지능형 홈 AI@Home matter AX Sprint | 9/11 18:00 | 미공개 |
| 국립공원 위성 모니터링 AI 챌린지 ①②③④ | 9/21 · 10/6 | 주제별 600만원 |

### 출처

- [위비티(Wevity) — IT·웹/모바일 공모전](https://www.wevity.com/?c=find&s=1&gub=1&cidx=20)
- [인공지능팩토리 경진대회](https://aifactory.space/ko/competition)
- [데이콘 경진대회](https://dacon.io/competitions)
- [전국민 AI 경진대회](https://aichallenge4all.or.kr/competitions)
- [NHN NAN 2026](https://event.wanted.co.kr/nan2026-nhn) · [ZDNet 보도](https://zdnet.co.kr/view/?no=20260731140707)
- [SKT 모두의 promp.T](https://news.sktelecom.com/prompt)
- [2026 대전 AI 영상 공모전](https://aikive.com/event)
- [제4회 스마트축산 AI 경진대회](https://smartlivestock.co.kr/)
- [임베디드SW경진대회](https://www.eswcontest.or.kr/main.php)
- [지능형 홈 AX Sprint 2026](https://linkareer.com/activity/338955)

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
- [aifilmcontests.com](https://aifilmcontests.com/) — 영화제 57건 집계 (마감일·상금 대부분 여기서 확인)
- [melies.co/ai-film-festivals](https://melies.co/ai-film-festivals)
