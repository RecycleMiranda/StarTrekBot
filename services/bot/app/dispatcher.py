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
from .protocol_manager import get_protocol_manager

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

def _execute_tool(tool: str, args: dict, event: InternalEvent, profile: dict, session_id: str, is_chinese: bool = False) -> dict:
    """Executes a ship tool with user context."""
    from . import tools
    result = None
    
    # Tool name aliasing - map AI shortcuts to actual function names
    tool_aliases = {
        # Self-destruct aliases
        "self_destruct": "initialize_self_destruct",
        "destruct": "initialize_self_destruct",
        "init_destruct": "initialize_self_destruct",
        "initiate_self_destruct": "initialize_self_destruct",
        # Auth aliases
        "auth_destruct": "authorize_self_destruct",
        "vouch_destruct": "authorize_self_destruct",
        "authorize_sequence": "authorize_self_destruct",
        # Activate aliases
        "start_destruct": "activate_self_destruct",
        "engage_destruct": "activate_self_destruct",
        "begin_destruct": "activate_self_destruct",
        "start_countdown": "activate_self_destruct",
        # Status aliases
        "destruct_status": "get_destruct_status",
        "check_destruct": "get_destruct_status",
        "destruct_info": "get_destruct_status",
        # Cancel aliases
        "abort_self_destruct": "request_cancel_self_destruct",
        "abort_destruct": "request_cancel_self_destruct",
        "cancel_destruct": "request_cancel_self_destruct",
        "stop_destruct": "request_cancel_self_destruct",
        # Cancel auth aliases
        "auth_cancel_destruct": "authorize_cancel_self_destruct",
        "vouch_cancel": "authorize_cancel_self_destruct",
        # Confirm cancel aliases
        "confirm_cancel_destruct": "confirm_cancel_self_destruct",
        "finalize_cancel": "confirm_cancel_self_destruct",
        # Repair mode aliases
        "repair_mode": "enter_repair_mode",
        "diagnose": "enter_repair_mode",
        "diagnostic": "enter_repair_mode",
        "self_repair": "enter_repair_mode",
        "exit_repair": "exit_repair_mode",
        "end_repair": "exit_repair_mode",
        "read_module": "read_repair_module",
        "view_code": "read_repair_module",
        "module_outline": "get_repair_module_outline",
        "code_outline": "get_repair_module_outline",
        "rollback": "rollback_repair_module",
        "undo_repair": "rollback_repair_module",
        "list_backups": "list_repair_backups",
        "show_backups": "list_repair_backups",
        # Code Q&A aliases
        "code_question": "ask_about_code",
        "analyze_code": "ask_about_code",
        "explain_code": "ask_about_code",
        "check_code": "ask_about_code",
    }



    if tool in tool_aliases:
        original_tool = tool
        tool = tool_aliases[tool]
        logger.info(f"[Dispatcher] Aliased tool '{original_tool}' -> '{tool}'")
    
    try:
        if tool == "status":
            result = tools.get_status()

        elif tool == "time":
            result = tools.get_time()
        elif tool == "calc":
            result = tools.calc(args.get("expr", ""))
        elif tool == "replicate":
            result = tools.replicate(args.get("item_name", ""), str(event.user_id), profile.get("rank", "Ensign"), clearance=profile.get("clearance", 1))
        elif tool == "holodeck":
            result = tools.reserve_holodeck(
                args.get("program", "Standard Grid"), 
                args.get("hours", 1.0), 
                str(event.user_id), 
                profile.get("rank", "Ensign"),
                clearance=profile.get("clearance", 1),
                disable_safety=args.get("disable_safety", False)
            )
        elif tool == "get_ship_schematic":
            result = tools.get_ship_schematic(args.get("ship_name", "Galaxy"), clearance=profile.get("clearance", 1))
        elif tool == "get_historical_archive":
            result = tools.get_historical_archive(args.get("topic", "Federation"))
        elif tool == "personal_log":
            result = tools.personal_log(args.get("content", ""), str(event.user_id))
            
        # --- Self-Destruct 3-Step Flow ---
        elif tool == "initialize_self_destruct":
            result = tools.initialize_self_destruct(
                args.get("seconds", 60), 
                args.get("silent", False), 
                str(event.user_id), 
                profile.get("clearance", 1), 
                session_id
            )
            
        elif tool == "authorize_self_destruct":
            result = tools.authorize_self_destruct(
                str(event.user_id), 
                profile.get("clearance", 1), 
                session_id
            )
            
        elif tool == "activate_self_destruct":
            result = _run_async(tools.activate_self_destruct(
                str(event.user_id), 
                profile.get("clearance", 1), 
                session_id,
                _destruct_notify
            ))
            
        # --- Cancel Flow ---
        elif tool == "request_cancel_self_destruct":
            result = tools.request_cancel_self_destruct(
                str(event.user_id), 
                profile.get("clearance", 1), 
                session_id
            )
            
        elif tool == "authorize_cancel_self_destruct":
            result = tools.authorize_cancel_self_destruct(
                str(event.user_id), 
                profile.get("clearance", 1), 
                session_id
            )
            
        elif tool == "confirm_cancel_self_destruct":
            result = tools.confirm_cancel_self_destruct(
                str(event.user_id), 
                profile.get("clearance", 1), 
                session_id
            )
            
        elif tool == "get_destruct_status":
            result = tools.get_destruct_status(session_id)
            
        # --- Repair Mode Tools ---
        elif tool == "enter_repair_mode":
            result = tools.enter_repair_mode(
                str(event.user_id),
                profile.get("clearance", 1),
                session_id,
                args.get("module") or args.get("target_module")
            )
            
        elif tool == "exit_repair_mode":
            result = tools.exit_repair_mode(session_id)
            
        elif tool == "read_repair_module":
            result = tools.read_repair_module(
                args.get("module") or args.get("name", ""),
                profile.get("clearance", 1)
            )
            
        elif tool == "get_repair_module_outline":
            result = tools.get_repair_module_outline(
                args.get("module") or args.get("name", ""),
                profile.get("clearance", 1)
            )
            
        elif tool == "rollback_repair_module":
            result = tools.rollback_repair_module(
                args.get("module") or args.get("name", ""),
                profile.get("clearance", 1),
                args.get("backup_index", 0)
            )
            
        elif tool == "list_repair_backups":
            result = tools.list_repair_backups(
                args.get("module") or args.get("name", ""),
                profile.get("clearance", 1)
            )
            
        elif tool == "ask_about_code":
            result = _run_async(tools.ask_about_code(
                args.get("question") or args.get("query", ""),
                str(event.user_id),
                profile.get("clearance", 1),
                session_id
            ))

            
        elif tool == "get_personnel_file":



            result = tools.get_personnel_file(args.get("target_mention", ""), str(event.user_id), is_chinese=is_chinese)
            
        elif tool == "update_biography":
            result = tools.update_biography(args.get("content", ""), str(event.user_id))
            
        elif tool == "update_protocol":
            category = args.get("category", "rp_engine")
            key = args.get("key")
            value = args.get("value")
            action = args.get("action", "set")  # Default to 'set' for backwards compat
            
            # Step 0: Handle nested dict structures from AI
            # AI sometimes sends: {chinese_style: {action: 'remove', suffix: '123'}}
            for potential_key in ["chinese_style", "persona", "wake_response", "decision_logic", "security_protocols"]:
                if potential_key in args and isinstance(args[potential_key], dict):
                    nested = args[potential_key]
                    key = potential_key
                    action = nested.get("action", action)
                    # Extract value from nested dict - check common value keys
                    value = nested.get("value") or nested.get("suffix") or nested.get("content") or nested.get("text") or ""
                    logger.info(f"[Dispatcher] Extracted from nested dict: key={key}, action={action}, value={value}")
                    break
            
            # Step 1: Normalize the key - translate prompt labels to actual JSON keys
            key_translation = {
                "STYLE/LANGUAGE RULES": "chinese_style",
                "REPLY STYLE/SUFFIX": "chinese_style",
                "style": "chinese_style",
                "reply_style": "chinese_style",
                "reply_suffix": "chinese_style",
                "suffix": "chinese_style",
                "IDENTITY": "persona",
                "identity": "persona",
                "role": "persona",
                "SECURITY": "security_protocols",
                "security": "security_protocols",
                "DECISION LOGIC": "decision_logic",
                "logic": "decision_logic",
                "strategy": "decision_logic",
                "wake_sound": "wake_response",
                "wake_word": "wake_response",
            }
            if key and key in key_translation:
                original_key = key
                key = key_translation[key]
                logger.info(f"[Dispatcher] Translated key '{original_key}' -> '{key}'")
            
            # Step 2: Expanded Smart Mapping for shorthand args (non-dict values only)
            if not key or value is None:
                mappers = {
                    "chinese_style": ["chinese_style", "style", "reply_style", "reply_suffix", "suffix"],
                    "persona": ["persona", "identity", "role"],
                    "wake_response": ["wake_response", "wake_sound", "wake_word"],
                    "decision_logic": ["decision_logic", "logic", "strategy"]
                }
                
                found = False
                for target_key, synonyms in mappers.items():
                    for syn in synonyms:
                        if syn in args and not isinstance(args[syn], dict):
                            key = target_key
                            value = args[syn]
                            logger.info(f"[Dispatcher] Smart-mapped protocol update: {key}={value} (from {syn})")
                            found = True
                            break
                    if found: break
            
            # Action Detection: Infer intent from the value string if action wasn't explicit
            if action == "set" and value and isinstance(value, str):
                value_lower = value.lower()
                # Check for "add" or "append" signals
                if any(sig in value_lower for sig in ["add ", "append ", "include ", "also ", "在末尾加", "添加"]):
                    action = "append"
                    # Strip the action word from the value
                    for sig in ["add ", "append ", "include ", "also ", "在末尾加", "添加"]:
                        value = value.replace(sig, "").strip()
                    logger.info(f"[Dispatcher] Detected APPEND intent: {value}")
                # Check for "remove" or "cancel" signals
                elif any(sig in value_lower for sig in ["remove ", "cancel ", "delete ", "stop ", "取消", "删除", "不要"]):
                    action = "remove"
                    for sig in ["remove ", "cancel ", "delete ", "stop ", "取消", "删除", "不要"]:
                        value = value.replace(sig, "").strip()
                    logger.info(f"[Dispatcher] Detected REMOVE intent: {value}")

            
            # Final Safeguard: If we still don't have a key, reject.
            if not key:
                return {"ok": False, "message": "Unable to determine which protocol key to update. Please specify 'key' and 'value'."}

            result = tools.update_protocol(
                category,
                key,
                value or "",
                str(event.user_id),
                profile.get("clearance", 1),
                action=action
            )
        else:
            return {"ok": False, "message": f"Unknown tool: {tool}", "error": "unknown_tool"}
            
        if result and "ok" not in result:
            result["ok"] = True
        return result
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {"ok": False, "message": f"Execution error: {str(e)}", "error": str(e)}

