import time
import datetime
import ast
import operator
import logging
import re

logger = logging.getLogger(__name__)

def get_status() -> dict:
    """
    Returns real-time starship status from ShipSystems.
    """
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    return {
        "ok": True,
        "message": f"STATUS REPORT: {ss.get_shield_status()}. Alert status: {ss.alert_status.value}.",
        "shields_active": ss.shields_active,
        "shield_integrity": ss.shield_integrity,
        "alert": ss.alert_status.value,
        "subsystems": {k: v.value for k, v in ss.subsystems.items()}
    }

def get_subsystem_status(name: str) -> dict:
    """
    Returns the status of a specific subsystem.
    """
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    name = name.lower()
    if name in ss.subsystems:
        state = ss.subsystems[name].value
        return {
            "ok": True,
            "name": name,
            "state": state,
            "message": f"子系统 {name} 当前状态：{state}。"
        }
    return {"ok": False, "message": f"找不到子系统：{name}。"}

def get_time() -> dict:
    """
    Returns current system time.
    """
    now = datetime.datetime.now()
    return {
        "ok": True,
        "message": f"Current system time: {now.strftime('%H:%M:%S')} (CST)",
        "iso": now.strftime("%H:%M:%S"),
        "unix": int(time.time()),
        "tz": "CST"
    }

def calc(expr: str) -> dict:
    """
    Safely evaluates a basic mathematical expression.
    Only allows: numbers, +, -, *, /, (, ), ., and spaces.
    """
    # Whitelist characters
    if not all(c in "0123456789+-*/(). " for c in expr):
        return {"ok": False, "result": None, "error": "invalid_characters"}

    try:
        # Use a safe eval-like approach for basic math
        # ast.parse is safer than raw eval
        node = ast.parse(expr, mode='eval')
        
        # Simple recursive evaluator for specific nodes
        def eval_node(n):
            if isinstance(n, ast.Expression):
                return eval_node(n.body)
            if isinstance(n, ast.Num):
                return n.n
            if isinstance(n, ast.BinOp):
                left = eval_node(n.left)
                right = eval_node(n.right)
                ops = {
                    ast.Add: operator.add,
                    ast.Sub: operator.sub,
                    ast.Mult: operator.mul,
                    ast.Div: operator.truediv,
                }
                return ops[type(n.op)](left, right)
            if isinstance(n, ast.UnaryOp):
                operand = eval_node(n.operand)
                if isinstance(n.op, ast.USub):
                    return -operand
                return operand
            raise ValueError(f"Unsupported node: {type(n)}")

        result = eval_node(node)
        return {"ok": True, "result": result, "error": None}
    except Exception as e:
        logger.warning(f"Calculation failed: {e}")
        return {"ok": False, "result": None, "error": str(e)}

def replicate(item_name: str, user_id: str, rank: str, clearance: int = 1) -> dict:
    """
    Replicates an item using replicator credits (1.8 Style: 5 credits per item).
    """
    from .quota_manager import get_quota_manager
    from .ship_systems import get_ship_systems
    
    ss = get_ship_systems()
    if not ss.is_subsystem_online("replicator"):
        return {"ok": False, "message": "无法完成：复制机系统下线。"}

    qm = get_quota_manager()
    cost = 5 # 1.8 Standard cost
    
    item_lower = item_name.lower()
    if any(k in item_lower for k in ["phaser", "weapon", "explosive", "rifles"]):
        if clearance < 9:
            return {"ok": False, "message": "权限不足拒绝访问"}
        cost = 50 # Weapons are expensive
    
    balance = qm.get_balance(user_id, rank)
    if balance < cost:
        return {"ok": False, "message": f"无法完成：你的配额不足。需要 {cost} 个配额，当前剩余 {balance} 个。"}
        
    qm.spend_credits(user_id, cost)
    return {
        "ok": True,
        "message": f"复制中…（消耗 {cost} 配额）\n[嘀—— 嘶嘶——]\n复制完成：{item_name}。",
        "item": item_name,
        "cost": cost
    }

