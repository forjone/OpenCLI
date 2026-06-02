# 架构说明

## 一句话

`VideoPost`（一份母版）→ `PlatformAdapter`（按平台 prompt 走 Claude 改写）→ `Uploader`（驱动浏览器/CLI 实际上传）→ `PostResult`，4 个平台并发执行。

## 模块依赖

```
                    ┌─────────────┐
                    │   cli.py    │
                    │   web.py    │
                    └──────┬──────┘
                           │
                  ┌────────▼────────┐
                  │  orchestrator   │  publish(master, [targets], adapter)
                  └────────┬────────┘
                           │ asyncio.gather
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
       ┌─────────┐    ┌─────────┐    ┌──────────┐
       │ adapter │───▶│Uploader │───▶│PostResult│
       │ (LLM)   │    │(per-plat)│   │          │
       └─────────┘    └────┬────┘    └──────────┘
                           │
                ┌──────────┴─────────┐
                ▼                    ▼
        ┌──────────────┐   ┌────────────────┐
        │  patchright  │   │  biliup CLI    │
        │ (douyin/xhs/ │   │  (bilibili)    │
        │  tencent)    │   └────────────────┘
        └──────────────┘
```

## 关键设计决策

### 1. 为什么有 `Uploader` ABC

SAU 每个平台是独立的 700+ 行 Python 文件，函数签名各不相同，无法被一个统一调度器调用。我们的 `Uploader` 抽象规定了：
- `login(account, qrcode_callback)` — 触发交互式登录
- `check_session(account)` — 验证 cookie 有效性
- `upload(account, post)` — 上传一条，**返回 PostResult 不抛异常**
- `validate(post)` — 同步校验平台硬约束

这样 orchestrator + adapter 不用知道平台细节。

### 2. 为什么 `platform_extras` 用 dict 而不是子类化

B 站需要 `tid`（分区 id），抖音需要 `productLink`，视频号需要 `category`。如果给每个平台开一个 `VideoPost` 子类，类型膨胀。把这些字段塞 dict 里、用 `required_extras` 在 validate 时检查 —— 简单，且对前端友好（JSON 直接映射）。

### 3. 为什么用 Claude 而不是开源模型

文案改写对 instruction following 和"风格切换"要求高，Sonnet 4.6 在中文社媒文案上明显优于 7B-13B 开源模型。**且因为我们用 prompt caching**，每个平台的 system prompt 只首次发布时计费，后续基本免费。

### 4. 为什么不用 LangChain / LlamaIndex

不需要。整个 LLM 调用只有一处（`adapters/llm.py`），加任何 framework 都是负债。直接调 SDK 即可。

### 5. 为什么 `bilibili.py` 走 biliup CLI 而其它走 Playwright

B 站官方禁止网页端用脚本上传大文件，社区方案 `biliup` 是基于 B 站官方上传 API 的逆向，比 Playwright 稳定 10 倍。SAU 也是这么做的，我们沿用。

### 6. 为什么 Web 后端用 FastAPI 而不是 Flask

- async 原生支持（uploader 全是 async）
- 自动 OpenAPI / pydantic schema —— 前端可以直接生成 TypeScript 类型
- WebSocket / SSE 内置（后续 QR 登录推送会用到）
- 比 SAU 的 Flask 少一半样板代码

## 待办（按优先级）

| # | 任务 | 价值 |
|---|---|---|
| P0 | Web 前端 MVP（账号管理 + 发布表单 + 历史） | 让产品可用 |
| P0 | QR 登录的 SSE 流 | 体验决定型 |
| P1 | 重写 douyin_uploader 用类型化代码 | 长期可维护 |
| P1 | 多账号矩阵：每个账号独立的风格 prompt | 差异化卖点 |
| P2 | 数据回流：定时抓播放/点赞 | v2 杀手 feature |
| P2 | 定时发布队列 | SAU 已有但我们暂未接 |

## 不做的事

- ❌ 海外平台（TikTok/YouTube）—— MVP 范围外
- ❌ 直播推流
- ❌ 视频剪辑 / 字幕生成（让用户用专门工具，我们只做"发布")
- ❌ 多用户 SaaS —— 这是私有化工具，单机/单用户
