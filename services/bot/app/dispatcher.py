import os
import logging
import base64
import asyncio
import threading
from typing import Optional
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
    """Run async coroutine, handling both sync and async contexts."""
    try:
        # Check if there's already a running loop
        loop = asyncio.get_running_loop()
        # We're in an async context, create a task instead
        import concurrent.futures
        future = concurrent.futures.Future()
        
        async def run_and_set():
            try:
                result = await coro
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
        
        # Schedule in the current loop via a new thread
        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        
        # Run in thread pool to avoid blocking
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_in_thread)
            return future.result(timeout=60)
            
    except RuntimeError:
        # No running loop, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# Global session mode tracking
SESSION_MODES = {}
# Global search results cache (for pagination)
SEARCH_RESULTS = {} # {session_id: {"items": [], "query": "", "page": 1}}

def _encode_image(image_path: str) -> Optional[str]:
    """Helper to read local image and encode to base64."""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.warning(f"[Dispatcher] Image encoding failed: {e}")
        return None

async def _execute_tool(tool: str, args: dict, event: InternalEvent, profile: dict, session_id: str, is_chinese: bool = False) -> dict:
    """Execute a tool dynamically based on name and args. Async version."""
    from . import tools
    result = None
    tool_name = tool # Capture original name for logic inference
    
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
        "abort_self_destruct": "authorize_cancel_self_destruct",
        "abort_destruct": "authorize_cancel_self_destruct",
        "cancel_destruct": "authorize_cancel_self_destruct",
        "stop_destruct": "authorize_cancel_self_destruct",
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
        "activate_diagnostic_mode": "enter_repair_mode",
        "enter_diagnostic_mode": "enter_repair_mode",
        "self_repair": "enter_repair_mode",
        "exit_repair": "exit_repair_mode",
        "end_repair": "exit_repair_mode",
        "exit_diagnostic": "exit_repair_mode",
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
        # 1.8 Protocol Aliases
        "lock_computer": "set_absolute_override",
        "unlock_computer": "set_absolute_override",
        "red_alert": "set_alert_status",
        "activate_red_alert": "set_alert_status",
        "yellow_alert": "set_alert_status",
        "activate_yellow_alert": "set_alert_status",
        "change_alert_status": "set_alert_status",
        "update_alert": "set_alert_status",
        "cancel_alert": "set_alert_status",
        "cancel_red_alert": "set_alert_status",
        "deactivate_alert": "set_alert_status",
        "stand_down": "set_alert_status",
        "raise_shields": "toggle_shields",
        "lower_shields": "toggle_shields",
        "shield_status": "get_shield_status",
        "weapon_lock": "weapon_lock_fire",
        "open_fire": "weapon_lock_fire",
        "locate_user": "locate_user",
        "replicate": "replicate",
        "report_replicator_status": "get_subsystem_status",
        "subsystem_status": "get_subsystem_status",
        "set_subsystem": "set_subsystem_state",
        "toggle_system": "set_subsystem_state",
        "system_offline": "set_subsystem_state",
        "system_online": "set_subsystem_state",
    }



    if tool in tool_aliases:
        original_tool = tool
        tool = tool_aliases[tool]
        logger.info(f"[Dispatcher] Aliased tool '{original_tool}' -> '{tool}'")
    
    # 1.8 Absolute Command Override (Z-flag) check
    from .permissions import is_command_override_active
    is_owner = (str(event.user_id) == "2819163610" or str(event.user_id) == "1993596624")
    
    if is_command_override_active() and not is_owner and tool != "set_absolute_override":
        logger.warning(f"[Dispatcher] Command REJECTED due to Absolute Override for user {event.user_id}")
        return {"ok": False, "message": "权限不足拒绝访问"}

    try:
        if tool == "status":
            result = tools.get_status()

        elif tool == "time":
            result = tools.get_time()
        elif tool == "calc":
            result = tools.calculator(args.get("expression"))
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
        elif tool == "search_memory":
            result = tools.search_memory(args.get("query"), session_id)
            
        elif tool == "query_knowledge_base" or tool == "search_memory_alpha":
            # Multi-result handling with Visual LCARS
            result = tools.query_knowledge_base(args.get("query"), session_id) if tool == "query_knowledge_base" else tools.search_memory_alpha(args.get("query"), session_id)
            
            if result.get("ok") and "items" in result:
                items = result["items"]
                # Store in cache for pagination
                SEARCH_RESULTS[session_id] = {
                    "items": items,
                    "query": args.get("query"),
                    "page": 1,
                    "total_pages": (len(items) + 3) // 4
                }
                
                # Render Page 1
                from .render_engine import get_renderer
                renderer = get_renderer()
                img_b64 = renderer.render_report(items[:4], page=1, total_pages=SEARCH_RESULTS[session_id]["total_pages"])
                event.meta["image_b64"] = img_b64
                logger.info(f"[Dispatcher] Visual report rendered for {tool}")
            
        elif tool == "set_reminder":
            result = tools.set_reminder(args.get("time"), args.get("content"), str(event.user_id))
            
        elif tool == "override_safety":
            result = tools.override_safety(
                str(event.user_id), 
                clearance=profile.get("clearance", 1),
                disable_safety=args.get("disable_safety", False)
            )
            
        # --- Self-Destruct 3-Step Flow ---
        elif tool in ["initialize_self_destruct", "activate_self_destruct"]:
            # Define callback for async notifications
            async def notify_callback(sid, message):
                sq = send_queue.SendQueue.get_instance()
                session_key = f"{event.platform}:{event.group_id or event.user_id}"
                await sq.enqueue_send(session_key, message, {
                    "group_id": event.group_id,
                    "user_id": event.user_id
                })
            
            if tool == "initialize_self_destruct":
                result = await tools.initialize_self_destruct(
                    args.get("duration", 300), 
                    args.get("silent", False), 
                    str(event.user_id), 
                    profile.get("clearance", 1), 
                    session_id,
                    notify_callback,
                    language="zh" if is_chinese else "en"
                )
            else: # activate_self_destruct
                result = await tools.activate_self_destruct(
                    str(event.user_id), 
                    profile.get("clearance", 1), 
                    session_id,
                    notify_callback
                )
            
        elif tool == "authorize_self_destruct":
            result = tools.authorize_self_destruct(
                str(event.user_id), 
                profile.get("clearance", 1), 
                session_id
            )
            
        # --- Cancel Flow ---
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
            if result.get("ok"):
                SESSION_MODES[session_id] = "diagnostic"
                logger.info(f"[Dispatcher] Session {session_id} entered persistent diagnostic mode")
            
        elif tool == "exit_repair_mode":
            result = tools.exit_repair_mode(session_id)
            if result.get("ok") or result.get("exit_repair_mode"):
                SESSION_MODES.pop(session_id, None)
                logger.info(f"[Dispatcher] Session {session_id} exited diagnostic mode")

            
        elif tool == "read_repair_module":
            result = tools.read_repair_module(
                args.get("module") or args.get("name", ""),
                profile.get("clearance", 1)
            )
            
        # --- 1.8 Protocol Hard-coded Tools ---
        elif tool == "set_absolute_override":
            # State is inferred from tool_name if not in args
            state = args.get("state") if "state" in args else ("lock" in tool_name or "激活" in tool_name)
            result = tools.set_absolute_override(state, str(event.user_id), profile.get("clearance", 1))
            
        elif tool == "set_alert_status":
            # Priority Level Inference using BEFORE-ALIAS name
            level = args.get("level") or args.get("new_alert_status")
            validate_current = None
            
            if not level:
                tool_lower = original_tool.lower()
                if any(k in tool_lower for k in ["cancel", "normal", "解除", "stand_down", "deactivate", "abort"]):
                    level = "NORMAL"
                    # Extract target for validation: What are they trying to cancel?
                    if "red" in tool_lower or "红色" in tool_lower:
                        validate_current = "RED"
                    elif "yellow" in tool_lower or "黄色" in tool_lower:
                        validate_current = "YELLOW"
                elif "red" in tool_lower or "红色" in tool_lower:
                    level = "RED"
                elif "yellow" in tool_lower or "黄色" in tool_lower:
                    level = "YELLOW"
                else:
                    level = "NORMAL"
                
            result = tools.set_alert_status(level.upper(), profile.get("clearance", 1), validate_current=validate_current)
            
            # Attach Image if returned and exists
            image_path = result.get("image_path")
            if image_path:
                image_b64 = _encode_image(image_path)
                if image_b64:
                    event.meta["image_b64"] = image_b64
                    logger.info(f"[Dispatcher] Attached image from {image_path} to event meta.")
            
        elif tool == "toggle_shields":
            active = args.get("active") if "active" in args else ("raise" in tool_name or "升起" in tool_name)
            result = tools.toggle_shields(active, profile.get("clearance", 1))
            
        elif tool == "next_page" or tool == "prev_page":
            session_data = SEARCH_RESULTS.get(session_id)
            if not session_data:
                result = {"ok": False, "message": "无法完成：当前未开启查询进程，请先通过‘查询数据库’开启搜索。"}
            else:
                items = session_data["items"]
                current_page = session_data["page"]
                total_pages = session_data["total_pages"]
                
                new_page = current_page + 1 if tool == "next_page" else current_page - 1
                if 1 <= new_page <= total_pages:
                    SEARCH_RESULTS[session_id]["page"] = new_page
                    start_idx = (new_page - 1) * 4
                    end_idx = start_idx + 4
                    
                    from .render_engine import get_renderer
                    renderer = get_renderer()
                    img_b64 = renderer.render_report(items[start_idx:end_idx], page=new_page, total_pages=total_pages)
                    event.meta["image_b64"] = img_b64
                    result = {"ok": True, "message": f"正在调取第 {new_page} 页，共 {total_pages} 页。"}
                else:
                    result = {"ok": False, "message": f"无法完成：已到达{'末尾' if tool == 'next_page' else '首页'}。"}

        elif tool == "show_details":
            target_id = args.get("id", "").upper()
            session_data = SEARCH_RESULTS.get(session_id)
            if not session_data or not target_id:
                result = {"ok": False, "message": "无法完成：请指定有效的检索编号（例如：1A）。"}
            else:
                target_item = next((i for i in session_data["items"] if i["id"] == target_id), None)
                if target_item:
                    # If it's a detail request, we can send the full text or high-res image
                    msg = f"--- 详细记录检索: {target_id} ---\n\n{target_item.get('content', '该条目无详细文本说明。')}"
                    result = {"ok": True, "message": msg}
                    # If there's an image, attach it
                    if target_item.get("image_b64"):
                        event.meta["image_b64"] = target_item["image_b64"]
                else:
                    result = {"ok": False, "message": f"无法完成：未能在当前结果集中找到编号为 {target_id} 的条目。"}
            from .ship_systems import get_ship_systems
            result = {"ok": True, "message": get_ship_systems().get_shield_status()}
            
        elif tool == "replicate":
            result = tools.replicate(
                args.get("item_name") or args.get("item", "Tea, Earl Grey, Hot"),
                str(event.user_id),
                profile.get("rank", "Ensign"),
                profile.get("clearance", 1)
            )
            
        elif tool == "locate_user":
            result = await tools.locate_user(args.get("target_mention"), profile.get("clearance", 1))
            
        elif tool == "weapon_lock_fire":
            # Simulate 1.8 weapon check
            from .ship_systems import get_ship_systems
            ss = get_ship_systems()
            if not ss.is_subsystem_online("weapons"):
                result = {"ok": False, "message": "无法完成，武器系统下线。"}
            else:
                is_fire = any(k in tool_name.lower() for k in ["fire", "开火", "射击"])
                msg = "确认，正在开火。" if is_fire else "目标已锁定。"
                result = {"ok": True, "message": msg}
            
        elif tool == "get_subsystem_status":
            name = args.get("name") or args.get("subsystem")
            if not name and "replicator" in tool_name:
                name = "replicator"
            result = tools.get_subsystem_status(name or "unknown")
            
        elif tool == "set_subsystem_state":
            result = tools.set_subsystem_state(
                args.get("name") or args.get("subsystem") or ("replicator" if "replicator" in tool_name else ""),
                args.get("state") or ("ONLINE" if "online" in tool_name else "OFFLINE"),
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
            # Direct call to RepairAgent natural language interface
            from .repair_agent import get_repair_agent
            agent = get_repair_agent()
            result = await agent.answer_code_question(
                session_id, 
                str(event.user_id), 
                args.get("question", ""), 
                profile.get("clearance", 1),
                language="zh" if is_chinese else "en"
            )

            
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

async def _execute_ai_logic(event: InternalEvent, user_profile: dict, session_id: str, force_tool: str = None, force_args: dict = None):
    """
    Helper to execute AI generation and processing logic.
    Supports forcing a specific tool for diagnostic mode.
    """
    profile_str = permissions.format_profile_for_ai(user_profile)
    
    if force_tool:
        # Synthetic result for forced tool execution
        result = {
            "ok": True,
            "intent": "tool_call",
            "tool": force_tool,
            "args": force_args or {},
            "is_chinese": True, # Assume Chinese for diagnostic mode
            "original_query": event.text,
            "needs_escalation": False
        }
    else:
        # Normal AI generation in thread pool (generate_computer_reply is sync)
        future = _executor.submit(
            rp_engine_gemini.generate_computer_reply,
            event.text, 
            router.get_session_context(session_id),
            {
                "user_profile": profile_str
            }
        )
        result = future.result(timeout=15)
    
    logger.info(f"[Dispatcher] AI result: {result}")
    
    # Check if we have a valid result (tool_call has empty reply, which is ok)
    if result and result.get("ok") and (result.get("reply") or result.get("intent") == "tool_call"):
        reply_raw = result.get("reply", "")
        intent = result.get("intent")
        
        image_b64 = event.meta.get("image_b64")
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
            # Await the tool execution (it might be async)
            tool_result = await _execute_tool(tool, args, event, user_profile, session_id, is_chinese=is_chinese)
            
            if tool_result.get("ok"):
                # Intercept for Polymath Synthesis (KB/Memory Alpha)
                if tool in ["query_knowledge_base", "search_memory_alpha"]:
                    logger.info(f"[Dispatcher] Synthesizing raw data for {tool}...")
                    raw_data = tool_result.get("message", "")
                    
                    # Run synthesis in thread pool
                    future = _executor.submit(
                        rp_engine_gemini.synthesize_search_result,
                        result.get("original_query", ""),
                        raw_data,
                        is_chinese
                    )
                    reply_text = future.result(timeout=20)
                else:
                    reply_text = tool_result.get("message") or tool_result.get("reply") or f"Tool execution successful: {tool_result.get('result', 'ACK')}"
                
                # Check for image content from tool (e.g. Personnel File)
                if "image_io" in tool_result:
                    img_io = tool_result["image_io"]
                    image_b64 = base64.b64encode(img_io.getvalue()).decode("utf-8")
                
                # FINAL SYNC: Pick up any image_b64 set in event.meta during tool execution 
                # (e.g. by set_alert_status or search rendering)
                if event.meta.get("image_b64"):
                    image_b64 = event.meta.get("image_b64")
            else:
                reply_text = f"Unable to comply. {tool_result.get('message', 'System error.')}"
            
            intent = f"tool_res:{tool}"
        else:
            # Format report if it's a dict for text fallback
            reply_text = report_builder.format_report_to_text(reply_raw)
        
        logger.info(f"[Dispatcher] Sending reply (intent={intent}): {reply_text[:100]}...")
        
        # SUPPRESSION: If we have an image_b64 and it's a tool result (like a report), 
        # minimize the text part to avoid duplication with the visual content.
        if image_b64 and intent.startswith("tool_res:"):
            # If it's a search result, the user already sees the data on the screen
            reply_text = "Accessing Federation Database... Data report displayed below."
        sq = send_queue.SendQueue.get_instance()
        session_key = f"qq:{event.group_id or event.user_id}"
        
        await sq.enqueue_send(session_key, reply_text, {
            "group_id": event.group_id,
            "user_id": event.user_id,
            "reply_to": event.message_id,
            "image_b64": image_b64
        })
        
        # Add AI reply to history for context in next turn
        if not result.get("needs_escalation"):
            router.add_session_history(session_id, "assistant", reply_text, "Computer")
        
        # Check if escalation is needed
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
        return False


async def handle_event(event: InternalEvent):
    """
    Main entry point for processing incoming events.
    """
    logger.info(f"[Dispatcher] Processing event: {event.event_type} from {event.user_id}")
    
    # Session ID logic (Group ID takes precedence)
    session_id = event.group_id if event.group_id else f"p_{event.user_id}"
    
    # Check whitelist
    if not is_group_enabled(event.group_id or session_id if "group" in session_id else None):
        logger.info(f"[Dispatcher] Group {event.group_id} not in whitelist. Dropping event.")
        return False
        
    try:
        # Skip empty messages
        if not event.text or not event.text.strip():
            logger.info("[Dispatcher] Empty message, skipping.")
            return False

        # --- DIAGNOSTIC MODE INTERCEPT ---
        if SESSION_MODES.get(session_id) == "diagnostic":
            logger.info(f"[Dispatcher] Session {session_id} is in diagnostic mode. Intercepting.")
            
            # Check for exit command
            sender = event.raw.get("sender", {})
            nickname = sender.get("card") or sender.get("nickname")
            title = sender.get("title") # QQ Group Title

            if event.text.strip() in ["退出", "exit", "quit", "关闭诊断模式", "退出诊断模式"]:
                # Route to exit_repair_mode
                from . import permissions
                user_profile = permissions.get_user_profile(str(event.user_id), nickname, title)
                # Create synthetic result for execution
                await _execute_ai_logic(event, user_profile, session_id, force_tool="exit_repair_mode")
                return True
            else:
                # Force route to ask_about_code
                from . import permissions
                user_profile = permissions.get_user_profile(str(event.user_id), nickname, title)
                await _execute_ai_logic(event, user_profile, session_id, force_tool="ask_about_code", force_args={"question": event.text})
                return True
        
        # --- ACCESS CONTROL GATING (Legacy & Security) ---
        from .permissions import is_user_restricted, is_command_locked, get_user_profile
        
        # 1. Individual Restriction
        if is_user_restricted(event.user_id):
            logger.warning(f"[Dispatcher] User {event.user_id} is restricted. Dropping.")
            return False
            
        # Command Lockout Check
        if is_command_locked():
            # Only allow Level 8+ during lockout

            profile = get_user_profile(str(event.user_id), event.nickname, event.title)
            if profile.get("clearance", 1) < 8:
                logger.warning(f"[Dispatcher] Command Lockout active. User {event.user_id} (Clearance {profile.get('clearance')}) refused.")
                sq = send_queue.SendQueue.get_instance()
                session_key = f"{event.platform}:{event.group_id or event.user_id}"
                await sq.enqueue_send(session_key, "ACCESS DENIED: Shipboard command authority is currently locked to Senior Officers.", {"from_computer": True})
                return False
        
        # Route the message with full event meta for attribution
        route_result = router.route_event(session_id, event.text, {
            "event": event.model_dump(),
            "event_raw": event.raw
        })
        logger.info(f"[Dispatcher] Route result: {route_result}")
        
        # Check if we should respond (computer mode or high confidence)
        confidence = route_result.get("confidence", 0)
        route = route_result.get("route", "chat")
        
        should_respond = False
        # Dual-Stage Triage
        # Stage 1: Fast Rule High-Confidence (e.g. Wake Word / Manual Enter)
        if route == "computer" and confidence >= 0.8:
            should_respond = True
        # Stage 2: Ambiguous Latch/Follow-up (0.5 < conf < 0.8) -> LLM Judge
        elif 0.5 < confidence < 0.8:
            logger.info(f"[Dispatcher] Borderline confidence ({confidence}), calling secondary judge...")
            try:
                from . import judge_gemini
                judge_result = await judge_gemini.judge_intent(
                    trigger={"text": event.text, "user_id": event.user_id},
                    context=router.get_session_context(session_id)
                )

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
                
                await sq.enqueue_send(session_key, bleep_text, {
                    "group_id": event.group_id,
                    "user_id": event.user_id,
                    "reply_to": event.message_id
                })
                return True

            # Fetch full ALAS User Profile
            sender = event.raw.get("sender", {})
            nickname = sender.get("card") or sender.get("nickname")
            title = sender.get("title") # QQ Group Title
            from . import permissions
            user_profile = permissions.get_user_profile(event.user_id, nickname, title)
            
            # Generate AI reply using helper (async await)
            await _execute_ai_logic(event, user_profile, session_id)
            return True
            
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

