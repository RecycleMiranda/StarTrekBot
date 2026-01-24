import os
import time
import json
import logging
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from .models import InternalEvent
from . import dispatcher, router, judge_gemini

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI(title="bot-service", version="0.0.1")

def log_jsonl(filename: str, data: dict):

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

@app.websocket("/onebot/v11/ws")
async def onebot_v11_ws(websocket: WebSocket):
    """
    Reverse WebSocket endpoint for OneBot v11 (e.g. NapCatQQ).
    """
    await websocket.accept()
    print("[WebSocket] OneBot v11 connection accepted.")
    try:
        while True:
            data = await websocket.receive_json()
            
            # OneBot v11 message event processing
            if data.get("post_type") == "message":
                event = InternalEvent(
                    event_type=data.get("message_type"), # private or group
                    platform="qq",
                    user_id=str(data.get("user_id")),
                    group_id=str(data.get("group_id")) if data.get("group_id") else None,
                    message_id=str(data.get("message_id")),
                    text=data.get("raw_message"),
                    raw=data,
                    ts=data.get("time")
                )
                dispatcher.handle_event(event)
            
            # You can handle meta_event (heartbeat) or notice here if needed
            
    except WebSocketDisconnect:
        print("[WebSocket] OneBot v11 connection closed.")

@app.post("/route")
async def post_route(request: Request):
    """
    Determine if the message should go to computer/RP or chat.
    Includes Gemini Judge for secondary verification.
    """
    body = await request.json()
    session_id = body.get("session_id", "default")
    text = body.get("text", "")
    meta = body.get("meta") or {}

    # 1. First pass: Rule-based router
    r_res = router.route_event(session_id, text, meta)
    
    final_route = r_res["route"]
    final_confidence = r_res["confidence"]
    final_reason = r_res["reason"]
    
    judge_called = False
    j_res = None
    judge_error = None

    # 2. Strategy: When to call Gemini Judge
    # - Skip if manual command or high-confidence wake word
    # - Call only if router says 'computer' but confidence is not 'very high' (< 0.92)
    needs_judge = (
        r_res["reason"] not in ["manual_enter", "manual_exit"] and
        not (r_res["reason"] == "wake_word" and r_res["confidence"] >= 0.95) and
        r_res["route"] == "computer" and r_res["confidence"] < 0.92
    )

    if needs_judge:
        judge_called = True
        context = router.get_session_context(session_id)
        # Context should not include the current trigger for the LLM
        # get_session_context returns history including current text (because router.py adds it first)
        # So we take history[:-1] if matches
        if context and context[-1]["text"] == text:
            context = context[:-1]
            
        try:
            j_res = await judge_gemini.judge_intent(
                trigger={"text": text, "ts": int(time.time())},
                context=context,
                meta={**meta, "session_id": session_id}
            )
            final_route = j_res["route"]
            final_confidence = j_res["confidence"]
            final_reason = f"judge_{j_res['reason']}"
        except Exception as e:
            logger.error(f"Judge failed: {e}")
            judge_error = str(e)
            # A-Strategy Fallback: chat
            final_route = "chat"
            final_confidence = 0.5
            final_reason = "judge_fallback_chat" if "TIMEOUT" in judge_error.upper() else "judge_error_fallback_chat"

    # Log to router_log.jsonl
    log_data = {
        "ts": int(time.time()),
        "session_id": session_id,
        "text": text,
        "pred_route": r_res["route"],
        "confidence": r_res["confidence"],
        "reason": r_res["reason"],
        "mode_active": r_res["mode"]["active"],
        "expires_at": r_res["mode"]["expires_at"],
        "meta": meta,
        "judge_called": judge_called,
        "judge_route": j_res["route"] if j_res else None,
        "judge_confidence": j_res["confidence"] if j_res else None,
        "judge_reason": j_res["reason"] if j_res else None,
        "judge_error": judge_error,
        "final_route": final_route,
        "final_confidence": final_confidence,
        "final_reason": final_reason
    }
    log_jsonl("router_log.jsonl", log_data)

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "router": r_res,
            "judge": j_res,
            "final": {
                "route": final_route,
                "confidence": final_confidence,
                "reason": final_reason
            }
        }
    }

@app.post("/judge")
async def post_judge(request: Request):
    """
    Direct endpoint to test Gemini Judge.
    """
    body = await request.json()
    text = body.get("text", "")
    context_texts = body.get("context", [])
    meta = body.get("meta") or {}

    context = [{"text": t} for t in context_texts]
    
    try:
        res = await judge_gemini.judge_intent(
            trigger={"text": text, "ts": int(time.time())},
            context=context,
            meta=meta
        )
        return {"code": 0, "message": "ok", "data": res}
    except ValueError as e:
        return {"code": 400, "message": str(e), "data": None}
    except Exception as e:
        logger.error(f"Internal Judge error: {e}")
        return {"code": 500, "message": "internal_judge_error", "data": None}

@app.post("/route/feedback")
async def post_route_feedback(request: Request):
    """
    Collect feedback for routing decisions.
    """
    body = await request.json()
    log_data = {
        "ts": int(time.time()),
        "session_id": body.get("session_id"),
        "text": body.get("text"),
        "pred_route": body.get("pred_route"),
        "correct_route": body.get("correct_route"),
        "note": body.get("note")
    }
    log_jsonl("router_feedback.jsonl", log_data)

    return {"code": 0, "message": "ok", "data": None}
