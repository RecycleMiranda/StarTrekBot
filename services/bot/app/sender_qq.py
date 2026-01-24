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

        base_url = f"http://{self.host}:{self.port}"
        
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # Prepare message text with quote/reply if requested
        message_to_send = text
        
        # Add Image if present
        image_b64 = meta.get("image_b64")
        if image_b64:
            message_to_send += f"[CQ:image,file=base64://{image_b64}]"

        reply_to = meta.get("reply_to")
        if reply_to:
            message_to_send = f"[CQ:reply,id={reply_to}]{message_to_send}"

        # OneBot v11 format
        payload = {
            "group_id": int(group_id),
            "message": message_to_send
        }

        # Try paths - /send_group_msg works for NapCat
        paths = [
            "/send_group_msg",
            "/api/send_group_msg"
        ]
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for path in paths:
                endpoint = f"{base_url}{path}"
                try:
                    logger.info(f"[QQSender] Trying {endpoint}...")
                    response = await client.post(endpoint, json=payload, headers=headers)
                    
                    if response.status_code == 404:
                        continue
                    
                    resp_json = response.json()
                    if resp_json.get("retcode") == 0 or resp_json.get("status") == "ok":
                        logger.info(f"[QQSender] Successfully sent {send_item_id} via {path}")
                        return
                    else:
                        logger.warning(f"[QQSender] {path} returned: {resp_json}")
                except Exception as e:
                    logger.warning(f"[QQSender] {path} failed: {e}")
                    continue
            
            raise RuntimeError("ALL_SEND_PATHS_FAILED")


