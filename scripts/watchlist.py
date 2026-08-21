#!/usr/bin/env python3
"""
AI 플랫폼 챌린지 감시기(watchtower).

Artlist·Higgsfield·Runway 처럼 AI 서비스가 직접 여는 챌린지는 정기 공고가
아니다. 어느 날 갑자기 랜딩페이지 하나가 올라오고 3주 뒤 조용히 끝난다.
공모전 포털(위비티·링커리어·aifilmcontests)에는 대개 실리지 않는다.

그래서 "목록을 긁는" 방식이 아니라 "새 URL이 생겼는지 감시하는" 방식을 쓴다.

  1. 업체별 사이트맵/허브 페이지에서 challenge·contest 류 URL을 모은다
  2. data/watch.state.json 에 없는 새 URL만 상세 페이지를 열어본다
  3. 제목·상금·마감일을 최대한 뽑아 data/review.queue.json 에 쌓는다
  4. 사람이 확인한 뒤 data/manual.global.json 으로 옮긴다

자동으로 목록에 올리지 않는 이유:
  랜딩페이지의 마감일은 "by Aug 31" 같은 산문이라 연도·시간대가 빠져 있고,
  카운트다운이 JS로만 그려지는 경우도 흔하다. 틀린 D-day를 띄우느니
  사람이 30초 확인하는 편이 낫다는 게 이 저장소의 기존 방침이고
  (data/manual.global.json 의 _readme 참고) 여기서도 그대로 따른다.

이 파일은 registry + 파서만 갖고 있다. 실행은 scripts/watch_challenges.py.
"""
from __future__ import annotations

import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
import sources                                             # noqa: E402


