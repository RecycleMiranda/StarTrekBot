import os
import json
import logging
import difflib
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class SOPManager:
    _instance = None
    
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.cache_path = os.path.join(self.base_path, "config", "SOP_CACHE.json")
        self.cache = {}
        self._load_cache()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                self._last_load_time = os.path.getmtime(self.cache_path)
                logger.info(f"[SOPManager] Loaded {len(self.cache)} SOP entries.")
            except Exception as e:
                logger.error(f"[SOPManager] Failed to load SOP Cache: {e}")
                self.cache = {}
        else:
            self.cache = {
                "system_defaults": {
                    "report_status": {
                        "trigger": ["report status", "报告状态", "报一下状态"],
                        "tool_chain": [{"tool": "get_status", "args": {"scope": "all", "depth": "summary"}}],
                        "confidence": 1.0
                    }
                },
                "learned_procedures": {}
            }
            self._save_cache()

    def _save_cache(self):
        try:
            # ADS 15: Merge Awareness
            # Before saving, check if disk version is newer than our last load
            if os.path.exists(self.cache_path):
                mtime = os.path.getmtime(self.cache_path)
                if mtime > getattr(self, "_last_load_time", 0):
                    logger.info("[SOPManager] External change detected. Merging disk state before save...")
                    self._load_cache()

            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            
            self._last_load_time = os.path.getmtime(self.cache_path)

            # ADS 14: Universal Git Sync
            from .protocol_manager import get_protocol_manager
            pm = get_protocol_manager()
            pm.git_sync(f"LCARS: Updated SOP Cache ({len(self.cache.get('learned_procedures', {}))} learned)", extra_files=[self.cache_path])
        except Exception as e:
            logger.error(f"[SOPManager] Failed to save SOP Cache: {e}")

    def find_match(self, query: str) -> Optional[Dict]:
        """
        ADS 9.1: Semantic Fast-Path Matching.
        Tries to find a cached SOP for the given query.
        """
        query = query.lower().strip()
        
        # 1. Exact & Substring Match in System Defaults
        for entry_id, sop in self.cache.get("system_defaults", {}).items():
            for trigger in sop.get("trigger", []):
                if trigger in query:
                    logger.info(f"[SOPManager] System Match: {entry_id}")
                    return sop

        # 2. Fuzzy Matching in Learned Procedures
        best_match = None
        highest_ratio = 0.0
        
        all_learned = self.cache.get("learned_procedures", {})
        for q_key, sop in all_learned.items():
            ratio = difflib.SequenceMatcher(None, query, q_key).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = sop
        
        if highest_ratio > 0.85: # Threshold for Fast-Path
            logger.info(f"[SOPManager] Learned Match ({highest_ratio:.2f}): {best_match.get('intent_id')}")
            return best_match
            
        return None

    def add_learned_sop(self, query: str, tool_chain: List[Dict], intent_id: str):
        """
        Phase 9.2: Adds a new procedure to the learned cache.
        """
        self.cache.setdefault("learned_procedures", {})[query.lower().strip()] = {
            "intent_id": intent_id,
            "tool_chain": tool_chain,
            "confidence": 0.5, # Initial low confidence
            "status": "DRAFT"  # Requires review
        }
        self._save_cache()

def get_sop_manager():
    return SOPManager.get_instance()
