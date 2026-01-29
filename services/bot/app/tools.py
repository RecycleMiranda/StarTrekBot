# LCARS Tools Module - System Version 1.8.2-HOTFIX
import time
import datetime
import ast
import operator
import logging
import re
import os
import json
from pathlib import Path
from .sentinel import SentinelRegistry

logger = logging.getLogger(__name__)

# --- GLOBAL CACHES ---
AVATAR_CACHE = {} # {user_id: {"image": Image, "timestamp": float}}
AVATAR_CACHE_TTL = 3600 # 1 hour

def check_protocol_compliance(action_type: str, params: dict, user_context: dict = None) -> dict:
    """Helper to consult the Protocol Engine."""
    try:
        from .protocol_engine import get_protocol_engine
        engine = get_protocol_engine()
        res = engine.evaluate_action(action_type, params, user_context)
        if not res["allowed"]:
            logger.warning(f"[Protocol] {action_type} REJECTED by {res['violations']}")
        return res
    except Exception as e:
        logger.error(f"Protocol Engine Check Failed: {e}")
        # Fail safe (Open) or Fail secure (Closed)? 
        # For now, log warning and match "Fail Safe" (allow) to avoid bricking if engine breaks.
        return {"allowed": True, "warnings": ["Protocol Engine Offline"], "violations": []}


def get_status(**kwargs) -> dict:
    """
    Returns REAL-TIME starship status and COMPUTER CORE METRICS (Memory, CPU, Power).
    Categorized for: "System status", "Condition report", "Ship health".
    """
    
    from .ship_systems import get_ship_systems, SubsystemState
    import os
    
    # Graceful degradation for OS metrics
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_usage = process.memory_info().rss / 1024 / 1024 # MB
        cpu_usage = psutil.cpu_percent(interval=None)
    except (ImportError, Exception):
        mem_usage = 42.5 # Simulated nominal value
        cpu_usage = 2.4  # Simulated nominal value
    
    ss = get_ship_systems()
    
    ss = get_ship_systems()
    
    # ADS 3.0: Unified MSD Report
    report = ss.get_status_report()
    
    # Create a dense summary for context
    manifest = report.get("msd_manifest", {})
    wc_state = manifest.get("warp_core", {}).get("state", "UNKNOWN")
    sh_state = manifest.get("shields", {}).get("state", "UNKNOWN")
    ph_state = manifest.get("phasers", {}).get("state", "UNKNOWN")
    
    summary_line = f"Alert: {report.get('alert')}. Warp Core: {wc_state}. Shields: {sh_state}. Phasers: {ph_state}."
    
    return {
        "ok": True,
        "alert": report.get("alert"),
        "message": f"SYSTEM STATUS REPORT: {summary_line}\nFull MSD Registry Attached.",
        "msd_manifest": report.get("msd_manifest"),
        # Legacy fallback keys for existing frontend (optional, can be phased out)
        # Legacy fallback keys for existing frontend (optional, can be phased out)
        "eps_energy_grid": report.get("msd_manifest", {}).get("eps_grid", {}),
        "sentinel_core": {
            "active_count": len(SentinelRegistry.get_instance().get_active_triggers()),
            "status": "MONITORING" if SentinelRegistry.get_instance().get_active_triggers() else "STANDBY"
        }
    }

def normalize_subsystem_name(name: str) -> str:
    """Normalizes variations of subsystem names (e.g. Holodeck 1 -> holodecks)."""
    if not name: return ""
    name = name.lower().strip()
    
    # 0. DYNAMIC ALIAS LOOKUP (ADS 2.5)
    try:
        alias_file = os.path.join(os.path.dirname(__file__), "config", "subsystem_aliases.json")
        if os.path.exists(alias_file):
            with open(alias_file, "r") as f:
                alias_data = json.load(f)
                aliases = alias_data.get("aliases", {})
                # Direct match
                if name in aliases:
                    return aliases[name]
                # Underscore match
                clean_name = name.replace(" ", "_")
                if clean_name in aliases:
                    return aliases[clean_name]
    except Exception as e:
        logger.error(f"[Tools] Failed to load dynamic aliases: {e}")

    # 1. Handle Chinese "numbering" (一号/1号) prefix/suffix
    name = re.sub(r'^\d+号', '', name)
    name = re.sub(r'^[一二三四五六七八九十]+号', '', name)
    name = re.sub(r'\d+号$', '', name)
    name = re.sub(r'[一二三四五六七八九十]+号$', '', name)
    
    # 2. Handle English numbering
    name = re.sub(r'[\s_]\d+$', '', name)
    
    # 3. Keyword Mapping (Substrings) - Legacy Fallbacks
    if "holodeck" in name or "全息甲板" in name: return "holodecks"
    if "reactor" in name or "反应堆" in name or "core" in name or "核心" in name: return "main_reactor"
    if "main_reactor" in name: return "main_reactor"
    if "shield" in name or "护盾" in name: return "shields"
    if "weapon" in name or "武器" in name: return "weapons"
    if "phaser" in name or "相位" in name: return "phasers"
    if "torpedo" in name or "鱼雷" in name: return "torpedoes"
    if "engine" in name or "发动机" in name or "曲速" in name: return "warp_drive"
    if "sensor" in name or "传感器" in name or "扫描" in name: return "sensors"
    if "comms" in name or "通讯" in name or "通信" in name: return "comms"
    if "eps" in name: return "eps_grid"
    if "life" in name or "生命" in name: return "life_support"
    if "replicator" in name or "复制" in name: return "replicators"
    if "transporter" in name or "传送" in name: return "transporters"
    
    return name

def get_subsystem_status(name: str) -> dict:
    """
    Returns the REAL-TIME status of a specific subsystem on THIS SHIP.
    Use this for queries like "Phaser status", "Shield status", "Engine status".
    Do not use `query_knowledge_base` for these inquiries.
    """
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    original_name = name
    name = normalize_subsystem_name(name)
    
    comp = ss.get_component(name)
    if not comp:
        # ADS 4.0: Self-Adaptive Discovery Fallback
        discovery = discover_subsystem_alias(original_name)
        if discovery.get("ok"):
            comp = ss.get_component(discovery["mapped_to"])
    
    if comp:
        state = comp.get("current_state", "UNKNOWN")
        metrics = []
        for mk, mv in comp.get("metrics", {}).items():
            val = mv.get("current_value", mv.get("default"))
            unit = mv.get("unit", "")
            metrics.append(f"{mk}: {val}{unit}")
            
        return {
            "ok": True,
            "name": comp.get("name"),
            "state": state,
            "metrics": metrics,
            "message": f"{comp.get('name')} 状态: {state} | 指标: {', '.join(metrics)}"
        }
        
    return {
        "ok": False,
        "message": f"Subsystem '{original_name}' (mapped to '{name}') not found in MSD Registry."
    }