# ══════════════════════════════════════════════════════════════════════
#  감시 대상
#
#  sitemaps : (사이트맵 URL, 하위 사이트맵 필터 정규식|None)
#             sitemapindex 면 필터에 걸리는 하위 사이트맵만 한 단계 내려간다.
#  hubs     : (허브 페이지 URL, 링크 경로 정규식)
#             서버 HTML 에 <a href> 가 들어 있는 페이지만 의미가 있다.
#
#  ⚠ 여기 없는 업체는 "안 여는 곳"이 아니라 "자동으로 못 보는 곳"이다.
#    Kling·PixVerse·SeaArt 처럼 로그인 뒤 JS로만 그려지는 곳은 아래
#    MANUAL_CHECK 로 뺐다. 리포트에 체크리스트로 다시 나온다.
# ══════════════════════════════════════════════════════════════════════
PLATFORMS = [
    {
        "brand": "Higgsfield", "org": "Higgsfield", "orgTier": "top",
        "fee": "sub", "feeText": "Higgsfield 구독 필요",
        "hubs": [("https://higgsfield.ai/contests", r"/contests/[\w\-]+$")],
        "sitemaps": [("https://higgsfield.ai/sitemap.xml", r"blog|marketing")],
    },
    {
        "brand": "Artlist", "org": "Artlist", "orgTier": "mid",
        "sitemaps": [("https://artlist.io/blog/sitemap.xml", None)],
    },
    {
        "brand": "ElevenLabs", "org": "ElevenLabs", "orgTier": "top",
        "sitemaps": [("https://elevenlabs.io/sitemap.xml", r"articles|events|pagesv2")],
    },
    {
        "brand": "Runway", "org": "Runway", "orgTier": "top",
        "hubs": [("https://runwayml.com/gen48", r"/gen48")],
        "sitemaps": [("https://runwayml.com/sitemap.xml", None)],
    },
    {
        "brand": "Krea", "org": "Krea AI", "orgTier": "mid",
        "sitemaps": [("https://www.krea.ai/sitemap.xml", None)],
        "only": r"/blog/|/news/",          # /nodes/ 밑은 사용자가 만든 앱이라 대회가 아니다
    },
    {
        # app.pixverse.ai 는 앱 셸이라 못 읽지만 pixverse.ai 블로그는 서버 렌더다.
        # PixLight 글로벌 AI 필름 공모가 여기서 잡혔다.
        "brand": "PixVerse", "org": "PixVerse", "orgTier": "major",
        "hubs": [("https://pixverse.ai/en/blog", r"/blog/[\w\-]+$")],
    },
    {
        # 공식 콘테스트 페이지가 서버 렌더 + 회차가 잦다. 애니·일러스트 계열.
        "brand": "PixAI", "org": "PixAI", "orgTier": "mid",
        "hubs": [("https://pixai.art/en/contest/official", r"/contest/[\w\-]+$"),
                 ("https://pixai.art/en/contest/community", r"/contest/[\w\-]+$")],
    },
    {
        "brand": "Artbreeder", "org": "Artbreeder", "orgTier": "mid",
        "hubs": [("https://www.artbreeder.com/contests", r"/contests/[\w]+$")],
    },
    {
        "brand": "CapCut", "org": "CapCut · Dreamina (ByteDance)", "orgTier": "major",
        "hubs": [("https://www.capcut.com/blog", r"/create/[\w\-]+$")],
    },
    {
        "brand": "Udio", "org": "Udio", "orgTier": "mid",
        "hubs": [("https://www.udio.com/blog", r"/blog/[\w\-]+$")],
    },
    {
        "brand": "Stability AI", "org": "Stability AI", "orgTier": "major",
        "sitemaps": [("https://stability.ai/sitemap.xml", None)],
    },
    {
        "brand": "Synthesia", "org": "Synthesia", "orgTier": "major",
        "sitemaps": [("https://www.synthesia.io/sitemap.xml", None)],
    },
    {
        "brand": "LTX Studio", "org": "LTX Studio (Lightricks)", "orgTier": "mid",
        "sitemaps": [("https://ltx.studio/sitemap.xml", None)],
    },
    {
        "brand": "Luma", "org": "Luma AI", "orgTier": "mid",
        "sitemaps": [("https://lumalabs.ai/sitemap.xml", None)],
        "hubs": [("https://lumalabs.ai/news", r"/news/[\w\-]+$")],
    },
    {
        "brand": "Vidu", "org": "Vidu (ShengShu)", "orgTier": "mid",
        # 3천 개짜리 단일 urlset 이라 블로그 경로만 본다
        "sitemaps": [("https://www.vidu.com/sitemap.xml", None)],
        "only": r"/blog/",
    },
    {
        "brand": "Moonvalley", "org": "Moonvalley", "orgTier": "mid",
        "sitemaps": [("https://www.moonvalley.com/sitemap.xml", None)],
    },
    {
        "brand": "Recraft", "org": "Recraft", "orgTier": "mid",
        "sitemaps": [("https://www.recraft.ai/sitemap.xml", None)],
    },
    {
        "brand": "Suno", "org": "Suno", "orgTier": "mid",
        "sitemaps": [("https://suno.com/sitemap.xml", None)],
    },
    {
        "brand": "OpenAI", "org": "OpenAI", "orgTier": "top",
        "sitemaps": [("https://openai.com/sitemap.xml", r"/page/|index|news|stories")],
    },
    {
        "brand": "Civitai", "org": "Civitai", "orgTier": "mid",
        # 커뮤니티 글까지 섞여 나온다. 노이즈가 많은 대신 공식 챌린지도 여기 올라온다.
        "sitemaps": [("https://civitai.com/sitemap-articles.xml", None)],
        "noisy": True,
    },
]

