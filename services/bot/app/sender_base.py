from typing import Protocol, Optional

class Sender(Protocol):
    async def send(self, text: str, meta: dict, send_item_id: str, moderation_info: Optional[dict] = None) -> None:
        """
        Sends a message to the target platform.
        """
        ...
