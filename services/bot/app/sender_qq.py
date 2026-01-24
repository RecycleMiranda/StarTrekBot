import os
import httpx
import logging
from typing import Optional
from .sender_base import Sender
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)

class QQSender(Sender):
    def __init__(self):
        config = ConfigManager.get_instance()
        self.host = config.get("napcat_host", "napcat")
        self.port = config.get("napcat_port", 6099)
        self.token = config.get("napcat_token", "")
        self.timeout = float(os.getenv("QQ_SEND_TIMEOUT_SECONDS", "5.0"))

    async def send(self, text: str, meta: dict, send_item_id: str, moderation_info: Optional[dict] = None) -> None:
        """
        Sends message to NapCat via OneBot v11 HTTP API.
        """
        group_id = meta.get("group_id")
        if not group_id:
            raise RuntimeError("NO_GROUP_ID_IN_META")

        # Build NapCat endpoint URL
        base_url = f"http://{self.host}:{self.port}"
        endpoint = f"{base_url}/send_group_msg"
        
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # OneBot v11 format
        payload = {
            "group_id": int(group_id),
            "message": text
        }

        logger.info(f"[QQSender] Sending to {endpoint}: {text[:50]}...")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            resp_json = response.json()
            
            if resp_json.get("retcode") == 0:
                logger.info(f"[QQSender] Successfully sent {send_item_id}")
            else:
                logger.warning(f"[QQSender] Send failed: {resp_json}")
                raise RuntimeError(f"SEND_FAILED: {resp_json.get('message', 'unknown')}")

