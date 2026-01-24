# output_for_chatgpt

- commit hash: Pending (Local)
- 变更文件列表:
  - `services/bot/app/sender_base.py` (New)
  - `services/bot/app/sender_mock.py`
  - `services/bot/app/sender_qq.py` (New)
  - `services/bot/app/send_queue.py`
  - `services/bot/app/main.py`
  - `README.md`
  - `docs/project.md`

- VPS 验证命令 (以 127.0.0.1:8088 为准):

  1) **验证 Mock 发送 (Default)**:
     ```bash
     curl -X POST http://127.0.0.1:8088/send/enqueue \
          -H "Content-Type: application/json" \
          -d '{"session_id": "test_plug", "text": "Mock test"}'
     ```
     *预期*: `tail -n 1 /opt/StarTrekBot/data/send_log.jsonl` 中 `provider` 为 `MockSender`。

  2) **验证 QQ 适配器 (未配置 Endpoint 时)**:
     *启动参数*: `SENDQ_SENDER=qq` (通过环境变量或 override)
     ```bash
     curl -X POST http://127.0.0.1:8088/send/enqueue \
          -H "Content-Type: application/json" \
          -d '{"session_id": "test_plug", "text": "QQ test"}'
     ```
     *预期*: `send_log.jsonl` 中出现一条 `status: failed` 的记录，`error` 包含 `QQ_SEND_ENDPOINT_NOT_CONFIGURED`，且 Worker 不中断。

  3) **验证 QQ 适配器错误处理**:
     *配置错误的 Endpoint*: `QQ_SEND_ENDPOINT=http://127.0.0.1:1/invalid`
     *预期*: `send_log.jsonl` 记录连接错误（Connection error），体现了可靠的消息状态追踪。
