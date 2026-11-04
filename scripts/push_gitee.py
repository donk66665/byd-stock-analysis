"""
push_gitee.py — 在 Gitee 创建仓库并推送当前项目

用法：
    python scripts/push_gitee.py <access_token> [仓库名]

说明：
    1. 令牌在 https://gitee.com/profile/personal_access_tokens 生成，勾选 projects 权限
    2. 脚本会先用令牌换取用户信息，再创建仓库（已存在则复用），最后推送 main 分支
    3. 令牌只在本进程内使用，不写入任何文件；推送后 remote 地址会被脱敏成不带令牌的形式
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://gitee.com/api/v5"


def api(path: str, token: str, method: str = "GET", payload: dict | None = None) -> dict:
    url = f"{API}{path}"
    data = None
    headers = {"Content-Type": "application/json;charset=UTF-8"}
    if method == "GET":
        url += "?" + urllib.parse.urlencode({"access_token": token})
    else:
        payload = dict(payload or {})
        payload["access_token"] = token
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("  $", " ".join(c if "://" not in c else c.split("://")[0] + "://***" for c in cmd))
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    token = sys.argv[1].strip()
    repo_name = sys.argv[2] if len(sys.argv) > 2 else "byd-stock-analysis"

    print("[1] 校验令牌")
    try:
        me = api("/user", token)
    except urllib.error.HTTPError as exc:
        print(f"  令牌无效或权限不足：HTTP {exc.code}")
        return 1
    user = me["login"]
    print(f"  已登录：{user}（{me.get('name') or ''}）")

    print(f"[2] 创建仓库 {user}/{repo_name}")
    try:
        repo = api("/user/repos", token, "POST", {
            "name": repo_name,
            "description": "比亚迪(002594)后复权股价走势分析与可视化 — 教材 P92 实战演练 + 2023-2026 数据扩展",
            "private": False,
            "auto_init": False,
            "has_issues": True,
            "has_wiki": False,
        })
        print(f"  创建成功：{repo['html_url']}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        if exc.code in (400, 403, 409) and ("already exists" in body or "已被使用" in body):
            print("  仓库已存在，直接复用")
            repo = {"html_url": f"https://gitee.com/{user}/{repo_name}"}
        else:
            print(f"  创建失败：HTTP {exc.code} {body[:300]}")
            return 1

    print("[3] 配置 remote")
    run(["git", "remote", "remove", "origin"])
    remote_url = f"https://{user}:{token}@gitee.com/{user}/{repo_name}.git"
    r = run(["git", "remote", "add", "origin", remote_url])
    if r.returncode != 0:
        print("  remote 配置失败：", r.stderr.strip()[:300])
        return 1

    print("[4] 推送 main")
    r = run(["git", "push", "-u", "origin", "main", "--force"])
    if r.returncode != 0:
        print("  推送失败：", (r.stderr or r.stdout).strip()[:500])
        return 1
    print("  推送成功")

    print("[5] 脱敏 remote（避免令牌落盘）")
    run(["git", "remote", "set-url", "origin", f"https://gitee.com/{user}/{repo_name}.git"])

    print(f"\n仓库地址：{repo['html_url']}")
    print(f"Pages 需在仓库「服务 → Gitee Pages」手动开启，选择分支 main，部署目录填 web")
    return 0


if __name__ == "__main__":
    sys.exit(main())
