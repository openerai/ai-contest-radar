#!/usr/bin/env python3
"""
AI 플랫폼 챌린지 감시 실행기.

  python scripts/watch_challenges.py               # 새 챌린지 탐색 → 리포트 + 큐 갱신
  python scripts/watch_challenges.py --seed        # 첫 실행: 지금 있는 URL을 '봤음'으로만 기록
  python scripts/watch_challenges.py --dry-run     # 파일 안 쓰고 결과만 출력
  python scripts/watch_challenges.py --no-news     # 구글 뉴스 채널 끄기

만드는 파일
  data/watch.state.json   한 번이라도 본 URL. 같은 걸 매주 다시 알리지 않기 위한 기억.
  data/review.queue.json  사람이 확인해야 할 후보. 확인 끝난 항목은 여기서 지운다.

사람이 할 일 (한 건당 30초)
  1. review.queue.json 의 url 을 열어 마감일·상금·참가 조건을 확인
  2. 같은 항목의 draft 를 data/manual.global.json 의 "extra" 로 옮기고 값 수정
  3. review.queue.json 에서 그 항목을 지우거나 "status": "done" 으로 표시
  4. python scripts/update_contests.py 실행

큐에 남은 항목은 마감일이 지나면 다음 실행 때 자동으로 빠진다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sources                                             # noqa: E402
import watchlist                                           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATE = DATA / "watch.state.json"
QUEUE = DATA / "review.queue.json"
TODAY = date.today().isoformat()


def norm_title(t: str) -> str:
    """중복 판정용 제목 정규화 (update_contests.py 와 같은 규칙)."""
    return re.sub(r"[^0-9a-z가-힣]", "", (t or "").lower())


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  ! {path.name} JSON 오류: {e} — 기본값으로 시작합니다")
        return default


def save_json(path: Path, payload: dict, dry: bool) -> None:
    if dry:
        print(f"  (dry-run) {path.name} 미기록")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  → {path.relative_to(ROOT)} 기록")


def still_open(item: dict) -> bool:
    """마감일이 지났으면 큐에서 뺀다. 마감일을 못 뽑은 건은 30일간 남긴다."""
    if item.get("status") in ("done", "dismissed"):
        return False
    dl = (item.get("draft") or {}).get("deadline")
    if dl:
        return dl >= TODAY
    seen = item.get("discovered", TODAY)
    return (date.fromisoformat(TODAY) - date.fromisoformat(seen)).days <= 30


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true",
                    help="현재 URL을 모두 '봤음'으로만 기록하고 리포트하지 않음")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=180,
                    help="사이트맵 lastmod 기준 이 기간 안의 글만 후보로 봄")
    ap.add_argument("--max-new", type=int, default=25,
                    help="한 번에 상세 페이지를 열어볼 최대 건수")
    ap.add_argument("--no-news", action="store_true", help="구글 뉴스 채널 끄기")
    args = ap.parse_args()

    print(f"AI 플랫폼 챌린지 감시 · 기준일 {TODAY}")

    state = load_json(STATE, {"seen": {}})
    seen: dict = state.setdefault("seen", {})
    queue_doc = load_json(QUEUE, {"items": []})
    old_items = [i for i in queue_doc.get("items", []) if still_open(i)]
    dropped = len(queue_doc.get("items", [])) - len(old_items)

    # ── 1. 업체별 탐색 ────────────────────────────────────────────────
    fresh: list[tuple[dict, str, str]] = []          # (site, url, lastmod)
    for site in watchlist.PLATFORMS:
        found = watchlist.discover(site, days=args.days)
        new = [(u, lm) for u, lm in found if u not in seen]
        print(f" · {site['brand']:12} 후보 {len(found):3}건 · 신규 {len(new)}건")
        for u, lm in new:
            fresh.append((site, u, lm))

    # ── 2. 새 URL 만 상세 확인 ────────────────────────────────────────
    added: list[dict] = []
    # 같은 대회가 랜딩페이지·블로그·번역판으로 여러 번 잡힌다. 제목 기준으로 한 번만 큐에 넣는다.
    known_titles = {norm_title(i.get("title", "")) for i in old_items}
    if args.seed:
        print(f"\n[seed] 신규 {len(fresh)}건을 확인 없이 '봤음' 처리합니다")
    else:
        for site, url, lastmod in fresh[:args.max_new]:
            info = watchlist.enrich(site, url, lastmod)
            if not info:
                continue
            # 커뮤니티 글이 섞여 들어오는 소스(Civitai)는 상금이나 마감일 중
            # 하나라도 잡힌 것만 큐에 올린다. 안 그러면 잡담이 큐를 덮는다.
            if site.get("noisy") and not (
                    info["cashUsd"] or info["confidence"] in ("high", "medium")):
                seen[url] = {"first": TODAY, "brand": site["brand"], "skipped": "noisy"}
                continue
            nt = norm_title(info["title"])
            if nt and nt in known_titles:
                seen[url] = {"first": TODAY, "brand": site["brand"], "dup": True}
                continue
            known_titles.add(nt)
            item = {
                "discovered": TODAY,
                "brand": site["brand"],
                "url": url,
                "title": info["title"],
                "deadline": info["deadline"],
                "deadlineGuess": info["deadlineGuess"],
                "deadlineEvidence": info["deadlineEvidence"],
                "confidence": info["confidence"],
                "cashUsd": info["cashUsd"],
                "status": "new",
                "draft": watchlist.draft_record(site, info),
            }
            added.append(item)
        if len(fresh) > args.max_new:
            print(f"  · 신규 {len(fresh)}건 중 {args.max_new}건만 확인 "
                  f"(나머지는 다음 실행에서 — --max-new 로 조절)")

    for site, url, lastmod in fresh:
        # max-new 로 잘린 건은 아직 안 봤으므로 기억하지 않는다
        if args.seed or any(a["url"] == url for a in added):
            seen[url] = {"first": TODAY, "brand": site["brand"]}

    # ── 3. 뉴스 채널 ──────────────────────────────────────────────────
    news_new: list[dict] = []
    if not args.no_news and not args.seed:
        for n in watchlist.news_candidates():
            if n["url"] in seen:
                continue
            seen[n["url"]] = {"first": TODAY, "brand": "news"}
            news_new.append({**n, "discovered": TODAY})
        print(f" · 뉴스 채널 신규 {len(news_new)}건")
    # 지난 실행에서 올라온 기사도 30일간 같이 남겨 둔다 (아직 안 봤을 수 있으니)
    cutoff = (date.fromisoformat(TODAY) - timedelta(days=30)).isoformat()
    kept_news = [n for n in queue_doc.get("news", [])
                 if n.get("discovered", TODAY) >= cutoff
                 and n["url"] not in {x["url"] for x in news_new}]
    news_all = news_new + kept_news

    # ── 4. 기록 ──────────────────────────────────────────────────────
    items = old_items + added
    state["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state["seenCount"] = len(seen)
    save_json(STATE, state, args.dry_run)
    save_json(QUEUE, {
        "_readme": [
            "scripts/watch_challenges.py 가 찾은, 사람 확인이 필요한 AI 플랫폼 챌린지 후보.",
            "url 을 열어 마감일·상금·참가 조건을 확인한 뒤 draft 를",
            "data/manual.global.json 의 extra 로 옮기세요. 그리고 여기서는 지우거나",
            "\"status\": \"done\" 으로 표시하면 다음 실행 때 빠집니다.",
            "마감일이 지난 항목, 마감일을 못 뽑은 채 30일이 지난 항목은 자동으로 빠집니다.",
        ],
        "updatedAt": state["updatedAt"],
        "items": items,
        "news": news_all,
    }, args.dry_run)

    # ── 5. 리포트 ────────────────────────────────────────────────────
    print(f"\n── 결과 ── 신규 {len(added)}건 · 큐 유지 {len(old_items)}건 "
          f"(만료 {dropped}건 제거) · 누적 확인 URL {len(seen)}개")
    for it in added:
        dl = it["deadline"] or (f"{it['deadlineGuess']}(짐작)" if it["deadlineGuess"] else "미상")
        mark = "✓" if it["confidence"] == "high" else "?"
        cash = f"${it['cashUsd']:,}" if it["cashUsd"] else "상금 미상"
        print(f"\n  [{it['brand']}] {it['title'][:70]}")
        print(f"    마감 {dl} {mark} · {cash}")
        print(f"    {it['url']}")
        if it["deadlineEvidence"]:
            print(f"    근거: …{it['deadlineEvidence'][:110]}…")
    if news_new:
        print("\n  ── 뉴스에서 잡힌 것 (직접 확인) ──")
        for n in news_new[:12]:
            print(f"    · {n['title'][:90]}\n      {n['url'][:110]}")

    print("\n  ── 자동 감시 불가 · 직접 확인 ──")
    for brand, url, why in watchlist.MANUAL_CHECK:
        print(f"    · {brand:12} {url:38} ({why})")

    if sources.WARNINGS:
        print(f"\n경고 {len(sources.WARNINGS)}건:")
        for w in sources.WARNINGS:
            print("  -", w)

    print("\n완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
