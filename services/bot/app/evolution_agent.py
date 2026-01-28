import os
import json
import logging
from typing import Dict, List, Optional
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TRAINING_LIB_PATH = os.path.join(REPO_ROOT, "services/bot/app/config/training_library.jsonl")

class EvolutionAgent:
    """
    Handles 'Dehydration Training': Refining user corrections into permanent system protocols.
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = EvolutionAgent()
        return cls._instance

    def __init__(self):
        self._ensure_library()

    def _ensure_library(self):
        if not os.path.exists(TRAINING_LIB_PATH):
            os.makedirs(os.path.dirname(TRAINING_LIB_PATH), exist_ok=True)
            with open(TRAINING_LIB_PATH, "w", encoding="utf-8") as f:
                pass  # Create empty file

    async def dehydrate_correction(self, raw_feedback: str, last_response: str) -> Dict:
        """
        Uses LLM to refinery the user's feedback into a formal protocol.
        """
        from . import rp_engine_gemini
        
        prompt = f"""
LCARS NEURAL EVOLUTION PROTOCOL (DEHYDRATION PHASE)
Role: Senior System Architect Assistant
Task: Refine a raw user correction into a formal, immutable system directive.

CONTEXT:
User Feedback: "{raw_feedback}"
Last Computer Response: "{last_response}"

INSTRUCTIONS:
1. DEHYDRATION: Identify the core stylistic or logical rule the user wants to enforce.
2. SYNTHESIS: Convert it into a concise, professional LCARS directive (e.g., "MANDATE: Output must end with status code.")
3. CATEGORIZATION: Decide if this applies to 'tone', 'formatting', or 'operational_logic'.

RETURN FORMAT (JSON ONLY):
{{
    "rule_name": "Short identifier",
    "refined_directive": "The actual LCARS directive text",
    "category": "tone|formatting|logic",
    "priority": 1-10
}}
"""
        try:
            # Use the existing synthesis engine or a dedicated thinking model
            config = ConfigManager.get_instance()
            res = rp_engine_gemini.generate_technical_diagnosis(prompt)
            
            # Since generate_technical_diagnosis returns diagnosis/suggested_fix, 
            # we adapt the prompt or use a more direct call if needed. 
            # For now, let's assume it returns a compatible json if we prompt it right.
            
            # Let's use a more robust direct call via rp_engine_gemini if possible
            # or just use the tool we have.
            
            # For now, we manually parse if the tool returns diagnosis as the json string.
            refined_data = json.loads(res.get("diagnosis", "{}"))
            if refined_data:
                self.persist_rule(refined_data)
                return {"ok": True, "directive": refined_data["refined_directive"]}
                
        except Exception as e:
            logger.error(f"Failed to dehydrate correction: {e}")
            return {"ok": False, "message": str(e)}

    def persist_rule(self, rule_data: Dict):
        """Appends the rule to the training library."""
        with open(TRAINING_LIB_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rule_data, ensure_ascii=False) + "\n")
        logger.info(f"[EvolutionAgent] Persistent rule added: {rule_data.get('rule_name')}")

    def get_active_directives(self) -> str:
        """Compiles all stored rules into a dynamic prompt segment."""
        if not os.path.exists(TRAINING_LIB_PATH):
            return ""
        
        directives = []
        try:
            with open(TRAINING_LIB_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    directives.append(f"- {data['refined_directive']}")
        except Exception as e:
            logger.error(f"Error reading training library: {e}")
            
        return "\n".join(directives)

def get_evolution_agent():
    return EvolutionAgent.get_instance()
