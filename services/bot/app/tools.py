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

def replicate(item_name: str, user_id: str, rank: str) -> dict:
    """
    Replicates an item using replicator credits.
    Standard items cost 5-50 credits.
    """
    from .quota_manager import get_quota_manager
    qm = get_quota_manager()
    
    # Generic cost logic (could be improved with a dictionary)
    item_lower = item_name.lower()
    cost = 10 # Default
    if any(k in item_lower for k in ["tea", "coffee", "water"]): cost = 5
    if any(k in item_lower for k in ["steak", "pasta", "meal"]): cost = 15
    if any(k in item_lower for k in ["padd", "tool", "spare"]): cost = 25
    if any(k in item_lower for k in ["diamond", "gold", "luxury"]): cost = 500
    
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

def reserve_holodeck(program_name: str, duration_hours: float, user_id: str, rank: str) -> dict:
    """
    Reserves a holodeck session.
    Costs 50 credits per hour.
    """
    from .quota_manager import get_quota_manager
    qm = get_quota_manager()
    
    cost = int(duration_hours * 50)
    
    if qm.spend_credits(user_id, cost):
        return {
            "ok": True,
            "message": f"Holodeck session reserved: '{program_name}' for {duration_hours} hours.",
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

def personal_log(content: str, user_id: str) -> dict:
    """
    Records a personal log. Grants random credits (2h cooldown).
    """
    from .quota_manager import get_quota_manager
    qm = get_quota_manager()
    
    result = qm.record_log(user_id)
    return result
