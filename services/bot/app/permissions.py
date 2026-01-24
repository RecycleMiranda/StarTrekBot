from typing import Dict, Optional

# LCARS Clearance Levels
# Level 0: Guest/Civilian - Public ship info only.
# Level 1: Crew Member - General ship data, personal logs.
# Level 2: Senior Officer - Tactical data, engineering status, sensor control.
# Level 3: Command/Captain - Classified files, priority overrides, self-destruct access.
# Level 4: Section 31 - Absolute clearance for all ship/federation systems.

LEVEL_LABELS = {
    0: "Guest (Civilian)",
    1: "Crew Member (Standard)",
    2: "Senior Officer (Tactical)",
    3: "Command (Captain/Admiral)",
    4: "Section 31 (Classified)",
}

# User to Level mapping (user_id -> level)
# You can add QQ numbers here to grant higher clearance.
USER_LEVELS: Dict[str, int] = {
    "2819163610": 4,  # The Owner (Section 31)
}

DEFAULT_LEVEL = 1  # Most people are "Crew" by default

def get_user_clearance(user_id: str) -> int:
    """Returns the numeric clearance level for a user."""
    return USER_LEVELS.get(str(user_id), DEFAULT_LEVEL)

def get_clearance_label(level: int) -> str:
    """Returns the descriptive label for a clearance level."""
    return LEVEL_LABELS.get(level, "Unknown")
