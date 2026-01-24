import time
import json
import logging
import os

# Data directory
DATA_DIR = "/app/data"
SEND_LOG_PATH = os.path.join(DATA_DIR, "send_log.jsonl")

logger = logging.getLogger(__name__)

async def send(text: str, meta: dict, send_item_id: str, moderation_info: dict = None) -> None:
    """
    Mock sender that writes to a JSONL log file.
    In the future, this is where QQ API calls would happen.
    """
    log_entry = {
        "ts": int(time.time()),
        "iso_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "send_item_id": send_item_id,
        "session_key": meta.get("session_key"),
        "group_id": meta.get("group_id"),
        "user_id": meta.get("user_id"),
        "text": text,
        "moderation": moderation_info,
        "meta": {k: v for k, v in meta.items() if k not in ["session_key", "group_id", "user_id"]}
    }
    
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SEND_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        logger.info(f"[MockSender] Sent message {send_item_id} to {log_entry['session_key']}")
    except Exception as e:
        logger.warning(f"Failed to write send log: {e}")