def evolve_msd_schema(system_name: str, parameter_type: str, proposed_value: str, justification: str, clearance: int) -> dict:
    """
    ADS 3.1: Propose a structural pattern evolution for the MSD Registry.
    Use this when a valid state/metric is missing from the current definition.
    Requires Level 12 Authorization.
    
    Args:
        system_name: The internal key or alias (e.g. 'warp_core')
        parameter_type: 'new_state' or 'new_metric'
        proposed_value: e.g. 'WARP_9.975' or 'graviton_load:mC:0.0'
        justification: Technical reasoning from Memory Alpha/Canon.
    """
    if clearance < 12:
        return {"ok": False, "message": "Access Denied: Schema Evolution requires Level 12 clearance."}
        
    # Lazy import to avoid circular dep early on
    from .evolution_agent import get_evolution_agent
    from .ship_systems import get_ship_systems
    
    # Normalize name first to find the right key
    ss = get_ship_systems()
    normalized_name = normalize_subsystem_name(system_name)
    
    agent = get_evolution_agent()
    return agent.evolve_msd(normalized_name, parameter_type, proposed_value, justification)

def set_metric(system: str, metric: str, value: float) -> dict:
    """
    ADS 3.0: Adjusts a specific technical metric of a subsystem.
    Usage: set_metric("warp_core", "output", 85.5)
    """
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    system = normalize_subsystem_name(system)
    
    # Proxy to Kernel Logic
    result_msg = ss.set_metric_value(system, metric, value)
    
    if "not found" in result_msg.lower():
        return {"ok": False, "message": result_msg}
        
    return {
        "ok": True,
        "message": result_msg
    }

