# StarTrekBot

[中文](#中文) | [English](#english)

---

## 中文

### 项目简介
一个用于 QQ 机器人的 Python FastAPI 骨架，支持官方 Webhook 和个人号 (OneBot v11)。

### 运行环境
- **本地运行**:
  ```bash
  cd infra
  docker compose up -d --build
  curl http://127.0.0.1:8080/health
  ```
- **生产环境 (VPS)**:
  - **IP**: `104.194.88.246`
  - **域名**: `https://startrekbot.miranda5799.top`

### 配置发送队列 / Send Queue Config
防风控限速与发送通道配置（可在 VPS 的 `infra/docker-compose.override.yml` 修改）：
```yaml
services:
  bot:
    environment:
      - SENDQ_ENABLED=true
      - SENDQ_SENDER=mock  # 默认为 mock 记录日志，切换为 qq 以调用真实通道
      - SENDQ_GLOBAL_RPS=2.0
      - SENDQ_SESSION_COOLDOWN_MS=1200
      # 群聊过滤：指定授权的群号（以逗号分隔）；留空或 * 为不限制
      - BOT_ENABLED_GROUPS=123456,789012
      # 若使用 qq sender，需配置以下
      - QQ_SEND_ENDPOINT=http://127.0.0.1:xxxx/send # 你的发送通道地址
      - QQ_SEND_TOKEN=your_token
```

### 配置 Gemini RP (AI Studio)
用于生成星舰计算机回复（可在 VPS 的 `infra/docker-compose.override.yml` 修改）：
```yaml
services:
  bot:
    environment:
      - GEMINI_API_KEY=你的API_KEY
      - GEMINI_RP_MODEL=gemini-2.0-flash-lite
      - COMPUTER_PREFIX=Computer:  # 默认前缀
      - RP_STYLE_STRICT=true       # 强制短回复
```

> [!NOTE]
> 角色风格由 [computer_style.md](file:///Users/wanghaozhe/Documents/GitHub/StarTrekBot/docs/computer_style.md) 定义。

### 配置安全审核 / Moderation Config
在 VPS 的 `infra/docker-compose.override.yml` 中添加腾讯云 TMS 密钥：
```yaml
services:
  bot:
    environment:
      - MODERATION_ENABLED=true
      - TENCENT_SECRET_ID=你的SECRET_ID
      - TENCENT_SECRET_KEY=你的SECRET_KEY
      - TENCENT_REGION=ap-guangzhou
```

### 配置 Gemini Judge / Gemini Judge Config
为了提高分发准度，请在 VPS 的 `infra/docker-compose.override.yml` 中添加 API Key：
```yaml
services:
  bot:
    environment:
      - GEMINI_API_KEY=你的API_KEY
      - GEMINI_MODEL=gemini-2.0-flash-lite
```

### 测试 Webhook
**测试 QQ 官方 Webhook (生产环境)**
> 注意：如果设置了 `WEBHOOK_TOKEN` 环境变量，请添加 `-H "X-Webhook-Token: <your_token>"`
```bash
curl -X POST https://startrekbot.miranda5799.top/qq/webhook \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Token: your_token_here" \
     -d '{"type": "message", "author_id": "user123", "content": "hello bot"}'
```

### 筛选器测试 / Router Test
**测试消息分发 (Router)**
- 计算机命令示例 / Computer Command:
```bash
curl -X POST https://startrekbot.miranda5799.top/route \
     -H "Content-Type: application/json" \
     -d '{"session_id": "user1", "text": "报告传感器状态"}'
```
- 闲聊示例 / Smalltalk:
```bash
curl -X POST https://startrekbot.miranda5799.top/route \
     -H "Content-Type: application/json" \
     -d '{"session_id": "user1", "text": "你是谁"}'
```

**反馈纠错 (Feedback)**
```bash
curl -X POST https://startrekbot.miranda5799.top/route/feedback \
     -H "Content-Type: application/json" \
     -d '{"session_id": "user1", "text": "报告传感器状态", "pred_route": "chat", "correct_route": "computer", "note": "误判为闲聊"}'
```

**测试 Gemini Judge 单测 (Judge Test)**
```bash
curl -X POST https://startrekbot.miranda5799.top/judge \
     -H "Content-Type: application/json" \
     -d '{"text": "Computer, scan for life forms", "context": ["We are entering the system"]}'
```
- **意图分发** (Router): 结合规则引擎与 Gemini Judge
- **安全审核** (Moderation): 接入腾讯内容安全 TMS
- **星舰控制** (Tools): 本地工具集 (Status/Time/Calc) 支持 AI 工具调用
- **异步发送** (Send Queue): 全局限速 (RPS) 与 Session 冷却
- **管理面板** (Admin UI): 基于 LCARS 风格的 Web 管理后台

**测试安全审核 (Moderation)**
```bash
curl -X POST https://startrekbot.miranda5799.top/moderation/check \
     -H "Content-Type: application/json" \
     -d '{"text": "正常文本测试", "stage": "input"}'
```

**测试发送队列 (Send Queue)**
- 入队测试 / Enqueue:
```bash
curl -X POST https://startrekbot.miranda5799.top/send/enqueue \
     -H "Content-Type: application/json" \
     -d '{"text": "Computer, reply test message 1"}'
```
- 查看状态 / Status:
```bash
curl https://startrekbot.miranda5799.top/send/status
```
*(注：发送记录会记录在 VPS 的 `/app/data/send_log.jsonl` 中)*

### 管理面板 / Admin Web UI (M5)
可以通过浏览器访问星舰管理面板，在线修改群聊白名单、前缀等设置，无需重启服务。
- **URL**: `https://your-domain.top/admin?token=你的WEBHOOK_TOKEN`
- **功能**:
  - 管理 `BOT_ENABLED_GROUPS` (群聊白名单)
  - 修改 `COMPUTER_PREFIX` (计算机前缀)
  - 切换 `SENDER_TYPE` (Mock/QQ)
  - 配置 `QQ_SEND_ENDPOINT`
- **持久化**: 设置将保存至 `/app/data/settings.json`。

**测试本地工具 (Tools)**
- 状态 / Status: `curl https://startrekbot.miranda5799.top/tools/status`
- 时间 / Time: `curl https://startrekbot.miranda5799.top/tools/time`
- 计算 / Calc: 
```bash
curl -X POST https://startrekbot.miranda5799.top/tools/calc \
     -H "Content-Type: application/json" \
     -d '{"expr": "1024 * 2 / (8 + 8)"}'
```

**测试统一入口 (Ingest Pipeline)**
- 模拟接收消息并自动回复 (支持工具调用):
```bash
curl -X POST https://startrekbot.miranda5799.top/ingest \
     -H "Content-Type: application/json" \
     -d '{"session_id": "user1", "text": "Computer, report shield status."}'
```
*(注：如果识别为 tool_call，系统将执行本地工具并使用模板回复)*
*(注：若 `MODERATION_ENABLED=true` 且包含敏感词，将返回 `allow: false`)*

### 个人号接入 (OneBot v11)
连接个人 QQ 账号，建议使用 **NapCatQQ**:

1. **运行 NapCatQQ** (Docker):
   ```bash
   docker run -d \
     --name napcat \
     -e ACCOUNT=你的QQ号 \
     -v $(pwd)/napcat/config:/app/napcat/config \
     mlikiowa/napcat-docker:latest
   ```
2. **配置反向 WebSocket**:
   在 NapCat 配置 (`onebot11_<account>.json`) 中，将 `reverse_ws_url` 设置为:
   `ws://startrekbot.miranda5799.top/onebot/v11/ws`
   *(若未通过 SSL 代理，请使用 `ws://104.194.88.246:8080/onebot/v11/ws`)*
3. **登录**:
   运行 `docker logs -f napcat` 查看二维码，使用手机 QQ 扫码登录。

---

## English

### Project Overview
A Python FastAPI skeleton for QQ bots, supporting both official Webhooks and personal accounts (OneBot v11).

### Environments
- **Local Run**:
  ```bash
  cd infra
  docker compose up -d --build
  curl http://127.0.0.1:8080/health
  ```
- **Production (VPS)**:
  - **IP**: `104.194.88.246`
  - **Domain**: `https://startrekbot.miranda5799.top`

### Test Webhook
**Test QQ Official Webhook (Production)**
> Note: If `WEBHOOK_TOKEN` is set, add `-H "X-Webhook-Token: <your_token>"`
```bash
curl -X POST https://startrekbot.miranda5799.top/qq/webhook \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Token: your_token_here" \
     -d '{"type": "message", "author_id": "user123", "content": "hello bot"}'
```

### Personal Account Integration (OneBot v11)
To connect your personal QQ account, use **NapCatQQ** (recommended):

1. **Run NapCatQQ** (Docker):
   ```bash
   docker run -d \
     --name napcat \
     -e ACCOUNT=YourQQNumber \
     -v $(pwd)/napcat/config:/app/napcat/config \
     mlikiowa/napcat-docker:latest
   ```
2. **Configure Reverse WebSocket**:
   In NapCat config (`onebot11_<account>.json`), set `reverse_ws_url` to:
   `ws://startrekbot.miranda5799.top/onebot/v11/ws`
   *(If not using SSL proxy, use `ws://104.194.88.246:8080/onebot/v11/ws`)*
3. **Login**:
   Run `docker logs -f napcat` to see the QR code, scan it with your mobile QQ.
