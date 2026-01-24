# output_for_chatgpt

- commit hash: 2985b1a (Local)
- 变更文件列表:
  - `services/bot/app/router.py` (New)
  - `services/bot/app/main.py`
  - `infra/docker-compose.yml`
  - `README.md`
  - `docs/project.md`

- VPS 验证命令 (以 127.0.0.1:8088 为准):
  1) **测试 Router (Computer)**:
     ```bash
     curl -X POST http://127.0.0.1:8088/route \
          -H "Content-Type: application/json" \
          -d '{"session_id": "test_vps", "text": "报告传感器状态"}'
     ```
     *预期输出*: `{"code":0,"message":"ok","data":{"route":"computer",...}}`

  2) **测试 Router (Chat)**:
     ```bash
     curl -X POST http://127.0.0.1:8088/route \
          -H "Content-Type: application/json" \
          -d '{"session_id": "test_vps", "text": "随便聊聊"}'
     ```
     *预期输出*: `{"code":0,"message":"ok","data":{"route":"chat",...}}`

  3) **测试反馈**:
     ```bash
     curl -X POST http://127.0.0.1:8088/route/feedback \
          -H "Content-Type: application/json" \
          -d '{"session_id": "test_vps", "text": "报告", "pred_route": "chat", "correct_route": "computer"}'
     ```

  4) **验证日志落盘**:
     ```bash
     docker exec bot ls -l /app/data/
     # 或在 VPS 宿主机查看
     ls -l /opt/StarTrekBot/data/
     tail -n 2 /opt/StarTrekBot/data/router_log.jsonl
     ```
