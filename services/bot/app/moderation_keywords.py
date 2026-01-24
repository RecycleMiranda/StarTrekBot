import re
import os
import logging
import httpx

logger = logging.getLogger(__name__)

KEYWORDS_FILE = "/app/data/keywords.txt"
REMOTE_LIST_URL = "https://raw.githubusercontent.com/Konsheng/Sensitive-lexicon/refs/heads/master/sensitive-lexicon.txt"

class KeywordFilter:
    _instance = None
    _keywords = set()

    def __init__(self):
        self.reload()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reload(self):
        """Reloads keywords from the text file."""
        if not os.path.exists(KEYWORDS_FILE):
            # Create a default placeholder file
            os.makedirs(os.path.dirname(KEYWORDS_FILE), exist_ok=True)
            with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
                f.write("# 每行一个违禁词\n# starship_explode_placeholder\n")
            logger.info("Created default empty keywords.txt")
        
        try:
            with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # Filter out comments and empty lines
                self._keywords = set(
                    line.strip() for line in lines 
                    if line.strip() and not line.startswith("#")
                )
            logger.info(f"Loaded {len(self._keywords)} local keywords.")
        except Exception as e:
            logger.error(f"Failed to load keywords: {e}")

    def check(self, text: str) -> dict:
        """
        Checks if text contains any forbidden keywords.
        Returns a moderation-compatible result.
        """
        if not self._keywords:
            return {"allow": True, "action": "pass", "reason": "no_keywords_loaded"}

        for kw in self._keywords:
            if kw in text:
                return {
                    "allow": False, 
                    "action": "block", 
                    "risk_level": 3, 
                    "reason": f"local_keyword_match: {kw}",
                    "provider": "local"
                }
        
        return {"allow": True, "action": "pass", "risk_level": 0, "reason": "local_passed", "provider": "local"}

    async def sync_from_remote(self) -> dict:
        """Downloads the latest sensitive word list from GitHub."""
        logger.info(f"Syncing keywords from {REMOTE_LIST_URL}...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(REMOTE_LIST_URL)
                resp.raise_for_status()
                content = resp.text
                
                # Deduplicate and basic cleaning
                new_words = set()
                for line in content.splitlines():
                    clean = line.strip()
                    if clean and not clean.startswith("#"):
                        new_words.add(clean)
                
                if not new_words:
                    return {"code": 1, "message": "downloaded list is empty"}

                os.makedirs(os.path.dirname(KEYWORDS_FILE), exist_ok=True)
                with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
                    f.write("# StarTrekBot Cloud-Synced Keywords\n")
                    f.write("\n".join(sorted(list(new_words))))
                
                self.reload()
                return {"code": 0, "message": f"successfully synced {len(new_words)} keywords"}
        except Exception as e:
            logger.error(f"Failed to sync remote keywords: {e}")
            return {"code": 1, "message": f"sync failed: {str(e)}"}
