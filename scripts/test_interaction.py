# -*- coding: utf-8 -*-
"""交互自测：逐一点击关键控件，验证图表重绘、弹层、折叠等是否正常，并记录异常。"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "site" / "index.html").as_uri()
OUT = ROOT / "screenshots"


def main() -> int:
    fails: list[str] = []
    logs: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3,
                            is_mobile=True, has_touch=True, locale="zh-CN")
        pg = ctx.new_page()
        pg.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        pg.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
        pg.goto(PAGE, wait_until="load")
        pg.wait_for_timeout(1500)

        def canvases() -> int:
            return pg.evaluate("document.querySelectorAll('.page canvas').length")

        # 1. 概览
        n = canvases()
        print(f"1. 概览 canvas = {n}")
        if n < 1:
            fails.append("概览页无 canvas")

        # 2. 过程：折叠面板
        pg.click(".t-tabs__item:has-text('过程')")
        pg.wait_for_timeout(700)
        headers = pg.query_selector_all(".t-collapse-panel__header, .t-collapse-title")
        print(f"2. 过程 折叠头 = {len(headers)}")
        if headers:
            headers[1].click()
            pg.wait_for_timeout(500)
        steps = len(pg.query_selector_all(".t-step-item__title"))
        print(f"   步骤数 = {steps}")
        if steps != 5:
            fails.append(f"步骤数异常 {steps}")

        # 3. 走势：区间切换 + 全屏
        pg.click(".t-tabs__item:has-text('走势')")
        pg.wait_for_timeout(900)
        print(f"3. 走势 canvas = {canvases()}")
        if canvases() < 3:
            fails.append("走势页图表不足 3 个")

        for label in ["近 3 月", "近 1 月", "全年"]:
            pg.click(f".pills .t-tag:has-text('{label}')")
            pg.wait_for_timeout(600)
        checked = pg.evaluate("(document.querySelector('.pills .t-tag--checked')||{}).innerText")
        print(f"   区间选中 = {checked!r}")
        if "全年" not in str(checked):
            fails.append("区间切换选中态异常")

        btns = pg.query_selector_all(".page .card .icon-btn")
        btns[0].click()
        pg.wait_for_timeout(900)
        popup_open = pg.evaluate("!!document.querySelector('.t-popup')")
        popup_canvas = pg.evaluate("document.querySelectorAll('.zoom canvas').length")
        print(f"   全屏弹层 = {popup_open}, canvas = {popup_canvas}")
        pg.screenshot(path=str(OUT / "06-全屏图表.png"))
        if not popup_open or popup_canvas < 1:
            fails.append("全屏弹层未渲染图表")
        pg.click(".t-popup .t-button")
        pg.wait_for_timeout(500)

        # 4. 统计
        pg.click(".t-tabs__item:has-text('统计')")
        pg.wait_for_timeout(900)
        print(f"4. 统计 canvas = {canvases()}")
        if canvases() < 3:
            fails.append("统计页图表不足 3 个")

        # 5. 结论
        pg.click(".t-tabs__item:has-text('结论')")
        pg.wait_for_timeout(700)
        print(f"5. 洞察卡 = {len(pg.query_selector_all('.insight'))}")

        b.close()

    errs = [l for l in logs if l.startswith("[error]") or l.startswith("[pageerror]")]
    print(f"\n控制台: 共 {len(logs)} 条，error {len(errs)}")
    for l in errs[:10]:
        print("  ", l[:300])
    if errs:
        fails.append(f"控制台 error {len(errs)} 条")
    print("\n结果:", "全部通过" if not fails else "存在问题 -> " + "; ".join(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
