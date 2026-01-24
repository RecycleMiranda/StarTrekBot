# bot project

## Local run
cd infra
docker compose up -d --build
curl http://127.0.0.1:8080/health

## Test Webhook
# Test QQ Webhook
curl -X POST http://127.0.0.1:8080/qq/webhook \
     -H "Content-Type: application/json" \
     -d '{"type": "message", "author_id": "user123", "content": "hello bot"}'

# Test Internal Event
curl -X POST http://127.0.0.1:8080/onebot/event \
     -H "Content-Type: application/json" \
     -d '{"event_type": "private_message", "user_id": "456", "text": "test internal", "raw": {}}'