async def _destruct_notify(session_id: str, message: str):
    """Sends background countdown messages to the chat platform."""
    from .send_queue import SendQueue
    sq = SendQueue.get_instance()
    # Mock meta for background send
    meta = {"from_computer": True, "priority": "high"}
    await sq.enqueue_send(session_id, message, meta)

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
    
    # --- ACCESS CONTROL GATING (Legacy & Security) ---
    from .permissions import is_user_restricted, is_command_locked, get_user_profile
    
    # 1. Individual Restriction
    if is_user_restricted(event.user_id):
        logger.warning(f"[Dispatcher] User {event.user_id} is restricted. Dropping.")
        return False
        
    # 2. Global Command Lockout
    if is_command_locked():
        # Only allow Level 8+ during lockout
        profile = get_user_profile(str(event.user_id), event.nickname, event.title)
        if profile.get("clearance", 1) < 8:
            logger.warning(f"[Dispatcher] Command Lockout active. User {event.user_id} (Clearance {profile.get('clearance')}) refused.")
            sq = send_queue.SendQueue.get_instance()
            session_key = f"{event.platform}:{event.group_id or event.user_id}"
            _executor.submit(_run_async, sq.enqueue_send(session_key, "ACCESS DENIED: Shipboard command authority is currently locked to Senior Officers.", {"from_computer": True}))
            return False
    
    # Route the message with full event meta for attribution
    try:
        route_result = router.route_event(session_id, event.text, {
            "event": event.model_dump(),
            "event_raw": event.raw
        })
        logger.info(f"[Dispatcher] Route result: {route_result}")
        
        # Check if we should respond (computer mode or high confidence)
        confidence = route_result.get("confidence", 0)
        route = route_result.get("route", "chat")
        
        # Dual-Stage Triage
        # Stage 1: Fast Rule High-Confidence (e.g. Wake Word / Manual Enter)
        if route == "computer" and confidence >= 0.8:
            should_respond = True
        # Stage 2: Ambiguous Latch/Follow-up (0.5 < conf < 0.8) -> LLM Judge
        elif 0.5 < confidence < 0.8:
            logger.info(f"[Dispatcher] Borderline confidence ({confidence}), calling secondary judge...")
            try:
                from . import judge_gemini
                judge_result = _executor.submit(
                    _run_async, 
                    judge_gemini.judge_intent(
                        trigger={"text": event.text, "user_id": event.user_id},
                        context=router.get_session_context(session_id)
                    )
                ).result(timeout=5)
                
                if judge_result.get("route") == "computer" and judge_result.get("confidence", 0) >= 0.7:
                    logger.info(f"[Dispatcher] Judge confirmed intent: {judge_result.get('reason')} (Conf: {judge_result.get('confidence')})")
                    should_respond = True
                else:
                    logger.info(f"[Dispatcher] Judge rejected intent: {judge_result.get('reason')} (Conf: {judge_result.get('confidence')})")
                    should_respond = False
            except Exception as e:
                logger.warning(f"[Dispatcher] Judge failed: {e}. Falling back to chat.")
                should_respond = False
        else:
            should_respond = False

        if should_respond:
            # Handle "Wake-only" bleep
            if route_result.get("is_wake_only"):
                logger.info("[Dispatcher] Wake-only detected, sending bleep.")
                sq = send_queue.SendQueue.get_instance()
                session_key = f"qq:{event.group_id or event.user_id}"
                
                # Fetch dynamic wake response from protocols
                pm = get_protocol_manager()
                bleep_text = pm.get_prompt("rp_engine", "wake_response", "*Computer Acknowledgment Chirp*")
                
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

            # Generate AI reply in a separate thread (it's now a sync call inside)
            future = _executor.submit(
                rp_engine_gemini.generate_computer_reply,
                trigger_text=event.text,
                context=router.get_session_context(session_id),
                meta={
                    "session_id": session_id, 
                    "user_id": event.user_id,
                    "user_profile": profile_str
                }
            )
            result = future.result(timeout=15)  # 15 second timeout
            
            logger.info(f"[Dispatcher] AI result: {result}")
            
            # Check if we have a valid result (tool_call has empty reply, which is ok)
            if result and result.get("ok") and (result.get("reply") or result.get("intent") == "tool_call"):
                reply_raw = result.get("reply", "")
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
                    is_chinese = result.get("is_chinese", False)
                    logger.info(f"[Dispatcher] Executing tool: {tool}({args}) [Lang: {'ZH' if is_chinese else 'EN'}]")
                    tool_result = _execute_tool(tool, args, event, user_profile, session_id, is_chinese=is_chinese)
                    
                    if tool_result.get("ok"):
                        reply_text = tool_result.get("message") or f"Tool execution successful: {tool_result.get('result', 'ACK')}"
                        # Check for image content from tool (e.g. Personnel File)
                        if "image_io" in tool_result:
                            img_io = tool_result["image_io"]
                            image_b64 = base64.b64encode(img_io.getvalue()).decode("utf-8")
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
        context = router.get_session_context(session_key.replace("qq:", "qq:"))
        escalation_result = rp_engine_gemini.generate_escalated_reply(
            query, is_chinese, requested_model, context, 
            meta={"user_profile": profile_str}
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

