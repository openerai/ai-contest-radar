#!/usr/bin/env python3
"""국내 공모전 소스가 현재 실행 환경(IP)에서 접근 가능한지 진단.

GitHub Actions 러너(미국)에서 한국 사이트 일부가 방화벽에 막히기 때문에,
어떤 소스를 자동 수집에 쓸 수 있는지 확인하는 용도.

  python scripts/probe_sources.py
"""
from __future__ import annotations

import socket
import sys
import time
from urllib.parse import urlparse

import requests

UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

TARGETS = [
    ("위비티",            "https://www.wevity.com/?c=find&s=1&gub=1&cidx=20", "ul.list"),
    ("인공지능팩토리",     "https://aifactory.space/ko/competition",           "taskList"),
    ("링커리어",          "https://linkareer.com/list/contest",                "activity"),
    ("씽굿",              "https://www.thinkcontest.com/contest/list",         "contest"),
    ("올콘",              "https://www.all-con.co.kr/view/contest",            "contest"),
    ("콘테스트코리아",     "https://www.contestkorea.com/sub/list.php",         "list"),
    ("캠퍼스픽",          "https://www.campuspick.com/contest",                "contest"),
    ("데이콘",            "https://dacon.io/competitions",                     "competition"),
    ("공공데이터포털",     "https://www.data.go.kr/suc/preliminaryRound.do",   "경진대회"),
    ("aifilmcontests",   "https://aifilmcontests.com/sitemap.xml",            "<loc>"),
]


def probe(name: str, url: str, needle: str) -> None:
    host = urlparse(url).hostname
    t0 = time.time()

    # 1) DNS
    try:
        ip = socket.gethostbyname(host)
    except OSError as e:
        print(f"{name:16} DNS 실패 ({e})")
        return

    # 2) TCP
    try:
        with socket.create_connection((host, 443), timeout=10):
            pass
        tcp = "TCP ok"
    except OSError as e:
        print(f"{name:16} ip={ip:15} TCP 실패 ({type(e).__name__}) — 방화벽 차단 가능성")
        return

    # 3) HTTP
    try:
        r = requests.get(url, headers=UA, timeout=20)
        dt = time.time() - t0
        hit = needle.lower() in r.text.lower()
        print(f"{name:16} ip={ip:15} {tcp} HTTP {r.status_code} "
              f"{len(r.text):>7}B {dt:5.1f}s 지문={'O' if hit else 'X'}")
    except requests.RequestException as e:
        dt = time.time() - t0
        print(f"{name:16} ip={ip:15} {tcp} HTTP 실패 {type(e).__name__} {dt:5.1f}s")


if __name__ == "__main__":
    try:
        out = requests.get("https://api.ipify.org", timeout=10).text
        print(f"실행 위치 공인 IP: {out}\n")
    except requests.RequestException:
        print("공인 IP 확인 실패\n")
    for t in TARGETS:
        probe(*t)
