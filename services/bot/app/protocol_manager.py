import os
import json
import logging
import re
import time
import subprocess
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Paths for Docker and Local
BASE_DIR = os.path.dirname(__file__)
PROTOCOLS_JSON = os.getenv("PROTOCOLS_PATH", os.path.join(BASE_DIR, "config", "federation_protocols.json"))
STANDARDS_MD = os.getenv("STANDARDS_MD_PATH", os.path.join(BASE_DIR, "FEDERATION_STANDARDS.md"))

class ProtocolManager:
    _instance = None
    _protocols: Dict[str, Any] = {}

    def __init__(self):
        self.load_protocols()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_protocols(self):
        # 1. Try to load from the target path (likely persistent volume)
        if os.path.exists(PROTOCOLS_JSON):
            try:
                with open(PROTOCOLS_JSON, "r", encoding="utf-8") as f:
                    self._protocols = json.load(f)
                    logger.info(f"Protocols loaded from {PROTOCOLS_JSON}")
                    return
            except Exception as e:
                logger.error(f"Failed to load protocols JSON: {e}")

        # 2. Fallback: If target doesn't exist, try to copy from the default template
        template_path = os.path.join(BASE_DIR, "config", "federation_protocols.json")
        if PROTOCOLS_JSON != template_path and os.path.exists(template_path):
            try:
                logger.info(f"Initializing persistent protocols from template: {template_path}")
                with open(template_path, "r", encoding="utf-8") as f:
                    self._protocols = json.load(f)
                
                # Immediately save to the persistent location
                os.makedirs(os.path.dirname(PROTOCOLS_JSON), exist_ok=True)
                with open(PROTOCOLS_JSON, "w", encoding="utf-8") as f:
                    json.dump(self._protocols, f, indent=2, ensure_ascii=False)
                return
            except Exception as e:
                logger.error(f"Failed to initialize protocols from template: {e}")

        self._protocols = {}

    def get_prompt(self, category: str, key: str, default: str = "") -> str:
        return self._protocols.get("system_prompts", {}).get(category, {}).get(key, default)

    def get_immutable(self) -> str:
        """Returns all immutable directives as a single flattened block."""
        directives = self._protocols.get("immutable_directives", {})
        if not isinstance(directives, dict):
            return ""
        
        flat_lines = []
        for val in directives.values():
            if isinstance(val, dict):
                flat_lines.extend([str(v) for v in val.values()])
            else:
                flat_lines.append(str(val))
        return "\n".join(flat_lines)

    def get_lexicon(self, category: str, default: str = "") -> str:
        return self._protocols.get("lexicon", {}).get(category, default)

    def update_protocol(self, category: str, key: str, value: str, action: str = "set") -> bool:
        """
        Updates a protocol value with smart merge logic.
        Actions:
        - 'set': Replaces the entire value (default, for backwards compat).
        - 'append': Adds the new value to the end of the existing value.
        - 'remove': Removes the specified substring from the existing value.
        """
        if category == "immutable_directives":
            logger.warning("ATTEMPT TO MODIFY IMMUTABLE DIRECTIVE BLOCKED.")
            return False
            
        if "system_prompts" not in self._protocols:
            self._protocols["system_prompts"] = {}
        if category not in self._protocols["system_prompts"]:
            self._protocols["system_prompts"][category] = {}
        
        current_value = self._protocols["system_prompts"][category].get(key, "")
        
        if action == "append":
            # Intelligently append, adding a separator if needed
            if current_value:
                new_value = current_value.rstrip() + " " + value.strip()
            else:
                new_value = value.strip()
            logger.info(f"[ProtocolManager] Appending to {key}: '{value}'")
        elif action == "remove":
            # Remove the specified substring
            new_value = current_value.replace(value, "").strip()
            # Clean up double spaces
            new_value = re.sub(r'\s+', ' ', new_value).strip()
            logger.info(f"[ProtocolManager] Removing from {key}: '{value}'")
        else:  # action == "set" or unknown
            new_value = value
            logger.info(f"[ProtocolManager] Setting {key} to: '{value}'")
        
        self._protocols["system_prompts"][category][key] = new_value
        
        # Save JSON
        try:
            os.makedirs(os.path.dirname(PROTOCOLS_JSON), exist_ok=True)
            with open(PROTOCOLS_JSON, "w", encoding="utf-8") as f:
                json.dump(self._protocols, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            # Sync to MD
            self._sync_to_markdown()
            
            # Small delay to ensure file modification is indexed by OS/Docker
            time.sleep(0.5)
            
            # Auto Git Sync
            self.git_sync(f"LCARS: Updated protocol {category}.{key}")
            return True
        except Exception as e:
            logger.error(f"Failed to save protocols: {e}")
            return False

    def git_sync(self, message: str, extra_files: list[str] = None):
        """Automatically commits changes to Git. Allows extra files to be staged."""
        from .repair_tools import git_sync_changes
        from pathlib import Path

        # Prepare list of paths
        files_to_sync = [Path(PROTOCOLS_JSON), Path(STANDARDS_MD)]
        if extra_files:
            for f in extra_files:
                files_to_sync.append(Path(f))
        
        # Call unified sync utility
        return git_sync_changes(files_to_sync, message)

    def _sync_to_markdown(self):
        """Generates a fresh FEDERATION_STANDARDS.md from current protocols."""
        try:
            rp = self._protocols.get("system_prompts", {}).get("rp_engine", {})
            im = self._protocols.get("immutable_directives", {})
            
            # Format Immutable Directives nicely
            im_lines = []
            for cat, rules in im.items():
                if isinstance(rules, dict):
                    for k, v in rules.items():
                        im_lines.append(f"- **{k.replace('_', ' ').title()}**: {v}")
                else:
                    im_lines.append(f"- {rules}")
            im_text = "\n".join(im_lines)

            content = f"""# Federation Standard Operations Protocols (FSOP)

## [CRITICAL] 1. Immutable Directives (Fixed Core)
> [!WARNING]
> The following rules are hardcoded into the ship's computer and CANNOT be modified via conversation or override.

{im_text}

## 2. Dynamic Behavioral Protocols
> [!TIP]
> These directives define the bot's current tuning and can be updated by Senior Officers (Level 10+).

### 2.1 Persona & Tone
{rp.get('persona', 'N/A')}

### 2.2 Wake Word Response
Current Wake Sound: `{rp.get('wake_response', '滴滴滴')}`

### 2.3 Response Strategy & Logic
{rp.get('decision_logic', 'N/A')}

### 2.4 Security & Lexicon
- **Protocols**: {rp.get('security_protocols', 'N/A')}
- **Style**: {rp.get('chinese_style', 'N/A')}

---
*Generated by LCARS Autonomous Evolution Logic.*
"""
            with open(STANDARDS_MD, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to sync to markdown: {e}")

def get_protocol_manager():
    return ProtocolManager.get_instance()
