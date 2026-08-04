"""
공모전 수집 소스별 파서.

각 함수는 dict 리스트를 돌려주며, 실패해도 예외를 밖으로 던지지 않고
빈 리스트 + 경고를 남깁니다. (한 소스가 죽어도 나머지는 수집되도록)
"""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}
TIMEOUT = 30
POLITE_DELAY = 0.4          # 상세 페이지 연속 요청 간 대기(초)

WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"  ! {msg}")


def get(url: str, tries: int = 3) -> str | None:
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            if r.ok:
                return r.text
            if r.status_code == 404:
                return None
        except requests.RequestException as e:
            if i == tries - 1:
                warn(f"요청 실패 {url} : {type(e).__name__}")
        time.sleep(1.5 * (i + 1))
    return None


def ld_blocks(html: str) -> list[dict]:
    """페이지의 모든 JSON-LD 블록을 평탄화해서 반환."""
    out: list[dict] = []
    for tag in BeautifulSoup(html, "lxml").select('script[type="application/ld+json"]'):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        out.extend(d if isinstance(d, list) else [d])
    return out


def ld_find(blocks: list, want_type: str) -> list[dict]:
    """중첩 구조 안까지 뒤져서 해당 @type 노드를 전부 찾는다.

    Higgsfield 처럼 CollectionPage.mainEntity 아래에 ItemList 가 숨어 있는
    경우가 있어 최상위만 보면 놓친다.
    """
    found: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("@type") == want_type:
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(blocks)
    return found


# ══════════════════════════════════════════════════════════════════════
#  국내 — 위비티(Wevity)
# ══════════════════════════════════════════════════════════════════════
# cidx = 위비티 분야 코드. tech=True 인 분야는 AI 밀도가 높아 목록 전 항목의
# 상세를 확인하고, 나머지는 제목에 AI 키워드가 있을 때만 상세를 본다(요청 절약).
WEVITY_LISTS = [
    (20, "웹/모바일/IT",    True),
    (21, "게임/소프트웨어", True),
    (22, "과학/공학",       True),
    (1,  "기획/아이디어",   False),
    (2,  "광고/마케팅",     False),
    (10, "영상/UCC/사진",   False),
]
WEVITY_URL = "https://www.wevity.com/?c=find&s=1&gub=1&cidx={cidx}"

# 제목·분야·상세에 이 중 하나라도 있어야 AI 공모전으로 인정
AI_KEYWORDS = [
    "AI", "A.I", "인공지능", "머신러닝", "딥러닝", "빅데이터", "데이터",
    "생성형", "생성 AI", "LLM", "챗봇", "알고리즘", "GPT", "AX",
]

# 위비티 총상금 구간 표기 → (하한, 상한) 원
PRIZE_BUCKETS = {
    "5천만원이상": (50_000_000, None),
    "5천만원~3천만원": (30_000_000, 50_000_000),
    "3천만원~1천만원": (10_000_000, 30_000_000),
    "1천만원이하": (None, 10_000_000),
}


def _won(text: str) -> int | None:
    """'300만원' '1억 2천만원' '1,200만원' → 정수(원)."""
    if not text:
        return None
    t = text.replace(",", "").replace(" ", "")
    total = 0
    hit = False
    m = re.search(r"(\d+(?:\.\d+)?)억", t)
    if m:
        total += int(float(m.group(1)) * 100_000_000)
        hit = True
    m = re.search(r"(\d+(?:\.\d+)?)천만", t)
    if m:
        total += int(float(m.group(1)) * 10_000_000)
        hit = True
    else:
        m = re.search(r"(\d+(?:\.\d+)?)만", t)
        if m:
            total += int(float(m.group(1)) * 10_000)
            hit = True
    return total if hit and total else None


GOV_HINTS = ("부", "청", "처", "위원회", "공사", "공단", "진흥원", "연구원",
             "재단", "협회", "원", "청장")
CORP_HINTS = ("삼성", "LG", "SK", "현대", "네이버", "카카오", "NHN", "KT",
              "롯데", "CJ", "한화", "포스코", "KB", "신한", "하나", "우리",
              "매일유업", "넥슨", "엔씨", "크래프톤", "쿠팡", "배민", "토스")
LOCAL_HINTS = ("광역시", "특별시", "특별자치", "도청", "시청", "군청",
               "서울시", "부산", "대구", "인천", "광주", "대전", "울산",
               "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주")