# ══════════════════════════════════════════════════════════════════════
#  브라우저로 열어야 보이는 곳 (앱 안 '이벤트' 탭)
#
#  Dreamina·Kling·NightCafe·SeaArt 는 서버 HTML 이 빈 껍데기라 requests 로는
#  0건이지만, 실제 화면에는 진행 중인 공모가 여러 건 떠 있다. scripts/render.py
#  (playwright)로 렌더한 뒤 '카드'에 해당하는 요소를 텍스트로 긁는다.
#
#  링크가 없는 목록이 많아서(모달로 열린다) URL 대신 '제목 + 남은 기간'을
#  후보로 삼는다. 그래서 이 채널은 항상 사람 확인 큐로만 간다.
#
#  marker : 진행 중인 카드에만 나타나는 문구. 이걸로 카드 요소를 찾는다.
#           끝난 항목(Awarded·Reviewing·Rewarded)은 자연히 걸러진다.
# ══════════════════════════════════════════════════════════════════════
RENDER_HUBS = [
    {
        "brand": "Dreamina", "org": "Dreamina (CapCut · ByteDance)", "orgTier": "major",
        "url": "https://dreamina.capcut.com/ai-tool/home?type=video&workspace=0&activeTab=activity",
        "marker": r"left to submit",
        "wait": "Left To Submit",
    },
    {
        "brand": "Kling AI", "org": "Kling AI (快手)", "orgTier": "top",
        "url": "https://app.klingai.com/global/activity-zone",
        "marker": r"before deadline",
        "wait": "Activity Zone",
    },
    {
        "brand": "NightCafe", "org": "NightCafe Studio", "orgTier": "mid",
        "url": "https://creator.nightcafe.studio/challenges",
        "marker": r"Entries close in",
        "wait": "Challenges",
    },
    {
        "brand": "SeaArt", "org": "SeaArt AI", "orgTier": "major",
        "url": "https://www.seaart.ai/event-center/activity",
        "marker": r"Ongoing",
        # 'Ongoing' 만 보면 '2026-08-21 Ongoing' 같은 날짜 칩이 잡힌다.
        # 주제 이름까지 들어간 카드만 남기려고 최소 길이를 올린다.
        "minLen": 30,
        "wait": "Daily Challenge",
    },
]

# 자동 감시가 불가능한 곳 — 리포트 맨 아래에 "직접 확인" 체크리스트로 출력한다.
# scripts/probe_watch_targets.py 로 확인한 결과다. 사정이 바뀌면 위로 올린다.
MANUAL_CHECK = [
    ("Tensor.Art", "https://tensor.art/events",      "렌더해도 목록이 안 뜸(로그인 필요 추정)"),
    ("Hailuo",     "https://hailuoai.video/",        "렌더해도 이벤트 목록 없음"),
    ("Vidu",       "https://www.vidu.com/activity",  "렌더해도 이벤트 목록 없음"),
    ("Wan",        "https://wan.video/activity",     "렌더 시 로드 실패"),
    ("OpenArt",    "https://openart.ai/",            "공모 경로가 자주 바뀜(404)"),
    ("Midjourney", "https://www.midjourney.com/",    "봇 차단(403)"),
    ("Leonardo",   "https://leonardo.ai/news/",      "봇 차단(403)"),
    ("Freepik",    "https://www.freepik.com/blog",   "봇 차단(403)"),
    ("Pika",       "https://pika.art/",              "사이트맵 비어 있음"),
    ("Ideogram",   "https://ideogram.ai/",           "사이트맵 비어 있음"),
    ("Adobe Firefly", "https://firefly.adobe.com/",  "사이트맵에 공모 경로 없음"),
    ("Shutterstock", "https://www.shutterstock.com/blog", "봇 차단(403)"),
]

# 감시 대상 브랜드 수 — 리포트에 함께 찍어 커버리지 변화를 눈에 보이게 한다.
WATCH_COUNT = len(PLATFORMS) + len(MANUAL_CHECK)

# Google 뉴스 RSS — 업체 사이트에 안 올라오고 기사로만 도는 건을 줍기 위한 보조 채널.
NEWS_QUERIES = [
    ('"AI video" (challenge OR contest) prize', "en-US", "US", "US:en"),
    ('"AI film" (contest OR competition) submissions prize', "en-US", "US", "US:en"),
    ("AI 영상 챌린지 상금 공모", "ko", "KR", "KR:ko"),
]

