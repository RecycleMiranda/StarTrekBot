import os
import time
import json
import logging
import asyncio
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from .models import InternalEvent
from . import dispatcher, router, judge_gemini, moderation, send_queue, rp_engine_gemini
from .sender_mock import MockSender
from .sender_qq import QQSender

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI(title="bot-service", version="0.0.1")

def log_jsonl(filename: str, data: dict):
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write log to {path}: {e}")

@app.on_event("startup")
async def startup_event():
    """
    Initialize sender and start the background worker.
    """
    sender_type = os.getenv("SENDQ_SENDER", "mock").lower()
    if sender_type == "qq":
        sender = QQSender()
        logger.info("Initializing QQSender adapter.")
    else:
        sender = MockSender()
        logger.info("Initializing MockSender.")

    sq = send_queue.SendQueue.get_instance(sender=sender)
    asyncio.create_task(sq.worker_loop())
    logger.info(f"Startup complete: SendQueue worker launched with {sender_type} sender.")

@app.on_event("shutdown")
def shutdown_event():
    """
    Gracefully stop the background worker.
    """
    sq = send_queue.SendQueue.get_instance()
    sq.stop()
    logger.info("Shutdown complete: SendQueue worker signaled to stop.")

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

async def _internal_route(session_id: str, text: str, meta: dict) -> dict:
    """
    Internal shared logic for routing a message.
    """
    # 1. First pass: Rule-based router
    r_res = router.route_event(session_id, text, meta)
    
    final_route = r_res["route"]
    final_confidence = r_res["confidence"]
    final_reason = r_res["reason"]
    
    judge_called = False
    j_res = None
    judge_error = None

    # 2. Strategy: When to call Gemini Judge
    needs_judge = (
        r_res["reason"] not in ["manual_enter", "manual_exit"] and
        not (r_res["reason"] == "wake_word" and r_res["confidence"] >= 0.95) and
        r_res["route"] == "computer" and r_res["confidence"] < 0.92
    )

    if needs_judge:
        judge_called = True
        context = router.get_session_context(session_id)
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
            final_route = "chat"
            final_confidence = 0.5
            final_reason = "judge_fallback_chat" if "TIMEOUT" in judge_error.upper() else "judge_error_fallback_chat"

    return {
        "router": r_res,
        "judge": j_res,
        "judge_called": judge_called,
        "judge_error": judge_error,
        "final": {
            "route": final_route,
            "confidence": final_confidence,
            "reason": final_reason
        }
    }

@app.post("/route")
async def post_route(request: Request):
    """
    Determine if the message should go to computer/RP or chat.
    """
    body = await request.json()
    session_id = body.get("session_id", "default")
    text = body.get("text", "")
    meta = body.get("meta") or {}

    # 0. Moderation Gate
    mod_res = await moderation.moderate_text(text, "input", meta)
    if not mod_res["allow"]:
        # (Same blocking logic as before)
        res_data = {
            "ts": int(time.time()),
            "session_id": session_id,
            "text": text,
            "pred_route": "chat",
            "confidence": 0.5,
            "reason": "blocked_by_moderation",
            "moderation": {
                "allow": mod_res["allow"],
                "action": mod_res["action"],
                "risk_level": mod_res["risk_level"],
                "reason": mod_res["reason"]
            },
            "meta": meta,
            "final_route": "chat",
            "final_confidence": 0.5,
            "final_reason": "blocked_by_moderation"
        }
        log_jsonl("router_log.jsonl", res_data)
        return {
            "code": 0, "message": "ok",
            "data": {
                "moderation": mod_res,
                "router": None,
                "judge": None,
                "final": {
                    "route": "chat",
                    "confidence": 0.5,
                    "reason": "blocked_by_moderation"
                }
            }
        }

    # 1. Route
    res = await _internal_route(session_id, text, meta)
    
    # 2. Log
    log_data = {
        "ts": int(time.time()),
        "session_id": session_id,
        "text": text,
        "pred_route": res["router"]["route"],
        "confidence": res["router"]["confidence"],
        "reason": res["router"]["reason"],
        "mode_active": res["router"]["mode"]["active"],
        "expires_at": res["router"]["mode"]["expires_at"],
        "meta": meta,
        "moderation": {
            "allow": mod_res["allow"],
            "action": mod_res["action"],
            "risk_level": mod_res["risk_level"]
        },
        "judge_called": res["judge_called"],
        "judge_route": res["judge"]["route"] if res["judge"] else None,
        "judge_confidence": res["judge"]["confidence"] if res["judge"] else None,
        "judge_reason": res["judge"]["reason"] if res["judge"] else None,
        "judge_error": res["judge_error"],
        "final_route": res["final"]["route"],
        "final_confidence": res["final"]["confidence"],
        "final_reason": res["final"]["reason"]
    }
    log_jsonl("router_log.jsonl", log_data)

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "moderation": mod_res,
            "router": res["router"],
            "judge": res["judge"],
            "final": res["final"]
        }
    }

