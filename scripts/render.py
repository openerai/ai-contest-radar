#!/usr/bin/env python3
"""
JS로만 그려지는 페이지를 실제 브라우저로 열어 HTML을 얻는다.

  python scripts/render.py https://dreamina.capcut.com/ai-tool/home?activeTab=activity

왜 필요한가
  Dreamina·Kling·SeaArt 같은 곳은 이벤트 목록이 서버 HTML에 없다. requests 로
  받으면 빈 껍데기(본문 50~300자)만 온다. 실제로는 화면에 진행 중인 공모가
  여러 건 떠 있는데 우리 수집기만 못 보는 상태였다.

  API를 직접 부르는 방법도 있지만(ByteDance 계열은 mweb-api-sg.capcut.com),
  서명 헤더가 붙어 있어 재현이 어렵고 조금만 바뀌어도 깨진다. 화면에 보이는
  것을 그대로 읽는 편이 단순하고 오래 간다.

설치
  pip install playwright && python -m playwright install chromium

  설치가 안 돼 있으면 조용히 None 을 돌려준다. 렌더링이 없어도 나머지 수집은
  그대로 돌아가야 하기 때문이다 (한 소스가 죽어도 나머지는 진행한다는 원칙).
"""
from __future__ import annotations

import sys

TIMEOUT_MS = 25_000
# 이벤트 목록이 XHR 로 뒤늦게 붙는다. 네트워크가 잠잠해질 때까지 기다린 뒤
# 조금 더 준다. 이 시간을 줄이면 목록이 비어 있는 채로 읽힌다.
SETTLE_MS = 3_500

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_WARNED = False


def available() -> bool:
    try:
        import playwright.sync_api                          # noqa: F401
        return True
    except ImportError:
        return False


def render(url: str, wait_text: str | None = None,
           timeout_ms: int = TIMEOUT_MS) -> str | None:
    """브라우저로 열어 렌더가 끝난 HTML 을 돌려준다. 실패하면 None.

    wait_text 를 주면 그 문자열이 화면에 나타날 때까지 기다린다.
    """
    global _WARNED
    if not available():
        if not _WARNED:
            print("  ! playwright 미설치 — JS 렌더 대상은 건너뜁니다 "
                  "(pip install playwright && python -m playwright install chromium)")
            _WARNED = True
        return None

    from playwright.sync_api import sync_playwright, Error as PWError

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(user_agent=UA, locale="en-US",
                                      viewport={"width": 1440, "height": 1000})
            page = ctx.new_page()
            # 이미지·폰트·영상은 받지 않는다. 목록 텍스트만 필요하고,
            # 이 사이트들은 미디어가 무거워 그대로 두면 타임아웃이 잦다.
            page.route("**/*", lambda route: (
                route.abort() if route.request.resource_type in
                ("image", "media", "font") else route.continue_()))
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except PWError:
                pass                                   # 계속 폴링하는 사이트가 있다
            if wait_text:
                try:
                    page.wait_for_selector(f"text={wait_text}", timeout=timeout_ms)
                except PWError:
                    pass
            page.wait_for_timeout(SETTLE_MS)
            html = page.content()
            ctx.close()
            browser.close()
            return html
    except Exception as e:                             # 렌더 실패가 수집 전체를 막지 않게
        print(f"  ! 렌더 실패 {url} : {type(e).__name__}")
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("사용법: python scripts/render.py <URL> [기다릴문자열]")
    import re
    from bs4 import BeautifulSoup

    html = render(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    if not html:
        raise SystemExit("렌더 실패")
    soup = BeautifulSoup(html, "lxml")
    for junk in soup(["script", "style"]):
        junk.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" "))
    print(f"HTML {len(html):,} bytes · 텍스트 {len(text):,}자\n")
    print(text[:3000])
