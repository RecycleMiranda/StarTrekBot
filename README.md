# StarTrekBot

[中文](#中文) | [English](#english)

---

## 中文

### 项目简介
一个用于 QQ 机器人的 Python FastAPI 骨架，支持官方 Webhook 和个人号 (OneBot v11)。

### 本地运行
```bash
cd infra
docker compose up -d --build
curl http://127.0.0.1:8080/health
```

### 测试 Webhook
**测试 QQ 官方 Webhook**
> 注意：如果设置了 `WEBHOOK_TOKEN` 环境变量，请添加 `-H "X-Webhook-Token: <your_token>"`
```bash
curl -X POST http://127.0.0.1:8080/qq/webhook \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Token: your_token_here" \
     -d '{"type": "message", "author_id": "user123", "content": "hello bot"}'
```

**测试内部事件 (Internal Event)**
```bash
curl -X POST http://127.0.0.1:8080/onebot/event \
     -H "Content-Type: application/json" \
     -d '{"event_type": "private_message", "user_id": "456", "text": "test internal", "raw": {}}'
```

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
   `ws://<your_ip>:8080/onebot/v11/ws`
3. **登录**:
   运行 `docker logs -f napcat` 查看二维码，使用手机 QQ 扫码登录。

---

## English

### Project Overview
A Python FastAPI skeleton for QQ bots, supporting both official Webhooks and personal accounts (OneBot v11).

### Local Run
```bash
cd infra
docker compose up -d --build
curl http://127.0.0.1:8080/health
```

### Test Webhook
**Test QQ Official Webhook**
> Note: If `WEBHOOK_TOKEN` is set, add `-H "X-Webhook-Token: <your_token>"`
```bash
curl -X POST http://127.0.0.1:8080/qq/webhook \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Token: your_token_here" \
     -d '{"type": "message", "author_id": "user123", "content": "hello bot"}'
```

**Test Internal Event**
```bash
curl -X POST http://127.0.0.1:8080/onebot/event \
     -H "Content-Type: application/json" \
     -d '{"event_type": "private_message", "user_id": "456", "text": "test internal", "raw": {}}'
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
   `ws://<your_ip>:8080/onebot/v11/ws`
3. **Login**:
   Run `docker logs -f napcat` to see the QR code, scan it with your mobile QQ.