# 브랜드 이름을 직접 넣어 훑는다.
#
# 위 일반 질의만으로는 큰 건을 놓친다. 실제로 xAI 의 Grok Imagine 오디세이 공모
# ($175,000)는 공지가 X 게시물뿐이라 사이트맵·허브·일반 뉴스 질의 어디에도
# 안 걸렸고, 브랜드 이름을 넣은 질의에서만 잡혔다. 사이트가 JS 셸이거나 봇을
# 막는 업체(Midjourney·Leonardo·Freepik·Kling·NightCafe…)는 사실상 이 채널이
# 유일한 통로다.
NEWS_BRANDS = [
    "Midjourney", "Leonardo AI", "Freepik", "Kling AI", "Hailuo", "MiniMax",
    "Vidu", "Luma AI", "Pika Labs", "Runway", "OpenArt", "NightCafe",
    "Tensor.Art", "Ideogram", "Recraft", "Adobe Firefly", "Canva",
    "Grok Imagine", "Sora", "Google Veo", "CapCut", "Dreamina", "Krea",
    "Seedream", "Higgsfield", "PixVerse", "Civitai", "Artlist",
]
NEWS_BRAND_CHUNK = 6        # 한 질의에 넣을 브랜드 수 (요청 수 절약)


def brand_news_queries() -> list[tuple[str, str, str, str]]:
    out = []
    for i in range(0, len(NEWS_BRANDS), NEWS_BRAND_CHUNK):
        names = " OR ".join(f'"{b}"' for b in NEWS_BRANDS[i:i + NEWS_BRAND_CHUNK])
        out.append((f"({names}) (challenge OR contest OR competition) prize",
                    "en-US", "US", "US:en"))
    return out

CHALLENGE_PAT = re.compile(
    r"challenge|contest|competition|hackathon|award|film-?fest|creative-?jam|/jam\b", re.I)

# 이미 끝난 대회 후기·수상자 발표·일반 정보성 글을 걸러낸다.
NOISE_PAT = re.compile(
    r"winner|winners|recap|results|success-stor|shortlist|jury|terms|policy|privacy|"
    r"-part-\d|how-to|what-is|why-|-vs-|best-|top-\d|guide|tips|history-of|"
    r"award-winning|nominee|-wins-|-won-", re.I)

# 목록 페이지(…/blog/competitions 같은 카테고리 인덱스)는 대회 하나가 아니다.
INDEX_TAIL = {"challenge", "challenges", "contest", "contests", "competition",
              "competitions", "award", "awards", "hackathon", "hackathons",
              "event", "events", "jam", "jams"}

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# "Deadline: August 31" 처럼 마감을 가리키는 단서
CUE = re.compile(
    r"deadline|due\b|clos(?:e|es|ing)|end(?:s|ing)?\b|until|by\b|submit|entries|"
    r"last day|final day|마감|접수", re.I)

# 같은 글의 다국어 판본(/pl/blog/…, /sv/blog/…)은 한 건으로 본다.
LANG_PREFIX = re.compile(
    r"^/(?:ar|bg|cs|da|de|el|es|fa|fi|fil|fr|he|hi|hr|hu|id|it|ja|ko|ms|nb|nl|no|pl|pt|"
    r"ro|ru|sk|sv|ta|th|tr|uk|vi|zh)(?:-[a-z]{2})?/", re.I)

# 상금 추출용 — 금액 근처에 이런 말이 있으면 상금으로 본다
PRIZE_CUE = re.compile(r"prize|pool|award|winner|win\b|cash|grand|상금", re.I)
# 반대로 이런 말 근처의 금액은 상금이 아니다
#  (심사위원 소개의 '박스오피스 $800 million' 이 상금으로 잡힌 적이 있다)
MONEY_NOISE = re.compile(
    r"box office|revenue|valuation|raised|funding|market cap|acquisition|acquired|"
    r"budget|grossed|worth|salary|투자|매출|흥행", re.I)
CASH_SANITY = 50_000_000       # 이 금액을 넘으면 오탐으로 보고 버린다


# ══════════════════════════════════════════════════════════════════════
#  날짜 파서
# ══════════════════════════════════════════════════════════════════════
_D_ISO = re.compile(r"\b(20\d{2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})\b")
_D_MDY = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(20\d{2}))?", re.I)
_D_DMY = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(?:\s*,?\s*(20\d{2}))?", re.I)
# '월/일' 글자를 반드시 요구한다. 점 표기(2026.8.31)를 허용하면
# 'Seedance 2.5' 같은 버전 번호가 2월 5일로 잡힌다. 점 표기는 _D_ISO 가 본다.
_D_KR = re.compile(r"(?:(20\d{2})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일")


