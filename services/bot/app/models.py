from pydantic import BaseModel
from typing import Optional

class InternalEvent(BaseModel):
    event_type: str            # message/group_message/private_message 等
    platform: str = "qq"
    user_id: Optional[str] = None
    group_id: Optional[str] = None
    message_id: Optional[str] = None
    text: Optional[str] = None
    raw: dict                  # 原始平台事件完整保留
    ts: Optional[int] = None