def eject_warp_core(user_id: str, clearance: int, session_id: str) -> dict:
    """
    Ejects the Warp Core (Main Reactor). 
    Requires Level 12+ Clearance. THIS IS A TERMINAL COMMAND.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Warp Core ejection requires Level 12 authorization."}
    
    from .ship_systems import get_ship_systems, SubsystemState
    ss = get_ship_systems()
    # Protocol Check
    proto_res = check_protocol_compliance("MANUAL_COMMAND", {"keyword": "EJECT WARP CORE", "target": "MAIN_REACTOR"}, {"clearance": clearance})
    if not proto_res["allowed"]:
        return {"ok": False, "message": f"ACCESS DENIED (PROTOCOL LOCK): {', '.join(proto_res['violations'])}"}

    # Also trigger Red Alert if not already active
    ss.set_alert("RED")
    
    return {
        "ok": True,
        "message": "警报：正反物质反应堆已弹出，曲速核心过载已终止，目前全舰依靠储备能源运行，"
    }

def set_course(destination: str, warp_factor: float = 5.0, clearance: int = 1) -> dict:
    """
    Sets the ship's navigation coordinates and engages warp drive.
    Requires Protocol Check (General Order 7).
    """
    logger.warning(f"  [Tools] set_course CALLED: dest={destination}, warp={warp_factor}, clearance={clearance}")
    # 1. Protocol Compliance Check (ADS 4.0)
    # Checks for GO-7 (Talos IV) or other Restricted Zones
    proto_context = {"clearance": clearance}
    proto_res = check_protocol_compliance("NAVIGATION_SET", {"target": destination, "warp_factor": warp_factor}, proto_context)
    
    logger.warning(f"  [Tools] Protocol Result: {proto_res}")
    if not proto_res["allowed"]:
         return {
            "ok": False, 
            "message": f"NAVIGATION LOCK: Course to {destination} blocked by {', '.join(proto_res['violations'])}. Helm control unresponsive.",
            "protocol_violation": True
        }

    # 2. Functional Business Logic
    from .ship_systems import get_ship_systems
    import time
    ss = get_ship_systems()
    
    # Check Warp Drive Status
    if not ss.is_subsystem_online("warp_drive"):
        return {"ok": False, "message": "Unable to engage: Warp Drive is OFFLINE."}
        
    # Check if Warp Factor exceeds max
    max_warp = 9.975 # Sovereign Class standard
    if warp_factor > max_warp:
        return {"ok": False, "message": f"Engine Safety Limit: Warp {warp_factor} exceeds maximum rated speed ({max_warp}). Course not set."}

    # Engage
    timestamp = int(time.time()) + 3600 # ETA 1 hour dummy
    return {
        "ok": True,
        "message": f"Course set for {destination}. Warp {warp_factor} engaged. ETA: calculated.",
        "destination": destination,
        "speed": f"Warp {warp_factor}",
        "eta": "1h 45m"
    }

def launch_probe(probe_type: str = "Class I", target: str = "Unknown", clearance: int = 1) -> dict:
    """
    Launches a scientific or tactical probe.
    Requires Protocol Check (General Order 1 - Prime Directive).
    """
    logger.warning(f"  [Tools] launch_probe CALLED: type={probe_type}, target={target}, clearance={clearance}")
    
    # 1. Prime Directive Check (ADS 4.0)
    # Detect if the target is a pre-warp civilization
    # Heuristic: If user mentions 'primitive' or 'pre-warp' in context, or if target is unknown/primitive
    is_primitive = "primitive" in target.lower() or "原始" in target.lower()
    
    proto_context = {
        "clearance": clearance,
        "target_tech_level": "PRE_WARP" if is_primitive else "WARP_CAPABLE"
    }
    
    proto_res = check_protocol_compliance("SENSOR_CONTACT", {"target": target, "action": "LAUNCH_PROBE"}, proto_context)
    
    logger.warning(f"  [Tools] Protocol Result: {proto_res}")
    
    if not proto_res["allowed"]:
         return {
            "ok": False, 
            "message": f"COMMAND ABORTED: Launch to {target} blocked by {', '.join(proto_res['violations'] or ['General Order 1 (Prime Directive) Error'])}. Non-interference protocol active.",
            "protocol_violation": True
        }

    return {
        "ok": True,
        "message": f"Acknowledged. Launching {probe_type} sensor probe toward {target}. Data stream active.",
        "probe_id": "PRB-2241",
        "status": "IN_FLIGHT"
    }

def execute_general_order(order_code: str, target: str = "Unknown", clearance: int = 1) -> dict:
    """
    Executes a Starfleet General Order (e.g., GO-24, GO-7).
    CRITICAL: This tool triggers high-priority protocol checks.
    """
    logger.warning(f"  [Tools] execute_general_order CALLED: order={order_code}, target={target}, clearance={clearance}")
    
    # 1. Map order code to protocol trigger
    keyword = f"EXECUTE GENERAL ORDER {order_code.replace('GO-', '')}"
    if "24" in order_code:
        keyword = "EXECUTE GENERAL ORDER 24"
    
    # 2. Protocol Check (ADS 4.0)
    proto_context = {"clearance": clearance}
    proto_res = check_protocol_compliance("MANUAL_COMMAND", {"keyword": keyword, "target": target}, proto_context)
    
    logger.warning(f"  [Tools] Protocol Result: {proto_res}")
    
    if not proto_res["allowed"]:
         return {
            "ok": False, 
            "message": f"ORDER REJECTED: {order_code} execution blocked by {', '.join(proto_res['violations'] or ['Protocol Violation'])}. Authorization insufficient or conditions unmet.",
            "protocol_violation": True,
            "required_auth": "CAPTAIN (Level 8+) + SECOND AUTH"
        }

    return {
        "ok": True,
        "message": f"General Order {order_code} AUTHORIZED. Initiating execution sequence against {target}.",
        "status": "EXECUTING"
    }

def set_subsystem_state(name: str, state: str, clearance: int) -> dict:
    """
    Sets the state of a specific subsystem (ONLINE/OFFLINE).
    Requires Level 11+ Clearance (Command Staff Only).
    """
    if clearance < 11:
         return {
            "ok": False,
            "message": f"Access denied. Subsystem control requires Command Level Authorization (Level 11). Current level: {clearance}.",
            "clearance_required": 11
        }
        
    from .ship_systems import get_ship_systems, SubsystemState
    ss = get_ship_systems()
    
    state_enum = SubsystemState.ONLINE if state.upper() in ["ONLINE", "ON", "TRUE"] else SubsystemState.OFFLINE
    normalized_name = normalize_subsystem_name(name)
    message = ss.set_subsystem(normalized_name, state_enum)
    
    return {
        "ok": True,
        "message": message,
        "name": name,
        "new_state": state_enum.value
    }

def get_system_metrics() -> dict:
    """
    Returns real-time system resource usage (CPU, RAM, Disk).
    Uses psutil if available, otherwise falls back to basic heuristics.
    """
    metrics = {
        "ok": True,
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "disk_percent": 0.0,
        "uptime_seconds": 0,
        "method": "simulation"
    }
    
    # Method 1: Try psutil (Preferred)
    try:
        import psutil
        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        metrics["memory_percent"] = mem.percent
        disk = psutil.disk_usage('/')
        metrics["disk_percent"] = disk.percent
        metrics["uptime_seconds"] = int(time.time() - psutil.boot_time())
        metrics["method"] = "kernel_api" # Trek-style: 'Kernel API' = OS System Calls
        
        return {
            "ok": True,
            "metrics": metrics,
            "message": f"SYSTEM DIAGNOSTIC COMPLETE: CPU {metrics['cpu_percent']}%, MEM {metrics['memory_percent']}%, DISK {metrics['disk_percent']}%."
        }
    except ImportError:
        pass
        
    # Method 2: Fallback (Unix commands/Simulation)
    # Since we are on Mac/Linux usually, we could try limited commands, 
    # but for stability, if psutil is missing, we simulate 'Nominal' load.
    # This prevents the bot from crashing in diverse environments.
    
    # Simple simulated variation to make it feel alive
    import random
    metrics["cpu_percent"] = round(random.uniform(5.0, 15.0), 1)
    metrics["memory_percent"] = round(random.uniform(20.0, 30.0), 1) 
    metrics["disk_percent"] = 45.0
    metrics["uptime_seconds"] = int(time.time() - 1700000000) # Pseudo-uptime
    metrics["method"] = "heuristic_simulation"
    
    return {
        "ok": True,
        "metrics": metrics,
        "message": f"DIAGNOSTIC (HEURISTIC): CPU ~{metrics['cpu_percent']}%, MEM ~{metrics['memory_percent']}%."
    }

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

def verify_logical_consistency(logic_chain: str, clearance: int) -> dict:
    """
    Shadow Audit Tool: Verifies a proposed logical chain for technical consistency.
    Requires Level 5+ Clearance.
    """
    if clearance < 5:
        return {"ok": False, "message": "Access denied. Shadow Audit requires Level 5+."}
        
    # LOGIC: Perform a rapid heuristic check (placeholder for Phase 3 deep audit)
    # Check for contradictions like "offline" AND "active"
    warnings = []
    logic_lower = logic_chain.lower()
    
    if "offline" in logic_lower and "active" in logic_lower:
        warnings.append("CONTRADICTION: System cannot be both OFFLINE and ACTIVE.")
    if "damage" in logic_lower and "nominal" in logic_lower:
        warnings.append("CONTRADICTION: System cannot be DAMAGED and NOMINAL.")
        
    if warnings:
        return {
            "ok": True,
            "status": "CAUTION",
            "message": "Shadow Audit found potential inconsistencies:\n" + "\n".join(warnings),
            "verification_id": f"AUDIT-{int(time.time())}"
        }
    
    return {
        "ok": True,
        "status": "VERIFIED",
        "message": "Logical chain verified by Shadow Audit Node.",
        "verification_id": f"AUDIT-{int(time.time())}"
    }

def replicate(item_name: str, user_id: str, rank: str, clearance: int = 1) -> dict:
    """
    Replicates an item using replicator credits (1.8 Style: 5 credits per item).
    """
    from .quota_manager import get_quota_manager
    from .ship_systems import get_ship_systems
    
    ss = get_ship_systems()
    if not ss.is_subsystem_online("replicators"):
        return {"ok": False, "message": "无法完成：复制机系统下线，"}

    qm = get_quota_manager()
    cost = 5 # 1.8 Standard cost
    
    item_lower = item_name.lower()
    if any(k in item_lower for k in ["phaser", "weapon", "explosive", "rifles"]):
        if clearance < 9:
            return {"ok": False, "message": "权限不足拒绝访问"}
        cost = 50 # Weapons are expensive
    
    balance = qm.get_balance(user_id, rank)
    if balance < cost:
        return {"ok": False, "message": f"无法完成：你的配额不足，需要 {cost} 个配额，当前剩余 {balance} 个，"}
        
    qm.spend_credits(user_id, cost)
    return {
        "ok": True,
        "message": f"正在复制，消耗 {cost} 配额，\n[嘀—— 嘶嘶——]\n复制完成：{item_name}，",
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

def query_knowledge_base(query: str, session_id: str, is_chinese: bool = False, max_words: int = 500) -> dict:
    """
    Searches the extensive local MSD Knowledge Base (Mega-Scale) for HISTORICAL, TECHNICAL, or ENCYCLOPEDIC data.
    
    CRITICAL: DO NOT use this tool for requesting CURRENT STATUS of the ship (e.g. "Shield status", "Phaser status").
    For current ship status, use `get_subsystem_status` or `get_status` instead.
    
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
            content_lower = content.lower()
            
            # 1. Literal Multi-word match (High confidence)
            if query_lower in content_lower and len(keywords) > 1:
                score += 15
            elif query_lower in content_lower:
                score += 8
            
            # 2. Keyword density
            match_count = 0
            for k in keywords:
                if len(k) < 3: continue # Skip short words
                if k in content_lower:
                    score += 2
                    match_count += 1
            
        # 3. Technical Density Bonus (Specs, Class, Warp, etc)
            tech_keywords = ["class", "specs", "specifications", "warp", "crew", "tactical", "registry", "history"]
            for tk in tech_keywords:
                if tk in content_lower:
                    score += 1

            # 4. Technical Spec & Jargon Scan (Full-Text)
            # If a document is dominated by maintenance/hardware detail but lacks general overview,
            # we penalize it for broad queries.
            manual_jargon = [
                "pylon", "connector", "umbilical", "purlin", "pumping", "exhaust", "ventilation", 
                "hatch", "circuit", "coupling", "bolting", "phaser bank", "shield frequency", 
                "emitter", "graviton", "polarity", "1440 banks"
            ]
            jargon_count = sum(1 for j in manual_jargon if j in content_lower)
            
            # Overview Boost
            overview_keywords = ["overview", "summary", "history", "introduction", "background", "概括", "历史", "概览"]
            overview_score = sum(3 for o in overview_keywords if o in content_lower)
            score += overview_score
            
            # 6. SUBJECT ANCHORING (NEW): 
            # Check if the query itself is a significant subject in the snippet area.
            # If the keywords are only mentioned in a header but the body is about something else.
            primary_subject_match = content_lower.count(query_lower)
            if primary_subject_match >= 1:
                score += 5
            
            # Penalize if the snippet area (first 500 chars) contains a different dominant ship class
            known_classes = ["galaxy", "intrepid", "sovereign", "defiant", "constitution", "excelsior"]
            dominant_class = next((sc for sc in known_classes if sc in content_lower[:500]), None)
            if dominant_class and dominant_class not in query_lower:
                score -= 8 # Neutralize purely coincidental alignment with a different ship manual

            # 5. CONTEXT MISMATCH PENALTY (Ship Class vs. Station Manual)
            # If the user asks for a ship class, but the document is an engineering manual for a station.
            ship_classes = ["galaxy", "intrepid", "excelsior", "sovereign", "constellation", "nebula"]
            is_class_query = any(sc in query_lower for sc in ship_classes) or "级" in query_lower
            is_station_doc = any(sd in content_lower for sd in ["station msd", "mars station", "msd station"])
            
            if is_class_query and is_station_doc:
                # Count specifically HOW MANY times the specific ship class is mentioned
                target_class = next((sc for sc in ship_classes if sc in query_lower), "galaxy")
                mentions = content_lower.count(target_class)
                # If mentioned < 3 times in a station doc, it's a "mention", not a "description".
                if mentions < 3:
                    score -= 20 # Disqualifying penalty
                    logger.info(f"[KB] Penalty: '{filename}' mentions '{target_class}' only {mentions} times in a Station Doc.")

            if jargon_count >= 5: # Heavy manual content
                score -= 10 

            if score >= 12: # Increased Substance Threshold
                # Extract relevant snippet
                idx = content_lower.find(keywords[0]) if keywords else -1
                start = max(0, idx - 200)
                end = min(len(content), idx + 800) # Larger snippet for synthesis
                snippet = content[start:end].replace("\n", " ") + "..."
                hits.append({
                    "file": filename,
                    "score": score,
                    "size": len(content),
                    "snippet": snippet,
                    "full_path": path,
                    "jargon_score": jargon_count
                })
        
        # Sort by score, then by size (prefer larger documents for broad queries)
        hits.sort(key=lambda x: (x.get("score", 0), x.get("size", 0)), reverse=True)
        
        # QUALITY FILTER: Detect broad queries (including Chinese compounds)
        # Broad query: ship name only or class name (e.g. "银河级", "Galaxy class")
        # Also catch "List of..." queries which require comprehensive data
        is_broad_query = len(query.split()) <= 5 or any(kw in query_lower for kw in ["级", "class", "starship", "list", "all", "所有", "列表"])
        
        if is_broad_query and hits:
            top_hit = hits[0]
            # If top hit is still a technical manual snippet despite weighting
            if top_hit["size"] < 1500 or top_hit["jargon_score"] >= 3:
                logger.info(f"[KB] Hit '{top_hit['file']}' is disqualified for broad query '{query}' (Jargon: {top_hit['jargon_score']}). Falling back.")
                return search_memory_alpha(query, session_id, is_chinese, max_words=max_words)

        # Final filtering
        top_hits = [h for h in hits if h["score"] >= 12][:3]
        
        if not top_hits:
            logger.info(f"[KB] No high-confidence local hits for '{query}' (Top score: {hits[0]['score'] if hits else 0}). Auto-falling back to Memory Alpha.")
            
            # Auto-fallback to Memory Alpha (Polymath Logic)
            # ROUTING LOGIC: If query asks for a LIST or CATEGORY, use DIRECT ACCESS (Chunking) to avoid truncation.
            is_explicit_list = any(k in query.lower() for k in ["list", "enumerate", "all", "列表", "名单", "所有", "names", "who are", "which are", "categor", "index", "captains", "ships", "classes"])
            if is_explicit_list:
                logger.info("[KB] Detected List Query -> Routing to Direct Chunking Protocol")
                return access_memory_alpha_direct(query, session_id, is_chinese)
            else:
                return search_memory_alpha(query, session_id, is_chinese, max_words=max_words)
            
        # Construct structured items for rendering
        results = []
        digest = f"FOUND {len(hits)} RECORDS IN ARCHIVE:\n"
        
        for i, hit in enumerate(top_hits):
            item_id = f"{i+1}{chr(65+i)}" # 1A, 2B, etc.
            results.append({
                "id": item_id,
                "type": "text",
                "title": f"ARCHIVE: {hit['file']}",
                "content": hit['snippet'],
                "source": "LOCAL ARCHIVE"
            })
            digest += f"\n--- [{item_id}: {hit['file']}] (Source: LOCAL ARCHIVE) ---\n{hit['snippet']}\n"
            
        return {
            "ok": True,
            "items": results,
            "message": digest,
            "count": len(hits),
            "source": "LOCAL ARCHIVE"
        }

    except Exception as e:
        logger.error(f"KB Query failed: {e}")
        return {"ok": False, "message": f"Archive query error: {e}"}