def _mk(y: int | None, m: int, d: int, today: date) -> date | None:
    """연도가 없으면 오늘 이후가 되는 가장 가까운 해로 채운다."""
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    for yy in ([y] if y else [today.year, today.year + 1]):
        try:
            got = date(yy, m, d)
        except ValueError:
            continue
        if y or got >= today - timedelta(days=1):
            return got
    return None


def date_candidates(text: str, today: date) -> list[tuple[int, date, bool]]:
    """(위치, 날짜, 연도가 본문에 있었는지) 목록.

    연도가 없으면 '오늘 이후 가장 가까운 해'로 채우는데, 이 추측이 자주 틀린다.
    ('Judging Period July 22-6, 2026' 처럼 연도가 다른 조각에 붙어 있는 경우)
    그래서 추측 여부를 같이 넘겨 신뢰도 판정에 쓴다.
    """
    out: list[tuple[int, date, bool]] = []
    for m in _D_ISO.finditer(text):
        d = _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)), today)
        if d:
            out.append((m.start(), d, True))
    for m in _D_MDY.finditer(text):
        d = _mk(int(m.group(3)) if m.group(3) else None,
                MONTHS[m.group(1).lower()[:3]], int(m.group(2)), today)
        if d:
            out.append((m.start(), d, bool(m.group(3))))
    for m in _D_DMY.finditer(text):
        d = _mk(int(m.group(3)) if m.group(3) else None,
                MONTHS[m.group(2).lower()[:3]], int(m.group(1)), today)
        if d:
            out.append((m.start(), d, bool(m.group(3))))
    for m in _D_KR.finditer(text):
        d = _mk(int(m.group(1)) if m.group(1) else None,
                int(m.group(2)), int(m.group(3)), today)
        if d:
            out.append((m.start(), d, bool(m.group(1))))
    return sorted(set(out))


_MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s*(million|billion|[MK]\b)?", re.I)
_MULT = {"million": 1_000_000, "billion": 1_000_000_000, "m": 1_000_000, "k": 1_000}


def prize_cash(text: str) -> int:
    """상금으로 보이는 달러 금액. 문맥을 보고 고른다.

    sources.parse_cash_usd 는 본문에서 가장 큰 금액을 집는다. 랜딩페이지에는
    심사위원 이력('박스오피스 $800 million')처럼 상금이 아닌 큰 숫자가 섞여
    있어서 그대로 쓰면 상금이 800배로 부풀었다. 그래서 여기서는
    '금액 주변에 prize/pool 이 있는가'를 먼저 본다.
    """
    text = re.sub(r"\s+", " ", text or "")
    cued, plain = [], []
    for m in _MONEY.finditer(text):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if m.group(2):
            v *= _MULT[m.group(2).lower()]
        v = int(v)
        if v <= 0 or v > CASH_SANITY:
            continue
        around = text[max(0, m.start() - 90):m.end() + 60]
        if MONEY_NOISE.search(around):
            continue
        (cued if PRIZE_CUE.search(around) else plain).append(v)
    pool = cued or plain
    return max(pool) if pool else 0


_CREDITS = re.compile(r"([\d,]{3,})\s*(?:credits?|크레딧)", re.I)


def prize_credits(text: str) -> int:
    """'5,000,000 Credits' 처럼 크레딧으로 주는 상금.

    PixAI·Kling 계열 콘테스트는 상금이 전부 플랫폼 크레딧이라 달러 파서로는
    0원짜리로 보인다. 크레딧은 현금이 아니므로 cash 와 섞지 않고 따로 담는다.
    """
    best = 0
    for m in _CREDITS.finditer(text or ""):
        try:
            v = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        best = max(best, v)
    return best


