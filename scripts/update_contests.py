#!/usr/bin/env python3
"""
AI 공모전 레이더 데이터 갱신기.

  python scripts/update_contests.py            # 수집 → data/*.js 갱신
  python scripts/update_contests.py --dry-run  # 파일 안 쓰고 결과만 출력

동작
  1. 각 소스를 긁는다 (한 소스가 죽어도 나머지는 진행)
  2. data/manual.*.json 의 사람 데이터를 덮어씌운다
       overrides : 자동 수집 항목의 특정 필드를 사람 값으로 교체
       extra     : 자동으로는 못 잡는 항목을 통째로 추가 (플랫폼 이벤트 등)
       block     : 목록에서 제외할 id
  3. 마감 지난 항목 제거 (반복·상시 항목은 유지)
  4. 안전장치: 자동 수집량이 직전 대비 절반 미만이면 파일을 쓰지 않고 실패
  5. data/kr.js, data/global.js 로 출력 (JSON이 아니라 JS인 이유는 아래 참고)

왜 .json 이 아니라 .js 인가
  브라우저는 file:// 에서 fetch()로 로컬 JSON을 못 읽는다(CORS).
  <script src="data/kr.js"> 는 file:// 에서도 되고 GitHub Pages 에서도 된다.
  즉 이 파일 하나로 "더블클릭해서 열기"와 "웹에 배포하기"가 모두 성립한다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sources                                             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TODAY = date.today().isoformat()

# 자동 수집량이 직전 실행의 이 비율 미만이면 → 사이트 구조가 깨진 것으로 보고 중단
SANITY_RATIO = 0.5


def norm_title(t: str) -> str:
    """중복 판정용 제목 정규화."""
    t = re.sub(r"[^0-9a-z가-힣]", "", (t or "").lower())
    return t


def load_manual(name: str) -> dict:
    p = DATA / name
    if not p.exists():
        print(f"  · {name} 없음 — 수동 데이터 없이 진행")
        return {"extra": [], "overrides": {}, "block": []}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  ! {name} JSON 오류: {e}")
        raise
    d.setdefault("extra", [])
    d.setdefault("overrides", {})
    d.setdefault("block", [])
    return d


def prev_meta(js_path: Path) -> dict:
    """직전 생성 파일에서 _meta 를 되읽어 자동 수집량 비교에 쓴다."""
    if not js_path.exists():
        return {}
    m = re.search(r"=\s*(\{.*\})\s*;?\s*$", js_path.read_text(encoding="utf-8"), re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1)).get("_meta", {})
    except json.JSONDecodeError:
        return {}


def merge(auto: list[dict], manual: dict) -> list[dict]:
    """자동 수집 결과에 사람이 관리하는 값을 얹는다.

    overrides 의 키는 자동 수집 id("wevity-109144") 또는 공모전 제목 둘 다 된다.
    자동 id 는 사이트가 글 번호를 바꾸면 흔들리므로, 평소에는 제목으로 거는
    편이 안전하다. 제목은 공백·기호를 무시하고 비교한다.
    """
    blocked = set(manual["block"]) | {norm_title(b) for b in manual["block"]}
    manual_titles = {norm_title(x.get("title", "")) for x in manual["extra"]}
    manual_ids = {x.get("id") for x in manual["extra"]}

    merged: list[dict] = []
    for rec in auto:
        nt = norm_title(rec.get("title", ""))
        if rec["id"] in blocked or nt in blocked or rec["id"] in manual_ids:
            continue
        if nt in manual_titles:                    # 수동 항목이 이미 다루는 대회
            continue
        merged.append(rec)

    for rec in manual["extra"]:
        if rec.get("id") in blocked or norm_title(rec.get("title", "")) in blocked:
            continue
        merged.append({**rec, "source": rec.get("source", "manual")})
    return merged


def apply_overrides(records: list[dict], overrides: dict) -> list[dict]:
    """사람이 확인한 값을 덮어씌운다.

    반드시 dedupe() '이후' 에 부른다. 중복 제거 전에 걸면, 오버라이드가 붙은
    레코드가 중복 통합에서 밀려나고 다른 소스의 값이 살아남는 일이 생긴다.
    (실제로 NHN 해커톤에서 링커리어의 '3억 5000만 원' 이 보도자료 기준
     8,000만원을 덮어써 버렸다.)
    """
    ov_by_title = {norm_title(k): v for k, v in overrides.items()}
    used: set[str] = set()

    for rec in records:
        nt = norm_title(rec.get("title", ""))
        key = rec["id"] if rec["id"] in overrides else (nt if nt in ov_by_title else None)
        if key is None:
            # 부분 포함으로도 한 번 찾아본다 (소스마다 회차·괄호 표기가 달라서)
            for ok, ov in ov_by_title.items():
                if len(ok) >= 8 and (ok in nt or nt in ok):
                    key, patch = ok, ov
                    break
            else:
                continue
        patch = overrides.get(key) or ov_by_title[key]
        used.add(key)
        rec.update(patch)
        rec["overridden"] = True
        # 사람이 정확한 총상금을 넣어줬다면 자동 수집의 '구간' 표시는 버린다
        if "prizeTotal" in patch and "prizeApprox" not in patch:
            rec["prizeApprox"] = False
            rec.pop("prizeMin", None)
            rec.pop("prizeMax", None)

    stale = [k for k in overrides
             if k not in used and norm_title(k) not in used]
    if stale:
        print(f"  · 적용되지 않은 override {len(stale)}개 "
              f"(대회가 끝났거나 제목이 바뀜): "
              + ", ".join(stale[:5]) + ("…" if len(stale) > 5 else ""))
    return records


# 같은 공모전이 여러 소스에 뜰 때 어느 쪽 레코드를 남길지 정하는 기준
SOURCE_RANK = {
    "manual": 100,          # 사람이 확인한 값이 항상 우선
    "linkareer": 30,        # 시상규모가 정확한 금액이라 위비티보다 낫다
    "wevity": 20,           # 상금은 구간이지만 접수기간·공식 URL이 정확
    "aifilmcontests": 20,
    "devpost": 20,          # 마감일·상금이 API 값이라 정확하다
    "melies": 12,           # 디렉터리라 상금·참가비가 없다. 이름·날짜만 믿는다
    "higgsfield": 15,
    "aifactory": 10,
}


def quality(r: dict) -> int:
    """레코드의 정보 충실도. 중복일 때 높은 쪽을 남긴다."""
    q = SOURCE_RANK.get(r.get("source", ""), 0)
    if r.get("prizeTotal") is not None or r.get("cash"):
        q += 15 if r.get("prizeApprox") else 40
    if r.get("start"):
        q += 5
    if r.get("deadline"):
        q += 5
    q -= 5 * len(r.get("verify") or [])
    return q


def same_contest(a: dict, b: dict) -> bool:
    """제목이 같거나 한쪽이 다른 쪽을 포함하면 같은 공모전으로 본다.

    '[NHN] 게임 X AI 해커톤 (NAN2026)' 과 'NHN 게임 X AI 해커톤' 처럼 소스마다
    대괄호·회차 표기가 붙는 경우를 잡기 위한 것. 포함 관계만으로는 우연히
    겹칠 수 있어서 마감일이 3일 이내로 붙어 있을 때만 인정한다.
    """
    na, nb = norm_title(a.get("title", "")), norm_title(b.get("title", ""))
    if not na or not nb:
        return False
    if na == nb:
        return True
    if len(na) < 8 or len(nb) < 8:
        return False
    da, db = a.get("deadline"), b.get("deadline")

    if na in nb or nb in na:
        if not da or not db:
            return True
        try:
            gap = abs((date.fromisoformat(da) - date.fromisoformat(db)).days)
        except ValueError:
            return True
        return gap <= 3

    # 포함 관계는 아니지만 거의 같은 제목인 경우.
    # ('2026 포항시…' vs '2026년 포항시…' 처럼 소스마다 조사·표기가 조금 다름)
    # 오탐이 나면 서로 다른 대회가 하나로 합쳐지므로, 마감일이 완전히 같을
    # 때만 그리고 유사도 0.9 이상일 때만 인정한다.
    if not da or da != db:
        return False
    return SequenceMatcher(None, na, nb).ratio() >= 0.90


def dedupe(records: list[dict]) -> tuple[list[dict], int]:
    """중복 제거. 충실도가 높은 쪽을 남기되, 비어 있는 필드는 진 쪽에서 채운다."""
    kept: list[dict] = []
    merged = 0
    for rec in sorted(records, key=quality, reverse=True):
        hit = next((k for k in kept if same_contest(k, rec)), None)
        if hit is None:
            kept.append(rec)
            continue
        merged += 1
        for key, val in rec.items():
            if key in ("id", "title", "source", "overridden"):
                continue
            cur = hit.get(key)
            if val in (None, "", [], {}) or cur not in (None, "", [], {}):
                continue
            hit[key] = val                      # 빈 칸만 보충
        hit.setdefault("alsoFrom", []).append(rec.get("source", "?"))
    return kept, merged


# 마감일을 못 넣은 단발 대회를 이 기간 넘게 두지 않는다.
# scripts/verify_contests.py 와 같은 값을 쓴다.
STALE_DAYS = 45


def load_verify_state() -> dict:
    """scripts/verify_contests.py 가 남긴 검수 기록 (없으면 빈 값)."""
    p = DATA / "verify.state.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("records", {})
    except json.JSONDecodeError:
        return {}


def stamp_verified(records: list[dict], state: dict) -> list[dict]:
    """마지막으로 검수한 날짜를 레코드에 붙인다 (화면에 '최종 확인'으로 표시)."""
    for r in records:
        st = state.get(r.get("id", ""))
        if st and st.get("checkedAt"):
            r["checkedAt"] = st["checkedAt"]
    return records


def drop_expired(records: list[dict], state: dict) -> tuple[list[dict], int, int]:
    """마감이 지난 항목과, 마감일을 못 넣은 채 오래 방치된 항목을 걷어낸다.

    두 번째 규칙이 없으면 `deadline: null` 인 단발 대회가 영원히 남는다.
    실제로 작년에 끝난 OpenArt Music Video Awards 가 그렇게 몇 달을 버텼다.
    반복(daily·weekly·rolling) 항목은 마감일이 없는 게 정상이라 제외한다.
    """
    keep, dropped, stale = [], 0, 0
    for r in records:
        dl = r.get("deadline")
        recur = r.get("recur", "once")
        if dl and dl < TODAY and recur == "once":
            dropped += 1
            continue
        if not dl and recur == "once":
            first = (state.get(r.get("id", ""), {}) or {}).get("firstSeen")
            if first:
                try:
                    age = (date.fromisoformat(TODAY) - date.fromisoformat(first)).days
                except ValueError:
                    age = 0
                if age >= STALE_DAYS:
                    print(f"  · 마감일 미상 {age}일 경과로 제외: {r.get('title','')[:50]}")
                    stale += 1
                    continue
        keep.append(r)
    return keep, dropped, stale


def stamp_html(html_name: str, data_src: str, version: str, dry: bool) -> None:
    """HTML 의 <script src="data/kr.js?v=..."> 버전을 갱신한다.

    이게 없으면 브라우저가 옛 데이터 파일을 캐시에서 꺼내 쓴다. 페이지는
    최신인데 목록만 지난주 것인 상태가 되는데, 화면상 구분이 안 돼 가장
    성가신 종류의 버그가 된다. 갱신할 때마다 쿼리를 바꿔 확실히 끊는다.
    """
    p = ROOT / html_name
    if not p.exists():
        print(f"  ! {html_name} 없음 — 캐시 버스터 갱신 건너뜀")
        return
    src = p.read_text(encoding="utf-8")
    pat = re.compile(r'(<script src="' + re.escape(data_src) + r')(\?v=[^"]*)?(">)')
    new, n = pat.subn(rf'\1?v={version}\3', src)
    if not n:
        print(f"  ! {html_name} 에서 {data_src} script 태그를 못 찾음")
        return
    if new == src or dry:
        return
    p.write_text(new, encoding="utf-8")
    print(f"  → {html_name} 캐시 버스터 v={version}")


def write_js(path: Path, var: str, records: list[dict], meta: dict, dry: bool) -> None:
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "_meta": meta,
        "contests": records,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=1)
    js = (
        "/* 자동 생성 파일 — 직접 고치지 마세요.\n"
        "   사람이 관리하는 값은 data/manual.*.json 에 넣고\n"
        "   `python scripts/update_contests.py` 를 다시 실행하세요. */\n"
        f"window.{var} = {body};\n"
    )
    if dry:
        print(f"  (dry-run) {path.name} 미기록 — {len(records)}건")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(js, encoding="utf-8")
    print(f"  → {path.relative_to(ROOT)} 기록 ({len(records)}건, {len(js):,} bytes)")


def build(kind: str, auto: list[dict], manual_file: str, var: str,
          out_name: str, html_name: str, dry: bool) -> bool:
    print(f"\n[{kind}] 자동 {len(auto)}건 수집")
    manual = load_manual(manual_file)
    out_path = DATA / out_name

    state = load_verify_state()
    records = merge(auto, manual)
    records, dup = dedupe(records)
    records = apply_overrides(records, manual["overrides"])
    records, dropped, stale = drop_expired(records, state)
    records = stamp_verified(records, state)
    print(f"  수동 {len(manual['extra'])}건 병합 · 중복 {dup}건 통합 · "
          f"만료 {dropped}건 제거 · 방치 {stale}건 제거 → 최종 {len(records)}건")

    by_src: dict[str, int] = {}
    for r in records:
        by_src[r.get("source", "?")] = by_src.get(r.get("source", "?"), 0) + 1
    print("  출처별:", ", ".join(f"{k} {v}" for k, v in sorted(by_src.items())))

    # 안전장치는 '최종 건수' 로 본다. 보조 소스 하나가 막혀도(위비티 403 등)
    # 주 소스가 살아 있으면 통과하고, 주 소스가 무너졌을 때만 막는다.
    # 만료 제거로 자연히 줄어드는 폭까지 고려해 절반을 기준으로 잡았다.
    prev = prev_meta(out_path)
    prev_final = prev.get("finalCount")
    if prev_final and len(records) < prev_final * SANITY_RATIO:
        print(f"  !! 최종 {len(records)}건 < 직전 {prev_final}건의 "
              f"{int(SANITY_RATIO*100)}% — 소스가 깨졌을 가능성이 큽니다. "
              f"파일을 갱신하지 않습니다.")
        return False

    meta = {
        "autoCount": len(auto),
        "finalCount": len(records),
        "manualCount": len(manual["extra"]),
        "bySource": by_src,
        "warnings": list(sources.WARNINGS),
    }
    write_js(out_path, var, records, meta, dry)
    stamp_html(html_name, f"data/{out_name}",
               datetime.now(timezone.utc).strftime("%Y%m%d%H%M"), dry)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 결과만 출력")
    ap.add_argument("--skip-kr", action="store_true")
    ap.add_argument("--skip-global", action="store_true")
    ap.add_argument("--linkareer-pages", type=int, default=20,
                    help="링커리어 목록 조회 페이지 수")
    ap.add_argument("--wevity-limit", type=int, default=30,
                    help="위비티 카테고리당 최대 상세 조회 건수")
    ap.add_argument("--afc-limit", type=int, default=90,
                    help="aifilmcontests 최대 상세 조회 건수")
    ap.add_argument("--skip-devpost", action="store_true")
    ap.add_argument("--skip-melies", action="store_true")
    ap.add_argument("--devpost-pages", type=int, default=4,
                    help="Devpost 목록 조회 페이지 수 (1페이지 9건)")
    ap.add_argument("--devpost-min-cash", type=int, default=sources.DEVPOST_MIN_CASH,
                    help="이 금액(USD) 미만 상금의 해커톤은 제외")
    args = ap.parse_args()

    print(f"AI 공모전 데이터 갱신 · 기준일 {TODAY}")
    ok = True

    if not args.skip_kr:
        print("\n── 국내 수집 ──")
        auto_kr: list[dict] = []
        print(" · 링커리어 (주 소스)")
        auto_kr += sources.fetch_linkareer(pages=args.linkareer_pages)
        print(" · 인공지능팩토리")
        auto_kr += sources.fetch_aifactory()
        # 위비티는 Cloudflare 가 데이터센터 IP를 403 처리해 GitHub Actions 에서는
        # 늘 실패한다. 로컬(한국 IP)에서는 잘 되고 데이터도 좋아서, 되면 쓰고
        # 안 되면 조용히 넘어가는 보조 소스로 둔다.
        print(" · 위비티 (보조 · CI에서는 차단됨)")
        auto_kr += sources.fetch_wevity(limit_per_list=args.wevity_limit)
        ok &= build("국내", auto_kr, "manual.kr.json", "KR_DATA", "kr.js",
                    "index.html", args.dry_run)

    if not args.skip_global:
        print("\n── 해외 수집 ──")
        auto_gl: list[dict] = []
        print(" · aifilmcontests.com")
        auto_gl += sources.fetch_aifilmcontests(max_items=args.afc_limit)
        # Devpost 는 공개 API 라 마감일·상금이 구조화돼 온다. 기업 스폰서
        # AI 해커톤이 여기로 많이 들어온다.
        if not args.skip_devpost:
            print(" · Devpost (AI 해커톤)")
            auto_gl += sources.fetch_devpost(pages=args.devpost_pages,
                                             min_cash=args.devpost_min_cash)
        # melies.co 디렉터리. FilmFreeway 가 봇을 막아 공식 페이지를 못 읽는
        # 아시아권 AI 영화제(부산·제주·K-Culture 등)가 여기에만 실린다.
        if not args.skip_melies:
            print(" · melies.co (AI 영화제 디렉터리)")
            auto_gl += sources.fetch_melies()
        # Higgsfield 는 JSON-LD 가 실제 페이지와 어긋나 자동 수집에서 제외.
        # 사유는 sources.fetch_higgsfield 주석 참고. 값은 manual.global.json 에 있다.
        ok &= build("해외", auto_gl, "manual.global.json", "GLOBAL_DATA", "global.js",
                    "global.html", args.dry_run)

    if sources.WARNINGS:
        print(f"\n경고 {len(sources.WARNINGS)}건:")
        for w in sources.WARNINGS:
            print("  -", w)

    print("\n완료." if ok else "\n일부 갱신이 중단되었습니다.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