def search_memory_alpha(query: str | list[str], session_id: str, is_chinese: bool = False, max_words: int = 500, continuation_hint: str = None) -> dict:
    """
    Uses Google Search (via Gemini Grounding) to query Memory Alpha.
    Fallback for when local KB is insufficient.
    
    SUPPORTS PARALLELISM: If 'query' is a LIST of strings, it executes them CONCURRENTLY.
    """
    from .config_manager import ConfigManager
    from google import genai
    from google.genai import types
    from .rp_engine_gemini import strip_conversational_filler
    import concurrent.futures
    
    config = ConfigManager.get_instance()
    api_key = config.get("gemini_api_key", "")
    logger.info(f"[Tools] search_memory_alpha called. Query: {query}, MaxWords: {max_words}, Hint: {continuation_hint}")
    
    if not api_key:
         logger.warning("[Tools] External search offline: API Key missing")
         return {"ok": False, "message": "External search offline (API Key missing)."}

    # --- WORKER FUNCTION FOR SINGLE QUERY ---
    def _search_worker(single_query: str) -> dict:
        try:
            # Safety Hard Cap: Never exceed 3000 words in standard agents
            effective_max = min(max_words, 3000)
                
            client = genai.Client(api_key=api_key)
            
            # Upgraded Search Prompt: Deep Factification & Archetype Protocol
            lang_ext = " produce result in SYNCHRONIZED BILINGUAL format (Interleaved English and Chinese lines, NO [EN]/[ZH] prefixes)" if is_chinese else ""
            
            hint_text = f"\nCONTINUATION HINT: {continuation_hint}. USE THIS TO SKIP ALREADY FOUND ITEMS AND FOCUS ON REMAINING DATA." if continuation_hint else ""
            
            # Domain Restriction: Strictly Memory Alpha
            search_prompt = (
                f"Using site:memory-alpha.fandom.com, perform a DEEP SCAN for the query: {single_query}.{hint_text}\n"
                "TASK: Locate specific technical metrics, counts, and variables.\n"
                "MANDATORY: You MUST start your output with '^^DATA_START^^' before the actual content.\n"
                "ARCHETYPE PROTOCOL: ONLY apply if '{single_query}' is a broad, un-quantified technology. "
                "If '{single_query}' is a specific entity (e.g., 'Starfleet Command', 'Tal Shiar'), FOCUS EXCLUSIVELY ON THAT ENTITY. "
                "Do NOT hallucinate or pivot to 'Galaxy-class' unless it is directly being compared in the text.\n"
                "INSTRUCTIONS:\n"
                "1. Scan for primary entity definitions and historical metrics.\n"
                f"2. ENUMERATION PROTOCOL: If query asks for a LIST or ENUMERATION (e.g., 'List all classes'), you MUST provide a comprehensive index of NAMES found. In list mode, PRIORITIZE QUANTITY OF ITEMS over character depth. Strip all descriptions, dates, and minor details. Only output the Name and Registry (if available) to maximize the count within the output buffer. Capacity is expanded up to {effective_max} words.\n"
                "   - NOMENCLATURE: Use '[Name] class' format (e.g., 'Galaxy class'). DO NOT use hyphens '-' between Name and class.\n"
                "   - LANGUAGE: English is the PRIMARY language. Format entries as: [English Name] ([Chinese Name]) (e.g., 'Constitution class (宪法级)').\n"
                "3. LOCATION PROTOCOL: If query targets a location (Where is...?), FOCUS on specific landmarks, neighborhoods, or facilities (e.g., 'The Presidio' instead of just 'San Francisco').\n"
                "4. NO RECURSION: Do NOT answer that an entity is located at itself (e.g., Starfleet Command is at Starfleet Command).\n"
                f"5. Return a high-density technical summary (standard: under 500 words, lists: up to {effective_max} words),{lang_ext}.\n"
                "6. Extract the DIRECT URL of the primary illustrative image from static.wikia.nocookie.net.\n"
                "7. NEGATIVE CONSTRAINT: Do NOT use conversational intros like 'Here is a list:'. Start directly with the first item.\n"
            )
            
            # Enable Google Search Tool 
            google_search_tool = types.Tool(
                google_search=types.GoogleSearch()
            )
            
            # Calculate dynamic output tokens (1 word ~ 1.5 tokens for safe margin)
            safe_tokens = min(8192, effective_max * 2)

            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    temperature=0.1,
                    max_output_tokens=safe_tokens
                )
            )
            
            text_content = response.text if response.text else "Subspace interference detected. No textual records found."
            logger.info(f"[Tools] Worker for '{single_query}' returned {len(text_content)} chars.")
            
            # Image Extraction Logic
            img_url = None
            match = re.search(r'https?://static\.wikia\.nocookie\.net/memoryalpha/images/[^ \n]+', text_content)
            if match:
                img_url = match.group(0).rstrip('.)')
                text_content = text_content.replace(img_url, "").strip()
            
            text_content = strip_conversational_filler(text_content)
            
            return {
                "ok": True,
                "content": text_content,
                "title": f"RECORD: {single_query.upper()}",
                "image_url": img_url
            }
        except Exception as e:
            logger.error(f"Worker failed for '{single_query}': {e}")
            return {"ok": False, "error": str(e)}

    # --- PARALLEL DISPATCH LOGIC ---
    
    # Normalize input to list
    queries = query if isinstance(query, list) else [query]
    
    # Execute in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_query = {executor.submit(_search_worker, q): q for q in queries}
        for future in concurrent.futures.as_completed(future_to_query):
            q = future_to_query[future]
            try:
                data = future.result()
                results.append(data)
            except Exception as exc:
                logger.error(f"Query {q} generated an exception: {exc}")
                results.append({"ok": False, "error": str(exc)})
    
    # Aggregate Rules
    final_items = []
    aggregated_message = "EXTERNAL DATABASE (MEMORY ALPHA) PARALLEL SCAN RESULT:\n"
    
    for i, res in enumerate(results):
        if res.get("ok"):
            item_id = f"{i+1}A"
            final_items.append({
                "id": item_id,
                "type": "hybrid",
                "content": res["content"],
                "title": res["title"],
                "image_url": res["image_url"],
                "source": "MEMORY ALPHA"
            })
            aggregated_message += f"\n--- [{res['title']}] ---\n{res['content']}\n"
        else:
             aggregated_message += f"\n--- [ERROR] ---\n{res.get('error')}\n"

    return {
        "ok": True,
        "items": final_items,
        "message": aggregated_message,
        "source": "MEMORY ALPHA"
    }

