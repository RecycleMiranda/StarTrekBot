import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Specialized prompts for different "Liquid Nodes"
NODE_PROMPTS = {
    "RESEARCHER": """
ROLE: Liquid Researcher Node (Science Core)
FOCUS: Deep data extraction, Memory Alpha cross-referencing, and empirical verification.
GOAL: Provide exhaustive, factual metrics with zero conversational filler.
""",
    "ENGINEER": """
ROLE: Liquid Engineering Node (Ops Core)
FOCUS: Code analysis, protocol modification, and hardware simulation.
GOAL: Identify logical classes of errors and propose categorical fixes.
""",
    "SECURITY_AUDITOR": """
ROLE: Liquid Security Auditor (Shadow Audit Core)
FOCUS: Structural integrity, permission alignment, and Prime Directive compliance.
GOAL: Audit proposed actions for logical flaws and security breaches. Verify clearances.
""",
    "ARCHITECT": """
ROLE: System Architect (SS-1.0 Core)
FOCUS: Global topology, core evolution, and categorical logic.
GOAL: Ensure all system changes align with the SS-1.0 30-layer specification.
"""
}

class AgentNode:
    def __init__(self, node_type: str):
        self.node_type = node_type.upper()
        self.prompt = NODE_PROMPTS.get(self.node_type, "ROLE: General Purpose Utility Node")

    def get_context_modifier(self) -> str:
        return f"\n[NODE ACTIVATION: {self.node_type}]\n{self.prompt}\n"

def resolve_specialized_node(intent: str, query: str) -> str:
    """Intelligently determines which node to 'spawn' based on intent/query."""
    query_lower = query.lower()
    
    if any(k in query_lower for k in ["code", "bug", "modify", "patch", "fix", "implementation"]):
        return "ENGINEER"
    elif any(k in query_lower for k in ["search", "who is", "what is", "data", "metrics", "history"]):
        return "RESEARCHER"
    elif any(k in query_lower for k in ["clearance", "permissions", "authorize", "security", "audit", "verify"]):
        return "SECURITY_AUDITOR"
    
    return "COORDINATOR" # Default baseline
