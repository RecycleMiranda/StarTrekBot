import os
import httpx
import logging
from typing import Optional
from .sender_base import Sender

logger = logging.getLogger(__name__)

class QQSender(Sender):
    def __init__(self):
        self.endpoint = os.getenv("QQ_SEND_ENDPOINT")
        self.token = os.getenv("QQ_SEND_TOKEN")
        self.timeout = float(os.getenv("QQ_SEND_TIMEOUT_SECONDS", "3.0"))

    async def send(self, text: str, meta: dict, send_item_id: str, moderation_info: Optional[dict] = None) -> None:
        """
        Sends message to an external QQ adapter/gateway via HTTP.
        """
        if not self.endpoint:
            raise RuntimeError("QQ_SEND_ENDPOINT_NOT_CONFIGURED")

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        payload = {
            "text": text,
            "send_item_id": send_item_id,
            "meta": meta,
            "moderation": moderation_info
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.endpoint, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"[QQSender] Successfully delivered {send_item_id} to endpoint.")
