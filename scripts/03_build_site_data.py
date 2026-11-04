"""
03_build_site_data.py — 把 analysis.json 打包成页面可直接加载的 web/data.js

为什么用 .js 而不是 .json：
    页面可能以 file:// 双击打开，此时 fetch('*.json') 会被 CORS 拦截，
    而 <script src="data.js"> 不受此限制，保证离线可用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "analysis.json"
OUT = ROOT / "web" / "data.js"


def main() -> int:
    if not SRC.exists():
        print(f"缺少 {SRC}，请先运行 scripts/02_analyze.py")
        return 1
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(
        "/* 由 scripts/03_build_site_data.py 自动生成，请勿手改 */\n"
        f"window.__DATA__ = {body};\n",
        encoding="utf-8",
    )
    print(f"已写出 {OUT.relative_to(ROOT)}（{OUT.stat().st_size / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