@app.post("/ingest")
async def post_ingest(request: Request):
    """
    Unified entry point: ingestion -> moderation -> routing -> [RP] -> enqueue
    """
    body = await request.json()
    session_id = body.get("session_id", "default")
    text = body.get("text", "")
    meta = body.get("meta") or {}

    # a) Moderation (Input)
    mod_res = await moderation.moderate_text(text, "input", meta)
    if not mod_res["allow"]:
        return {
            "code": 0, "message": "ok",
            "data": {
                "moderation": mod_res,
                "router": None,
                "final": {"route": "chat", "confidence": 0.5, "reason": "blocked_by_moderation"},
                "rp": None,
                "enqueued": None
            }
        }

    # b) Routing
    route_res = await _internal_route(session_id, text, meta)
    final = route_res["final"]

    # c) RP Engine (if route is computer)
    rp_res = None
    enqueued = None
    if final["route"] == "computer":
        context_data = router.get_session_context(session_id)
        # Extract plain text context
        context = [c["text"] for c in context_data]
        if context and context[-1] == text:
            context = context[:-1]
            
        rp_res = await rp_engine_gemini.generate_computer_reply(text, context, meta)
        
        # d) Enqueue
        session_key = meta.get("group_id") or session_id
        meta["session_key"] = session_key
        
        sq = send_queue.SendQueue.get_instance()
        enqueued = await sq.enqueue_send(session_key, rp_res["reply"], meta)

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "moderation": mod_res,
            "router": route_res["router"],
            "final": final,
            "rp": rp_res,
            "enqueued": enqueued
        }
    }

@app.get("/rp/health")
def get_rp_health():
    """
    Check RP engine status.
    """
    return {"code": 0, "message": "ok", "data": rp_engine_gemini.get_status()}

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

@app.post("/moderation/check")
async def post_moderation_check(request: Request):
    """
    Direct endpoint to test content moderation.
    """
    body = await request.json()
    text = body.get("text", "")
    stage = body.get("stage", "input")
    meta = body.get("meta") or {}
    
    res = await moderation.moderate_text(text, stage, meta)
    return {"code": 0, "message": "ok", "data": res}

@app.get("/moderation/health")
def get_moderation_health():
    """
    Check moderation service status.
    """
    return {"code": 0, "message": "ok", "data": moderation.get_status()}

@app.post("/send/enqueue")
async def post_send_enqueue(request: Request):
    """
    Manually enqueue a message for sending.
    """
    body = await request.json()
    session_id = body.get("session_id", "default")
    text = body.get("text", "")
    meta = body.get("meta") or {}
    
    # Use group_id as priority session_key per requirements
    session_key = meta.get("group_id") or session_id
    # Ensure key info stays in meta for the sender
    meta["session_key"] = session_key
    
    sq = send_queue.SendQueue.get_instance()
    res = await sq.enqueue_send(session_key, text, meta)
    
    if "error" in res:
        return {"code": 1, "message": res["error"], "data": res}
    return {"code": 0, "message": "ok", "data": res}

@app.get("/send/status")
def get_send_status():
    """
    View queue occupancy and statistics.
    """
    sq = send_queue.SendQueue.get_instance()
    return {"code": 0, "message": "ok", "data": sq.get_status()}

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