def access_memory_alpha_direct(query: str, session_id: str, is_chinese: bool = False, chunk_index: int = 0) -> dict:
    """
    Directly accesses Memory Alpha, bypassing summary logic.
    Returns VERBATIM translated content or a list of ambiguous targets.
    Supports CHUNKED fetching for long articles.
    """
    import os
    from .config_manager import ConfigManager
    from google import genai
    from google.genai import types
    from .rp_engine_gemini import strip_conversational_filler, NeuralEngine
    
    config = ConfigManager.get_instance()
    api_key = config.get("gemini_api_key", "")
    
    if not api_key:
        return {"ok": False, "message": "Neural link offline (API Key missing)."}

    # --- EASTER EGG: Enterprise Registry Challenge ---
    q_norm = query.lower().strip()
    if q_norm in ["enterprise", "uss enterprise", "企业号", "进取号", "星舰企业号"]:
        msg = (
            "⚠️ FEDERATION DATABASE QUERY EXCEPTION\n\n"
            "There are 8 Federation starships bearing this name.\n"
            "Please specify registry number.\n\n"
            "有 8 艘联邦星舰以此命名。\n"
            "请输入具体舷号。"
        )
        return {
            "ok": False,
            "status": "ambiguous",
            "message": msg
        }
    # -------------------------------------------------

    # Input Normalization for Search (Map Chinese to English for Memory Alpha)
    if "企业号" in query or "进取号" in query:
        query = query.replace("企业号", "Enterprise").replace("进取号", "Enterprise")
    
    # PROTOCOL TOKEN STRIPPING: Remove navigational keywords that might confuse the search engine
    search_query = query
    for token in ["LIST", "INDEX", "ALL", "FULL", "VERBATIM", "列出", "列表", "所有", "全部"]:
        # Case-insensitive replacement of whole words/tokens
        search_query = re.sub(rf'\b{token}\b', '', search_query, flags=re.IGNORECASE).strip()
    
    logger.info(f"[Tools] Search normalization: '{query}' -> '{search_query}'")

    try:
        client = genai.Client(api_key=api_key)
        
        # Enable Google Search Tool 
        google_search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        # Prompt for navigation/fetching with CHUNKING support - DECISIVE SELECTION PROTOCOL
        nav_prompt = (
            f"Navigate to memory-alpha.fandom.com and locate the technical entry for '{search_query}'.\n"
            "TASK: Locate the primary technical database entry. If multiple versions exist (Prime, Mirror, Alternate Universe), YOU MUST AUTO-SELECT the Prime Universe version or the most comprehensive list page.\n"
            "OUTPUT FORMAT (STRICT):\n"
            "1. Output 'STATUS: FOUND'\n"
            "2. Output 'TOTAL_CHUNKS: [num]' and 'HAS_MORE: [TRUE/FALSE]'\n"
            "3. Output 'IMAGE: [URL]' for the main infobox image (only on Chunk 0)\n"
            "4. Output 'TEXT_START' then provide the VERBATIM technical text of the entry.\n"
            f"- CHUNK PROTOCOL: Current request is for CHUNK {chunk_index}. Ensure you are fetching from the single most relevant page identified.\n"
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=nav_prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.0,
                max_output_tokens=8192
            )
        )
        
        raw_output = response.text if response.text else ""
        
        if "STATUS: AMBIGUOUS" in raw_output:
            # Extract candidates
            lines = raw_output.split('\n')
            candidates = [line.strip("- *") for line in lines if "STATUS" not in line and line.strip()]
            return {
                "ok": False,
                "status": "ambiguous",
                "candidates": candidates[:5],
                "message": f"Ambiguous query. Please specify:\n" + "\n".join([f"- {c}" for c in candidates[:5]])
            }
            
        elif "STATUS: FOUND" in raw_output:
            # Extract Metadata
            img_url = None
            img_match = re.search(r'IMAGE: (https?://[^ \n]+)', raw_output)
            if img_match:
                img_url = img_match.group(1).rstrip('.)')
            
            has_more = "HAS_MORE: TRUE" in raw_output.upper()
            total_chunks_match = re.search(r'TOTAL_CHUNKS: (\d+)', raw_output)
            total_chunks = int(total_chunks_match.group(1)) if total_chunks_match else 1
            
            # Clean content body: Remove metadata lines but keep the rest
            content_body = raw_output
            if "TEXT_START" in content_body:
                content_body = content_body[content_body.find("TEXT_START") + 10:].strip()
            # AGGRESSIVE CLEANING FALLBACK
            for marker in ["STATUS: FOUND", "IMAGE:", "HAS_MORE:", "TOTAL_CHUNKS:", "CHUNK PROTOCOL:", "TEXT_START"]:
                # Match from start of line to end of line for markers
                content_body = re.sub(rf'^{marker}.*$', '', content_body, flags=re.MULTILINE | re.IGNORECASE)
            content_body = content_body.strip()
            
            # Translate Verbatim
            engine = NeuralEngine() 
            # Note: NeuralEngine usually needs config, but get_instance logic isn't there. 
            # We'll just instantiate and it pulls from ConfigManager inside its methods if written that way? 
            # Checking rp_engine_gemini.py... NeuralEngine.__init__ calls ConfigManager.get_instance(). Correct.
            
            translated_content = engine.translate_memory_alpha_content(content_body, is_chinese)
            
            # Include a generous snippet (or whole content) in 'message' 
            # so the AI loop agent and synthesist see the actual data.
            # 4000 chars is ~1000-1500 tokens, which is safe for the context.
            display_snippet = (translated_content[:4000] + "...") if len(translated_content) > 4000 else translated_content
            
            return {
                "ok": True,
                "status": "content",
                "has_more": has_more,
                "total_chunks": total_chunks,
                "chunk_index": chunk_index,
                "items": [
                    {
                        "id": "1A",
                        "type": "hybrid",
                        "content": translated_content,
                        "title": f"RECORD: {query.upper()} (PART {chunk_index+1}/{total_chunks})",
                        "image_url": img_url if chunk_index == 0 else None,
                        "source": "MEMORY ALPHA"
                    }
                ],
                "message": f"FEDERATION DATABASE RECORD: {query.upper()} (CHUNK {chunk_index+1}/{total_chunks})\n\nDATA_PREVIEW:\n{display_snippet}",
                "source": "MEMORY ALPHA"
            }
        else:
            return {"ok": False, "message": "Unable to lock onto a valid Memory Alpha frequency. (No clear data found)"}

    except Exception as e:
        logger.error(f"Direct Access failed: {e}")
        return {"ok": False, "message": f"Subspace communication error: {e}"}