def reserve_holodeck(program_name: str, duration_hours: float, user_id: str, rank: str, clearance: int = 1, disable_safety: bool = False) -> dict:
    """
    Reserves a holodeck session with safety protocol check.
    """
    from .quota_manager import get_quota_manager
    qm = get_quota_manager()
    
    # Safety Protocol Check (12-level)
    if disable_safety and clearance < 9:
         return {
            "ok": False,
            "message": f"Access denied. Disabling safety protocols is a restricted Senior Officer command (Level 9 Required). Current level: {clearance}.",
            "cost": 0,
            "remaining": qm.get_balance(user_id, rank)
        }
        
    cost = int(duration_hours * 50)
    if disable_safety: cost += 100 # Risk surcharge
    
    if qm.spend_credits(user_id, cost):
        status = "SAFETY PROTOCOLS DISABLED" if disable_safety else "Safety protocols active"
        return {
            "ok": True,
            "message": f"Holodeck reserved: '{program_name}' ({duration_hours}h). {status}.",
            "cost": cost,
            "remaining": qm.get_balance(user_id, rank)
        }
    else:
        return {
            "ok": False,
            "message": "Insufficient holodeck energy credits.",
            "cost": cost,
            "remaining": qm.get_balance(user_id, rank)
        }

def get_ship_schematic(ship_name: str, clearance: int = 1) -> dict:
    """
    Retrieves ship technical schematics. Requires Level 4+ for detailed specs.
    """
    ship_db = {
        "Constitution": {
            "class": "Heavy Cruiser",
            "length": "289m",
            "decks": 21,
            "crew": 430,
            "max_warp": 8.0,
            "summary": "The flagship of the mid-23rd century, iconic for its exploration missions."
        },
        "Sovereign": {
            "class": "Heavy Cruiser / Explorer",
            "length": "685m",
            "decks": 24,
            "crew": 700,
            "max_warp": 9.985,
            "summary": "State-of-the-art combat and exploration vessel of the late 24th century."
        },
        "Galaxy": {
            "class": "Explorer",
            "length": "642m",
            "decks": 42,
            "crew": 1012,
            "max_warp": 9.6,
            "summary": "A massive deep-space explorer designed for long-term diplomatic and scientific missions."
        }
    }
    
    ship_key = next((k for k in ship_db if k.lower() in ship_name.lower()), "Generic")
    
    if clearance < 4 and ship_key != "Generic":
        return {
            "ok": False,
            "message": f"Access denied. Technical schematics for {ship_key} class require Clearance Level 4. Current level: {clearance}.",
            "clearance_required": 4
        }
        
    data = ship_db.get(ship_key)
    if not data:
        return {"ok": False, "message": f"No records found for class: {ship_name}."}
        
    return {
        "ok": True,
        "message": f"RECORD RETRIEVED: {ship_key} Class {data['class']}. Length: {data['length']}. Max Warp: {data['max_warp']}. {data['summary']}",
        "title": f"TECHNICAL SCHEMATIC: {ship_key} CLASS",
        "sections": [
            {"category": "General Specs", "content": f"Class: {data['class']}\nLength: {data['length']}\nDecks: {data['decks']}"},
            {"category": "Tactical/Propulsion", "content": f"Max Warp: {data['max_warp']}\nCrew Compliment: {data['crew']}"},
            {"category": "Mission Profile", "content": data['summary']}
        ]
    }

