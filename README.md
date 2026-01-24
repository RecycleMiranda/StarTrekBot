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
防风控限速配置（可在 VPS 的 `infra/docker-compose.override.yml` 修改）：
```yaml
services:
  bot:
    environment:
      - SENDQ_GLOBAL_RPS=2.0
      - SENDQ_SESSION_COOLDOWN_MS=1200
```

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