def find_deadline(text: str, today: date | None = None) -> tuple[str | None, str, str]:
    """본문에서 마감일을 추정한다.

    돌려주는 값: (ISO 날짜|None, 근거 문장, 신뢰도 high|low|none)

    high   : 마감 단서 뒤에 연도까지 적힌 날짜 (또는 JSON-LD Event.endDate)
    medium : 마감 단서는 있지만 연도가 없어 추측한 날짜
    low    : 단서 없이 본문에 있던 미래 날짜 중 가장 늦은 것
    """
    today = today or date.today()
    text = re.sub(r"\s+", " ", text or "")
    horizon = today + timedelta(days=400)
    cands = [(p, d, y) for p, d, y in date_candidates(text, today) if today <= d <= horizon]
    if not cands:
        return None, "", "none"

    for pos, d, has_year in cands:
        if CUE.search(text[max(0, pos - 120):pos]):
            return (d.isoformat(), text[max(0, pos - 90):pos + 40].strip(),
                    "high" if has_year else "medium")

    pos, d, _ = max(cands, key=lambda x: x[1])
    return d.isoformat(), text[max(0, pos - 90):pos + 40].strip(), "low"


# ══════════════════════════════════════════════════════════════════════
#  수집
# ══════════════════════════════════════════════════════════════════════
def _locs(xml: str) -> list[tuple[str, str]]:
    out = []
    for blk in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", blk, re.S)
        lm = re.search(r"<lastmod>(.*?)</lastmod>", blk, re.S)
        if loc:
            out.append((loc.group(1).strip(), (lm.group(1)[:10] if lm else "")))
    return out


def sitemap_entries(url: str, child: str | None, max_children: int = 8) -> list[tuple[str, str]]:
    xml = sources.get(url)
    if not xml:
        sources.warn(f"사이트맵 로드 실패 {url}")
        return []
    if "<sitemapindex" in xml:
        kids = [k.strip() for k in re.findall(r"<loc>(.*?)</loc>", xml)]
        if child:
            kids = [k for k in kids if re.search(child, k, re.I)]
        out: list[tuple[str, str]] = []
        for k in kids[:max_children]:
            time.sleep(sources.POLITE_DELAY)
            sub = sources.get(k)
            if sub:
                out += _locs(sub)
        return out
    return _locs(xml)


def hub_entries(url: str, path_pat: str) -> list[tuple[str, str]]:
    html = sources.get(url)
    if not html:
        sources.warn(f"허브 페이지 로드 실패 {url}")
        return []
    soup = BeautifulSoup(html, "lxml")
    seen: dict[str, str] = {}
    for a in soup.select("a[href]"):
        href = a["href"].split("?")[0].split("#")[0]
        if not href or not re.search(path_pat, href):
            continue
        seen[urljoin(url, href)] = ""
    return list(seen.items())


def discover(site: dict, days: int = 180) -> list[tuple[str, str]]:
    """한 업체에서 챌린지 후보 URL을 모은다. (url, lastmod)"""
    raw: list[tuple[str, str]] = []
    for u, child in site.get("sitemaps", []):
        raw += sitemap_entries(u, child)
    for u, pat in site.get("hubs", []):
        raw += hub_entries(u, pat)

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    only = site.get("only")
    out: dict[str, str] = {}
    for url, lastmod in raw:
        if only and not re.search(only, url):
            continue
        if not CHALLENGE_PAT.search(url) or NOISE_PAT.search(url):
            continue
        path = urlparse(url).path
        if path.rstrip("/").split("/")[-1].lower() in INDEX_TAIL:
            continue
        if LANG_PREFIX.match(path):           # 같은 글의 번역판
            continue
        if lastmod and lastmod < cutoff:
            continue
        out[url.rstrip("/")] = lastmod
    return sorted(out.items())


_COUNTDOWN = re.compile(
    r"(\d{1,3})\s*days?(?:\s*and\s*(\d{1,2})\s*hours?)?\s*"
    r"(?:left|before|remaining|to go)", re.I)


def countdown_deadline(text: str, today: date | None = None) -> str | None:
    """'18 days and 6 hours before deadline' → 마감 예정일."""
    m = _COUNTDOWN.search(text or "")
    if not m:
        return None
    days = int(m.group(1))
    if days > 400:
        return None
    return ((today or date.today()) + timedelta(days=days)).isoformat()