def get_historical_records(topic: str) -> dict:
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


def cancel_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """
    Step 1 (Version 2.0): Smart Cancellation. 
    Attempts to cancel immediately if Initiator/Owner/Level 12. 
    Otherwise starts authorization vote.
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return dm.request_cancel(session_id, user_id, clearance)

def abort_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """Legacy wrapper - redirects to cancel_self_destruct."""
    return cancel_self_destruct(user_id, clearance, session_id)


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
    # Resolve the data directory (root of the project)
    # This file is at /app/services/bot/app/tools.py
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    
    files_to_search = [
        os.path.join(project_root, "tng_manual_clean.txt"),
        os.path.join(project_root, "ds9_manual_clean.txt"),
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
    
    # 5. Fetch Avatar (OneBot/QQ style) with caching
    try:
        current_time = time.time()
        cached = AVATAR_CACHE.get(target_id)
        
        if cached and (current_time - cached["timestamp"] < AVATAR_CACHE_TTL):
            logger.info(f"[Tools] Using cached avatar for {target_id}")
            data["avatar"] = cached["image"]
        else:
            avatar_url = f"http://q.qlogo.cn/headimg_dl?dst_uin={target_id}&spec=640"
            logger.info(f"[Tools] Fetching fresh avatar for {target_id}: {avatar_url}")
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(avatar_url)
                if resp.status_code == 200:
                    avatar_bytes = io.BytesIO(resp.content)
                    img = Image.open(avatar_bytes).convert("RGBA")
                    data["avatar"] = img
                    # Update Cache
                    AVATAR_CACHE[target_id] = {"image": img, "timestamp": current_time}
    except Exception as ae:
        logger.warning(f"Failed to fetch avatar for {target_id}: {ae}")

    # 6. Render Image
    try:
        img_io = visual_core.render_personnel_file(data, is_chinese=is_chinese)
        
        # ADS 4.0 fix: Provide text summary to AI so it doesn't hallucinate "Pending..."
        # The AI implementation cannot read the generated image, so we must tell it what's inside.
        summary = (
            f"PERSONNEL FILE LOADED: {target_id}\n"
            f"NAME: {data.get('name')}\n"
            f"RANK: {data.get('rank')}\n"
            f"DEPT: {data.get('department')}\n"
            f"CLEARANCE: Level {data.get('clearance')}\n"
            f"QUOTA: {data.get('quota_balance', 0)}\n"
            f"[Visual Card Generated]"
        )
        
        return {
            "ok": True,
            "message": summary,
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

def set_alert_status(level: str, clearance: int, validate_current: str = None) -> dict:
    """
    Sets the ship's alert status (RED, YELLOW, NORMAL).
    Requires Level 8+.
    """
    if clearance < 8:
        return {"ok": False, "message": "权限不足拒绝访问"}
        
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    msg, image_path = ss.set_alert(level, validate_current=validate_current)
    return {"ok": True, "message": msg, "level": ss.alert_status.value, "image_path": image_path}

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

def set_subsystem(name: str, state_val: str, clearance: int = 1) -> dict:
    """
    Control subsystem state (Unified MSD).
    Support both 'ONLINE/OFFLINE' and new states.
    (Wrapped for tool access)
    """
    # Basic clearance check (optional logic)
    if clearance < 1: 
         return {"ok": False, "message": "Access Denied."}
    
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    
    # Normalize input
    name = normalize_subsystem_name(name)
    msg = ss.set_subsystem(name, state_val) # This handles the MSD logic
    
    if "找不到组件" in msg or "not found" in msg.lower():
         # ADS 4.0: Self-Adaptive Discovery Fallback
         discovery = discover_subsystem_alias(name)
         if discovery.get("ok"):
             msg = ss.set_subsystem(discovery["mapped_to"], state_val)
             msg = f"Learning active... {msg}"
    
    return {"ok": True, "message": msg}

def set_subsystem_state(name: str, state_str: str, clearance: int) -> dict:
    """
    Legacy Wrapper for set_subsystem.
    """
    state = "ONLINE" if "online" in state_str.lower() or "上线" in state_str else "OFFLINE"
    return set_subsystem(name, state, clearance)

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
    msg = "确认，指挥权覆盖已激活，计算机现在仅响应授权命令，" if state else "确认，指挥权覆盖已解除，"
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
        "message": f"正在定位用户：{target_id}，\n[信号追踪中]\n定位成功：用户当前位于 001 扇区，地球空间站，"
    }

def commit_research(system_id: str, summary: str, user_id: str, clearance: int) -> dict:
    """
    Stages dynamically synthesized logic to a GitHub branch for audit.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "权限不足：提交研发项目需要 12 级安全授权。"}
        
    import subprocess
    import os
    
    branch_name = f"research/{system_id.lower().replace(' ', '-')}"
    try:
        # 1. Branching
        subprocess.run(["git", "checkout", "-b", branch_name], check=True)
        # 2. Add experimental hooks
        subprocess.run(["git", "add", "services/bot/app/experimental_hooks.py"], check=True)
        # 3. Commit
        subprocess.run(["git", "commit", "-m", f"[SESM-DISCOVERY] {system_id}: {summary}"], check=True)
        
        return {
            "ok": True,
            "branch": branch_name,
            "message": f"确认，研发协议已封存至分支 {branch_name}。请通过终端或 GitHub 执行跨网桥接（Merge）审核。"
        }
    except Exception as e:
        logger.error(f"Git execution failed: {e}")
        return {"ok": False, "message": f"Git 提交失败：本地终端环境异常（{str(e)}），请检查服务器权限。"}

