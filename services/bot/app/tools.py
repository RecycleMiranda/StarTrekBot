import time
import datetime
import ast
import operator
import logging

logger = logging.getLogger(__name__)

def get_status() -> dict:
    """
    Returns mock starship status.
    """
    return {
        "shields_percent": 92,
        "warp_factor": 0.0,
        "alert": "green",
        "power_status": "nominal",
        "ts": int(time.time()),
        "tz": "CST"
    }

def get_time() -> dict:
    """
    Returns current system time.
    """
    now = datetime.datetime.now()
    return {
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
    Replicates an item using replicator credits with ALAS clearance check.
    """
    from .quota_manager import get_quota_manager
    qm = get_quota_manager()
    
    item_lower = item_name.lower()
    cost = 10 # Default
    required_clearance = 1
    
    # Clearance & Cost Logic
    if any(k in item_lower for k in ["tea", "coffee", "water", "juice"]): 
        cost = 5
        required_clearance = 1
    elif any(k in item_lower for k in ["steak", "pasta", "meal", "soup"]): 
        cost = 15
        required_clearance = 2
    elif any(k in item_lower for k in ["padd", "tool", "spare", "component"]): 
        cost = 25
        required_clearance = 5 # Standard Officer
    elif any(k in item_lower for k in ["phaser", "weapon", "explosive", "hazardous", "rifles"]): 
        cost = 150
        required_clearance = 8 # Senior Officer / Command
    elif any(k in item_lower for k in ["torpedo", "detonator", "cloak"]):
        cost = 500
        required_clearance = 11 # Admiralty/Section 31
    elif any(k in item_lower for k in ["diamond", "gold", "luxury"]): 
        cost = 500
        required_clearance = 4
        
    # Check Clearance
    if clearance < required_clearance:
        return {
            "ok": False,
            "message": f"Access denied. Replication of {item_name} requires Clearance Level {required_clearance}. Current level: {clearance}.",
            "cost": 0,
            "remaining": qm.get_balance(user_id, rank)
        }
    
    if qm.spend_credits(user_id, cost):
        return {
            "ok": True,
            "message": f"Replication successful: {item_name}.",
            "cost": cost,
            "remaining": qm.get_balance(user_id, rank)
        }
    else:
        return {
            "ok": False,
            "message": "Insufficient replicator credits.",
            "cost": cost,
            "remaining": qm.get_balance(user_id, rank)
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

def get_historical_archive(topic: str) -> dict:
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

def initiate_self_destruct(seconds: int, silent: bool, user_id: str, clearance: int, session_id: str) -> dict:
    """
    Initiates the self-destruct sequence. Requires either Level 12 or 3x Level 8 signatures.
    """
    from .auth_system import get_auth_system
    auth = get_auth_system()
    
    metadata = {"duration": seconds, "silent": silent}
    res = auth.request_action(session_id, "SELF_DESTRUCT", user_id, clearance, metadata)
    
    if res.get("authorized"):
        # We need to trigger this via dispatcher/manager
        return {"ok": True, "authorized": True, "metadata": metadata, "message": f"CRITICAL: Self-destruct sequence authorized for {seconds} seconds."}
    
    return res

def authorize_sequence(action_type: str, user_id: str, clearance: int, session_id: str) -> dict:
    """
    Adds a signature to a pending authorization sequence.
    """
    from .auth_system import get_auth_system
    auth = get_auth_system()
    
    return auth.vouch_for_action(session_id, action_type, user_id, clearance)

def abort_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """
    Aborts an active self-destruct sequence.
    """
    # Requires Level 8+ to even try, Level 12 to solo abort
    from .auth_system import get_auth_system
    from .self_destruct import get_destruct_manager
    
    auth = get_auth_system()
    dm = get_destruct_manager()
    
    # Abort also requires Level 12 solo or Level 8+ multi-sig auth if we want to be strict,
    # but for simplicity let's allow Level 12 solo or Level 8+ current sequence request.
    if clearance >= 12:
        asyncio.create_task(dm.abort_sequence(session_id))
        return {"ok": True, "message": "SELF-DESTRUCT ABORTED: Command override by Level 12 officer."}
    
    if clearance < 8:
        return {"ok": False, "message": "ACCESS DENIED: Insufficient clearance to abort self-destruct."}
        
    # Kick off an 'ABORT' auth sequence? No, let's keep it simple: 
    # Just allow Level 8+ to cancel it for now as per user request (cancel also needs多人授权? 
    # User said: "如果一个人的权限是十二级，那么他就可以一个人启动自毁，或者取消自毁，而如果没有的话，那就需要多人授权... 取消也是")
    
    # Let's use the same auth system for the ABORT action too
    res = auth.request_action(session_id, "ABORT_DESTRUCT", user_id, clearance, {})
    if res.get("authorized"):
        asyncio.create_task(dm.abort_sequence(session_id))
        return {"ok": True, "message": "SELF-DESTRUCT ABORTED: Multi-signature authorization complete."}
    
    return res

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
