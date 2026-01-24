import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join("/app/data", "settings.json")

DEFAULT_CONFIG = {
    "enabled_groups": os.getenv("BOT_ENABLED_GROUPS", "*"),
    "computer_prefix": os.getenv("COMPUTER_PREFIX", "Computer:"),
    "rp_style_strict": os.getenv("RP_STYLE_STRICT", "true").lower() == "true",
    "sender_type": os.getenv("SENDQ_SENDER", "mock"),
    "qq_send_endpoint": os.getenv("QQ_SEND_ENDPOINT", ""),
    "qq_send_token": os.getenv("QQ_SEND_TOKEN", ""),
    "gemini_rp_model": os.getenv("GEMINI_RP_MODEL", "gemini-2.0-flash-lite"),
}

class ConfigManager:
    _instance = None
    _config: Dict[str, Any] = {}

    def __init__(self):
        self.load_config()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_config(self):
        """Loads config from file, falls back to defaults."""
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                    # Merge file config into defaults to ensure all keys exist
                    self._config = {**DEFAULT_CONFIG, **file_config}
                    logger.info("Configuration loaded from settings.json")
                    return
            except Exception as e:
                logger.warning(f"Failed to load settings.json: {e}")
        
        self._config = DEFAULT_CONFIG.copy()
        logger.info("Using default configuration (env fallback)")

    def save_config(self, new_config: Dict[str, Any]):
        """Persists config to file."""
        # Only update keys that exist in defaults to prevent pollution
        for key in DEFAULT_CONFIG:
            if key in new_config:
                self._config[key] = new_config[key]
        
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info("Configuration saved to settings.json")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings.json: {e}")
            return False

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def get_all(self):
        return self._config