def query_knowledge_base(query: str, session_id: str) -> dict:
    """
    Searches the extensive local MSD Knowledge Base (Mega-Scale).
    Scans the markdown files in the msd_knowledge_base directory.
    """
    import os
    # Use relative path so it works inside Docker
    KB_DIR = os.path.join(os.path.dirname(__file__), "msd_knowledge_base")
    
    hits = []
    
    try:
        if not os.path.exists(KB_DIR):
             return {"ok": False, "message": f"Knowledge Base directory not found at {KB_DIR}.", "hits": []}

        # Priority scan: Index first
        files = sorted([f for f in os.listdir(KB_DIR) if f.endswith(".md")])
        
        # Simple keyword matching (enhanced logic could go here)
        query_lower = query.lower()
        keywords = query_lower.split()
        
        for filename in files:
            path = os.path.join(KB_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                
            score = 0
            if query_lower in content.lower():
                score += 5
            
            for k in keywords:
                if k in content.lower():
                    score += 1
            
            if score > 0:
                # Extract relevant snippet (rudimentary)
                idx = content.lower().find(keywords[0]) if keywords else -1
                start = max(0, idx - 200)
                end = min(len(content), idx + 500)
                snippet = content[start:end].replace("\n", " ") + "..."
                hits.append({
                    "file": filename,
                    "score": score,
                    "snippet": snippet,
                    "full_path": path 
                })
        
        # Sort by score
        hits.sort(key=lambda x: x["score"], reverse=True)
        top_hits = hits[:3]
        
        if not top_hits:
            return {"ok": False, "message": "No matching records found in local archives.", "count": 0}
            
        # Construct a digest
        digest = f"FOUND {len(hits)} RECORDS IN ARCHIVE:\n"
        for hit in top_hits:
            digest += f"\n--- [FILE: {hit['file']}] ---\n{hit['snippet']}\n"
            
        return {
            "ok": True,
            "message": digest,
            "count": len(hits),
            "top_file": top_hits[0]["file"]
        }

    except Exception as e:
        logger.error(f"KB Query failed: {e}")
        return {"ok": False, "message": f"Archive query error: {e}"}

def search_memory_alpha(query: str, session_id: str) -> dict:
    """
    Uses Google Search (via Gemini Grounding) to query Memory Alpha.
    Fallback for when local KB is insufficient.
    """
    from .config_manager import ConfigManager
    from google import genai
    from google.genai import types
    
    config = ConfigManager.get_instance()
    api_key = config.get("gemini_api_key", "")
    logger.info(f"[Tools] search_memory_alpha called. Query: {query}")
    
    if not api_key:
         logger.warning("[Tools] External search offline: API Key missing")
         return {"ok": False, "message": "External search offline (API Key missing)."}
         
    try:
        client = genai.Client(api_key=api_key)
        logger.info("[Tools] GenAI client initialized for search.")
        
        # We use a separate model call to perform the search and reasoning
        search_prompt = f"Search Memory Alpha (Star Trek Wiki) for: {query}. Summarize the technical specifications or details."
        
        # Enable Google Search Tool
        google_search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=search_prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                response_mime_type="text/plain", 
                temperature=0.3
            )
        )
        
        if response.text:
             return {
                 "ok": True,
                 "message": f"EXTERNAL DATABASE (MEMORY ALPHA) RESULT:\n{response.text}",
                 "source": "Memory Alpha / Google Search"
             }
        else:
            return {"ok": False, "message": "External database returned no data."}

    except Exception as e:
        logger.error(f"Memory Alpha search failed: {e}")
        return {"ok": False, "message": f"Subspace communication error: {e}"}
    """
    Retrieves library computer historical records.
    """
    archives = {
        "TOS": "The Original Series (2260s): Exploring the final frontier with Captain Kirk and Mr. Spock.",
        "TNG": "The Next Generation (2360s): Strategic diplomacy and exploration under Captain Picard.",
        "DS9": "Deep Space 9: Frontier life and the Dominion War on a Cardassian-built station.",
        "VOY": "Voyager: The long journey from the Delta Quadrant back to Federation space.",
        "Federation": "The United Federation of Planets: Founded in 2161 by Humans, Vulcans, Andorians, and Tellarites."
    }
    
    found_key = next((k for k in archives if k.lower() in topic.lower()), None)
    
    if not found_key:
        return {"ok": False, "message": "Insufficient data in historical archives for specified topic."}
        
    return {
        "ok": True,
        "message": f"RECORD RETRIEVED: {archives[found_key]}"
    }

def personal_log(content: str, user_id: str) -> dict:
    """
    Records a personal log. Grants random credits (2h cooldown).
    """
    from .quota_manager import get_quota_manager
    qm = get_quota_manager()
    
    result = qm.record_log(user_id)
    return result

# --- SELF-DESTRUCT & AUTH TOOLS ---

# --- SELF-DESTRUCT TOOLS (3-Step Flow) ---

def get_destruct_status(session_id: str) -> dict:
    """
    Query the current self-destruct sequence status.
    Returns state, remaining time, authorization status, etc.
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return dm.get_status(session_id)


async def initialize_self_destruct(seconds: int, silent: bool, user_id: str, clearance: int, session_id: str, notify_callback, language: str = "en") -> dict:
    """
    Step 2 (Version 1.8): Initialize and start the self-destruct countdown.
    Requires Level 9+. This will only succeed if 3 unique signatures have been 
    previously collected via 'authorize_self_destruct' (or if called by Level 11+).
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return await dm.initialize(session_id, user_id, clearance, duration=seconds, silent=silent, language=language, notify_callback=notify_callback)


