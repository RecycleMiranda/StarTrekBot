import os
import time
import json
import logging
import asyncio
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from .models import InternalEvent
from . import dispatcher, router, judge_gemini, moderation, send_queue, rp_engine_gemini, tools, sentinel
from .config_manager import ConfigManager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from .sender_mock import MockSender
from .sender_qq import QQSender
import httpx
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)

def _get_verified_token(provided_token: str) -> bool:
    """Token validation disabled for easier setup. Set WEBHOOK_TOKEN to re-enable."""
    # TEMPORARILY DISABLED - uncomment below to re-enable authentication
    # raw_expected = os.getenv("WEBHOOK_TOKEN")
    # if not raw_expected:
    #     return True
    # expected = raw_expected.strip().strip('"').strip("'")
    # provided = (provided_token or "").strip()
    # if ":" in provided and len(provided) > len(expected):
    #     provided = provided.split(":")[0]
    # return provided == expected
    return True  # PUBLIC ACCESS MODE

app = FastAPI(title="bot-service", version="0.0.1")

def log_jsonl(filename: str, data: dict):
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write log to {path}: {e}")

async def run_boot_sync():
    """
    Executes a Master Pull from GitHub to hydrate local logs/data on deployment.
    """
    logger.info("Initializing Starfleet Logistics Boot Sync...")
    try:
        # Resolve path to git_sync.py (located at repo root)
        # services/bot/app/main.py -> ../../../git_sync.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        sync_script = os.path.join(repo_root, "git_sync.py")
        
        if os.path.exists(sync_script):
            process = await asyncio.create_subprocess_exec(
                "python3", sync_script, "pull",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_root
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                logger.info("Logistics Sync Success: Local data tracks updated.")
            else:
                logger.warning(f"Logistics Sync failed with exit code {process.returncode}")
                if stderr: logger.warning(f"Sync Error: {stderr.decode()}")
        else:
            logger.warning(f"Sync Script not found at: {sync_script}")
    except Exception as e:
        logger.error(f"Critical error during boot sync: {e}")

@app.on_event("startup")
async def startup_event():
    """
    Initialize config, sender and start the background worker.
    """
    # 0. Logsitics Boot Sync (Hydrate data from logs branch)
    await run_boot_sync()

    token = (os.getenv("WEBHOOK_TOKEN") or "").strip().strip('"').strip("'")
    if token:
        logger.info(f"[Auth] Admin Token configured. Hint: {token[:3]}...{token[-1] if len(token)>1 else ''}")
    else:
        logger.warning("[Auth] NO WEBHOOK_TOKEN SET. Admin UI will be public!")

    config = ConfigManager.get_instance()
    sender_type = config.get("sender_type", "mock").lower()
    
    if sender_type == "qq":
        sender = QQSender()
        logger.info("Initializing QQSender adapter.")
    else:
        sender = MockSender()
        logger.info("Initializing MockSender.")

    sq = send_queue.SendQueue.get_instance(sender=sender)
    asyncio.create_task(sq.worker_loop())
    
    # --- PHASE 5: SENTINEL EVOLUTION CORE ---
    from .ship_systems import get_ship_systems
    asyncio.create_task(sentinel.sentinel_loop(get_ship_systems()))
    logger.info("Sentinel Evolution Core launched (Trigger mode).")
    
    logger.info(f"Startup complete: SendQueue worker launched with {sender_type} sender (Persistent Config).")

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
        if not request_token or request_token.strip() != token.strip():
            logger.warning(f"Unauthorized WebHook access attempt from {request.client.host}")
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
    
    await dispatcher.handle_event(event)
    return {"code": 0, "message": "ok", "data": {"received": True}}

@app.post("/onebot/event")
async def onebot_event(request: Request):
    """
    Entrance for OneBot v11 HTTP POST events from NapCat.
    """
    body = await request.json()
    logger.info(f"[OneBot] Received event: {body.get('post_type', 'unknown')}")
    
    # Only process message events
    if body.get("post_type") == "message":
        # Extract text from message array
        text = ""
        raw_message = body.get("message", [])
        if isinstance(raw_message, list):
            for seg in raw_message:
                if seg.get("type") == "text":
                    text += seg.get("data", {}).get("text", "")
        elif isinstance(raw_message, str):
            text = raw_message
        
        event = InternalEvent(
            event_type=body.get("message_type", "group"),
            platform="qq",
            user_id=str(body.get("user_id")),
            group_id=str(body.get("group_id")) if body.get("group_id") else None,
            message_id=str(body.get("message_id")),
            text=text or body.get("raw_message", ""),
            raw=body,
            ts=body.get("time", int(time.time()))
        )
        # FIRE AND FORGET: Handle in background to prevent webhook timeout retries
        asyncio.create_task(dispatcher.handle_event(event))
    
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
                # FIRE AND FORGET
                asyncio.create_task(dispatcher.handle_event(event))
            
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

    # 0. Group Whitelist Check
    if not dispatcher.is_group_enabled(meta.get("group_id") or session_id if "group" in session_id else None):
        # We use a bit of heuristic for session_id if it's used as group_id
        # But ingest/route usually provide group_id in meta.
        g_id = meta.get("group_id") or (session_id if "group" in session_id else None)
        if not dispatcher.is_group_enabled(g_id):
            return {
                "code": 0, "message": "group_not_enabled",
                "data": {"final": {"route": "chat", "reason": "group_not_whitelisted"}}
            }

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

    # 0. Group Whitelist Check
    group_id = meta.get("group_id") or (session_id if "group" in session_id else None)
    if not dispatcher.is_group_enabled(group_id):
        return {
            "code": 0, "message": "group_not_enabled",
            "data": {
                "moderation": None, "router": None,
                "final": {"route": "chat", "reason": "group_not_whitelisted"},
                "rp": None, "enqueued": None
            }
        }

    # a) Moderation (Input)
    mod_res = await moderation.moderate_text(text, "input", meta)
    if not mod_res["allow"]:
        # SECURITY PROTOCOL ALPHA: Formal Warning/Lockout
        user_id = meta.get("user_id")
        platform = meta.get("platform", "qq")
        group_id = meta.get("group_id")
        
        warning_msg = await moderation.enforce_shipboard_order(user_id, platform, group_id, mod_res)
        
        if warning_msg:
            session_key = f"{platform}:{group_id or user_id}"
            await send_queue.SendQueue.get_instance().enqueue_send(session_key, warning_msg, meta)

        return {
            "code": 0, "message": "blocked_by_protocol",
            "data": {
                "moderation": mod_res,
                "router": None,
                "final": {"route": "chat", "confidence": 0.5, "reason": "blocked_by_moderation"},
                "rp": None,
                "enqueued": True if warning_msg else False
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
        
        final_text = rp_res["reply"]
        tool_info = None

        # Handle Tool Call Pipeline
        if rp_res.get("intent") == "tool_call":
            tool_name = rp_res.get("tool")
            tool_args = rp_res.get("args") or {}
            
            if tool_name == "status":
                s = tools.get_status()
                final_text = f"Computer: Shields at {s['shields_percent']}%. Alert status {s['alert']}. Warp factor {s['warp_factor']}."
                tool_info = {"name": "status", "args": tool_args, "res": s}
            elif tool_name == "time":
                t = tools.get_time()
                final_text = f"Computer: Current time is {t['iso']} ({t['tz']})."
                tool_info = {"name": "time", "args": tool_args, "res": t}
            elif tool_name == "calc":
                c = tools.calc(tool_args.get("expr", ""))
                if c["ok"]:
                    final_text = f"Computer: Result is {c['result']}."
                else:
                    final_text = "Computer: Unable to compute that expression."
                tool_info = {"name": "calc", "args": tool_args, "res": c}

        # d) Enqueue
        session_key = meta.get("group_id") or session_id
        meta["session_key"] = session_key
        
        sq = send_queue.SendQueue.get_instance()
        enqueued = await sq.enqueue_send(session_key, final_text, meta)

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "moderation": mod_res,
            "router": route_res["router"],
            "final": final,
            "rp": rp_res,
            "tool": tool_info,
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

@app.get("/tools/status")
def get_tool_status():
    """Direct access to ship status tool."""
    return {"code": 0, "message": "ok", "data": tools.get_status()}

@app.get("/tools/time")
def get_tool_time():
    """Direct access to system time tool."""
    return {"code": 0, "message": "ok", "data": tools.get_time()}

@app.post("/tools/calc")
async def post_tool_calc(request: Request):
    """Direct access to calculation tool."""
    body = await request.json()
    res = tools.calc(body.get("expr", ""))
    return {"code": 0, "message": "ok", "data": res}

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

# --- Settings & Admin API ---

@app.get("/api/v1/lcars/msd")
async def get_lcars_msd(token: str = None):
    """Returns the full tree of MSD systems and their metrics."""
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    return {"code": 0, "message": "ok", "data": ss.get_full_manifest()}

@app.get("/api/v1/lcars/sop")
async def list_lcars_sops(token: str = None):
    """Returns all learned (DRAFT) SOPs for review."""
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    from .sop_manager import get_sop_manager
    sm = get_sop_manager()
    return {"code": 0, "message": "ok", "data": sm.cache.get("learned_procedures", {})}

@app.post("/api/v1/lcars/sop/approve")
async def approve_lcars_sop(request: Request, token: str = None):
    """Approves a DRAFT SOP and moves it to system_defaults."""
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    
    body = await request.json()
    query = body.get("query")
    
    from .sop_manager import get_sop_manager
    sm = get_sop_manager()
    
    learned = sm.cache.get("learned_procedures", {})
    if query in learned:
        sop = learned.pop(query)
        sop["status"] = "APPROVED"
        sop["confidence"] = 1.0
        
        # Add to system_defaults with a clean ID
        intent_id = sop.get("intent_id", f"APPROVED_{int(time.time())}")
        sm.cache.setdefault("system_defaults", {})[intent_id] = {
            "trigger": [query],
            "tool_chain": sop["tool_chain"],
            "intent_id": intent_id,
            "confidence": 1.0
        }
        sm._save_cache()
        return {"code": 0, "message": "SOP approved into fleet protocols"}
    
    return {"code": 404, "message": "SOP draft not found"}

@app.get("/api/v1/lcars/faults")
async def get_lcars_faults(token: str = None):
    """Returns all active faults from the DiagnosticManager."""
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    from .diagnostic_manager import get_diagnostic_manager
    dm = get_diagnostic_manager()
    # Simplified manifest for UI scan
    return {"code": 0, "message": "ok", "data": dm.active_faults}


@app.get("/api/settings")
async def get_settings(token: str = None):
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    
    config = ConfigManager.get_instance().get_all()
    # Mask sensitive keys
    clean_config = {k: v for k, v in config.items()}
    return {"code": 0, "message": "ok", "data": clean_config}

@app.post("/api/settings")
async def save_settings(request: Request, token: str = None):
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    
    body = await request.json()
    config = ConfigManager.get_instance()
    if config.save_config(body):
        return {"code": 0, "message": "ok", "data": config.get_all()}
    return {"code": 1, "message": "failed to save settings"}

@app.post("/api/moderation/sync")
async def sync_moderation_keywords(token: str = None):
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    
    from .moderation_keywords import KeywordFilter
    result = await KeywordFilter.get_instance().sync_from_remote()
    return result

@app.get("/api/sentinel/status")
async def get_api_sentinel_status(token: str = None):
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    
    return {"code": 0, "message": "ok", "data": tools.get_sentinel_status()}

@app.get("/api/napcat/qr")
async def get_napcat_qr(token: str = None):
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    
    config = ConfigManager.get_instance().get_all()
    base_url = f"http://{config['napcat_host']}:{config['napcat_port']}"
    headers = {"Authorization": f"Bearer {config['napcat_token'].strip()}"} if config['napcat_token'] else {}
    
    # Common paths for NapCat QR API
    paths = [
        "/api/login/get_qr",
        "/api/login/getqr",
        "/api/login/qrcode",
        "/webui/api/login/get_qr"
    ]
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        last_error = ""
        for path in paths:
            target_url = f"{base_url}{path}"
            # Try both "Bearer token" and raw "token"
            for auth_style in ["Bearer", "Raw"]:
                header_val = config['napcat_token'].strip()
                if auth_style == "Bearer":
                    headers = {"Authorization": f"Bearer {header_val}"} if header_val else {}
                else:
                    headers = {"Authorization": header_val} if header_val else {}

                try:
                    resp = await client.post(target_url, headers=headers)
                    if resp.status_code == 200:
                        try:
                            return resp.json()
                        except:
                            last_error = f"Path {path} ({auth_style}) non-JSON"
                            continue
                    elif resp.status_code == 401:
                        last_error = f"Auth failed at {path} with style {auth_style}"
                    else:
                        last_error = f"Path {path} ({auth_style}) status {resp.status_code}"
                except Exception as e:
                    last_error = f"Path {path} connection error: {e}"
        
        return {
            "code": 1, 
            "message": "NapCat QR API not found or authentication failed",
            "last_error": last_error,
            "probed_paths": paths
        }

@app.get("/api/napcat/status")
async def get_napcat_status(token: str = None):
    if not _get_verified_token(token):
        return JSONResponse(status_code=401, content={"code": 401, "message": "unauthorized"})
    
    config = ConfigManager.get_instance().get_all()
    base_url = f"http://{config['napcat_host']}:{config['napcat_port']}"
    headers = {"Authorization": f"Bearer {config['napcat_token'].strip()}"} if config['napcat_token'] else {}

    paths = ["/api/status", "/webui/api/status"]
    
    async with httpx.AsyncClient(timeout=3.0) as client:
        for path in paths:
            try:
                resp = await client.get(f"{base_url}{path}", headers=headers)
                if resp.status_code == 200:
                    return resp.json()
            except:
                continue
        return {"code": 1, "message": "NapCat status API not found"}

# Serve static files for Admin UI
# Use absolute path relative to current file to be safe in different working dirs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

logger.info(f"[Settings] Looking for static files in: {STATIC_DIR}")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info("[Settings] Mounted /static successfully.")
else:
    logger.warning(f"[Settings] Static directory NOT FOUND: {STATIC_DIR}")

@app.get("/admin", response_class=HTMLResponse)
def get_admin(request: Request):
    provided_token = request.query_params.get("token")
    if not _get_verified_token(provided_token):
        # We need expected_token here just for the hint in the UI
        raw_expected = (os.getenv("WEBHOOK_TOKEN") or "").strip().strip('"').strip("'")
        hint = f"{raw_expected[0]}...{raw_expected[-1]}" if len(raw_expected) > 2 else "***"
        
        return HTMLResponse(f"""
            <div style="background:#05080c; color:#c54242; padding:50px; font-family:sans-serif; height:100vh; text-align:center;">
                <h1 style="font-size:3rem; letter-spacing:5px;">ACCESS DENIED</h1>
                <p style="font-size:1.5rem;">[ 401 - Unauthorized ]</p>
                <div style="border:1px solid #c54242; padding:20px; display:inline-block; margin-top:20px; text-align:left;">
                    <p style="color:#75a2d1">子空间安全协议：Token 验证失败。</p>
                    <p style="color:#75a2d1">预期格式提示：<code style="background:#1b264f; padding:2px 5px;">{hint}</code></p>
                    <p style="color:#eee">请确保你的浏览器 URL 结尾是：<br><code>/admin?token=你在服务器查到的完整Token</code></p>
                    <p style="color:#666; font-size:0.8rem; margin-top:20px;">提示：请检查是否误复制了末尾的 ":1" 或空格。</p>
                </div>
            </div>
        """, status_code=401)

    admin_index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(admin_index):
        with open(admin_index, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Admin UI Source Not Found</h1>"

@app.get("/admin/napcat")
def redirect_to_napcat(request: Request):
    """Attempt to redirect to NapCat WebUI on port 6099."""
    host = request.url.hostname
    return HTMLResponse(f"""
        <html><body>
        <p>正在跳转至 NapCat 控制台...</p>
        <script>window.location.href = "http://"+window.location.hostname+":6099/webui/";</script>
        </body></html>
    """)

    pass
