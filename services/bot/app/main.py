import os
import time
from fastapi import FastAPI, Request
from .models import InternalEvent
from . import dispatcher

app = FastAPI(title="bot-service", version="0.0.1")

@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"code": 0, "message": "ok", "data": {"ok": True, "env": os.getenv("APP_ENV", "dev")}}

@app.post("/qq/webhook")
async def qq_webhook(request: Request):
    """
    Entrance for QQ Official Robot WebHook with optional token authentication.
    """
    token = os.getenv("WEBHOOK_TOKEN")
    if token:
        request_token = request.headers.get("X-Webhook-Token")
        if request_token != token:
            return {
                "code": 401,
                "message": "unauthorized",
                "data": None
            }

    body = await request.json()
    
    # Minimal extraction logic for OneBot-like skeleton
    # Fields depend on the platform's specific structure
    event = InternalEvent(
        event_type=body.get("type", "unknown"),
        platform="qq",
        user_id=body.get("author_id") or body.get("user_id"),
        group_id=body.get("group_id") or body.get("guild_id"),
        message_id=body.get("id") or body.get("message_id"),
        text=body.get("content") or body.get("text"),
        raw=body,
        ts=int(time.time())
    )
    
    dispatcher.handle_event(event)
    return {"code": 0, "message": "ok", "data": {"received": True}}

@app.post("/onebot/event")
def onebot_event(event: InternalEvent):
    """
    Entrance for standard internal events.
    """
    dispatcher.handle_event(event)
    return {"code": 0, "message": "ok", "data": {"received": True}}
