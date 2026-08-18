#!/usr/bin/env python3
"""
감시 후보 사이트가 '자동으로 볼 수 있는 곳'인지 진단한다.

  python scripts/probe_watch_targets.py                    # 기본 후보군 전체
  python scripts/probe_watch_targets.py krea.ai pika.art   # 특정 도메인만

왜 필요한가
  AI 서비스 절반은 로그인 뒤 JS로만 그려져서 서버 HTML에 챌린지 목록이
  아예 없다. 그런 곳을 watchlist.PLATFORMS 에 넣어 두면 매 실행마다 요청만
  쓰고 0건을 돌려준다. 넣기 전에 여기서 먼저 재 본다.

읽는 법
  sitemap  사이트맵에서 challenge·contest 류 URL이 몇 개 나오는지
  hub      허브 페이지(/contests, /challenges …) 서버 HTML에 링크가 있는지
  → 둘 중 하나라도 잡히면 PLATFORMS 에 넣을 값이 있다는 뜻이다.
    아무것도 안 잡히면 watchlist.MANUAL_CHECK 로 보낸다.
"""
from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
import watchlist                                           # noqa: E402

HUB_PATHS = [
    "/contests", "/contest", "/challenges", "/challenge", "/competitions",
    "/events", "/event", "/awards", "/blog", "/news", "/community/challenges",
    "/activity", "/activities", "/creators", "/programs",
]

# AI 이미지·영상 서비스 후보군. 여기 있다고 다 감시되는 건 아니고,
# 이 스크립트로 걸러서 되는 곳만 watchlist.PLATFORMS 로 옮긴다.
CANDIDATES = [
    # 영상 생성
    "runwayml.com", "lumalabs.ai", "pika.art", "klingai.com", "hailuoai.video",
    "www.vidu.com", "pixverse.ai", "higgsfield.ai", "www.moonvalley.com",
    "ltx.studio", "www.genmo.ai", "haiper.ai", "kaiber.ai", "viggle.ai",
    "www.domoai.app", "dreamina.capcut.com", "www.capcut.com", "wan.video",
    "hedra.com", "www.heygen.com", "www.synthesia.io", "www.captions.ai",
    "www.descript.com", "argil.ai", "www.tavus.io",
    # 이미지 생성
    "www.midjourney.com", "leonardo.ai", "ideogram.ai", "www.recraft.ai",
    "www.krea.ai", "www.freepik.com", "playground.com", "civitai.com",
    "www.seaart.ai", "openart.ai", "tensor.art", "www.shakker.ai",
    "creator.nightcafe.studio", "nightcafe.studio", "www.artbreeder.com",
    "pixai.art", "www.magnific.ai", "www.photoroom.com", "bfl.ai",
    "stability.ai", "firefly.adobe.com", "www.canva.com", "lexica.art",
    # 음악·음성 (영상 제작과 함께 열리는 챌린지가 많다)
    "suno.com", "www.udio.com", "elevenlabs.io", "mubert.com",
    # 스톡·툴 · 기타
    "artlist.io", "www.shutterstock.com", "www.storyblocks.com",
    "openai.com", "deepmind.google", "labs.google", "www.aitubo.ai",
]

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
      "Accept-Language": "en-US,en;q=0.9"}
TIMEOUT = 20


def _get(url: str) -> tuple[int | None, str]:
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        return r.status_code, (r.text if r.ok else "")
    except requests.RequestException:
        return None, ""


def probe_sitemap(host: str) -> tuple[str, list[str]]:
    code, xml = _get(f"https://{host}/sitemap.xml")
    if not xml:
        return (f"HTTP {code}" if code else "실패"), []
    kids = []
    if "<sitemapindex" in xml:
        kids = [k.strip() for k in re.findall(r"<loc>(.*?)</loc>", xml)
                if re.search(r"blog|news|post|article|content|page|event|main|marketing",
                             k, re.I)][:6]
        locs = []
        for k in kids:
            _, sub = _get(k)
            locs += re.findall(r"<loc>(.*?)</loc>", sub)
    else:
        locs = re.findall(r"<loc>(.*?)</loc>", xml)
    hits = [u for u in locs
            if watchlist.CHALLENGE_PAT.search(u) and not watchlist.NOISE_PAT.search(u)]
    return f"ok(locs {len(locs)}, 하위 {len(kids)})", hits


def probe_hubs(host: str) -> list[tuple[str, int, list[str]]]:
    out = []
    for path in HUB_PATHS:
        url = f"https://{host}{path}"
        code, html = _get(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        links = {urljoin(url, a["href"].split("?")[0])
                 for a in soup.select("a[href]")
                 if watchlist.CHALLENGE_PAT.search(a["href"])}
        links = {l for l in links if not watchlist.NOISE_PAT.search(l)}
        if links:
            out.append((path, len(links), sorted(links)[:3]))
    return out


def probe(host: str) -> str:
    sm_note, sm_hits = probe_sitemap(host)
    hubs = probe_hubs(host)
    verdict = "쓸 수 있음" if (sm_hits or hubs) else "자동 감시 불가"
    lines = [f"\n{host}  →  {verdict}", f"  sitemap : {sm_note} · 후보 {len(sm_hits)}건"]
    for u in sm_hits[:4]:
        lines.append(f"      {u}")
    for path, n, sample in hubs:
        lines.append(f"  hub {path:22} 링크 {n}건")
        for u in sample:
            lines.append(f"      {u}")
    return "\n".join(lines)


def main() -> int:
    hosts = sys.argv[1:] or CANDIDATES
    print(f"감시 후보 진단 {len(hosts)}곳 (사이트당 최대 {len(HUB_PATHS) + 7} 요청)\n")
    with ThreadPoolExecutor(max_workers=6) as ex:
        for line in ex.map(probe, hosts):
            print(line)
    print("\n'쓸 수 있음' 인 곳만 scripts/watchlist.py 의 PLATFORMS 에 넣으세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
