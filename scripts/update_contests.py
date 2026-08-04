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
    blocked = {norm_title(b) if not b.startswith(("wevity-", "aifactory-", "afc-", "hf-"))
               else b for b in manual["block"]}
    overrides = manual["overrides"]
    ov_by_title = {norm_title(k): v for k, v in overrides.items()}

    manual_titles = {norm_title(x.get("title", "")) for x in manual["extra"]}
    manual_ids = {x.get("id") for x in manual["extra"]}

    used_ov: set[str] = set()
    merged: list[dict] = []
    for rec in auto:
        nt = norm_title(rec.get("title", ""))
        if rec["id"] in blocked or nt in blocked or rec["id"] in manual_ids:
            continue
        if nt in manual_titles:                    # 수동 항목이 이미 다루는 대회
            continue
        patch = overrides.get(rec["id"]) or ov_by_title.get(nt)
        if patch:
            used_ov.add(rec["id"] if rec["id"] in overrides else nt)
            rec = {**rec, **patch, "overridden": True}
            # 사람이 정확한 총상금을 넣어줬다면 자동 수집의 '구간' 표시는 버린다
            if "prizeTotal" in patch and "prizeApprox" not in patch:
                rec["prizeApprox"] = False
                rec.pop("prizeMin", None)
                rec.pop("prizeMax", None)
        merged.append(rec)

    for rec in manual["extra"]:
        if rec.get("id") in blocked or norm_title(rec.get("title", "")) in blocked:
            continue
        merged.append({**rec, "source": rec.get("source", "manual")})

    stale = [k for k in overrides if k not in used_ov and norm_title(k) not in used_ov]
    if stale:
        print(f"  · 적용되지 않은 override {len(stale)}개 (대회가 끝났거나 제목이 바뀜): "
              + ", ".join(stale[:5]) + ("…" if len(stale) > 5 else ""))
    return merged


def drop_expired(records: list[dict]) -> tuple[list[dict], int]:
    keep, dropped = [], 0
    for r in records:
        dl = r.get("deadline")
        recur = r.get("recur", "once")
        if dl and dl < TODAY and recur == "once":
            dropped += 1
            continue
        keep.append(r)
    return keep, dropped


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

    prev = prev_meta(out_path)
    prev_auto = prev.get("autoCount")
    if prev_auto and len(auto) < prev_auto * SANITY_RATIO:
        print(f"  !! 자동 수집 {len(auto)}건 < 직전 {prev_auto}건의 "
              f"{int(SANITY_RATIO*100)}% — 소스 구조 변경 의심. 파일을 갱신하지 않습니다.")
        return False

    records = merge(auto, manual)
    records, dropped = drop_expired(records)
    print(f"  수동 {len(manual['extra'])}건 병합 · 만료 {dropped}건 제거 → 최종 {len(records)}건")

    by_src: dict[str, int] = {}
    for r in records:
        by_src[r.get("source", "?")] = by_src.get(r.get("source", "?"), 0) + 1
    print("  출처별:", ", ".join(f"{k} {v}" for k, v in sorted(by_src.items())))

    meta = {
        "autoCount": len(auto),
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
    ap.add_argument("--wevity-limit", type=int, default=30,
                    help="위비티 카테고리당 최대 상세 조회 건수")
    ap.add_argument("--afc-limit", type=int, default=90,
                    help="aifilmcontests 최대 상세 조회 건수")
    args = ap.parse_args()

    print(f"AI 공모전 데이터 갱신 · 기준일 {TODAY}")
    ok = True

    if not args.skip_kr:
        print("\n── 국내 수집 ──")
        auto_kr: list[dict] = []
        print(" · 위비티")
        auto_kr += sources.fetch_wevity(limit_per_list=args.wevity_limit)
        print(" · 인공지능팩토리")
        auto_kr += sources.fetch_aifactory()
        ok &= build("국내", auto_kr, "manual.kr.json", "KR_DATA", "kr.js",
                    "index.html", args.dry_run)

    if not args.skip_global:
        print("\n── 해외 수집 ──")
        auto_gl: list[dict] = []
        print(" · aifilmcontests.com")
        auto_gl += sources.fetch_aifilmcontests(max_items=args.afc_limit)
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