def classify_host(host: str) -> str:
    h = host or ""
    if any(k in h for k in CORP_HINTS):
        return "대기업"
    if any(k in h for k in LOCAL_HINTS):
        return "지자체"
    if any(h.endswith(k) or k in h for k in GOV_HINTS):
        return "정부·공공"
    return "기타"


def classify_cat(title: str, field: str) -> str:
    t = f"{title} {field}"
    if re.search(r"해커톤|hackathon|개발|앱|어플|소프트웨어|임베디드|SW", t, re.I):
        return "해커톤·개발"
    if re.search(r"영상|UCC|숏폼|콘텐츠|영화|광고|디자인|사진|예술", t):
        return "AI영상·콘텐츠"
    if re.search(r"경진대회|알고리즘|데이터|분석|예측|챌린지|모델", t):
        return "데이터·알고리즘"
    return "아이디어·기획"


def classify_who(target: str, title: str) -> str:
    """참가 범위 분류.

    지역 판정은 '응모대상'만 본다. 제목에는 '2026 대전 AI 영상 공모전'처럼
    개최 도시가 들어가는 일이 많아 제목까지 보면 전국 대회를 지역 한정으로
    잘못 분류한다.
    """
    t = (target or "").strip()
    if not t:
        return "전국민"
    if "제한없음" in t or "일반인" in t or "누구나" in t:
        return "전국민"
    if any(k in t for k in LOCAL_HINTS) and "전국" not in t:
        return "지역·소속한정"
    if "청소년" in t or "어린이" in t:
        return "청소년·어린이"
    if "대학" in t:
        return "대학생"
    return "전국민"


def parse_wevity_detail(html: str) -> dict:
    """상세 페이지의 ul.cd-info-list 를 key→value 로."""
    s = BeautifulSoup(html, "lxml")
    info: dict[str, str] = {}
    box = s.select_one(".cd-info-list")
    if box:
        for li in box.select("li"):
            tit = li.select_one(".tit")
            if not tit:
                continue
            key = tit.get_text(" ", strip=True)
            val = li.get_text(" ", strip=True)
            if val.startswith(key):
                val = val[len(key):].strip()
            info[key] = val
    body = s.select_one(".cd-cont") or s
    info["_body"] = body.get_text(" ", strip=True)[:1500]
    return info


