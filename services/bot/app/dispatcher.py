import os
import logging
from .models import InternalEvent

logger = logging.getLogger(__name__)

# Config
# Should be a comma-separated list of group IDs, e.g., "123456,789012"
ENABLED_GROUPS_RAW = os.getenv("BOT_ENABLED_GROUPS", "").strip()
ENABLED_GROUPS = [g.strip() for g in ENABLED_GROUPS_RAW.split(",") if g.strip()]

def is_group_enabled(group_id: str | None) -> bool:
    """
    Checks if the given group_id is in the whitelist.
    Private messages (group_id is None) are allowed by default.
    """
    if group_id is None:
        return True
    
    # If whitelist is empty or contains wildcard "*", allow all groups
    if not ENABLED_GROUPS or "*" in ENABLED_GROUPS:
        return True
        
    return str(group_id) in ENABLED_GROUPS

def handle_event(event: InternalEvent):
    """
    Dispatcher for internal events with group filtering.
    """
    if not is_group_enabled(event.group_id):
        logger.info(f"[Dispatcher] Group {event.group_id} not in whitelist. Dropping event.")
        return False

    logger.info(f"[Dispatcher] Handling Event: {event.model_dump_json(indent=2)}")
    
    # Placeholder for further logic
    return True