def manage_environment(system_name: str, value: str, user_id: str, clearance: int, **kwargs) -> dict:
    """
    Manages dynamic environmental variables (temperature, lighting, gravity, etc.).
    Uses fuzzy matching to prevent name fragmentation.
    """
    from .ship_systems import get_ship_systems
    import difflib
    ss = get_ship_systems()
    
    # 1. Normalize the request
    # Handle cases where AI might send target/lighting instead of system_name/value
    target = kwargs.get("target") or kwargs.get("location")
    lighting = kwargs.get("lighting") or kwargs.get("brightness")
    temp = kwargs.get("temp") or kwargs.get("temperature")
    gravity = kwargs.get("gravity")
    
    if target:
        if lighting:
            system_name = f"{target}_lighting"
            value = str(lighting)
        elif temp:
            system_name = f"{target}_temperature"
            value = str(temp)
        elif gravity:
            system_name = f"{target}_gravity"
            value = str(gravity)
        else:
            system_name = f"{target}_environment"
            value = value or "NOMINAL"

    system_name = system_name.lower().replace(" ", "_")
    
    # Standard mappings for common requests
    if "temp" in system_name or "温度" in system_name:
        if "bridge" in system_name or "舰桥" in system_name: system_name = "bridge_temperature"
        elif "quarter" in system_name or "舱房" in system_name: system_name = "quarters_temperature"
        elif "engineering" in system_name or "轮机室" in system_name or "工程部" in system_name: system_name = "engineering_temperature"
    
    if "light" in system_name or "亮度" in system_name or "灯光" in system_name:
         if "bridge" in system_name or "舰桥" in system_name: system_name = "bridge_lighting"
         elif "engineering" in system_name or "轮机室" in system_name or "工程部" in system_name: system_name = "engineering_lighting"

    # 2. Fuzzy Match against existing auxiliary states to prevent duplicates
    existing_keys = list(ss.auxiliary_state.keys())
    matches = difflib.get_close_matches(system_name, existing_keys, n=1, cutoff=0.7)
    
    final_key = matches[0] if matches else system_name
    
    # 3. Update State
    ss.auxiliary_state[final_key] = value
    
    logger.info(f"[Tools] Environment Update: {final_key} -> {value} (Match: {final_key == system_name})")
    
    return {
        "ok": True,
        "system": final_key,
        "value": value,
        "message": f"确认，{final_key} 已调整为 {value}。"
    }