def fetch_wevity(limit_per_list: int = 30) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    listed = 0

    for cidx, label, tech in WEVITY_LISTS:
        html = get(WEVITY_URL.format(cidx=cidx))
        if not html:
            warn(f"위비티 [{label}] 목록 로드 실패")
            continue
        s = BeautifulSoup(html, "lxml")
        rows = [li for li in s.select("ul.list li") if li.select_one('a[href*="ix="]')]
        if not rows:
            warn(f"위비티 [{label}] 목록 항목 0개 — 구조 변경 의심")
            continue
        listed += len(rows)

        for li in rows[:limit_per_list]:
            href = li.select_one('a[href*="ix="]')["href"]
            ix = re.search(r"ix=(\d+)", href).group(1)
            if ix in seen:
                continue

            title = (li.select_one(".tit").get_text(" ", strip=True)
                     if li.select_one(".tit") else "")
            sub = li.select_one(".sub-tit")
            if sub:                                        # 제목 뒤 '분야 : …' 꼬리 제거
                title = title.replace(sub.get_text(" ", strip=True), "").strip()
            title = re.sub(r"\s*(SPECIAL|IDEA|신규|추천)\s*$", "", title).strip()
            day = (li.select_one(".day").get_text(" ", strip=True)
                   if li.select_one(".day") else "")
            if "마감" in day and "임박" not in day:
                continue                                   # 이미 종료
            if "D+" in day:
                continue

            # 비(非)기술 분야는 제목에 AI 힌트가 있을 때만 상세를 확인한다
            if not tech and not any(k in title for k in AI_KEYWORDS):
                continue

            seen.add(ix)
            detail_url = "https://www.wevity.com/" + href.lstrip("/")
            time.sleep(POLITE_DELAY)
            dhtml = get(detail_url)
            if not dhtml:
                continue
            info = parse_wevity_detail(dhtml)

            blob = " ".join([title, info.get("분야", ""), info.get("_body", "")])
            if not any(k in blob for k in AI_KEYWORDS):
                continue                                   # AI 무관 → 제외

            # 접수기간 "2026-07-13 ~ 2026-08-17 D-13"
            start = deadline = None
            dates = re.findall(r"(\d{4}-\d{2}-\d{2})", info.get("접수기간", ""))
            if dates:
                start = dates[0]
                deadline = dates[-1] if len(dates) > 1 else dates[0]
            if not deadline:
                continue                                   # 마감일 없으면 D-day 계산 불가

            # 위비티는 총상금을 정확한 액수가 아니라 구간으로만 준다.
            # 구간을 정확한 금액인 척 보여주면 안 되므로 min/max 를 따로 싣고
            # prizeApprox 로 "이건 구간이다" 를 표시한다.
            bucket = info.get("총 상금", "").strip()
            lo, hi = PRIZE_BUCKETS.get(bucket.replace(" ", ""), (None, None))
            top = _won(info.get("1등 상금", ""))

            host = info.get("주최/주관", "").strip() or "미상"
            target = info.get("응모대상", "").strip()
            homepage = info.get("홈페이지", "").strip()
            if not homepage.startswith("http"):
                homepage = detail_url

            out.append({
                "id": f"wevity-{ix}",
                "title": title,
                "host": host,
                "hostType": classify_host(host),
                "cat": classify_cat(title, info.get("분야", "")),
                "start": start,
                "deadline": deadline,
                "prizeTotal": lo,                          # 구간 하한(정렬·필터용)
                "prizeMin": lo,
                "prizeMax": hi,
                "prizeApprox": bool(lo or hi),
                "prizeBucket": bucket or None,
                "topPrize": (f"1등 {top // 10000:,}만원" if top else
                             (f"총상금 {bucket}" if bucket else "공고 확인 필요")),
                "who": target or "공고 확인",
                "whoType": classify_who(target, title),
                "bonus": [],
                "note": (f"위비티 자동 수집. 접수 {start} ~ {deadline}."
                         + (f" 총상금 구간 {bucket}." if bucket else "")),
                "url": homepage,
                "tags": [t.strip() for t in info.get("분야", "").split(",")[:3] if t.strip()],
                "verify": ([] if top else ["prize"]),
                "source": "wevity",
            })

    if listed and not out:
        warn(f"위비티 목록 {listed}건을 봤지만 AI 공모전 0건 — 필터 확인 필요")
    return out


# ══════════════════════════════════════════════════════════════════════
#  국내 — 인공지능팩토리
# ══════════════════════════════════════════════════════════════════════
AIFACTORY_OPEN = ("참가 접수중", "진행예정", "접수중")


def fetch_aifactory() -> list[dict]:
    html = get("https://aifactory.space/ko/competition")
    if not html:
        warn("인공지능팩토리 로드 실패")
        return []
    s = BeautifulSoup(html, "lxml")

    # CSS 모듈 해시(taskList_task_list__XXXX)는 빌드마다 바뀌므로 접두사로 매칭
    cards = s.select("ul[class*=taskList] > li")
    if not cards:
        warn("인공지능팩토리 카드 목록 없음 — 구조 변경 의심")
        return []

    out, seen = [], set()
    for li in cards:
        badges = {p.get_text(strip=True) for p in li.select("p.w-full.text-center.truncate")}
        if not (badges & set(AIFACTORY_OPEN)) or "종료" in badges:
            continue                                       # 접수중/예정만

        titles = [p.get_text(" ", strip=True) for p in li.select("p.text-lg.font-bold")]
        if not titles:
            continue
        title = titles[0]
        parent = li.select_one("p[style*='linear-gradient']")
        parent_name = parent.get_text(" ", strip=True) if parent else ""
        full = (f"{parent_name} — {title}" if parent_name else title).strip()
        if full in seen:
            continue

        txt = li.get_text(" ", strip=True)
        m = re.search(r"(\d[\d,\.]*\s*(?:억|천만|만)원)", txt)
        prize = _won(m.group(1)) if m else None

        # 카드에 '2026.08.31 2026.09.21' 형태로 대회 기간이 들어있다
        dates = re.findall(r"(\d{4})[.\-](\d{2})[.\-](\d{2})", txt)
        start = deadline = None
        if dates:
            start = "-".join(dates[0])
            deadline = "-".join(dates[-1]) if len(dates) > 1 else None

        if not any(k in full for k in AI_KEYWORDS):
            continue
        seen.add(full)

        out.append({
            "id": "aifactory-" + re.sub(r"\W+", "-", full)[:44].strip("-").lower(),
            "title": full,
            "host": "인공지능팩토리 제휴",
            "hostType": "정부·공공",
            "cat": "데이터·알고리즘",
            "start": start,
            "deadline": deadline,
            "prizeTotal": prize,
            "prizeBucket": None,
            "topPrize": (f"{prize // 10000:,}만원" if prize else "공고 확인 필요"),
            "who": "전국 누구나 (공고 확인)",
            "whoType": "전국민",
            "bonus": [],
            "note": ("인공지능팩토리 자동 수집."
                     + (f" 대회 기간 {start} ~ {deadline}." if deadline else "")
                     + " 표기된 날짜는 대회 기간이며 접수 마감과 다를 수 있습니다."),
            "url": "https://aifactory.space/ko/competition",
            "tags": ["알고리즘", "데이터"],
            "verify": ["deadline"] + ([] if prize else ["prize"]),
            "source": "aifactory",
        })

    if not out:
        warn(f"인공지능팩토리 카드 {len(cards)}개 중 접수중 0건 (또는 파싱 실패)")
    return out


