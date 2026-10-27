# Git 推送指南

> 当前状态：仓库已 `git init -b main`，**29 个文件已全部 `git add`**，只差 `commit` 和 `push`。
> 本文档给出两种执行方式，任选其一。

---

## 一、前置：配置提交身份（只需一次）

当前本机 `user.name` / `user.email` 都是空的，不配会提交失败。

```bash
cd byd-stock-analytics
git config user.name "你的名字"
git config user.email "你的邮箱"
```

> 建议邮箱用 GitHub/Gitee 的 **noreply 邮箱**，避免真实邮箱被公开在 commit 记录里。
> GitHub：`设置 → Emails → Keep my email addresses private`，会给你一个 `xxxx@users.noreply.github.com`。
> Gitee：`设置 → 邮箱管理` 里同样有隐私邮箱选项。

---

## 二、方式 A：你自己跑（推荐，零泄露）

### 1. 提交

```bash
git commit -m "feat: 比亚迪股票价格走势分析与可视化 H5

- 数据层：pandas 清洗 242×11 行情数据，输出 8 段结构化指标
- 视图层：Vue 3 + TDesign Mobile Vue + ECharts，5 屏移动端报告
- 交付物：AGENTS.md / 6 张截图 / 交互记录"
```

### 2. 建空仓库

到平台上新建仓库，**不要勾选** README / .gitignore / License，保持空仓库。

### 3. 关联并推送

**GitHub（HTTPS）**

```bash
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

**GitHub（SSH）** — 需先把公钥加到 GitHub

```bash
git remote add origin git@github.com:你的用户名/仓库名.git
git push -u origin main
```

**Gitee（HTTPS）**

```bash
git remote add origin https://gitee.com/你的用户名/仓库名.git
git push -u origin main
```

**Gitee（SSH）**

```bash
git remote add origin git@gitee.com:你的用户名/仓库名.git
git push -u origin main
```

---

## 三、方式 B：把地址给我，我来推

### 需要你提供

| 信息 | 示例 | 说明 |
|---|---|---|
| 仓库地址 | `https://github.com/zhangsan/byd-stock-analysis.git` | HTTPS 或 SSH 都行 |
| 提交身份 | 姓名 + 邮箱 | 用于 `git config` |
| 默认分支名 | `main`（默认） | 与平台一致即可 |

### 我会做什么

1. 执行上面第 2 步的 `commit`；
2. `git remote add origin <你的地址>`；
3. `git push -u origin main`；
4. 把仓库链接和 `git log` 结果回给你。

### 认证怎么过

- **HTTPS**：push 时你屏幕上会弹出 Git Credential Manager 的登录窗口，
  点「Sign in with your browser」登录一次即可，我这边会等它完成。
- **SSH**：需要本机已有密钥。目前**没有** SSH 公钥，需要先执行：

  ```bash
  ssh-keygen -t ed25519 -C "你的邮箱"
  cat ~/.ssh/id_ed25519.pub
  ```

  把输出的公钥整行贴到 GitHub `Settings → SSH and GPG keys → New SSH key`。

### ⚠️ 绝对不要做的事

**不要把带 token 的地址贴给我**，例如：

```
https://ghp_xxxxxxxxxxxx@github.com/用户名/仓库.git
```

两个后果：

1. 这份作业要求提交**与 Agent 的交互记录**，token 会原样留在 `docs/对话记录.md` 里交给老师；
2. token 会被写进 `.git/config`，随仓库一起流传。

如果已经不小心贴过，立刻到平台**吊销该 token** 并重新生成。

---

## 四、常见报错对照

| 报错 | 原因 | 处理 |
|---|---|---|
| `Please tell me who you are` | 没配 `user.name` / `user.email` | 执行第一节的两条命令 |
| `remote origin already exists` | 重复添加远程 | `git remote set-url origin <新地址>` |
| `failed to push some refs` / `rejected` | 远程仓库非空（勾了 README） | `git pull --rebase origin main --allow-unrelated-histories` 后再 push |
| `src refspec main does not match any` | 还没 commit | 先执行 `git commit` |
| `Permission denied (publickey)` | SSH 公钥没配对 | 重跑 `ssh -T git@github.com` 验证 |
| `Authentication failed` | HTTPS 密码错误 | GitHub 已不支持密码，必须用 GCM 浏览器登录或 PAT |
| 中文文件名显示成 `\344\270\255` | 未关闭路径转义 | `git config core.quotepath false`（已配好） |

---

## 五、提交后自检

```bash
git log --oneline -1          # 应看到本次 commit
git ls-files | wc -l          # 应为 29
git remote -v                 # 确认地址正确
```

推送成功后，仓库里应能看到这些内容：

```
.gitattributes  .gitignore  AGENTS.md  README.md
data/            docs/       screenshots/   scripts/   site/
```