def authorize_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """
    Step 1 (Version 1.8): Record an authorization signature. 
    Requires Level 8+. 3 unique signatures must be recorded BEFORE calling 'initialize'.
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return dm.authorize(session_id, user_id, clearance)


async def activate_self_destruct(user_id: str, clearance: int, session_id: str, notify_callback) -> dict:
    """
    Alternate trigger for Step 2. In Version 1.8, 'initialize' handles activation.
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return await dm.initialize(session_id, user_id, clearance, notify_callback=notify_callback)


def authorize_cancel_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """
    Step 1 (Version 1.8): Record an authorization signature to cancel self-destruct.
    Requires Level 11+. 3 unique signatures must be recorded BEFORE calling 'confirm_cancel'.
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return dm.authorize_cancel(session_id, user_id, clearance)


def confirm_cancel_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """
    Step 2 (Version 1.8): Execute the self-destruct cancellation.
    Requires Level 9+. This will only succeed if 3 unique signatures have been 
    previously collected via 'authorize_cancel_self_destruct' (or if called by Level 11+).
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return dm.confirm_cancel(session_id, user_id, clearance)


# Legacy aliases for backward compatibility
def initiate_self_destruct(seconds: int, silent: bool, user_id: str, clearance: int, session_id: str, notify_callback) -> dict:
    """Legacy wrapper - redirects to initialize_self_destruct."""
    # Note: legacy caller might not provide notify_callback, but dispatcher now always does
    return initialize_self_destruct(seconds, silent, user_id, clearance, session_id, notify_callback)


def abort_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """Legacy wrapper - redirects to authorize_cancel_self_destruct."""
    return authorize_cancel_self_destruct(user_id, clearance, session_id)


def authorize_sequence(action_type: str, user_id: str, clearance: int, session_id: str) -> dict:
    """
    Legacy wrapper for backward compatibility.
    Maps action types to new functions.
    """
    if action_type in ["SELF_DESTRUCT", "self_destruct"]:
        return authorize_self_destruct(user_id, clearance, session_id)
    elif action_type in ["ABORT_DESTRUCT", "abort_destruct", "CANCEL"]:
        return authorize_cancel_self_destruct(user_id, clearance, session_id)
    else:
        return {"ok": False, "message": f"Unknown action type: {action_type}"}


# --- SELF-REPAIR TOOLS ---

def enter_repair_mode(user_id: str, clearance: int, session_id: str, target_module: str = None) -> dict:
    """
    Enter repair/diagnostic mode for a specific module.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required for repair mode."}
    
    from .repair_agent import get_repair_agent
    from . import repair_tools
    agent = get_repair_agent()
    session = agent.start_session(session_id, user_id, target_module)
    
    msg = f"REPAIR MODE ACTIVATED. "
    if target_module:
        from . import repair_tools
        accessible, reason = repair_tools.is_module_accessible(target_module)
        if accessible:
            msg += f"Target module: {target_module}. Ready for diagnostic commands."
        else:
            msg += f"Warning: {reason}"
    else:
        msg += f"No target module specified. Available modules: {', '.join(repair_tools.MODIFIABLE_MODULES)}"
    
    return {
        "ok": True,
        "in_repair_mode": True,
        "target_module": target_module,
        "message": msg
    }


def exit_repair_mode(session_id: str) -> dict:
    """Exit repair mode."""
    from .repair_agent import get_repair_agent
    agent = get_repair_agent()
    return agent.end_session(session_id)


def read_repair_module(module_name: str, clearance: int) -> dict:
    """
    Read a module's source code in repair mode.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required."}
    
    from . import repair_tools
    return repair_tools.read_module(module_name)


def get_repair_module_outline(module_name: str, clearance: int) -> dict:
    """
    Get structural outline of a module.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required."}
    
    from . import repair_tools
    return repair_tools.get_module_outline(module_name)


def rollback_repair_module(module_name: str, clearance: int, backup_index: int = 0) -> dict:
    """
    Rollback a module to a previous backup.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required."}
    
    from . import repair_tools
    return repair_tools.rollback_module(module_name, backup_index)