# ══════════════════════════════════════════════════════════════════════
#  해외 — aifilmcontests.com (sitemap → 상세 JSON-LD)
# ══════════════════════════════════════════════════════════════════════
CASH_PATTERNS = [
    (r"\$([\d,]+(?:\.\d+)?)\s*(?:million|M\b)", 1_000_000),
    (r"\$([\d,]+)\s*K\b",                          1_000),
    (r"\$([\d,]+)",                                    1),
]
CURRENCY_TO_USD = {"€": 1.08, "£": 1.27}


def parse_cash_usd(text: str) -> int | None:
    """설명문에서 가장 큰 달러 금액을 추출."""
    if not text:
        return None
    best = None
    for pat, mult in CASH_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            try:
                v = float(m.group(1).replace(",", "")) * mult
            except ValueError:
                continue
            if best is None or v > best:
                best = v
    for sym, rate in CURRENCY_TO_USD.items():
        for m in re.finditer(re.escape(sym) + r"([\d,]+)", text):
            try:
                v = float(m.group(1).replace(",", "")) * rate
            except ValueError:
                continue
            if best is None or v > best:
                best = v
    return int(best) if best else None


def classify_global_cat(text: str) -> str:
    t = text.lower()
    if re.search(r"music video|music-video|mv\b", t):
        return "음악·MV"
    if re.search(r"\bad\b|ads|advert|brand|commercial", t):
        return "AI 광고"
    if re.search(r"image|art award|photo|still", t):
        return "이미지·아트"
    if re.search(r"app|hackathon|developer|code", t):
        return "앱·개발"
    return "AI 필름"


