"""
tdesign_mcp.py — TDesign MCP 轻量客户端（stdio）

用途：在页面开发前，直接向 tdesign-mcp-server 查询组件文档 / 组件清单 / 图标名，
确保页面里用到的每个 TDesign 组件都符合官方 API，而不是凭记忆手写。

用法：
    python scripts/tdesign_mcp.py list
    python scripts/tdesign_mcp.py docs Card Table
    python scripts/tdesign_mcp.py icon chart
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time

CMD = "npx -y tdesign-mcp-server@latest"


class Client:
    def __init__(self) -> None:
        self.p = subprocess.Popen(
            CMD, shell=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()
        self._id = 0

    def _reader(self) -> None:
        assert self.p.stdout is not None
        for line in self.p.stdout:
            self.q.put(line)

    def _send(self, obj: dict) -> None:
        assert self.p.stdin is not None
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def _recv(self, want_id: int, timeout: float = 90.0) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("id") == want_id:
                return obj
        return None

    def rpc(self, method: str, params: dict | None = None) -> dict | None:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        return self._recv(self._id)

    def handshake(self) -> dict:
        r = self.rpc("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "byd-analysis", "version": "1.0"},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        if not r or "result" not in r:
            raise RuntimeError(f"握手失败：{r}")
        return r["result"]

    def call(self, tool: str, args: dict) -> str:
        r = self.rpc("tools/call", {"name": tool, "arguments": args})
        if not r:
            return "[超时无响应]"
        if "error" in r:
            return f"[错误] {r['error']}"
        content = (r.get("result") or {}).get("content") or []
        return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")

    def close(self) -> None:
        try:
            self.p.kill()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    args = sys.argv[2:]

    c = Client()
    info = c.handshake()
    print(f"# 已连接 {info['serverInfo']['name']} v{info['serverInfo']['version']}\n")

    if action == "list":
        out = c.call("get-component-list", {})
    elif action == "docs":
        out = c.call("get-component-docs", {"componentNames": args or ["Button"]})
    elif action == "dom":
        out = c.call("get-component-dom", {"componentNames": args or ["Button"]})
    elif action == "icon":
        out = c.call("search-icon", {"keywords": args})
    else:
        print("未知动作，可用：list | docs | dom | icon")
        c.close()
        return 1

    print(out)
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
