import os
import time
import logging
import re
import base64
import inspect
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
from . import render_engine
from . import context_bus
from . import agents
from . import shadow_audit
from . import watchdog
from . import emergency_kernel
from .protocol_manager import get_protocol_manager
from .ops_registry import OpsRegistry, TaskPriority, TaskState
from .evolution_agent import get_evolution_agent
from . import tools 

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
# NEURAL LOCKS: Prevents concurrent agentic loops in the same session
NEURAL_LOCKS = {} # {session_id: asyncio.Lock}
# PROCESSED_MESSAGES: Deduplication cache {message_id: timestamp}
PROCESSED_MESSAGES = {} 

def _prefetch_next_pages(session_id: str, is_chinese: bool):
    """
    Background worker to pre-render the next 1-2 pages of an article or search result.
    Optimizes for sequential 'next_page' requests.
    """
    session_data = SEARCH_RESULTS.get(session_id)
    if not session_data or not session_data.get("items"): return
    
    # Initialize pre_render_cache if not present
    if "pre_render_cache" not in session_data:
        session_data["pre_render_cache"] = {} # {page_num: image_b64}
        
    current_page = session_data.get("page", 1)
    items = session_data.get("items", [])
    total_pages = session_data.get("total_pages", 0)
    mode = session_data.get("mode", "search")
    
    # Only pre-warm the next 2 pages to save resources
    for next_p in [current_page + 1, current_page + 2]:
        if 1 <= next_p <= total_pages and next_p not in session_data["pre_render_cache"]:
            try:
                from .render_engine import get_renderer
                renderer = get_renderer()
                
                if mode == "article":
                    # For articles, each 'item' in session_data["items"] is a pre-split sub-page
                    page_items = [items[next_p - 1]]
                else:
                    # For standard search results, use ipp logic
                    ipp = session_data.get("items_per_page", 4)
                    start_idx = (next_p - 1) * ipp
                    page_items = items[start_idx : start_idx + ipp]
                
                if page_items:
                    img_b64 = renderer.render_report(page_items, page=next_p, total_pages=total_pages)
                    session_data["pre_render_cache"][next_p] = img_b64
                    logger.debug(f"[Dispatcher] Prefetched {mode} page {next_p} for session {session_id}")
            except Exception as e:
                logger.warning(f"[Dispatcher] Pre-render failed for page {next_p}: {e}")

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
        "system_status": "get_status",
        "status": "get_status",
        "ship_status": "get_status",
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
        "phaser_fire": "weapon_lock_fire",
        "fire_phasers": "weapon_lock_fire",
        "locate_user": "locate_user",
        "replicate": "replicate",
        "report_replicator_status": "get_subsystem_status",
        "subsystem_status": "get_subsystem_status",
        "set_subsystem": "set_subsystem_state",
        "toggle_system": "set_subsystem_state",
        "system_offline": "set_subsystem_state",
        "system_online": "set_subsystem_state",
        # 2.0 ADS & Audit Aliases
        "ads_test": "trigger_ads_test",
        "diagnose_system": "trigger_ads_test",
        "fault_audit": "audit_clear_fault",
        "clear_fault": "audit_clear_fault",
        "archive_fault": "audit_clear_fault",
        "start_ads_diagnostic": "trigger_ads_test",
        # 4.0 Protocol Aliases
        "request_authorization": "execute_general_order",
        "authorize": "execute_general_order",
        "command_auth": "execute_general_order",
        "execute_procedure": "execute_procedure",
        "start_procedure": "execute_procedure",
        "run_sequence": "execute_procedure",
    }



    original_tool = tool # Default to current tool name
    
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
        if tool == "get_status":
            result = tools.get_status(**args)

        elif tool == "set_course":
            result = tools.set_course(
                args.get("destination", "Unknown Sector"),
                float(args.get("warp_factor", 5.0)),
                profile.get("clearance", 1)
            )

        elif tool == "time":
            result = tools.get_time()
        elif tool == "calc":
            result = tools.calculator(args.get("expression"))
        elif tool == "replicate":
            result = tools.replicate(args.get("item_name", ""), str(event.user_id), profile.get("rank", "Ensign"), clearance=profile.get("clearance", 1))
        elif tool == "launch_probe":
            result = tools.launch_probe(
                args.get("probe_type", "Class I"),
                args.get("target", "Unknown"),
                profile.get("clearance", 1)
            )
        elif tool == "execute_general_order":
            result = tools.execute_general_order(
                args.get("order_code", "GO-24"),
                args.get("target", "Unknown"),
                profile.get("clearance", 1)
            )
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
            
        elif tool in ["query_knowledge_base", "search_memory_alpha", "access_memory_alpha_direct"]:
            # Multi-result handling with Visual LCARS (RENDER MOVED TO SYNTHESIS STAGE)
            if tool == "query_knowledge_base":
                raw_query = args.get("query", "")
                if isinstance(raw_query, list):
                    query_text = " ".join(str(q) for q in raw_query).lower()
                else:
                    query_text = str(raw_query).lower()

                # ENHANCED: Boundary-aware matching for listing keywords
                list_keywords = ["list", "all", "级别", "列表", "名录", "种类", "classes", "types", "vessels", "ships", "fleet"]
                pattern = r'\b(' + '|'.join(list_keywords) + r')\b'
                is_listing = bool(re.search(pattern, query_text)) or any(kw in query_text for kw in ["级别", "列表", "名录", "种类"]) or isinstance(raw_query, list)
                
                # Cap max_w to a safe threshold (3000 words vs 8000)
                max_w = args.get("max_words", 3000 if is_listing else 500)
                if is_listing: logger.info(f"[Dispatcher] Giga-Scan Protocol forced for KB: {max_w} words")
                result = tools.query_knowledge_base(args.get("query"), session_id, is_chinese=is_chinese, max_words=max_w)
            elif tool == "search_memory_alpha":
                raw_query = args.get("query", "")
                if isinstance(raw_query, list):
                    query_text = " ".join(str(q) for q in raw_query).lower()
                else:
                    query_text = str(raw_query).lower()

                list_keywords = ["list", "all", "级别", "列表", "名录", "种类", "classes", "types", "vessels", "ships", "fleet"]
                pattern = r'\b(' + '|'.join(list_keywords) + r')\b'
                is_listing = bool(re.search(pattern, query_text)) or any(kw in query_text for kw in ["级别", "列表", "名录", "种类"]) or isinstance(raw_query, list)
                
                max_w = args.get("max_words", 1500 if is_listing else 500) # MA is more expensive, cap lower
                if is_listing: logger.info(f"[Dispatcher] Giga-Scan Protocol forced for MA: {max_w} words")
                result = tools.search_memory_alpha(args.get("query"), session_id, is_chinese=is_chinese, max_words=max_w)
            else:
                chunk_index = args.get("chunk_index", 0)
                result = tools.access_memory_alpha_direct(args.get("query"), session_id, is_chinese=is_chinese, chunk_index=chunk_index)
            
            # Universal Pre-rendering/Pagination state setup
            is_handled = False
            if result.get("ok") and tool != "access_memory_alpha_direct":
                is_handled = True
                if "items" in result:
                    items = result["items"]
                    

                    # ENHANCED: Only trigger LCARS if content is significant or multiple items exist
                    content_len = len(items[0].get("content", "")) if items and len(items) == 1 else 999
                    if not items:
                        is_handled = False
                        logger.warning("[Dispatcher] KB/MA returned empty items list.")
                    elif content_len < 180:
                        is_handled = False # Fall back to standard AI synthesis
                        logger.info(f"[Dispatcher] Short content detected ({content_len} chars). Skipping LCARS.")
                        event.meta.pop("image_b64", None) # Clear previous artifacts
                    elif len(items) == 1 and content_len > 600:
                        from .render_engine import get_renderer
                        renderer = get_renderer()
                        sub_pages = renderer.split_content_to_pages(items[0])
                        SEARCH_RESULTS[session_id] = {
                            "mode": "search",
                            "query": args.get("query"),
                            "items": sub_pages,
                            "page": 1,
                            "total_pages": len(sub_pages),
                            "items_per_page": 1, # Direct mapping to items
                            "pre_render_cache": {}
                        }
                        # result["items"] is PRESERVED for AI loop. sub_pages are only for SEARCH_RESULTS.
                        # RENDER INITIAL PAGE FOR USER
                        img_b64 = renderer.render_report([sub_pages[0]], page=1, total_pages=len(sub_pages))
                        event.meta["image_b64"] = img_b64
                        logger.info(f"[Dispatcher] Long result decoupled: AI sees raw, UI gets Image Page 1/{len(sub_pages)}.")
                    else:
                        ipp = 4
                        total_p = (len(items) + ipp - 1) // ipp
                        SEARCH_RESULTS[session_id] = {
                            "mode": "search",
                            "query": args.get("query"),
                            "items": items,
                            "page": 1,
                            "total_pages": total_p,
                            "items_per_page": ipp,
                            "pre_render_cache": {}
                        }
                        # RENDER INITIAL PAGE FOR SEARCH LIST
                        from .render_engine import get_renderer
                        renderer = get_renderer()
                        img_b64 = renderer.render_report(items[:ipp], page=1, total_pages=total_p)
                        event.meta["image_b64"] = img_b64
                        logger.info(f"[Dispatcher] Search list decoupled: AI sees full list, UI gets Image Page 1/{total_p}.")
                    # TRIGGER INITIAL PRE-WARM FOR SEARCH
                    _executor.submit(_prefetch_next_pages, session_id, is_chinese)
                
                # Store and chunk article content for paging (Skip if already handled by search/long-hit logic)
                if result.get("ok") and not is_handled:
                    from .render_engine import get_renderer
                    renderer = get_renderer()
                    article_item = result.get("items", [])[0]
                    # Split the network chunk into visible sub-pages
                    sub_pages = renderer.split_content_to_pages(article_item)
                    
                    SEARCH_RESULTS[session_id] = {
                        "mode": "article",
                        "query": args.get("query"),
                        "items": sub_pages,
                        "page": 1,
                        "total_pages": len(sub_pages),
                        "chunk_index": result.get("chunk_index", 0),
                        "total_chunks": result.get("total_chunks", 1),
                        "has_more": result.get("has_more", False),
                        "pre_render_cache": {} # Initialize cache
                    }
                    # result["items"] is PRESERVED (Raw technical stream for AI reasoning)
                    # RENDER INITIAL PAGE FOR USER
                    img_b64 = renderer.render_report([sub_pages[0]], page=1, total_pages=len(sub_pages))
                    event.meta["image_b64"] = img_b64
                    logger.info(f"[Dispatcher] Article decoupled: AI sees full chunk, UI gets Image Page 1/{len(sub_pages)}.")

            if result.get("ok") and "items" in result:
                raw_items = result["items"]
                import httpx
                for item in raw_items:
                    # Pre-fetch Image if URL is present (essential for synthesis)
                    if item.get("image_url") and not item.get("image_b64"):
                        try:
                            logger.info(f"[Dispatcher] Pre-fetching image: {item['image_url']}")
                            with httpx.Client(timeout=10.0) as client:
                                r = client.get(item["image_url"])
                                if r.status_code == 200:
                                    item["image_b64"] = base64.b64encode(r.content).decode("utf-8")
                                    logger.info("[Dispatcher] Image pre-fetched successfully.")
                        except Exception as e:
                            logger.warning(f"[Dispatcher] Image pre-fetch failed: {e}")
            
        elif tool == "set_reminder":
            result = tools.set_reminder(args.get("time"), args.get("content"), str(event.user_id))
            
        elif tool == "override_safety":
            result = tools.override_safety(
                str(event.user_id), 
                clearance=profile.get("clearance", 1),
                disable_safety=args.get("disable_safety", False)
            )
            
        # --- Self-Destruct 3-Step Flow ---
        if tool in ["initialize_self_destruct", "activate_self_destruct", "start_destruct", "engage_destruct"]:
            # Define callback for async notifications
            async def notify_callback(sid, message):
                sq = send_queue.SendQueue.get_instance()
                session_key = f"{event.platform}:{event.group_id or event.user_id}"
                await sq.enqueue_send(session_key, message, {
                    "group_id": event.group_id,
                    "user_id": event.user_id
                })
            
            # ARGUMENT NORMALIZATION
            # ARGUMENT NORMALIZATION
            # 1. Duration: Check multiple aliases (duration_seconds, time, seconds)
            d_val = args.get("duration") or args.get("duration_seconds") or args.get("seconds") or args.get("time") or 300
            try:
                duration = int(d_val)
            except:
                duration = 300
                
            # 2. Silent Mode: Check 'silent' bool/str OR 'mode' enum
            s_val = args.get("silent", False)
            m_val = args.get("mode", "")
            
            silent = False
            if isinstance(s_val, bool): silent = s_val
            elif isinstance(s_val, str): silent = (s_val.lower() == "true")
            
            if not silent and isinstance(m_val, str) and "silent" in m_val.lower():
                silent = True
            
            # Both tools map to the same internal logic: Initialize (which starts countdown)
            result = await tools.initialize_self_destruct(
                duration, 
                silent, 
                str(event.user_id), 
                profile.get("clearance", 1), 
                session_id,
                notify_callback,
                language="zh" if is_chinese else "en"
            )
            
        elif tool == "authorize_self_destruct":
            result = tools.authorize_self_destruct(
                str(event.user_id), 
                profile.get("clearance", 1), 
                session_id
            )
            
        # --- Cancel Flow ---
        elif tool in ["cancel_self_destruct", "abort_self_destruct", "cancel_destruct", "abort_destruct"]:
             result = tools.cancel_self_destruct(
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
            # LOGIC FIX: Check user text for intent if arg is missing
            user_text = event.text.lower()
            is_raise = any(k in user_text for k in ["raise", "up", "enable", "on", "activate", "升起", "开启", "打开", "启动"])
            active = args.get("active", is_raise)
            # Handle string 'true'/'false' from AI
            if isinstance(active, str):
                active = (active.lower() == "true")
                
            result = tools.toggle_shields(active, profile.get("clearance", 1))

        elif tool in ["cancel_self_destruct", "abort_self_destruct", "cancel_destruct", "abort_destruct"]:
            result = tools.abort_self_destruct(profile.get("user_id"), profile.get("clearance", 1), session_id)
            
        elif tool in ["set_holodeck_program", "reserve_holodeck", "run_program", "start_simulation", "holodeck_control"]:
             # ARGUMENT NORMALIZATION: 'program'/'name'/'title' -> 'program_name'
             prog = args.get("program_name") or args.get("program") or args.get("name") or args.get("title") or "Generic Simulation"
             duration = float(args.get("duration", 1.0))
             safety = args.get("disable_safety", False)
             if isinstance(safety, str): safety = (safety.lower() == "true")
             
             result = tools.reserve_holodeck(
                 program_name=prog, 
                 duration_hours=duration,
                 user_id=profile.get("user_id"),
                 rank=profile.get("rank", "ENSIGN"),
                 clearance=profile.get("clearance", 1),
                 disable_safety=safety
             )

        elif tool == "next_page" or tool == "prev_page":
            session_data = SEARCH_RESULTS.get(session_id)
            if not session_data:
                result = {"ok": False, "message": "无法完成：当前未开启查询进程，请先通过‘查询数据库’开启搜索，"}
            else:
                if session_data.get("mode") == "article":
                    # DUAL-TIER ARTICLE PAGING: Sub-pages (local) vs Chunks (network)
                    current_page = session_data["page"]
                    total_pages = session_data["total_pages"]
                    
                    new_page = current_page + 1 if tool == "next_page" else current_page - 1
                    
                    # 1. LOCAL SUB-PAGING (Flipping through rendered paragraphs)
                    if 1 <= new_page <= total_pages:
                        session_data["page"] = new_page
                        
                        # CHECK PRE-RENDER CACHE FIRST
                        cache = session_data.get("pre_render_cache", {})
                        if new_page in cache:
                            logger.info(f"[Dispatcher] Cache hit for article page {new_page}. Instant display.")
                            img_b64 = cache[new_page]
                        else:
                            items = [session_data["items"][new_page - 1]]
                            from .render_engine import get_renderer
                            renderer = get_renderer()
                            img_b64 = renderer.render_report(items, page=new_page, total_pages=total_pages)
                        
                        event.meta["image_b64"] = img_b64
                        result = {"ok": True, "message": f"FEDERATION DATABASE // ARTICLE PAGE {new_page} OF {total_pages}"}
                        
                        # TRIGGER NEXT PRE-WARM
                        _executor.submit(_prefetch_next_pages, session_id, is_chinese)
                    
                    # 2. NETWORK CHUNK-PAGING (Fetching next 2000-word block)
                    elif tool == "next_page" and (session_data.get("has_more") or session_data.get("chunk_index", 0) < session_data.get("total_chunks", 1) - 1):
                        new_chunk = session_data.get("chunk_index", 0) + 1
                        logger.info(f"[Dispatcher] Article boundary reached. Fetching Segment {new_chunk}...")
                        
                        # Note: we use _run_async to call the tool since we are in a sync dispatcher wrapper usually
                        result = tools.access_memory_alpha_direct(session_data["query"], session_id, is_chinese=is_chinese, chunk_index=new_chunk)
                        if result.get("ok") and result.get("items"):
                            article_item = result.get("items", [])[0]
                            from .render_engine import get_renderer
                            renderer = get_renderer()
                            sub_pages = renderer.split_content_to_pages(article_item)
                            
                            session_data.update({
                                "items": sub_pages,
                                "page": 1,
                                "total_pages": len(sub_pages),
                                "chunk_index": result.get("chunk_index", 0),
                                "total_chunks": result.get("total_chunks", 1),
                                "has_more": result.get("has_more", False),
                                "pre_render_cache": {} # Clear cache on new chunk
                            })
                            
                            img_b64 = renderer.render_report([sub_pages[0]], page=1, total_pages=len(sub_pages))
                            event.meta["image_b64"] = img_b64
                            result = {"ok": True, "message": f"FEDERATION DATABASE // LOADING NEXT SEGMENT (CHUNK {new_chunk + 1})"}
                            
                            # TRIGGER PRE-WARM FOR NEW CHUNK
                            _executor.submit(_prefetch_next_pages, session_id, is_chinese)
                        else:
                            result = {"ok": False, "message": "无法调阅后续分片：子空间通信干扰，"}
                    else:
                        result = {"ok": False, "message": "NO FURTHER RECORDS FOUND."}
                else:
                    # STANDARD SEARCH LIST PAGING
                    items = session_data.get("items", [])
                    current_page = session_data["page"]
                    total_pages = session_data["total_pages"]
                    
                    new_page = current_page + 1 if tool == "next_page" else current_page - 1
                    if 1 <= new_page <= total_pages:
                        session_data["page"] = new_page
                        
                        # CHECK PRE-RENDER CACHE
                        cache = session_data.get("pre_render_cache", {})
                        if new_page in cache:
                            logger.info(f"[Dispatcher] Cache hit for search page {new_page}.")
                            img_b64 = cache[new_page]
                        else:
                            ipp = session_data.get("items_per_page", 4)
                            start_idx = (new_page - 1) * ipp
                            end_idx = start_idx + ipp
                            from .render_engine import get_renderer
                            renderer = get_renderer()
                            img_b64 = renderer.render_report(items[start_idx:end_idx], page=new_page, total_pages=total_pages)
                        
                        event.meta["image_b64"] = img_b64
                        result = {"ok": True, "message": f"FEDERATION DATABASE ACCESS GRANTED // PAGE {new_page} OF {total_pages}"}
                        
                        # TRIGGER NEXT PRE-WARM
                        _executor.submit(_prefetch_next_pages, session_id, is_chinese)
                    else:
                        result = {"ok": False, "message": "NO FURTHER RECORDS FOUND."}

        elif tool == "show_details":
            target_id = args.get("id", "").upper()
            session_data = SEARCH_RESULTS.get(session_id)
            if not session_data or not target_id:
                result = {"ok": False, "message": "无法完成：请指定有效的检索编号（例如：1A），"}
            else:
                target_item = next((i for i in session_data.get("items", []) if i["id"] == target_id), None)
                if target_item:
                    # If it's a detail request, we can send the full text or high-res image
                    msg = f"--- 详细记录检索: {target_id} ---\n\n{target_item.get('content', '该条目无详细文本说明。')}"
                    result = {"ok": True, "message": msg}
                    # If there's an image, attach it
                    if target_item.get("image_b64"):
                        event.meta["image_b64"] = target_item["image_b64"]
                else:
                    result = {"ok": False, "message": f"无法完成：未能在当前结果集中找到编号为 {target_id} 的条目，"}
            
        elif tool == "get_status":
            result = tools.get_status(
                user_id=str(event.user_id),
                clearance=profile.get("clearance", 1)
            )

        elif tool == "get_shield_status":
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
                result = {"ok": False, "message": "无法完成，武器系统下线，"}
            else:
                is_fire = any(k in tool_name.lower() for k in ["fire", "开火", "射击"])
                msg = "确认，正在开火，" if is_fire else "目标已锁定，"
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
                profile.get("clearance", 1),
                session_id=session_id
            )
            
        elif tool == "execute_procedure":
            result = tools.execute_procedure(
                args.get("procedure_name") or "Standard Procedure",
                args.get("steps") or [],
                session_id=session_id
            )
            
        elif tool == "manage_environment":
            # SYNTHETIC FIELD GENERATION
            # If AI didn't provide system_name, try to infer from tool_name/args
            # e.g. set_bridge_temperature -> system_name="bridge_temperature"
            sys_name = args.get("system_name") or args.get("name")
            if not sys_name:
                sys_name = "bridge_environment" if "bridge" in tool_name.lower() else "ambient_environment"
            
            result = tools.manage_environment(
                sys_name,
                str(args.get("value") or args.get("state") or "NOMINAL"),
                str(event.user_id),
                profile.get("clearance", 1),
                **args
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

        elif tool == "verify_logical_consistency":
            result = tools.verify_logical_consistency(
                args.get("logic_chain") or args.get("logic", ""),
                profile.get("clearance", 1)
            )

            
        elif tool == "get_personnel_file":
            # LOGIC FIX: If target is a NAME (not ID/Mention), route to Knowledge Base
            target = args.get("target_mention") or args.get("name") or args.get("who") or ""
            is_real_user = bool(re.search(r"\d+", str(target)))
            
            if target and not is_real_user and len(target) > 2:
                # User asked for "Picard", not a QQ users. Redirect to Research.
                logger.info(f"[Dispatcher] Redirecting personnel query '{target}' to Knowledge Base.")
                result = await tools.query_knowledge_base(f"Personnel File: {target} history and biography", session_id)
            else:
                result = tools.get_personnel_file(target, str(event.user_id), is_chinese=is_chinese)
            
        elif tool == "audit_clear_fault":
             result = tools.audit_clear_fault(args.get("fault_id"), profile.get("clearance", 1))

        elif tool == "trigger_ads_test":
             result = tools.trigger_ads_test(profile.get("clearance", 1), **args)

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
        
        elif tool == "register_sentinel_trigger":
            # Normalize arguments for Sentinel
            condition = args.get("condition") or args.get("if")
            action = args.get("action") or args.get("then")
            desc = args.get("description") or f"If {condition}, then {action}"
            ttl = args.get("ttl", 3600)
            
            result = tools.register_sentinel_trigger(
                condition=str(condition),
                action=str(action),
                description=str(desc),
                user_id=str(event.user_id),
                ttl=float(ttl)
            )

        elif tool == "get_sentinel_status":
            result = tools.get_sentinel_status()
        else:
            # PHASE 4: SELF-HEALING & ADAPTIVE RESOLUTION
            logger.warning(f"[Dispatcher] Unknown tool '{tool}' requested. Initiating Logic Repair Scan...")
            
            # Safe definition
            tool_lower = tool.lower() if tool else ""
            
            # 0. SEMANTIC ALIAS MAP (Hardcoded Hallucination Bridges)
            SEMANTIC_MAP = {
                # Weapons
                "fire_photon_torpedoes": "weapon_lock_fire",
                "launch_torpedoes": "weapon_lock_fire",
                "fire_phasers": "weapon_lock_fire",
                "torpedo_control": "weapon_lock_fire",
                "tactical_analysis": "weapon_lock_fire",
                # Holodeck
                "set_holosimulation": "reserve_holodeck",
                "holodeck_simulation": "reserve_holodeck",
                "start_simulation": "reserve_holodeck",
                # Scanning
                "scan_area": "query_knowledge_base",
                "scan_lifeforms": "query_knowledge_base",
                "long_range_scan": "search_memory_alpha",
                # System
                "computer_diagnosis": "get_system_metrics",
                "system_diagnostic": "get_system_metrics",
                "eject_reactor": "eject_warp_core",
                # Environment (Dynamic Phase 4)
                "set_temperature": "manage_environment",
                "adjust_lighting": "manage_environment",
                "set_brightness": "manage_environment",
                "environmental_control": "manage_environment"
            }
            
            corrected_tool = None
            if tool_lower in SEMANTIC_MAP: # Use tool_lower check
                corrected_tool = SEMANTIC_MAP[tool_lower]
                logger.info(f"[Dispatcher] SELF-HEALING: Semantic Map Hit '{tool}' -> '{corrected_tool}'")
            
            else:
                import difflib
                # 1. Inspect 'tools' module for all valid callable functions
                valid_tools = [
                    name for name in dir(tools) 
                    if callable(getattr(tools, name)) and not name.startswith("_")
                ]
                
                # 2. Find closest match (cutoff=0.6 covers simple typos like 'set_holodeck' -> 'reserve_holodeck')
                matches = difflib.get_close_matches(tool, valid_tools, n=1, cutoff=0.5)
                if matches:
                    corrected_tool = matches[0]
                    logger.info(f"[Dispatcher] SELF-HEALING: Fuzzy Match Hit '{tool}' -> '{corrected_tool}'")
                else:
                    # 3. SESM: CHECK EXPERIMENTAL HOOKS
                    from . import experimental_hooks
                    func = experimental_hooks.get_experimental_tool(tool)
                    if func:
                        logger.info(f"[Dispatcher] SESM: Executing synthesized hook '{tool}'")
                        corrected_tool = tool # Mark as found

            if corrected_tool:
                # 3. Dynamic Dispatch
                # Check tools first, then experimental_hooks
                func = getattr(tools, corrected_tool, None)
                if not func:
                    from . import experimental_hooks
                    func = getattr(experimental_hooks, corrected_tool, None)
                
                if not func:
                     return {"ok": False, "message": f"Unknown tool: {tool}", "error": "unknown_tool"}
                     
                # Check signature to safely pass args (naive approach: assume kwargs matching)
                try:
                    # Filter args to match signature? Not easy dynamically without inspect.
                    result = func(**args)
                    result["meta"] = {"self_healed": True, "original_tool": tool, "corrected_tool": corrected_tool}
                    
                except TypeError as te:
                     # Fallback: Check if it needs specific common args like 'user_id' not in args
                     logger.warning(f"[Dispatcher] Dynamic dispatch arg mismatch: {te}. Retrying with profile injection...")
                     try:
                         # SPECIAL HANDLER: Search Tools - squash extra args into query
                         if corrected_tool in ["query_knowledge_base", "search_memory_alpha"] and "query" in args:
                             # 1. Identify valid args for these tools (usually just query, session_id)
                             # 2. Squash everything else into query
                             base_query = args["query"]
                             extra_context = []
                             for k, v in args.items():
                                 if k not in ["query", "session_id", "user_id"]:
                                     extra_context.append(f"{k}: {v}")
                             
                             if extra_context:
                                 new_query = f"{base_query} ({' '.join(extra_context)})"
                                 logger.info(f"[Dispatcher] Squashing args for search: '{new_query}'")
                                 args = {"query": new_query, "session_id": session_id}
                         
                         # Standard Injection (Signature Aware)
                         standard_args = {
                             "user_id": str(event.user_id),
                             "session_id": session_id,
                             "clearance": profile.get("clearance", 1)
                         }
                         
                         sig = inspect.signature(func)
                         for k, v in standard_args.items():
                             if k in sig.parameters and k not in args:
                                 args[k] = v
                         
                         result = func(**args)
                         result["meta"] = {"self_healed": True, "original_tool": tool, "corrected_tool": corrected_tool}
                     except Exception as e2:
                         # CRITICAL: Re-raise so this bubbles up to the Dispatcher's ADS fault reporter
                         raise e2
            else:
                return {"ok": False, "message": f"Unknown tool: {tool} (No matching protocol found)", "error": "unknown_tool"}
            
        if result and "ok" not in result:
            result["ok"] = True
        return result
    except Exception as e:
        logger.error(f"Tool execution critical failure: {e}", exc_info=True)
        # CRITICAL: Re-raise so this bubbles up to the Dispatcher's ADS fault reporter
        raise e

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
    
    if isinstance(whitelist_raw, list):
        whitelist = [str(g).strip() for g in whitelist_raw if str(g).strip()]
    else:
        whitelist = [g.strip() for g in str(whitelist_raw).split(",") if g.strip()]
    
    if not whitelist or "*" in whitelist:
        return True
        
    return str(group_id) in whitelist

async def _execute_ai_logic(event: InternalEvent, user_profile: dict, session_id: str, force_tool: str = None, force_args: dict = None, ops_task=None, initial_cumulative_data: list = None):
    """
    STAR EXECUTION LOOP 2.0 (Liquid Agent Matrix with Phase 4 Resilience)
    Enhanced with ADS (Auto-Diagnostic Routine) fault reporting.
    """
    from .ops_registry import TaskState, OpsRegistry
    ops = OpsRegistry.get_instance()
    if ops_task:
        await ops.update_state(ops_task.pid, TaskState.RUNNING)
        
    try:
        wd = watchdog.get_watchdog()
        wd.record_heartbeat()
    except Exception as e:
        logger.warning(f"[Dispatcher] Watchdog heartbeat failed: {e}")

    profile_str = permissions.format_profile_for_ai(user_profile)
    logger.info(f"[Dispatcher] Starting Agentic Loop for session {session_id}")
    
    try: # --- ADS PROTECTED WRAPPER ---
        iteration = 0
        # SYNCED WITH FEDERATION PROTOCOL 2.1: Maximum efficiency mode
        max_iterations = 3 
        cumulative_data = initial_cumulative_data or [] 
        active_node = "COORDINATOR"
        last_audit_status = "NOMINAL"
        image_b64 = None
        last_tool_call = None
        executed_tools = []
        terminate_agent_loop = False
        reply_text = ""

        while iteration < max_iterations and not terminate_agent_loop:
            iteration += 1
            logger.info(f"[Dispatcher] Liquid Matrix Iteration {iteration}/{max_iterations}")

            if force_tool and iteration == 1:
                result = {"ok": True, "intent": "tool_call", "tool": force_tool, "args": force_args or {}, "is_chinese": True}
            else:
                extra_meta = {"user_profile": profile_str}
                if cumulative_data: extra_meta["cumulative_data"] = "\n---\n".join(cumulative_data)
                odn_snapshot = context_bus.get_odn_snapshot(session_id, user_profile)
                extra_meta["odn_snapshot"] = context_bus.format_snapshot_for_prompt(odn_snapshot)
                extra_meta["active_node"] = active_node

                future = _executor.submit(rp_engine_gemini.generate_computer_reply, event.text, router.get_session_context(session_id), extra_meta)
                result = future.result(timeout=20)
            
            if not result or not result.get("ok"): break

            intent = result.get("intent")
            tool_chain = result.get("tool_chain") or ([{"tool": result.get("tool"), "args": result.get("args") or {}}] if result.get("tool") else [])

            if intent == "tool_call" and tool_chain:
                for step_idx, step in enumerate(tool_chain):
                    tool = step.get("tool")
                    args = step.get("args") or {}
                    tool_result = await _execute_tool(tool, args, event, user_profile, session_id)
                    executed_tools.append(tool)
                    last_tool_result = tool_result

                    if tool_result and tool_result.get("ok"):
                        msg = tool_result.get("message", "") or "OK"
                        cumulative_data.append(f"ACTION ({tool}): {msg}")
                    else:
                        reply_text = f"Unable to comply. ERROR: {tool_result.get('message')}"
                        terminate_agent_loop = True
                        break
            else:
                reply_text = result.get("reply", "")
                
                # --- NEURAL EVOLUTION TRIGGER ---
                if "Processing correction" in reply_text or result.get("intent") == "correction":
                    logger.info("[Dispatcher] Neural Evolution Triggered. Dehydrating feedback...")
                    ea = get_evolution_agent()
                    # Run dehydration in background
                    async def run_evolution():
                        evo_res = await ea.dehydrate_correction(event.text, "Previous session history")
                        if evo_res.get("ok"):
                            logger.info(f"[Dispatcher] Evolution successful: {evo_res.get('directive')}")
                    
                    asyncio.create_task(run_evolution())
                
                break

        # ADS 2.7 Tune: Only synthesize if we actually executed tools during this call (meaning cumulative_data changed)
        # OR if we have pre-fetched data but the LLM hasn't produced a final narrative reply yet.
        if executed_tools or (cumulative_data and not reply_text):
            all_raw = "\n\n".join(cumulative_data)
            future = _executor.submit(rp_engine_gemini.synthesize_search_result, event.text, all_raw, True, context=router.get_session_context(session_id))
            reply_text = future.result(timeout=20)

        if reply_text or image_b64:
            sq = send_queue.SendQueue.get_instance()
            await sq.enqueue_send(f"qq:{event.group_id or event.user_id}", reply_text, {
                "group_id": event.group_id,
                "user_id": event.user_id,
                "reply_to": event.message_id,
                "image_b64": image_b64
            })
            return True
        if iteration >= max_iterations and not terminate_agent_loop:
            logger.warning(f"[Dispatcher] Efficiency Threshold reached for {session_id}. Reporting to ADS.")
            from .diagnostic_manager import get_diagnostic_manager
            dm = get_diagnostic_manager()
            dm.report_fault(
                "NeuralProcessor.Efficiency", 
                Exception("Cognitive Limit Reached"), 
                query=event.text, 
                traceback_str="Iteration cap 3/3 reached. Neural resource exhaustion detected."
            )
        
        return False

    except Exception as e:
        import traceback
        # ADS 2.10: Re-initialize reply_text to prevent UnboundLocalError during crash log
        if 'reply_text' not in locals():
            reply_text = "Subspace interference detected in internal matrix."
            
        from .diagnostic_manager import get_diagnostic_manager
        dm = get_diagnostic_manager()
        fault_id = dm.report_fault("Dispatcher.AgenticLoop", e, query=event.text, traceback_str=traceback.format_exc())
        logger.error(f"[Dispatcher] ADS CRASH [{fault_id}]: {e}")
        return False


async def handle_event(event: InternalEvent):
    """
    Main entry point for processing incoming events.
    """
    # --- MESSAGE DEDUPLICATION (ADS 2.2) ---
    current_ts = time.time()
    if event.message_id in PROCESSED_MESSAGES:
        elapsed = current_ts - PROCESSED_MESSAGES[event.message_id]
        if elapsed < 60: # 60s window
            logger.info(f"[Dispatcher] Duplicate Message ID {event.message_id} detected. Dropping.")
            return False
    
    PROCESSED_MESSAGES[event.message_id] = current_ts
    
    # Cleanup old message cache periodically
    if len(PROCESSED_MESSAGES) > 1000:
        expired = [m for m, t in PROCESSED_MESSAGES.items() if current_ts - t > 300]
        for m in expired: PROCESSED_MESSAGES.pop(m)

    # Session ID logic (Group ID takes precedence)
    session_id = event.group_id if event.group_id else f"p_{event.user_id}"
    
    # Check whitelist (ADS 2.11: Fixed bypass bug where numerical group IDs were ignored)
    if not is_group_enabled(event.group_id):
        return False
        
    print(f"\n{'='*30} NEW TRANSMISSION {'='*30}\n")
    logger.info(f"[Dispatcher] Processing event: {event.event_type} from {event.user_id}")
    
    # --- SESSION LOCKING (NEURAL LOCK) ---
    if session_id not in NEURAL_LOCKS:
        NEURAL_LOCKS[session_id] = asyncio.Lock()
    
    if NEURAL_LOCKS[session_id].locked():
        logger.warning(f"[Dispatcher] Session {session_id} is currently BUSY. Dropping overlapping event.")
        # Optional: Send a 'Thinking' indicator if this is the first overlap
        return False
        
    async with NEURAL_LOCKS[session_id]:
        # --- OPS COMMAND INTERCEPT (PRE-AI) ---
        is_ops_query = False
        if event.text:
            text_l = event.text.lower()
            if text_l.startswith("/ops") or any(kw in text_l for kw in ["后台任务", "进程列表", "任务列表", "显示进程", "查看进程"]):
                is_ops_query = True

        if is_ops_query:
            from . import ops_registry
            ops = ops_registry.OpsRegistry.get_instance()
            sq = send_queue.SendQueue.get_instance()
            session_key = f"{event.platform}:{event.group_id or event.user_id}"
            
            cmd_parts = event.text.split()
            # Normalization
            raw_cmd = cmd_parts[0][4:] if cmd_parts[0].startswith("/ops") and len(cmd_parts[0]) > 4 else "list"
            if any(kw in event.text for kw in ["终止", "停止", "abort", "cancel"]): raw_cmd = "abort"
            if any(kw in event.text for kw in ["优先", "置顶", "priority"]): raw_cmd = "priority"

            if raw_cmd == "list":
                tasks = await ops.get_active_tasks()
                if not tasks:
                    await sq.enqueue_send(session_key, "OPS: No active background processes.", {"from_computer": True}, priority=1)
                else:
                    report = "STATUS: ACTIVE PROCESSES\n" + "-"*30 + "\n"
                    for t in tasks:
                        # Calculate duration
                        dur = int(time.time() - t.created_at)
                        report += f"[{t.pid}] {t.priority.name} | {t.state.value} | {dur}s | {t.query[:20]}...\n"
                    await sq.enqueue_send(session_key, report, {"from_computer": True}, priority=1)
                return True
            elif raw_cmd == "abort":
                # Try to find PID in text
                pid_match = re.search(r"0x[0-9A-F]{4}", event.text, re.I)
                target_pid = pid_match.group(0).upper() if pid_match else (cmd_parts[1] if len(cmd_parts) > 1 else None)
                
                if target_pid:
                    success = await ops.abort_task(target_pid)
                    reply = f"OPS: Task {target_pid} terminated." if success else f"OPS: Task {target_pid} not found or already completed."
                else:
                    reply = "OPS: Specify PID to abort. Use '/ops list' to see active tasks."
                await sq.enqueue_send(session_key, reply, {"from_computer": True}, priority=1)
                return True
            elif raw_cmd == "priority":
                pid_match = re.search(r"0x[0-9A-F]{4}", event.text, re.I)
                target_pid = pid_match.group(0).upper() if pid_match else (cmd_parts[1] if len(cmd_parts) > 1 else None)
                
                if target_pid:
                    # Default to ALPHA (1) for manual priority shift
                    success = await ops.set_priority(target_pid, TaskPriority.ALPHA)
                    reply = f"OPS: Task {target_pid} priority shifted to ALPHA." if success else f"OPS: Task {target_pid} focus change failed."
                else:
                    reply = "OPS: Specify PID for priority shift."
                await sq.enqueue_send(session_key, reply, {"from_computer": True}, priority=1)
                return True
        
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
                
                # Generate AI reply using helper (async await)
                
                # ADS 4.0: PRE-LLM PROTOCOL SCAN (Hard Block for Restricted Topics)
                if True: # Local Scope
                     proto_scan = tools.check_text_protocols(event.text, {"clearance": user_profile.get("clearance", 1)})
                     if proto_scan.get("violation"):
                         if proto_scan.get("action") == "BLOCK":
                             logger.critical(f"[Dispatcher] PROTOCOL BLOCK: {proto_scan['message']}")
                             await send_to_user({
                                 "text": f"🛑 {proto_scan['message']}",
                                 "reply_to": event.message_id
                             })
                             return True
                         elif proto_scan.get("action") == "WARN":
                             # Append warning to prompt context? Or send warning first.
                             # For now, separate message
                             await send_to_user({
                                 "text": f"⚠️ {proto_scan['message']}",
                                 "reply_to": event.message_id
                             })

                # DETERMINISTIC NAVIGATION FAST-PATH (ADS 2.9: LLM-First for Status)
                # We have retired the Status Fast-Path to avoid sensitivity issues. 
                # Navigation tools (next/prev) remain deterministic for UI responsiveness.
                nav_text = event.text.strip().lower()
                force_tool = None
                initial_cumulative_data = []

                # Navigation Fast-Path
                if re.match(r'.*(next|next page|下一页|下页|继续|还|more).*', nav_text):
                    force_tool = "next_page"
                    logger.info("[Dispatcher] Fast-Path triggered: Force Next Page")
                elif re.match(r'.*(previous|prev|previous page|back|上一页|上页|返回).*', nav_text):
                    force_tool = "prev_page"
                    logger.info("[Dispatcher] Fast-Path triggered: Force Prev Page")
                    
                # PHASE 8: OPS TASK REGISTRATION & PARALLEL EXECUTION
                ops = OpsRegistry.get_instance()
                # Determine Priority
                priority = TaskPriority.GAMMA
                if any(kw in event.text.lower() for kw in ["destruct", "自毁", "red alert", "红警", "override"]):
                    priority = TaskPriority.ALPHA
                
                task = await ops.register_task(session_id, event.text, priority=priority)
                
                # Await in background: Lock now persists for the ENTIRE agentic loop
                await _execute_ai_logic(
                    event, user_profile, session_id, 
                    force_tool=force_tool, 
                    ops_task=task,
                    initial_cumulative_data=initial_cumulative_data
                )
                
                # Immediate Acknowledgment if needed (Silent by default unless high-stakes)
                if priority == TaskPriority.ALPHA:
                    sq = send_queue.SendQueue.get_instance()
                    session_key = f"{event.platform}:{event.group_id or event.user_id}"
                    await sq.enqueue_send(session_key, f"ACK: Critical Priority Task Registered [{task.pid}]. Processing...", {"from_computer": True}, priority=1)
                
                return True
                
            else:
                logger.info(f"[Dispatcher] Route is chat/low confidence, not responding.")
        except Exception as e:
            import traceback
            from .diagnostic_manager import get_diagnostic_manager
            dm = get_diagnostic_manager()
            fault_id = dm.report_fault("Dispatcher.handle_event", e, query=event.text, traceback_str=traceback.format_exc())
            
            logger.error(f"[Dispatcher] Error processing message [{fault_id}]: {e}", exc_info=True)
            
            # LCARS Error Reply
            try:
                sq = send_queue.SendQueue.get_instance()
                session_key = f"qq:{event.group_id or event.user_id}"
                is_ch = any('\u4e00' <= char <= '\u9fff' for char in event.text)
                error_msg = f"Unable to comply. CORE ERROR: [{fault_id}]" if not is_ch else f"无法执行。核心错误：[{fault_id}]"
                
                # Use run_async or similar if outside async context, but handle_event IS async
                await sq.enqueue_send(session_key, error_msg, {
                    "group_id": event.group_id,
                    "user_id": event.user_id,
                    "reply_to": event.message_id
                })
            except:
                pass
    
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