def fetch_aifilmcontests(max_items: int = 90) -> list[dict]:
    sm = get("https://aifilmcontests.com/sitemap.xml")
    if not sm:
        warn("aifilmcontests 사이트맵 로드 실패")
        return []
    urls = [u for u in re.findall(r"<loc>(.*?)</loc>", sm) if "/contests/" in u]
    if len(urls) < 10:
        warn(f"aifilmcontests 사이트맵 항목 {len(urls)}개 — 구조 변경 의심")
        return []

    today = date.today().isoformat()
    out: list[dict] = []
    for url in urls[:max_items]:
        time.sleep(POLITE_DELAY)
        html = get(url)
        if not html:
            continue
        ev = next((b for b in ld_blocks(html) if b.get("@type") == "Event"), None)
        if not ev:
            continue

        offers = ev.get("offers") or {}
        deadline = (offers.get("validThrough") or ev.get("endDate") or "")[:10]
        status = ev.get("eventStatus", "")
        if "Cancelled" in status or (deadline and deadline < today):
            continue                                        # 이미 종료

        desc = ev.get("description", "") or ""
        name = ev.get("name", "").strip()
        org = (ev.get("organizer") or {}).get("name", "") or "미상"

        # price 는 자유 텍스트다. '0' / '25' / 'Tiered on FilmFreeway' 등이 섞여 온다.
        price = str(offers.get("price", "")).strip()
        cur = offers.get("priceCurrency", "USD")
        if price in ("0", "0.0", "0.00"):
            fee, fee_text = "free", "무료"
        elif not price:
            fee, fee_text = "free", "무료(확인 필요)"
        elif re.fullmatch(r"[\d,.]+", price):
            fee, fee_text = "paid", f"참가비 {cur} {price}"
        else:
            fee, fee_text = "paid", f"참가비 있음 · {price[:60]}"

        cash = parse_cash_usd(desc)
        slug = url.rstrip("/").split("/")[-1]

        out.append({
            "id": f"afc-{slug}"[:60],
            "title": name,
            "org": org,
            "orgType": "영화제",
            "orgTier": "mid",
            "cat": classify_global_cat(f"{name} {desc}"),
            "deadline": deadline or None,
            "tz": "현지",
            "recur": "once",
            "cash": cash or 0,
            "credit": 0,
            "prizeText": (f"현금 약 ${cash:,}" if cash else "상금 정보는 공고 확인"),
            "who": "전 세계 창작자 누구나",
            "whoType": "전세계 누구나",
            "fee": fee,
            "feeText": fee_text,
            "entry": "영화제 폼 제출",
            "career": "festival",
            "bonus": [],
            "note": desc[:400],
            "url": ev.get("url") or url,
            "tags": [],
            "verify": ([] if cash else ["prize"]) + ([] if deadline else ["deadline"]),
            "source": "aifilmcontests",
        })
    if len(out) < 5:
        warn(f"aifilmcontests 수집 {len(out)}건 — 비정상적으로 적음")
    return out


# ══════════════════════════════════════════════════════════════════════
#  해외 — Higgsfield (JSON-LD ItemList)
#
#  ⚠ 기본 파이프라인에서 제외돼 있다 (update_contests.py 에서 호출하지 않음).
#  이유: Higgsfield 의 JSON-LD 가 실제 페이지와 어긋난다. 2026-08-04 확인 시
#  LD 는 Global Film Festival 을 "7/16~7/30" 으로 싣고 있었으나 상세 페이지는
#  "8/7 개시 ~ 8/31 마감" 이었고, 진행 중인 Adathon·Apps Contest 는 LD 에
#  아예 없었다. 틀린 날짜를 자동으로 넣느니 data/manual.global.json 의
#  사람 확인 값을 쓰는 편이 낫다. 나중에 LD 가 정확해지면 다시 연결할 것.
# ══════════════════════════════════════════════════════════════════════
def fetch_higgsfield() -> list[dict]:
    html = get("https://higgsfield.ai/contests")
    if not html:
        warn("Higgsfield 로드 실패")
        return []
    lists = ld_find(ld_blocks(html), "ItemList")
    items = [x for lst in lists for x in lst.get("itemListElement", [])]
    if not items:
        warn("Higgsfield JSON-LD ItemList 없음 (구조 변경 의심)")
        return []

    today = date.today().isoformat()
    out = []
    for it in items:
        ev = it.get("item", {})
        if ev.get("@type") != "Event":
            continue
        end = (ev.get("endDate") or "")[:10]
        if end and end < today:
            continue
        desc = ev.get("description", "") or ""
        name = ev.get("name", "").strip()
        cash = parse_cash_usd(desc + " " + name)
        is_credit = bool(re.search(r"credit", desc, re.I))
        out.append({
            "id": "hf-" + re.sub(r"\W+", "-", name).strip("-").lower()[:40],
            "title": name,
            "org": "Higgsfield",
            "orgType": "플랫폼",
            "orgTier": "top",
            "cat": classify_global_cat(f"{name} {desc}"),
            "deadline": end or None,
            "tz": "ET",
            "recur": "once",
            "cash": 0 if is_credit else (cash or 0),
            "credit": (cash or 0) if is_credit else 0,
            "prizeText": desc[:160] or "공고 확인",
            "who": "Higgsfield 구독자",
            "whoType": "구독자",
            "fee": "sub",
            "feeText": "Higgsfield 구독 필요",
            "entry": "플랫폼 제출",
            "career": "festival",
            "bonus": [],
            "note": desc[:400],
            "url": ev.get("url") or "https://higgsfield.ai/contests",
            "tags": ["플랫폼"],
            "verify": ["deadline"] if not end else [],
            "source": "higgsfield",
        })
    return out
