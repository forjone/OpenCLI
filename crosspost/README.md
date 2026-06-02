# crosspost

私有视频跨平台发布工具 —— 一个视频 → 抖音 / B站 / 小红书 / 视频号，按各平台风格 AI 改写文案后并发上传。

> 当前状态：**MVP 脚手架**。架构完整、单测通过；4 个平台的浏览器自动化层 fork 自 [social-auto-upload](https://github.com/dreammis/social-auto-upload)（已修关键 bug），AI 适配层、并发调度、SQLite、CLI、FastAPI 后端均为自研。Web 前端尚未实现。

## 目录结构

```
crosspost/
├── core/                     # 核心抽象（自研）
│   ├── models.py             # VideoPost / PostResult / Account
│   ├── interfaces.py         # Uploader ABC
│   └── orchestrator.py       # 并发发布调度器
│
├── adapters/                 # AI 平台适配层（自研）
│   ├── base.py               # PlatformAdapter / NullAdapter
│   ├── llm.py                # Claude SDK 封装（含 prompt caching）
│   └── prompts/              # 每个平台一份风格 prompt
│       ├── douyin.md
│       ├── bilibili.md
│       ├── xiaohongshu.md
│       └── tencent.md
│
├── uploader/                 # 平台 SDK 层
│   ├── douyin.py             # Uploader 接口实现（自研，~60 行）
│   ├── bilibili.py
│   ├── xiaohongshu.py
│   ├── tencent.py
│   ├── douyin_uploader/      # ↓ fork 自 SAU，已修 f-string bug
│   ├── bilibili_uploader/
│   ├── xiaohongshu_uploader/
│   ├── tencent_uploader/
│   └── base_video.py
│
├── storage/                  # SQLite 持久化（自研）
│   └── db.py
│
├── utils/                    # 通用工具（fork 自 SAU）
│   ├── login_qrcode.py
│   ├── log.py
│   └── stealth.min.js        # patchright 反检测脚本
│
├── cli.py                    # CLI 入口（自研）
├── web.py                    # FastAPI 后端（自研）
├── tests/
│   └── test_core.py
├── pyproject.toml
└── conf.example.py
```

## 安装

需要 **Python 3.12+**（SAU vendor code 在 3.10/3.11 上有 f-string SyntaxError，本仓库已修，但仍建议 3.12+）。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
patchright install chromium
cp conf.example.py conf.py
```

设置 Claude API key（用于 AI 文案改写）：
```bash
export ANTHROPIC_API_KEY=sk-...
```

## 使用：CLI

**1) 给每个平台账号登录一次（扫码）**
```bash
crosspost login --platform douyin --account main
crosspost login --platform bilibili --account main
crosspost login --platform xiaohongshu --account main
crosspost login --platform tencent --account main
```

**2) 检查 cookie 是否还有效**
```bash
crosspost check --platform douyin --account main
```

**3) 一稿多发（带 AI 风格改写）**
```bash
crosspost publish \
  --file ./videos/demo.mp4 \
  --title "我用 AI 一周做了 7 条视频" \
  --desc "完整流程拆解" \
  --tags AI,自媒体,效率 \
  --targets douyin:main bilibili:main xiaohongshu:main tencent:main \
  --extras bilibili:tid=21
```

**4) Dry run（不真正上传，只看 AI 改写结果）**
```bash
crosspost publish --file ./demo.mp4 --title "..." --targets douyin:main --dry-run
```

**5) 禁用 AI（直接用原文案）**
```bash
crosspost publish --file ./demo.mp4 --title "..." --targets douyin:main --no-ai
```

## 使用：Web API

```bash
uvicorn web:app --reload --port 8000
```

主要端点：
- `GET  /api/health`
- `GET  /api/platforms` — 列出 4 个平台的硬约束
- `GET  /api/accounts` — 已保存账号
- `POST /api/publish` — 发布
- `GET  /api/posts` — 历史记录

Web 前端（Vue / React）暂未实现，建议作为下一里程碑。

## 测试

```bash
pytest tests/ -v
```

`tests/test_core.py` 覆盖核心调度器、validator、NullAdapter，不依赖网络/浏览器。

## 改造自 social-auto-upload 的关键变更

| 变更 | 说明 |
|---|---|
| 🔴 修 f-string bug | `uploader/xiaohongshu_uploader/main.py:518` 改成两行写法，Python 3.10/3.11 也能解析（虽然我们要求 3.12+） |
| ❌ 砍前后端 | SAU 的 Flask 后端 + Vue 前端没用，自研 FastAPI 替代 |
| ❌ 砍多余平台 | 删 ks/baijiahao/tk/xhs 旧版 uploader，只留 4 个 |
| ✅ 加 `core/` | 统一 Uploader 接口、VideoPost 模型、并发调度器 |
| ✅ 加 `adapters/` | AI 平台风格适配，Claude SDK + prompt caching |
| ✅ 加 `storage/` | SQLite 账号/发布历史 |
| ✅ 加 pyproject 唯一依赖源 | 删 SAU 的 UTF-16 编码的 requirements.txt |

## Roadmap

- [x] 架构脚手架 + 4 平台 wrapper + AI 适配 + CLI + FastAPI 后端
- [ ] Web 前端（Vue3 + Element Plus 或 React + shadcn）
- [ ] QR 登录的 SSE 流（前端实时展示二维码）
- [ ] 数据回流：抓各平台播放/互动数据
- [ ] 多账号矩阵管理
- [ ] 定时发布队列 + 失败重试
- [ ] 把 vendor 的 SAU 代码增量重写（每个平台 ~700 行 → 200 行带类型注解的新实现）

## 隐私 & 安全

- 所有账号 cookie 存在本地 `cookies/` 目录（gitignored）
- 所有发布历史存在本地 SQLite（gitignored）
- 仅向 Claude API 发送：标题、简介、标签字符串。**不**上传视频文件内容。
