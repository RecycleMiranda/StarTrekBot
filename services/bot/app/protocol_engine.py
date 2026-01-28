import logging
import os
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

@dataclass
class Protocol:
    id: str
    name: str
    category: str
    priority: int
    raw_data: Dict[str, Any]

class ProtocolEngine:
    def __init__(self, protocols_dir: str = "services/bot/app/protocols"):
        self.protocols_dir = protocols_dir
        self.protocols: Dict[str, Protocol] = {}
        self.load_protocols()

    def load_protocols(self):
        """Recursively loads all YAML protocol definitions."""
        if yaml is None:
            logger.error("PyYAML not installed. Protocol Engine cannot load files.")
            return

        if not os.path.exists(self.protocols_dir):
            logger.warning(f"Protocol directory not found: {self.protocols_dir}")
            return

        for root, _, files in os.walk(self.protocols_dir):
            for file in files:
                if file.endswith(".yaml") or file.endswith(".yml"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            # Load all documents if multiple
                            docs = yaml.safe_load_all(f)
                            for doc in docs:
                                if not doc:
                                    continue
                                
                                # Handle single protocol vs list of protocols
                                protocol_list = doc if isinstance(doc, list) else [doc]
                                
                                for data in protocol_list:
                                    if not isinstance(data, dict) or 'id' not in data:
                                        continue
                                    
                                    p = Protocol(
                                        id=data['id'],
                                        name=data.get('name', 'Unknown'),
                                        category=data.get('category', 'GENERAL'),
                                        priority=data.get('priority', 100),
                                        raw_data=data
                                    )
                                    self.protocols[p.id] = p
                                    logger.info(f"Loaded Protocol: {p.id} ({p.name})")
                    except Exception as e:
                        logger.error(f"Failed to load protocol {path}: {e}")

    def get_protocol(self, protocol_id: str) -> Optional[Protocol]:
        return self.protocols.get(protocol_id)

    def evaluate_action(self, action_type: str, params: Dict[str, Any], user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Evaluates an action against ALL loaded protocols to see if any trigger matches.
        
        Args:
            action_type: e.g., "MANUAL_COMMAND", "NAVIGATION_SET", "ALERT_CHANGE", "SENSOR_CONTACT"
            params: Dict of parameters for the action (e.g., {'target': 'Talos IV', 'keyword': 'Destruct'})
            user_context: Dict containing 'user_id', 'auth_level', etc.
            
        Returns:
            Dict with keys: 
            - allowed: bool
            - violations: List[str] (names of blocking protocols)
            - warnings: List[str]
            - modifications: Dict (if a protocol modifies the parameters)
        """
        violations = []
        warnings = []
        modifications = {}
        
        for p_id, protocol in self.protocols.items():
            triggers = protocol.raw_data.get('trigger', [])
            if not isinstance(triggers, list):
                triggers = [triggers]
                
            for trigger in triggers:
                if trigger.get('type') != action_type:
                    continue
                
                # Check specifics
                match = True
                
                # Keyword matching (e.g. for COMMANDs)
                if 'keyword' in trigger:
                    input_kw = str(params.get('keyword', '')).upper()
                    trigger_kw = str(trigger['keyword']).upper()
                    if trigger_kw not in input_kw:
                        match = False
                        
                # Value matching (e.g. ALERT RED)
                if 'value' in trigger:
                    if str(params.get('value', '')).upper() != str(trigger['value']).upper():
                        match = False

                # Target matching (e.g. NAVIGATION)
                if 'target' in trigger:
                    trigger_target = str(trigger['target']).upper()
                    # Check if trigger target is in input target params
                    param_target = str(params.get('target', '')).upper()
                    if trigger_target not in param_target:
                        match = False

                if match:
                    # Protocol Triggered!
                    # Now check conditions (if any) to see if we satisfy them
                    conditions = protocol.raw_data.get('conditions', [])
                    conditions_met = True # Default true if no conditions (Hard Constraint)
                    
                    if conditions:
                        # Simple evaluator for authorization logic
                        # Real implementation would be more complex
                        if user_context:
                            auth_level = user_context.get('clearance', 0)
                            # Placeholder for condition logic
                            pass 

                    # Determine Action (Block vs Warn)
                    # For V1, we assume if it triggers and it has "BLOCK" or "LOCK" or "DENY" in actions, it's a violation.
                    actions = protocol.raw_data.get('actions', {})
                    on_trigger = actions.get('on_trigger', []) + actions.get('on_active', [])
                    
                    is_blocking = False
                    for act in on_trigger:
                        act_str = str(act).upper()
                        if any(x in act_str for x in ['BLOCK', 'LOCK', 'DENY', 'RESTRICT', 'SUSPEND']):
                            is_blocking = True
                            
                    if is_blocking:
                        logger.warning(f"Protocol VIOLATION: {protocol.name} blocks {action_type}")
                        violations.append(f"{protocol.name} ({protocol.id})")
                    else:
                        logger.info(f"Protocol Warning: {protocol.name} active for {action_type}")
                        warnings.append(f"Protocol Active: {protocol.name}")

        allowed = len(violations) == 0
        return {
            "allowed": allowed,
            "violations": violations,
            "warnings": warnings,
            "modifications": modifications
        }

# Singleton Instance
_engine_instance = None

def get_protocol_engine() -> ProtocolEngine:
    global _engine_instance
    if _engine_instance is None:
        # Adjust path relative to execution context if needed
        base_path = os.path.dirname(os.path.abspath(__file__))
        proto_dir = os.path.join(base_path, "protocols")
        _engine_instance = ProtocolEngine(proto_dir)
    return _engine_instance
