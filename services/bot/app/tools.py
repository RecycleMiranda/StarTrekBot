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
