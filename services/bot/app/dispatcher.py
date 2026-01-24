import os
import logging
import base64
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from .models import InternalEvent
from .config_manager import ConfigManager
from . import router
from . import send_queue
from . import rp_engine_gemini
from . import permissions
from . import report_builder
from . import visual_core

logger = logging.getLogger(__name__)

# Thread pool for running async code from sync context
_executor = ThreadPoolExecutor(max_workers=4)

def _run_async(coro):
    """Run async coroutine in a new event loop in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def _execute_tool(tool: str, args: dict, event: InternalEvent, profile: dict) -> dict:
    """Executes a ship tool with user context."""
    from . import tools
    try:
        if tool == "status":
            return tools.get_status()
        elif tool == "time":
            return tools.get_time()
        elif tool == "calc":
            return tools.calc(args.get("expr", ""))
        elif tool == "replicate":
            return tools.replicate(args.get("item_name", ""), str(event.user_id), profile.get("rank", "Ensign"))
        elif tool == "holodeck":
            return tools.reserve_holodeck(args.get("program", "Standard Grid"), args.get("hours", 1.0), str(event.user_id), profile.get("rank", "Ensign"))
        elif tool == "personal_log":
            return tools.personal_log(args.get("content", ""), str(event.user_id))
        return {"ok": False, "error": f"unknown_tool: {tool}"}
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {"ok": False, "error": str(e)}

def is_group_enabled(group_id: str | None) -> bool:
    """
    Checks if the given group_id is in the whitelist via ConfigManager.
    """
    if group_id is None:
        return True
    
    config = ConfigManager.get_instance()
    whitelist_raw = config.get("enabled_groups", "*")
    whitelist = [g.strip() for g in whitelist_raw.split(",") if g.strip()]
    
    if not whitelist or "*" in whitelist:
        return True
        
    return str(group_id) in whitelist

def handle_event(event: InternalEvent):
    """
    Dispatcher for internal events with group filtering.
    """
    if not is_group_enabled(event.group_id):
        logger.info(f"[Dispatcher] Group {event.group_id} not in whitelist. Dropping event.")
        return False

    logger.info(f"[Dispatcher] Handling Event: {event.model_dump_json(indent=2)}")
    
    # Skip empty messages
    if not event.text or not event.text.strip():
        logger.info("[Dispatcher] Empty message, skipping.")
        return False
    
    # Build session ID
    session_id = f"{event.platform}:{event.group_id or event.user_id}"
    
    # Route the message with full event meta for attribution
    try:
        route_result = router.route_event(session_id, event.text, {
            "event": event.model_dump(),
            "event_raw": event.raw
        })
        logger.info(f"[Dispatcher] Route result: {route_result}")
        
        # Check if we should respond (computer mode or high confidence)
        if route_result.get("route") == "computer" or route_result.get("confidence", 0) >= 0.7:
            # Handle "Wake-only" bleep
            if route_result.get("is_wake_only"):
                logger.info("[Dispatcher] Wake-only detected, sending bleep.")
                sq = send_queue.SendQueue.get_instance()
                session_key = f"qq:{event.group_id or event.user_id}"
                
                # Classic Star Trek computer chirping sound representation
                bleep_text = "*Computer Acknowledgment Chirp*"
                
                # Use executor to avoid "loop already running" error
                _executor.submit(
                    _run_async,
                    sq.enqueue_send(session_key, bleep_text, {
                        "group_id": event.group_id,
                        "user_id": event.user_id,
                        "reply_to": event.message_id
                    })
                )
                return True

            # Fetch full ALAS User Profile
            sender = event.raw.get("sender", {})
            nickname = sender.get("card") or sender.get("nickname")
            title = sender.get("title") # QQ Group Title
            user_profile = permissions.get_user_profile(event.user_id, nickname, title)
            profile_str = permissions.format_profile_for_ai(user_profile)

            # Generate AI reply in a separate thread to avoid event loop conflict
            future = _executor.submit(
                _run_async,
                rp_engine_gemini.generate_computer_reply(
                    trigger_text=event.text,
                    context=router.get_session_context(session_id),
                    meta={
                        "session_id": session_id, 
                        "user_id": event.user_id,
                        "user_profile": profile_str
                    }
                )
            )
            result = future.result(timeout=15)  # 15 second timeout
            
            logger.info(f"[Dispatcher] AI result: {result}")
            
            if result and result.get("ok") and result.get("reply"):
                reply_raw = result["reply"]
                intent = result.get("intent")
                
                image_b64 = None
                if intent == "report" and isinstance(reply_raw, dict):
                    # Render image
                    img_io = visual_core.render_report(reply_raw)
                    image_b64 = base64.b64encode(img_io.getvalue()).decode("utf-8")
                    reply_text = f"Generating visual report... (Intent: {intent})"
                elif intent == "tool_call":
                    tool = result.get("tool")
                    args = result.get("args") or {}
                    logger.info(f"[Dispatcher] Executing tool: {tool}({args})")
                    tool_result = _execute_tool(tool, args, event, user_profile)
                    
                    if tool_result.get("ok"):
                        reply_text = tool_result.get("message") or f"Tool execution successful: {tool_result.get('result', 'ACK')}"
                    else:
                        reply_text = f"Unable to comply. {tool_result.get('message', 'System error.')}"
                    
                    intent = f"tool_res:{tool}"
                else:
                    # Format report if it's a dict for text fallback
                    reply_text = report_builder.format_report_to_text(reply_raw)
                
                logger.info(f"[Dispatcher] Sending reply (intent={intent}): {reply_text[:100]}...")
                
                # Enqueue the response
                sq = send_queue.SendQueue.get_instance()
                session_key = f"qq:{event.group_id or event.user_id}"
                
                # Run async enqueue_send in thread
                enqueue_future = _executor.submit(
                    _run_async,
                    sq.enqueue_send(session_key, reply_text, {
                        "group_id": event.group_id,
                        "user_id": event.user_id,
                        "reply_to": event.message_id,
                        "image_b64": image_b64
                    })
                )
                enqueue_result = enqueue_future.result(timeout=5)
                logger.info(f"[Dispatcher] Enqueued: {enqueue_result}")
                
                # Add AI reply to history for context in next turn (only if not escalating, 
                # as escalation will send a better answer soon)
                if not result.get("needs_escalation"):
                    router.add_session_history(session_id, "assistant", reply_text, "Computer")
                
                # Check if escalation is needed - spawn background task for follow-up
                if result.get("needs_escalation"):
                    logger.info("[Dispatcher] Escalation needed, spawning background task...")
                    _executor.submit(
                        _handle_escalation,
                        result.get("original_query", event.text),
                        result.get("is_chinese", False),
                        event.group_id,
                        event.user_id,
                        session_key,
                        event.message_id,
                        result.get("escalated_model")
                    )
                
                return True

            else:
                logger.info(f"[Dispatcher] AI returned no reply: {result.get('reason', 'unknown')}")
        else:
            logger.info(f"[Dispatcher] Route is chat/low confidence, not responding.")
    except Exception as e:
        logger.error(f"[Dispatcher] Error processing message: {e}", exc_info=True)
    
    return False


def _handle_escalation(query: str, is_chinese: bool, group_id: str, user_id: str, session_key: str, original_message_id: str, requested_model: str | None):
    """
    Background handler for escalated queries - calls stronger model and sends follow-up message.
    """
    user_profile = permissions.get_user_profile(user_id)
    profile_str = permissions.format_profile_for_ai(user_profile)
    
    import time
    time.sleep(0.5)  # Small delay to ensure first message is sent first
    
    logger.info(f"[Dispatcher] Processing escalated query: {query[:50]}...")
    
    try:
        # Call the stronger model with context
        context = router.get_session_context(session_key.replace("qq:", "qq:")) # key is session_id
        escalation_result = _run_async(
            rp_engine_gemini.generate_escalated_reply(
                query, is_chinese, requested_model, context, 
                meta={"user_profile": profile_str}
            )
        )
        
        logger.info(f"[Dispatcher] Escalation result: {escalation_result}")
        
        if escalation_result and escalation_result.get("ok") and escalation_result.get("reply"):
            reply_raw = escalation_result["reply"]
            
            # Determine if we should render an image based on content type
            image_b64 = None
            if isinstance(reply_raw, dict) and "sections" in reply_raw:
                # Render image for structured escalation replies
                img_io = visual_core.render_report(reply_raw)
                image_b64 = base64.b64encode(img_io.getvalue()).decode("utf-8")
                reply_text = "Visual data report assembled."
            else:
                reply_text = report_builder.format_report_to_text(reply_raw)
                
            logger.info(f"[Dispatcher] Sending escalated reply: {reply_text[:100]}...")
            
            # Enqueue the follow-up response
            sq = send_queue.SendQueue.get_instance()
            enqueue_result = _run_async(
                sq.enqueue_send(session_key, reply_text, {
                    "group_id": group_id,
                    "user_id": user_id,
                    "is_escalated": True,
                    "reply_to": original_message_id,
                    "image_b64": image_b64
                })
            )
            logger.info(f"[Dispatcher] Escalated message enqueued: {enqueue_result}")
            
            # Record the final escalated answer in history
            router.add_session_history(session_key.replace("qq:", "qq:"), "assistant", reply_text, "Computer")
        else:
            logger.warning(f"[Dispatcher] Escalation returned no reply: {escalation_result}")
            
    except Exception as e:
        logger.error(f"[Dispatcher] Escalation failed: {e}", exc_info=True)

