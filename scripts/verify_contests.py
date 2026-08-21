#!/usr/bin/env python3
"""
목록에 올라간 공모전이 아직 살아 있는지 검수한다.

  python scripts/verify_contests.py                # 검수 → 리포트만
  python scripts/verify_contests.py --apply        # 확실히 끝난 건은 목록에서 내림
  python scripts/verify_contests.py --scope kr     # 국내 목록 검수 (기본 global)
  python scripts/verify_contests.py --no-cross     # 뉴스·대조표 확인 생략(빠름)

왜 필요한가
  마감일이 있는 대회는 날짜가 지나면 알아서 빠진다. 문제는 마감일을 못 넣은
  항목이다. `deadline: null` 이면 만료 판정에 걸리지 않아서, 작년에 끝난
  대회가 몇 달째 목록에 남는다. 실제로 OpenArt Music Video Awards(2026-01
  종료)와 PixVerse × UN AI for Good(2026-07 종료)이 그렇게 남아 있었다.

판정 방법 (센 순서)
  dead    페이지가 404 이거나 반복 실패
  ended   페이지의 JSON-LD Event.endDate 가 과거 /
          "winners announced" 류 문구 + 미래 일정 없음 /
          페이지에 적힌 가장 늦은 날짜가 이미 과거
  drift   페이지가 말하는 마감일이 우리 데이터와 다름 (자동 수정하지 않고 알림)
  unknown 페이지가 JS 셸이라 읽을 수 없음 → 우회 확인으로 넘어감

우회 확인 (--no-cross 로 끔)
  Kling·SeaArt·Vidu 처럼 로그인 뒤 JS로만 그려지는 곳은 공식 페이지를 읽을 수
  없다. 이때는 (1) melies.co AI 영화제 대조표의 같은 이름 항목, (2) 구글 뉴스
  RSS 의 해당 대회 기사(특히 '수상자 발표' 기사)로 상태를 짐작한다.

--apply 가 하는 일
  dead / ended 로 판정된 항목만 manual.*.json 의 block 에 넣고, 근거와 함께
  data/retired.json 으로 옮긴다. 되살리려면 block 에서 그 줄만 지우면 된다.
  drift·unknown 은 사람이 봐야 하므로 건드리지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
import sources                                             # noqa: E402
import watchlist                                           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TODAY = date.today()
TODAY_S = TODAY.isoformat()

SCOPES = {
    "global": {"js": "global.js", "var": "GLOBAL_DATA", "manual": "manual.global.json"},
    "kr":     {"js": "kr.js",     "var": "KR_DATA",     "manual": "manual.kr.json"},
}

# 페이지가 이 정도도 안 되면 JS 셸로 본다 (본문이 안 내려온 것)
READABLE_MIN = 400

ENDED_PAT = re.compile(
    r"winners? (?:have been |were |are )?announced|winners? announcement|"
    r"(?:contest|challenge|competition|festival|event|submissions?) (?:has |have )?"
    r"(?:now )?(?:ended|closed|concluded)|entries? (?:are )?closed|"
    r"no longer accepting|thanks? (?:to )?everyone who (?:entered|participated)|"
    r"종료(?:되었|됐|합니다)|마감되었|접수가 종료", re.I)

# 마감일을 못 넣은 단발성 항목이 이 기간을 넘기면 '오래된 것'으로 본다
STALE_DAYS = 45


def load_bundle(js_name: str) -> dict:
    p = DATA / js_name
    if not p.exists():
        raise SystemExit(f"{p} 가 없습니다. 먼저 update_contests.py 를 실행하세요.")
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", p.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit(f"{p} 파싱 실패")
    return json.loads(m.group(1))


def norm(t: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (t or "").lower())


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for junk in soup(["script", "style", "svg"]):
        junk.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" "))


def page_dates(text: str, dated_only: bool = True) -> list[date]:
    """페이지에 적힌 날짜들.

    dated_only=True 면 '연도까지 적힌' 날짜만 센다. 검수에서는 이게 중요하다.
    'Nov 17 - Nov 30' 처럼 연도가 없는 표기는 파서가 '가장 가까운 미래'로
    채우기 때문에, 작년에 끝난 페이지가 미래 일정이 있는 것처럼 보인다.
    실제로 2026-01 에 끝난 OpenArt Music Video Awards 가 이것 때문에
    '살아 있음'으로 통과했다.
    """
    return [d for _, d, y in watchlist.date_candidates(text, TODAY) if y or not dated_only]


# ══════════════════════════════════════════════════════════════════════
#  1차 — 공식 페이지 확인
# ══════════════════════════════════════════════════════════════════════
def fetch_with_status(url: str) -> tuple[int | None, str | None]:
    """(HTTP 상태코드, 본문). 상태코드를 봐야 '없어진 페이지'와 '봇 차단'을 가른다.

    sources.get 은 둘 다 None 을 돌려줘서 구분이 안 된다. FilmFreeway 가
    403 을 주는데 이걸 404 로 오해하면 살아 있는 영화제 13건을 목록에서
    내려 버린다 (실제로 첫 검수에서 그럴 뻔했다).
    """
    import requests
    for attempt in range(2):
        try:
            r = requests.get(url, headers=sources.UA, timeout=sources.TIMEOUT)
            return r.status_code, (r.text if r.ok else None)
        except requests.RequestException:
            if attempt:
                return None, None
            time.sleep(1.5)
    return None, None


def check_page(rec: dict, use_render: bool = True, is_hub: bool = False) -> dict:
    url = rec.get("url") or ""
    if not url.startswith("http"):
        return {"status": "unknown", "why": "URL 없음", "readable": False}

    code, html = fetch_with_status(url)
    if code in (404, 410):
        return {"status": "dead", "why": f"페이지 없음 (HTTP {code})", "readable": False}

    via_render = False
    text = page_text(html) if html else ""

    # requests 로 막히거나(403) 앱 셸만 온 경우 브라우저로 다시 열어 본다.
    # NightCafe·Kling 처럼 이 단계에서야 내용이 보이는 곳이 많다.
    if use_render and (html is None or len(text) < READABLE_MIN):
        import render
        rendered = render.render(url)
        if rendered and len(page_text(rendered)) > max(len(text), READABLE_MIN):
            html, text, via_render = rendered, page_text(rendered), True

    if html is None:
        why = (f"페이지를 못 읽음 (HTTP {code})" if code
               else "페이지 응답 없음 (연결 실패·타임아웃)")
        # 403·429·5xx 는 '사라진 것'이 아니라 '막힌 것'이다. 내리면 안 된다.
        return {"status": "blocked", "why": why, "readable": False, "httpStatus": code}

    readable = len(text) >= READABLE_MIN
    out: dict = {"status": "live", "why": "", "readable": readable,
                 "pageDeadline": None, "textLen": len(text), "viaRender": via_render}

    # JSON-LD Event. 정확할 때가 많지만 Higgsfield 처럼 끝난 회차의 날짜를
    # 그대로 두는 곳이 있어서, 과거 endDate 하나만으로 종료라고 하지 않는다.
    ld_past = None
    for ev in sources.ld_find(sources.ld_blocks(html), "Event"):
        end = (ev.get("endDate") or "")[:10]
        if not end:
            continue
        if end < TODAY_S:
            ld_past = end
        else:
            out["pageDeadline"] = end

    if not readable:
        return {**out, "status": "unknown",
                "why": (f"본문이 안 내려옴(JS 렌더 추정, 텍스트 {len(text)}자)"
                        + (f" · LD endDate {ld_past}(과거)" if ld_past else ""))}

    dated = page_dates(text)                       # 연도까지 적힌 날짜만
    once = rec.get("recur", "once") == "once"
    stored = rec.get("deadline")

    # 마감 단서('closes', 'deadline') 뒤에 붙은 날짜. 연도가 없어도 여기서는 센다.
    dl, evidence, conf = watchlist.find_deadline(text)
    if conf in ("high", "medium"):
        out["pageDeadline"] = out["pageDeadline"] or dl
        out["evidence"] = evidence[:160]
        out["confidence"] = conf

    # '살아 있다'는 신호: 연도 명시된 미래 날짜 또는 마감 단서가 가리키는 미래 날짜.
    # 이게 하나라도 있으면 종료 판정을 하지 않는다. Higgsfield 영화제는
    # 타임라인을 'Competition closes Sep 3' 처럼 연도 없이 적는데, 연도 명시
    # 날짜만 세면 1,000,000달러짜리 진행 중 대회가 종료로 잡힌다.
    past_evidence = bool(dated) and max(dated) < TODAY
    # 연도가 추정된 값(medium)은 페이지의 명시 날짜가 전부 과거일 때는 믿지 않는다.
    # PixVerse × UN 페이지가 'July 7-10, 2026' 을 'July 7' + 연도추정 2027 로
    # 읽혀서, 이미 끝난 행사가 살아 있는 것처럼 통과했다.
    cue_future = bool(dl) and dl >= TODAY_S and (
        conf == "high" or (conf == "medium" and not past_evidence))
    future_signal = [d for d in dated if d >= TODAY] or cue_future
    ended_hit = ENDED_PAT.search(text)

    # 허브 페이지는 다른 대회의 날짜가 섞여 있어 '마지막 날짜' 논리를 쓸 수 없다.
    # 종료 문구가 직접 있을 때만 끝난 것으로 본다.
    if is_hub and not ended_hit:
        return out
    if not future_signal and (past_evidence or ld_past):
        why = (f"JSON-LD Event.endDate {ld_past} (과거)" if ld_past and not past_evidence
               else f"페이지의 마지막 날짜가 {max(dated).isoformat()} (이미 과거)")
        if ended_hit:
            why += f" · 종료 문구 '{ended_hit.group(0)[:30]}'"
        if not once:
            # 반복 대회 공지 글에 미래 날짜가 없는 건 정상이다.
            return {**out, "status": "unknown", "why": f"반복 대회 · {why}"}
        if stored and stored >= TODAY_S and not ended_hit:
            # 우리 데이터는 아직 안 끝났다고 하는데 페이지에는 근거가 없다.
            # 둘 중 하나가 틀렸다 — 자동으로 내리지 않고 사람에게 넘긴다.
            return {**out, "status": "suspect",
                    "why": f"{why} · 그런데 우리 데이터 마감일은 {stored}"}
        return {**out, "status": "ended", "why": why}

    if ld_past:
        out["ldPastIgnored"] = ld_past

    # URL 이 사이트 루트(집계 사이트 첫 화면 등)면 그 페이지의 날짜는
    # 이 대회의 마감일이 아니다. 불일치 판정에서 뺀다.
    # 사이트 루트나 여러 대회가 한 화면에 있는 허브(Dreamina 이벤트 탭 등)는
    # 페이지에서 뽑은 날짜가 '이 대회의' 마감일이라는 보장이 없다.
    is_root = urlparse(url).path.strip("/") == "" or is_hub
    stored = rec.get("deadline")
    if stored and out.get("pageDeadline") and out["pageDeadline"] != stored and not is_root:
        gap = abs((date.fromisoformat(out["pageDeadline"]) - date.fromisoformat(stored)).days)
        # 연도가 없는 표기('deadline April 20')는 파서가 연도를 채운 값이라
        # 반년 넘게 벌어지면 십중팔구 연도 추측이 틀린 것이다. 알림을 흐리게
        # 만드는 대신 조용히 넘긴다. 연도가 명시된 값은 차이와 무관하게 알린다.
        if out.get("confidence") == "high" or gap <= 120:
            return {**out, "status": "drift",
                    "why": (f"우리 데이터 {stored} ↔ 페이지 {out['pageDeadline']}"
                            f" (페이지 값 신뢰도 {out.get('confidence', 'ld')})")}
        out["driftIgnored"] = f"{out['pageDeadline']} (연도 추정값 · {gap}일 차이)"

    if not stored and not out.get("pageDeadline"):
        return {**out, "status": "unknown", "why": "페이지에서 마감일을 못 찾음"}

    return out


# ══════════════════════════════════════════════════════════════════════
#  2차 — 우회 확인 (제3자 기록)
# ══════════════════════════════════════════════════════════════════════
def cross_melies(title: str, index: list[dict]) -> dict | None:
    nt = norm(title)
    best, score = None, 0.0
    for row in index:
        s = SequenceMatcher(None, nt, norm(row["name"])).ratio()
        if s > score:
            best, score = row, s
    # 0.72 로 뒀더니 'Naija AI Film Festival' 이 'Astana AI Film Festival' 에
    # 붙었다. AI·Film·Festival 처럼 흔한 낱말이 대부분이라 유사도가 쉽게 뜬다.
    # 그래서 고유 낱말(브랜드·지명)이 겹치는지도 같이 본다.
    if not best or score < 0.80:
        return None
    common = {"ai", "film", "festival", "awards", "award", "contest", "challenge",
              "international", "competition", "2025", "2026", "2027", "the"}
    a = {w for w in re.findall(r"[a-z가-힣]+", title.lower()) if w not in common}
    b = {w for w in re.findall(r"[a-z가-힣]+", best["name"].lower()) if w not in common}
    if a and b and not (a & b):
        return None
    end = best.get("end") or ""
    return {
        "source": "melies.co",
        "match": best["name"],
        "similarity": round(score, 2),
        "end": end,
        "verdict": "ended" if end and end < TODAY_S else "live",
        "url": best["url"],
    }


def cross_news(title: str, days: int = 120) -> dict | None:
    """대회 이름으로 기사를 찾아 본다. '수상자 발표' 기사는 종료 근거가 된다."""
    q = re.sub(r"[^\w가-힣 ]", " ", title)[:70].strip()
    if len(q) < 6:
        return None
    url = (f"https://news.google.com/rss/search?q={quote(q)}+when:{days}d"
           "&hl=en-US&gl=US&ceid=US:en")
    xml = sources.get(url)
    if not xml:
        return None
    hits = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S)[:8]:
        t = re.search(r"<title>(.*?)</title>", item, re.S)
        link = re.search(r"<link>(.*?)</link>", item, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S)
        if not (t and link):
            continue
        headline = BeautifulSoup(t.group(1), "lxml").get_text().strip()
        # 제목이 실제로 겹치는 기사만 (구글은 느슨하게 매칭해 준다)
        if SequenceMatcher(None, norm(title), norm(headline)).ratio() < 0.55 and \
                norm(title)[:22] not in norm(headline):
            continue
        hits.append({"headline": headline, "url": link.group(1).strip(),
                     "pub": (pub.group(1)[:16] if pub else "")})
    if not hits:
        return None
    ended = next((h for h in hits if ENDED_PAT.search(h["headline"])), None)
    return {
        "source": "google-news",
        "verdict": "ended" if ended else "seen",
        "headline": (ended or hits[0])["headline"],
        "url": (ended or hits[0])["url"],
        "pub": (ended or hits[0])["pub"],
        "count": len(hits),
    }


# ══════════════════════════════════════════════════════════════════════
#  검수
# ══════════════════════════════════════════════════════════════════════
def verify_all(records: list[dict], cross: bool, state: dict,
               use_render: bool = True) -> list[dict]:
    melies = sources.fetch_melies_index() if cross else []
    # 두 개 이상의 대회가 같은 URL 을 쓰면 그건 목록(허브) 페이지다.
    counts: dict[str, int] = {}
    for r in records:
        counts[r.get("url", "")] = counts.get(r.get("url", ""), 0) + 1
    hub_urls = {u for u, c in counts.items() if c > 1 and u}
    results = []

    for i, rec in enumerate(records, 1):
        rid = rec.get("id", "")
        res = check_page(rec, use_render=use_render, is_hub=rec.get("url") in hub_urls)
        res.update({"id": rid, "title": rec.get("title", ""), "url": rec.get("url", ""),
                    "source": rec.get("source", "?"), "deadline": rec.get("deadline"),
                    "recur": rec.get("recur", "once"), "cross": []})

        if cross and res["status"] in ("unknown", "dead", "blocked"):
            for fn in (lambda: cross_melies(rec.get("title", ""), melies),
                       lambda: cross_news(rec.get("title", ""))):
                got = fn()
                if got:
                    res["cross"].append(got)
                    if got["verdict"] == "ended":
                        res["status"] = "ended"
                        res["why"] = f"{got['source']} 기준 종료 ({got.get('end') or got.get('headline','')[:50]})"

        # 마감일 없는 단발성 항목은 오래 두지 않는다
        first = state.get(rid, {}).get("firstSeen", TODAY_S)
        age = (TODAY - date.fromisoformat(first)).days
        if (res["status"] in ("unknown", "live") and not rec.get("deadline")
                and rec.get("recur", "once") == "once" and age >= STALE_DAYS):
            res["status"] = "stale"
            res["why"] = f"마감일 미상인 단발 대회가 {age}일째 목록에 있음 (최초 확인 {first})"

        state.setdefault(rid, {})["firstSeen"] = first
        state[rid].update({"checkedAt": TODAY_S, "status": res["status"]})
        results.append(res)
        print(f"  [{i:>2}/{len(records)}] {res['status']:8} {rec.get('title','')[:52]}"
              + (f"  — {res['why'][:60]}" if res["why"] else ""))
    return results


def apply_retirements(scope: str, results: list[dict], dry: bool) -> int:
    """dead / ended 항목을 manual block 으로 내리고 retired.json 에 보관."""
    doomed = [r for r in results if r["status"] in ("dead", "ended")]
    if not doomed:
        return 0

    mpath = DATA / SCOPES[scope]["manual"]
    manual = json.loads(mpath.read_text(encoding="utf-8"))
    already = set(manual.get("block", []))
    new_ids = [r["id"] for r in doomed if r["id"] not in already]

    retired_path = DATA / "retired.json"
    retired = (json.loads(retired_path.read_text(encoding="utf-8"))
               if retired_path.exists() else {"_readme": [
                   "검수기가 '끝났다'고 판정해 목록에서 내린 대회 기록.",
                   "되살리려면 manual.*.json 의 block 에서 해당 id 를 지우세요.",
               ], "items": []})

    known = {i["id"] for i in retired["items"]}
    for r in doomed:
        if r["id"] in known:
            continue
        retired["items"].append({
            "id": r["id"], "title": r["title"], "url": r["url"],
            "source": r["source"], "retiredAt": TODAY_S,
            "reason": r["status"], "why": r["why"], "cross": r.get("cross", []),
        })

    if dry:
        print(f"  (dry-run) {len(doomed)}건 내림 처리 미기록")
        return len(doomed)

    if new_ids:
        # manual.*.json 은 사람이 손으로 관리하는 파일이라 통째로 다시 쓰지 않는다.
        # json.dumps 로 덮으면 한 줄에 여러 키를 담은 원래 서식이 전부 풀려서
        # 실제 변경 두 줄이 400줄짜리 diff 로 보인다. block 배열만 손댄다.
        src = mpath.read_text(encoding="utf-8")
        added = ",\n".join(f'  "{i}"' for i in new_ids)
        if re.search(r'"block"\s*:\s*\[\s*\]', src):
            src = re.sub(r'"block"\s*:\s*\[\s*\]', '"block": [\n' + added + "\n ]", src, count=1)
        else:
            src = re.sub(r'("block"\s*:\s*\[)', r"\1\n" + added + ",", src, count=1)
        json.loads(src)                       # 깨뜨리지 않았는지 확인하고 쓴다
        mpath.write_text(src, encoding="utf-8")
    retired_path.write_text(json.dumps(retired, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  → {mpath.name} block {len(new_ids)}건 추가 · retired.json {len(doomed)}건 기록")
    return len(doomed)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=list(SCOPES), default="global")
    ap.add_argument("--apply", action="store_true",
                    help="dead/ended 항목을 목록에서 내린다 (drift·unknown 은 건드리지 않음)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-cross", action="store_true", help="뉴스·대조표 우회 확인 생략")
    ap.add_argument("--no-render", action="store_true",
                    help="막히거나 JS 셸인 페이지를 브라우저로 다시 열지 않음 (빠름)")
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N건만 검수 (시험용)")
    args = ap.parse_args()

    cfg = SCOPES[args.scope]
    bundle = load_bundle(cfg["js"])
    records = bundle["contests"][:args.limit] if args.limit else bundle["contests"]
    print(f"공모전 검수 · {args.scope} {len(records)}건 · 기준일 {TODAY_S}\n")

    state_path = DATA / "verify.state.json"
    state_doc = (json.loads(state_path.read_text(encoding="utf-8"))
                 if state_path.exists() else {"records": {}})
    state = state_doc.setdefault("records", {})

    results = verify_all(records, cross=not args.no_cross, state=state,
                         use_render=not args.no_render)

    tally: dict[str, int] = {}
    for r in results:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    print("\n── 결과 ──", " · ".join(f"{k} {v}" for k, v in sorted(tally.items())))

    for kind, label in (("dead", "죽은 링크"), ("ended", "종료된 대회"),
                        ("suspect", "끝난 것 같음 · 사람 확인 필요"),
                        ("blocked", "봇 차단 · 확인 못 함"),
                        ("drift", "마감일 불일치"), ("stale", "오래 방치된 항목"),
                        ("unknown", "확인 불가")):
        rows = [r for r in results if r["status"] == kind]
        if not rows:
            continue
        print(f"\n[{label}] {len(rows)}건")
        for r in rows:
            print(f"  · {r['title'][:60]}")
            print(f"    {r['why']}")
            print(f"    {r['url'][:100]}")
            for c in r.get("cross", []):
                print(f"    ↳ {c['source']}: {c.get('match') or c.get('headline','')[:60]}"
                      f" ({c['verdict']})")

    retired = 0
    if args.apply:
        retired = apply_retirements(args.scope, results, args.dry_run)

    if not args.dry_run:
        state_doc["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        state_path.write_text(json.dumps(state_doc, ensure_ascii=False, indent=1),
                              encoding="utf-8")

    report = DATA / f"verify.report.{args.scope}.json"
    payload = {
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": args.scope,
        "tally": tally,
        "retired": retired,
        "results": results,
    }
    if not args.dry_run:
        report.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n  → {report.relative_to(ROOT)} 기록")

    if args.apply and retired:
        print("\n※ 목록에 반영하려면 `python scripts/update_contests.py` 를 다시 실행하세요.")
    print("\n완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
