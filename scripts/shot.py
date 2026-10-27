# -*- coding: utf-8 -*-
"""页面自测 + 截图：用本机 Chrome 渲染 file:// 页面，抓控制台报错并逐 Tab 截图。"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "site" / "index.html").as_uri()
SHOT = ROOT / "screenshots"
TABS = [("overview", "01-概览"), ("process", "02-过程"), ("trend", "03-走势"),
        ("stats", "04-统计"), ("insight", "05-结论")]


def main(only: str | None = None) -> None:
    SHOT.mkdir(exist_ok=True)
    logs: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            locale="zh-CN",
        )
        page = ctx.new_page()
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))

        page.goto(PAGE, wait_until="load")
        page.wait_for_timeout(1800)

        tabs = [t for t in TABS if (only is None or only in t[0])]

        for key, name in tabs:
            page.evaluate(
                """(k) => {
                    const items = document.querySelectorAll('.t-tabs__item');
                    for (const it of items) {
                        if (it.textContent.trim().length && it.textContent.trim() ===
                            ({overview:'概览',process:'过程',trend:'走势',stats:'统计',insight:'结论'})[k]) {
                            it.click(); break;
                        }
                    }
                }""",
                key,
            )
            page.wait_for_timeout(1100)
            page.evaluate("window.scrollTo(0,0)")
            page.wait_for_timeout(320)
            page.screenshot(path=str(SHOT / f"{name}.png"), full_page=True)
            print(f"[shot] {name}.png")

        # 全屏图表弹层
        page.evaluate("window.scrollTo(0,0)")
        page.wait_for_timeout(200)
        height = page.evaluate("document.body.scrollHeight")
        print(f"[info] bodyHeight={height}")

        browser.close()

    errs = [l for l in logs if l.startswith("[error]") or l.startswith("[pageerror]")]
    warns = [l for l in logs if l.startswith("[warning]")]
    print(f"[console] {len(logs)} 条，error {len(errs)}，warning {len(warns)}")
    for l in (errs + warns)[:40]:
        print("   ", l[:400])
    if errs:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
