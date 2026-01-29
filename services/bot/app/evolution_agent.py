import os
import json
import logging
import re
from typing import Dict, List, Optional
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)

from .repair_tools import git_sync_changes
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TRAINING_LIB_PATH = os.path.join(REPO_ROOT, "services/bot/app/config/training_library.jsonl")
MSD_REGISTRY_PATH = os.path.join(REPO_ROOT, "services/bot/app/config/msd_registry.json")

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
        try:
            with open(TRAINING_LIB_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(rule_data, ensure_ascii=False) + "\n")
            logger.info(f"[EvolutionAgent] Persistent rule added: {rule_data.get('rule_name')}")
            
            # ADS 7.0: Neural Sync Protocol - Auto-commit training data
            from .repair_tools import git_sync_changes
            git_sync_changes(Path(TRAINING_LIB_PATH), f"Neural Evolution: Added rule {rule_data.get('rule_name')}")
        except Exception as e:
            logger.error(f"Failed to persist rule or sync: {e}")

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
            
        except Exception as e:
            logger.error(f"Error reading training library: {e}")
            
        return "\n".join(directives)

    def evolve_msd(self, system_name: str, parameter_type: str, proposed_value: str, justification: str) -> Dict:
        """
        ADS 3.1: Evolution Protocol.
        Allows the AI to propose structural changes to the MSD Registry.
        
        Args:
            system_name: e.g., "warp_core"
            parameter_type: "new_state", "new_metric", "update_limit"
            proposed_value: e.g., "WARP_9.975"
            justification: e.g., "Voyager class sustained cruise velocity upgrade."
        """
        # 1. CANON FIREWALL CHECK
        canon_check = self._validate_msd_canon(parameter_type, proposed_value)
        if not canon_check["ok"]:
            return {
                "ok": False, 
                "message": f"Evolution Rejected (Canon Violation): {canon_check['reason']}"
            }
            
        # 2. Load Registry
        try:
            with open(MSD_REGISTRY_PATH, "r") as f:
                registry = json.load(f)
        except Exception as e:
            return {"ok": False, "message": f"Registry Load Failed: {e}"}

        # 3. Locate Component (if not adding a new one)
        target_node = None
        if parameter_type != "new_component":
            target_node = self._find_node_recursive(registry, system_name)
            if not target_node:
                 return {"ok": False, "message": f"System '{system_name}' not found in registry topology."}
             
        # 4. Apply Mutation
        change_log = ""
        if parameter_type == "new_state":
            current_states = target_node.get("states", [])
            if proposed_value in current_states:
                return {"ok": True, "message": f"State '{proposed_value}' already exists."}
            target_node["states"].append(proposed_value)
            change_log = f"Added state: {proposed_value}"
            
        elif parameter_type == "new_metric":
            # Expecting proposed_value as "metric_name:unit:default"
            try:
                m_name, m_unit, m_def = proposed_value.split(":")
                if "metrics" not in target_node: target_node["metrics"] = {}
                target_node["metrics"][m_name] = {"unit": m_unit, "default": float(m_def)}
                change_log = f"Added metric: {m_name} ({m_unit})"
            except ValueError:
                return {"ok": False, "message": "Format error. Use 'name:unit:default' for new metrics."}

        elif parameter_type == "new_component":
            # Expecting proposed_value as a JSON string with full component spec
            try:
                new_comp = json.loads(proposed_value)
                category = new_comp.get("category", "learned_systems")
                comp_key = new_comp.get("key") or system_name.lower().replace(" ", "_")
                
                if not comp_key:
                    return {"ok": False, "message": "Missing 'key' for new component."}

                # Organize into groups
                if category not in registry:
                    registry[category] = {
                        "display_name_en": category.replace("_", " ").title(),
                        "display_name_cn": f"新发现系统 ({category})",
                        "components": {}
                    }
                
                group = registry[category]
                if "components" not in group: group["components"] = {}
                
                if comp_key in group["components"]:
                    return {"ok": True, "message": f"Component '{comp_key}' already exists in {category}."}
                
                # Construct the component definition
                group["components"][comp_key] = {
                    "name": new_comp.get("name") or system_name,
                    "states": new_comp.get("states", ["OFFLINE", "ONLINE"]),
                    "default_state": new_comp.get("default_state", "ONLINE"),
                    "metrics": new_comp.get("metrics", {}),
                    "dependencies": new_comp.get("dependencies", ["eps_grid"]),
                    "learned": True
                }
                change_log = f"Expanded Registry: Integrated '{comp_key}' into '{category}' path."
                
            except json.JSONDecodeError:
                return {"ok": False, "message": "Format error. 'new_component' requires a valid JSON string payload."}
        
        else:
             return {"ok": False, "message": f"Unknown evolution type: {parameter_type}"}

        # 5. Evolution Log & Persistence
        import time
        if "_evolution_log" not in registry: registry["_evolution_log"] = []
        registry["_evolution_log"].append({
            "timestamp": time.time(),
            "system": system_name,
            "change": change_log,
            "justification": justification
        })

        try:
            with open(MSD_REGISTRY_PATH, "w") as f:
                json.dump(registry, f, indent=2)
                
            # 6. GIT SYNC
            git_msg = f"ADS 3.1 Evolution: {system_name} -> {change_log}"
            git_res = git_sync_changes([Path(MSD_REGISTRY_PATH)], git_msg)
            
            return {
                "ok": True,
                "message": f"Evolution Accepted. {change_log}. Logic persisted to MSD Registry. {git_res.get('message')}"
            }
        except Exception as e:
            return {"ok": False, "message": f"Persistence failed: {e}"}

    def _validate_msd_canon(self, p_type: str, value: str) -> Dict:
        """The 'Holy Timeline' Logic Checker (AI Powered)."""
        from .rp_engine_gemini import verify_canon_compliance
        
        # Contextualize the proposal
        context = f"Evolution Type: {p_type}. Value: {value}. The user is requesting to add this to the ship's MSD Registry."
        
        # Call the Judge
        verdict = verify_canon_compliance(value, context)
        
        if verdict["allowed"]:
            return {"ok": True}
        else:
            return {"ok": False, "reason": verdict["reason"]}

    def _find_node_recursive(self, node: Dict, target_alias: str) -> Optional[Dict]:
        """Helper to find the mutable dict node in the JSON tree."""
        for key, value in node.items():
            if not isinstance(value, dict): continue
            
            # Check matches
            if key == target_alias: return value
            if target_alias in value.get("aliases", []): return value
            
            # Recurse
            if "components" in value:
                found = self._find_node_recursive(value["components"], target_alias)
                if found: return found
            elif isinstance(value, dict): # Generic recursion
                found = self._find_node_recursive(value, target_alias)
                if found: return found
        return None

def get_evolution_agent():
    return EvolutionAgent.get_instance()
