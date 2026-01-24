from typing import Dict, Optional, TypedDict

class UserProfile(TypedDict):
    name: str
    rank: str
    department: str
    clearance: int

# LCARS Departments
DEPARTMENTS = {
    "COMMAND": "Command (Gold/Red)",
    "OPERATIONS": "Operations/Engineering (Gold/Yellow)",
    "SCIENCE": "Science/Medical (Blue)",
    "TACTICAL": "Tactical/Security (Gold/Yellow)",
    "MEDICAL": "Medical (Blue)",
    "CIVILIAN": "Civilian",
    "SECTION_31": "Section 31 (Classified)"
}

# LCARS Ranks (Ordered by authority)
RANKS = [
    "Admiral", "Captain", "Commander", "Lt. Commander", 
    "Lieutenant", "Lieutenant J.G.", "Ensign", "Crewman", "Civilian"
]

# User to Profile mapping (user_id -> UserProfile)
USER_PROFILES: Dict[str, UserProfile] = {
    "2819163610": {
        "name": "AAAAA你米兰达🌈", # Taken from user's QQ nickname in logs
        "rank": "Admiral",
        "department": "SECTION_31",
        "clearance": 4
    }
}

DEFAULT_PROFILE: UserProfile = {
    "name": "Unknown",
    "rank": "Ensign",
    "department": "OPERATIONS",
    "clearance": 1
}

def get_user_profile(user_id: str, nickname: Optional[str] = None) -> UserProfile:
    """Returns the full LCARS profile for a user."""
    profile = USER_PROFILES.get(str(user_id))
    if not profile:
        profile = DEFAULT_PROFILE.copy()
        if nickname:
            profile["name"] = nickname
    return profile

def format_profile_for_ai(profile: UserProfile) -> str:
    """Formats the profile for inclusion in AI prompts."""
    return (
        f"Name: {profile['name']}, "
        f"Rank: {profile['rank']}, "
        f"Department: {profile['department']}, "
        f"Clearance Level: {profile['clearance']}"
    )