def render_cards(site: dict) -> list[dict]:
    """브라우저로 연 이벤트 탭에서 진행 중인 카드를 긁는다.

    링크가 없는 목록이 많아 URL 대신 제목으로 식별한다. 그래서 결과는
    반드시 사람 확인 큐로만 보낸다 (자동 등록 없음).
    """
    import render                                        # 선택 의존성이라 여기서 import

    html = render.render(site["url"], site.get("wait"))
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    for junk in soup(["script", "style", "svg"]):
        junk.decompose()

    marker = re.compile(site["marker"], re.I)
    found: list[str] = []
    for el in soup.find_all(True):
        # 카드 한 장 크기의 요소만 본다. 위로 올라갈수록 목록 전체가 잡힌다.
        if len(el.find_all(True)) > 30:
            continue
        txt = re.sub(r"\s+", " ", el.get_text(" ")).strip()
        if site.get("minLen", 12) < len(txt) < 400 and marker.search(txt):
            found.append(txt)

    # 같은 카드가 부모·자식 요소로 여러 번 잡힌다. 긴 것부터 담고,
    # 이미 담은 텍스트에 포함되는 조각은 버린다.
    seen: list[str] = []
    for txt in sorted(set(found), key=len, reverse=True):
        if not any(txt in k for k in seen):
            seen.append(txt)

    out = []
    for txt in seen:
        # 카드 텍스트는 '남은 기간 + 제목 + 상금' 순서가 뒤섞여 있다.
        # 카운트다운 구절을 걷어낸 나머지의 첫 문장을 제목으로 본다.
        body = marker.sub(" ", _COUNTDOWN.sub(" ", txt)).strip(" ·|-")
        body = re.sub(r"^\s*(and|hours?|to submit|deadline)\b", "", body, flags=re.I).strip()
        title = re.split(r"\s{2,}|·|\|", body)[0][:120].strip()
        if len(title) < 6:
            title = body[:120]
        if len(title) < 6:                    # 제목을 못 건진 조각은 버린다
            continue
        out.append({
            "brand": site["brand"],
            "url": site["url"],
            "title": title,
            "summary": txt[:400],
            "lastmod": "",
            "deadline": None,                 # 카운트다운은 짐작이라 확정값으로 쓰지 않는다
            "deadlineGuess": countdown_deadline(txt),
            "deadlineEvidence": txt[:200],
            "confidence": "medium" if countdown_deadline(txt) else "none",
            "cashUsd": prize_cash(txt),
            "credits": prize_credits(txt),
            "looksLikeResult": False,
            "cat": sources.classify_global_cat(title),
            "hasEventLD": False,
        })
    return out


def news_candidates(days: int = 30, per_query: int = 12) -> list[dict]:
    """Google 뉴스 RSS. 업체 사이트에 안 뜨는 건을 줍기 위한 보조 채널."""
    import urllib.parse as up

    out: dict[str, dict] = {}
    for q, hl, gl, ceid in NEWS_QUERIES + brand_news_queries():
        url = (f"https://news.google.com/rss/search?q={up.quote(q)}+when:{days}d"
               f"&hl={hl}&gl={gl}&ceid={up.quote(ceid)}")
        xml = sources.get(url)
        if not xml:
            continue
        for item in re.findall(r"<item>(.*?)</item>", xml, re.S)[:per_query]:
            t = re.search(r"<title>(.*?)</title>", item, re.S)
            link = re.search(r"<link>(.*?)</link>", item, re.S)
            pub = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S)
            if not (t and link):
                continue
            title = BeautifulSoup(t.group(1), "lxml").get_text().strip()
            if not re.search(r"challenge|contest|competition|award|공모|챌린지|대회", title, re.I):
                continue
            # 수상자 발표 기사는 이미 끝난 대회다
            if re.search(r"wins?|winners?|수상|우승", title, re.I):
                continue
            out[link.group(1).strip()] = {
                "title": title, "url": link.group(1).strip(),
                "pub": (pub.group(1)[:16] if pub else ""), "query": q,
            }
        time.sleep(sources.POLITE_DELAY)
    return list(out.values())