def list_repair_backups(module_name: str, clearance: int) -> dict:
    """
    List available backups for a module.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required."}
    
    from . import repair_tools
    return repair_tools.list_backups(module_name)


async def ask_about_code(question: str, user_id: str, clearance: int, session_id: str) -> dict:
    """
    Ask a question about the codebase. The agent will read relevant code and answer.
    Requires Level 10+ for reading, Level 12+ for modifications.
    """
    from .repair_agent import get_repair_agent
    agent = get_repair_agent()
    return await agent.answer_code_question(session_id, user_id, question, clearance)


def is_code_question(message: str) -> bool:
    """Check if a message is asking about code."""
    from .repair_agent import get_repair_agent
    agent = get_repair_agent()
    return agent.is_code_related_question(message)


# --- ACCESS CONTROL TOOLS ---


def lockdown_authority(state: bool, user_id: str, clearance: int, session_id: str) -> dict:
    """
    Toggles global command lockout. Requires Level 12 (Solo) or Level 10+ (Multi-Sig).
    """
    from .permissions import set_command_lockout
    from .auth_system import get_auth_system
    
    if clearance >= 12:
        set_command_lockout(state)
        return {"ok": True, "message": f"COMMAND LOCKOUT {'ACTIVATED' if state else 'DEACTIVATED'}: Override by Level 12 officer."}
        
    if clearance < 10:
        return {"ok": False, "message": "ACCESS DENIED: Minimum Clearance Level 10 required for command lockout modification."}
        
    # Multi-sig for Level 10-11
    auth = get_auth_system()
    action = "LOCKOUT_ON" if state else "LOCKOUT_OFF"
    res = auth.request_action(session_id, action, user_id, clearance, {"state": state})
    
    if res.get("authorized"):
        set_command_lockout(state)
        return {"ok": True, "message": f"COMMAND LOCKOUT {'ACTIVATED' if state else 'DEACTIVATED'}: Multi-signature authorization complete."}
        
    return res

def restrict_user(target_mention: str, duration_minutes: int, user_id: str, clearance: int) -> dict:
    """
    Restricts a user from accessing the computer. Target is identified via @mention (QQ ID).
    Requires Level 8+.
    """
    from .permissions import restrict_access
    
    if clearance < 8:
        return {"ok": False, "message": "ACCESS DENIED: Senior Officer clearance (Level 8) required for access restriction."}
        
    # Extract QQ ID from mention (usually in format like [CQ:at,qq=123456789])
    target_id_match = re.search(r"\d+", target_mention)
    if not target_id_match:
        return {"ok": False, "message": f"Unable to identify target user from: {target_mention}"}
        
    target_id = target_id_match.group(0)
    restrict_access(target_id, duration_minutes)
    
    msg = f"ACCESS RESTRICTION ENFORCED: User {target_id} restricted for {duration_minutes if duration_minutes > 0 else 'infinite'} cycles."
    return {"ok": True, "message": msg, "target_id": target_id}

def lift_user_restriction(target_mention: str, user_id: str, clearance: int) -> dict:
    """
    Lifts an access restriction. Requires Level 8+.
    """
    from .permissions import lift_restriction
    
    if clearance < 8:
        return {"ok": False, "message": "ACCESS DENIED: Senior Officer clearance required to lift restriction."}
        
    target_id_match = re.search(r"\d+", target_mention)
    if not target_id_match:
        return {"ok": False, "message": "Unable to identify target user."}
        
    target_id = target_id_match.group(0)
    lift_restriction(target_id)
    return {"ok": True, "message": f"ACCESS RESTORED: Restriction lifted for user {target_id}."}

def update_user_profile(target_mention: str, field: str, value: str, user_id: str, clearance: int) -> dict:
    """
    Updates a specific field in a user's profile. Requires Level 12.
    Allowed fields: rank, clearance, station, department, is_core_officer.
    """
    from .permissions import update_user_profile_data
    
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Admiralty clearance (Level 12) required for personnel profile modification."}
        
    target_id_match = re.search(r"\d+", target_mention)
    if not target_id_match:
        return {"ok": False, "message": "Unable to identify target user profile."}
        
    target_id = target_id_match.group(0)
    
    # Field Validation
    allowed_fields = ["rank", "clearance", "station", "department", "is_core_officer"]
    if field not in allowed_fields:
        return {"ok": False, "message": f"Invalid profile field: {field}. Allowed: {', '.join(allowed_fields)}"}
        
    # Synchronization logic: If rank is updated, clearance should usually follow (AI handles this via prompt mostly, but we can nudge)
    updates = {field: value}
    
    # Special handling for boolean
    if field == "is_core_officer":
        updates[field] = str(value).lower() == "true"
        
    update_user_profile_data(target_id, updates)
    
    return {
        "ok": True, 
        "message": f"PERSONNEL RECORD UPDATED: User {target_id}, Field: {field}, New Value: {value}. Protocols refreshed.",
        "target_id": target_id
    }

def query_technical_database(query: str) -> dict:
    """
    Queries the Star Trek Technical Knowledge Base (TNG & DS9 Manuals).
    Searches clean text manuals and the unified glossary.
    """
    import os
    
    base_path = "/Users/wanghaozhe/Documents/GitHub/StarTrekBot"
    files_to_search = [
        os.path.join(base_path, "tng_manual_clean.txt"),
        os.path.join(base_path, "ds9_manual_clean.txt"),
        os.path.join("/Users/wanghaozhe/.gemini/antigravity/brain/043b8282-3619-44f4-9467-95077493a8b7", "Star_Trek_Technical_Glossary.md")
    ]
    
    results = []
    query_lower = query.lower()
    
    for fpath in files_to_search:
        if not os.path.exists(fpath):
            continue
        
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Find all occurrences with context
                # Simple implementation: split by lines and find lines containing query
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if query_lower in line.lower():
                        # Get 3 lines of context
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        snippet = "\n".join(lines[start:end])
                        source = os.path.basename(fpath)
                        results.append(f"Source: {source}\n{snippet}\n---")
                        
                        if len(results) >= 5: # Limit results
                            break
                if len(results) >= 5:
                    break
        except Exception as e:
            logger.warning(f"Failed to search {fpath}: {e}")
            
    if not results:
        return {"ok": False, "message": f"Insufficient data found for query: '{query}' in technical database."}
        
    return {
        "ok": True,
        "message": "DATA RETRIEVED FROM TECHNICAL ARCHIVES:\n" + "\n".join(results),
        "title": "TECHNICAL DATABASE QUERY RESULT",
        "sections": [{"category": "Search Results", "content": "\n".join(results)}]
    }

def get_personnel_file(target_mention: str, user_id: str, is_chinese: bool = False) -> dict:
    """
    Retrieves and visualizes a personnel file card.
    """
    from .permissions import get_user_profile
    from .quota_manager import get_quota_manager
    from . import visual_core
    from PIL import Image
    import httpx
    import io
    
    # 1. Resolve Target ID
    target_id = str(user_id) # Default to self
    nickname = None
    
    if target_mention:
        # Extract ID from mention [CQ:at,qq=12345] or just text
        match = re.search(r"\d+", target_mention)
        if match:
            target_id = match.group(0)
    
    # 2. Get Profile Data
    limit_break = (target_id == "2819163610")
    profile = get_user_profile(target_id)
    
    # 3. Get Quota Balance
    qm = get_quota_manager()
    # Rank needed for quota lookup, extract from profile
    rank = profile.get("rank", "Ensign")
    balance = qm.get_balance(target_id, rank)
    
    # 4. Prepare Data for Visual Core
    data = {
        "name": profile.get("name", "Unknown"),
        "rank": profile.get("rank", "Ensign"),
        "department": profile.get("department", "OPERATIONS"),
        "clearance": profile.get("clearance", 1),
        "station": profile.get("station", "General Duty"),
        "is_core_officer": profile.get("is_core_officer", False),
        "user_id": target_id,
        "quota_balance": balance,
        "biography": profile.get("biography", ""),
        "restricted": False, # TODO: check restricted status
        "avatar": None
    }
    
    # 5. Fetch Avatar (OneBot/QQ style)
    try:
        avatar_url = f"http://q.qlogo.cn/headimg_dl?dst_uin={target_id}&spec=640"
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(avatar_url)
            if resp.status_code == 200:
                avatar_bytes = io.BytesIO(resp.content)
                data["avatar"] = Image.open(avatar_bytes).convert("RGBA")
    except Exception as ae:
        logger.warning(f"Failed to fetch avatar for {target_id}: {ae}")

    # 6. Render Image
    try:
        img_io = visual_core.render_personnel_file(data, is_chinese=is_chinese)
        return {
            "ok": True,
            "message": f"正在显示人员档案: {target_id}",
            "image_io": img_io
        }
    except Exception as e:
        return {
            "ok": False,
            "message": f"视觉渲染失败: {e}"
        }
def update_biography(content: str, user_id: str) -> dict:
    """
    Updates the biography field in the user's personal profile.
    """
    from .permissions import update_user_profile_data
    
    update_user_profile_data(user_id, {"biography": content})
    
    return {
        "ok": True,
        "message": "COMMAND SUCCESSFUL: Personal biography updated in Starfleet Database."
    }
def update_protocol(category: str, key: str, value: str, user_id: str, clearance: int = 1, action: str = "set") -> dict:
    """
    Updates a system protocol or prompt. Requires Level 10+ clearance.
    Actions: 'set' (overwrite), 'append' (add to existing), 'remove' (delete from existing).
    """
    if clearance < 10:
        return {"ok": False, "message": "Access denied. Level 10 clearance required for protocol modification."}
    
    from .protocol_manager import get_protocol_manager
    pm = get_protocol_manager()
    success = pm.update_protocol(category, key, value, action=action)
    
    action_verb = {"set": "set", "append": "appended to", "remove": "removed from"}.get(action, "updated")
    
    if success:
        return {
            "ok": True,
            "message": f"Protocol {action_verb}: {category}.{key}. Federation Standards updated.",
            "result": "ACK"
        }
    else:
        return {"ok": False, "message": "Failed to update protocol. System file write error."}
# --- SHIP SYSTEMS & CONTROL TOOLS (1.8 Protocol) ---

def set_alert_status(level: str, clearance: int) -> dict:
    """
    Sets the ship's alert status (RED, YELLOW, NORMAL).
    Requires Level 8+.
    """
    if clearance < 8:
        return {"ok": False, "message": "权限不足拒绝访问"}
        
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    msg = ss.set_alert(level)
    return {"ok": True, "message": msg, "level": ss.alert_status.value}

def toggle_shields(active: bool, clearance: int) -> dict:
    """
    Toggles the ship's shields.
    Requires Level 8+.
    """
    if clearance < 8:
        return {"ok": False, "message": "权限不足拒绝访问"}
        
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    msg = ss.toggle_shields(active)
    return {"ok": True, "message": msg, "active": ss.shields_active}

def set_subsystem_state(name: str, state_str: str, clearance: int) -> dict:
    """
    Toggles a subsystem (online/offline).
    Requires Level 11+.
    """
    if clearance < 11:
        return {"ok": False, "message": "权限不足拒绝访问"}
        
    from .ship_systems import get_ship_systems, SubsystemState
    ss = get_ship_systems()
    state = SubsystemState.ONLINE if "online" in state_str.lower() or "上线" in state_str else SubsystemState.OFFLINE
    msg = ss.set_subsystem(name, state)
    return {"ok": True, "message": msg}

def set_absolute_override(state: bool, user_id: str, clearance: int) -> dict:
    """
    Toggles Absolute Command Override (Z-flag).
    Requires Level 11+.
    """
    from .permissions import set_command_override, USER_PROFILES
    
    # Check if user is owner or Level 11+
    is_owner = (user_id == "2819163610" or user_id == "1993596624")
    if not is_owner and clearance < 11:
        return {"ok": False, "message": "权限不足拒绝访问"}
        
    set_command_override(state)
    msg = "确认，指挥权覆盖已激活。计算机现在仅响应授权命令。" if state else "确认，指挥权覆盖已解除。"
    return {"ok": True, "message": msg}

async def locate_user(target_mention: str, clearance: int) -> dict:
    """
    Mock Geolocation for 1.8 (Simulating the IP API).
    """
    if clearance < 11:
        return {"ok": False, "message": "权限不足拒绝访问"}
    
    target_id_match = re.search(r"\d+", target_mention)
    if not target_id_match:
        return {"ok": False, "message": "无法识别目标。"}
    
    target_id = target_id_match.group(0)
    # 1.8 Mock logic: "Accessing Starfleet tracking... User located at Sector 001."
    return {
        "ok": True, 
        "message": f"正在定位用户：{target_id}…\n[信号追踪中…]\n定位成功：用户当前位于 001 扇区，地球空间站。"
    }