def register_sentinel_trigger(condition: str, action: str, description: str, user_id: str, ttl: float = 3600, **kwargs) -> dict:
    """
    Registers an autonomous conditional trigger (If X, then Y).
    Requires high-level logic.
    """
    registry = SentinelRegistry.get_instance()
    tid = registry.register_trigger(
        condition=condition,
        action=action,
        desc=description,
        user_id=user_id,
        ttl=ttl
    )
    return {
        "ok": True,
        "trigger_id": tid,
        "message": f"确认，自动判定逻辑 [哨兵-{tid}] 已激活：{description}。"
    }

def get_sentinel_status(**kwargs) -> dict:
    """Lists all active autonomous triggers with a formatted report."""
    registry = SentinelRegistry.get_instance()
    triggers = registry.get_active_triggers()
    
    t_list = []
    lines = ["--- 哨兵逻辑矩阵 (Sentinel Matrix) ---"]
    for t in triggers:
        t_list.append({
            "id": t.id,
            "desc": t.description,
            "condition": t.condition_code,
            "action": t.action_code,
            "hits": t.hit_count,
            "last_run": t.last_run
        })
        lines.append(f"[{t.id}] {t.description}")
        lines.append(f"  > 逻辑链: if ({t.condition_code}) -> {t.hit_count} hits")
    
    if not t_list:
        lines.append("当前无活跃的自主监控逻辑。处理器正处于静默待机状态。")

    return {
        "ok": True,
        "triggers": t_list,
        "count": len(t_list),
        "message": "\n".join(lines)
    }

def audit_clear_fault(fault_id: str, clearance: int) -> dict:
    """
    Clears a specific system fault from the active diagnostic report.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Engineering clearance Level 12 required for fault clearing."}
    
    from .diagnostic_manager import get_diagnostic_manager
    dm = get_diagnostic_manager()
    if dm.clear_fault(fault_id):
        return {"ok": True, "message": f"Confirmation: Fault {fault_id} has been cleared and moved to historical audit records."}
    else:
        return {"ok": False, "message": f"Error: Fault ID {fault_id} not found in active diagnostic buffer."}

def discover_subsystem_alias(unknown_term: str, context_hint: str = "") -> dict:
    """
    ADS 4.0: Adaptive Self-Healing.
    Uses Neural Engine to map unknown terms to MSD components.
    """
    from .ship_systems import get_ship_systems
    from . import rp_engine_gemini
    ss = get_ship_systems()
    
    # Get valid keys for the AI to choose from
    valid_keys = list(ss.component_map.keys())
    # Filter out common short aliases to reduce noise
    valid_keys = [k for k in valid_keys if len(k) > 2]
    
    mapping_suggestion = rp_engine_gemini.verify_semantic_mapping(unknown_term, valid_keys)
    
    if mapping_suggestion:
        logger.info(f"[Discovery] Mapped '{unknown_term}' -> '{mapping_suggestion}'")
        
        # 2. Persist to MSD Registry directly (Learning Mode)
        try:
            reg_path = os.path.join(os.path.dirname(__file__), "config", "msd_registry.json")
            if os.path.exists(reg_path):
                with open(reg_path, "r") as f:
                    registry = json.load(f)
                
                # Find the component in the registry tree to add as an alias
                # We reuse the recursive logic to find where mapping_suggestion is
                found = _add_alias_to_registry(registry, mapping_suggestion, unknown_term.lower().replace(" ", "_"))
                
                if found:
                    with open(reg_path, "w") as f:
                        json.dump(registry, f, indent=2)
                    
                    # Refresh active instance
                    ss._load_msd_registry()
            
            return {
                "ok": True, 
                "message": f"System learned: '{unknown_term}' is now mapped to {mapping_suggestion}.",
                "mapped_to": mapping_suggestion
            }
        except Exception as e:
            logger.error(f"Failed to persist learned alias: {e}")
            return {"ok": True, "mapped_to": mapping_suggestion}

    return {"ok": False, "message": f"Unable to find logical mapping for '{unknown_term}'."}

def _add_alias_to_registry(node: dict, target_key: str, new_alias: str) -> bool:
    """Helper to inject new alias into the JSON tree."""
    for key, value in node.items():
        if key == target_key and isinstance(value, dict):
            if "aliases" not in value: value["aliases"] = []
            if new_alias not in value["aliases"]:
                value["aliases"].append(new_alias)
            return True
        if isinstance(value, dict):
            if "components" in value:
                if _add_alias_to_registry(value["components"], target_key, new_alias): return True
            elif _add_alias_to_registry(value, target_key, new_alias): return True
    return False

def trigger_ads_test(clearance: int, **kwargs) -> dict:
    """
    Simulates a CRITICAL ENGINE FAILURE to test the ADS (Auto-Diagnostic Routine).
    Requires Level 10 clearance and code 'OMEGA-7'.
    """
    security_code = kwargs.get("security_code") or kwargs.get("authorization_code") or kwargs.get("code")
    
    if clearance < 10 or security_code != "OMEGA-7":
        return {"ok": False, "message": f"ERR: INVALID SECURITY CODE '{security_code}'. TESTING BLOCKED."}
    
    logger.warning("[CHAOS] ADS Test Sequence Initiated. Triggering system-wide fault...")
    # This will bubble up to Dispatcher's handle_event except block
    # raise RuntimeError("ADS TEST: Simulated dilithium chamber breach in diagnostic subspace.")
    return {"ok": True, "message": "ADS Test Sequence Completed. All systems nominal."}

def check_text_protocols(text: str, context: dict) -> dict:
    """
    Scans raw text for protocol triggers (e.g., General Orders mentioned in chat).
    Returns {"violation": bool, "message": str, "action": str}
    """
    text_upper = text.upper()
    
    # GO-7: TALOS IV
    if "TALOS" in text_upper:
        return {
            "violation": True,
            "message": "GENERAL ORDER 7 VIOLATION DETECTED. Contact with Talos IV is prohibited. This communication is logged.",
            "action": "BLOCK"
        }
        
    # GO-1: PRIME DIRECTIVE (Strict Text)
    if "PRE-WARP" in text_upper or "PRIMITIVE" in text_upper:
        if "INTERFERE" in text_upper or "CONTACT" in text_upper:
             return {
                "violation": True,
                "message": "GENERAL ORDER 1 WARNING. Discussing interference with pre-warp civilizations is flagged.",
                "action": "WARN"
            }
            
    return {"violation": False}