# ══════════════════════════════════════════════════════════════════════
#  상세 페이지에서 값 뽑기
# ══════════════════════════════════════════════════════════════════════
def _meta(soup: BeautifulSoup, *sels: str) -> str:
    for s in sels:
        tag = soup.select_one(s)
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def enrich(site: dict, url: str, lastmod: str = "") -> dict | None:
    """후보 URL 하나를 열어 제목·상금·마감일을 뽑는다."""
    html = sources.get(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    for junk in soup(["script", "style", "nav", "footer", "svg"]):
        junk.decompose()

    title = (_meta(soup, 'meta[property="og:title"]', 'meta[name="twitter:title"]')
             or (soup.title.get_text() if soup.title else "")).strip()
    desc = _meta(soup, 'meta[property="og:description"]', 'meta[name="description"]')
    text = re.sub(r"\s+", " ", soup.get_text(" "))[:20000]

    # JSON-LD Event 가 있으면 그게 가장 정확하다.
    # 단 Higgsfield 처럼 LD 가 실제 페이지와 어긋나는 곳이 있어서(끝난 날짜가
    # 그대로 남아 있는다) 이미 지난 endDate 는 믿지 않고 본문 파싱으로 돌아간다.
    events = sources.ld_find(sources.ld_blocks(html), "Event")
    ev = events[0] if events else None
    ld_end = ((ev.get("endDate") or "")[:10] if ev else "")

    deadline, evidence, conf = find_deadline(f"{title} {desc} {text}")
    if ld_end >= date.today().isoformat():
        deadline, evidence, conf = ld_end, "JSON-LD Event.endDate", "high"
    elif ld_end:
        evidence = f"(LD endDate {ld_end} 는 이미 지남 — 무시) {evidence}"

    # 확신이 없는 날짜는 deadline 에 넣지 않는다. 본문 아무 데나 있던 날짜를
    # 마감일로 올리면 D-day 가 조용히 틀린 채로 노출된다. 짐작값은 따로 남긴다.
    guess = None
    if conf != "high":
        guess, deadline = deadline, None

    cash = prize_cash(f"{title} {desc} {text}")
    credits = prize_credits(f"{title} {desc}")
    return {
        "brand": site["brand"],
        "url": url,
        "title": title[:160],
        "summary": (desc or text[:300]).strip()[:400],
        "lastmod": lastmod,
        "deadline": deadline,
        "deadlineGuess": guess,
        "deadlineEvidence": evidence[:200],
        "confidence": conf,
        "cashUsd": cash or 0,
        "credits": credits,
        # URL 은 공모처럼 생겼는데 실제로는 수상 소식인 글이 있다
        # ('…Win PixVerse Special Prize…'). 제목으로 한 번 더 거른다.
        "looksLikeResult": bool(re.search(
            r"wins?|winners?|수상|우승", f"{title}", re.I)),
        "cat": sources.classify_global_cat(f"{title} {desc}"),
        "hasEventLD": bool(ev),
    }


def slugify(brand: str, url: str) -> str:
    tail = urlparse(url).path.rstrip("/").split("/")[-1] or "item"
    return re.sub(r"\W+", "-", f"{brand}-{tail}").strip("-").lower()[:48]


def draft_record(site: dict, info: dict) -> dict:
    """manual.global.json 의 extra 에 그대로 붙여넣을 초안."""
    cash = info["cashUsd"]
    credits = info.get("credits", 0)
    verify = [] if (cash or credits) else ["prize"]
    if info["confidence"] != "high" or not info["deadline"]:
        verify.append("deadline")
    return {
        "id": slugify(site["brand"], info["url"]),
        "title": info["title"] or f"{site['brand']} 챌린지",
        "org": site.get("org", site["brand"]),
        "orgType": site.get("orgType", "플랫폼"),
        "orgTier": site.get("orgTier", "mid"),
        "cat": info["cat"],
        "deadline": info["deadline"],
        "tz": "현지",
        "recur": "once",
        "cash": cash,
        "credit": credits,
        "prizeText": (f"현금 약 ${cash:,}" if cash
                      else (f"플랫폼 크레딧 {credits:,}" if credits else "상금 정보는 공고 확인")),
        "who": "공고 확인 필요",
        "whoType": "전세계 누구나",
        "fee": site.get("fee", "free"),
        "feeText": site.get("feeText", "무료(확인 필요)"),
        "entry": "플랫폼 제출",
        "career": "platform",
        "bonus": [],
        "note": info["summary"],
        "url": info["url"],
        "tags": ["플랫폼"],
        "verify": verify,
    }
