import time
import logging
from typing import Dict, Optional, TypedDict, Tuple

logger = logging.getLogger(__name__)

# --- COMMAND LOCKOUT & ACCESS CONTROL (Legacy & Security Enhancement) ---
COMMAND_LOCKOUT = False
# user_id -> unlock_timestamp (0 = permanent until manual reset)
RESTRICTED_USERS: Dict[str, float] = {}

def is_command_locked() -> bool:
    return COMMAND_LOCKOUT

def set_command_lockout(state: bool):
    global COMMAND_LOCKOUT
    COMMAND_LOCKOUT = state

def is_user_restricted(user_id: str) -> bool:
    user_id = str(user_id)
    if user_id not in RESTRICTED_USERS:
        return False
    
    expiry = RESTRICTED_USERS[user_id]
    if expiry == 0:
        return True
        
    if time.time() > expiry:
        del RESTRICTED_USERS[user_id]
        return False
    return True

def restrict_access(user_id: str, minutes: int = 0):
    user_id = str(user_id)
    expiry = 0 if minutes == 0 else time.time() + (minutes * 60)
    RESTRICTED_USERS[user_id] = expiry

def lift_restriction(user_id: str):
    user_id = str(user_id)
    if user_id in RESTRICTED_USERS:
        del RESTRICTED_USERS[user_id]

class UserProfile(TypedDict):
    name: str
    rank: str
    department: str
    clearance: int
    station: str
    is_core_officer: bool

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

# Core Stations that boost authority
CORE_STATIONS = {
    "bridge": "Bridge", "舰桥": "Bridge", "舵手": "Bridge",
    "ops": "Operations", "运作": "Operations", "运作": "Operations",
    "engineering": "Engineering", "工程部": "Engineering", "轮机部": "Engineering",
    "chief": "Chief", "士官长": "Chief",
    "tactical": "Tactical", "战术部": "Tactical",
    "medical officer": "Medical", "医疗部": "Medical"
}

# LCARS Ranks Map (Keywords -> Standard Canon Rank)
# Star Trek uses Navy-style ranks.
RANK_MAP = {
    # Admirals
    "fleet admiral": "Fleet Admiral", "舰队上将": "Fleet Admiral", "舰队上将": "Fleet Admiral",
    "admiral": "Admiral", "上将": "Admiral", "上将": "Admiral",
    "vice admiral": "Vice Admiral", "中将": "Vice Admiral",
    "rear admiral": "Rear Admiral", "少将": "Rear Admiral",
    "commodore": "Commodore", "准将": "Commodore",
    
    # Officers
    "captain": "Captain", "舰长": "Captain", "上校": "Captain",
    "commander": "Commander", "大副": "Commander", "中校": "Commander",
    "lt. commander": "Lt. Commander", "少校": "Lt. Commander", "中校": "Lt. Commander",
    "lt. cmdr": "Lt. Commander",
    "lieutenant": "Lieutenant", "上尉": "Lieutenant",
    "lieutenant j.g.": "Lieutenant J.G.", "中尉": "Lieutenant J.G.",
    "lieutenant junior grade": "Lieutenant J.G.",
    "ensign": "Ensign", "少尉": "Ensign",
    
    # Enlisted & Others
    "crewman": "Crewman", "船员": "Crewman", "水兵": "Crewman", "下士": "Crewman",
    "civilian": "Civilian", "平民": "Civilian", "老百姓": "Civilian"
}

# Ordered list for hierarchy resolution (Highest to Lowest)
RANKS_HIERARCHY = [
    "Fleet Admiral", "Admiral", "Vice Admiral", "Rear Admiral", "Commodore",
    "Captain", "Commander", "Lt. Commander", 
    "Lieutenant", "Lieutenant J.G.", "Ensign", "Crewman", "Civilian"
]

# User to Profile mapping (Manual overrides)
USER_PROFILES: Dict[str, UserProfile] = {
    "2819163610": {
        "name": "AAAAA你米兰达🌈",
        "rank": "Admiral",
        "department": "SECTION_31",
        "clearance": 11,
        "station": "Command Center",
        "is_core_officer": True
    }
}

DEFAULT_PROFILE: UserProfile = {
    "name": "Unknown",
    "rank": "Ensign",
    "department": "OPERATIONS",
    "clearance": 1,
    "station": "General Duty",
    "is_core_officer": False
}

def resolve_station_from_title(title_text: str) -> Tuple[str, bool]:
    """Extracts station and determines if it's a core officer position."""
    if not title_text:
        return "General Duty", False
        
    title_lower = title_text.lower()
    for kw, station in CORE_STATIONS.items():
        if kw in title_lower:
            return station, True
    return "General Duty", False

def resolve_rank_from_title(title_text: str) -> str:
    """Attempts to match a title string to a Star Trek rank."""
    if not title_text:
        return "Ensign"
        
    title_lower = title_text.lower()
    # Check for keywords in the title
    for kw, standard_rank in RANK_MAP.items():
        if kw in title_lower:
            return standard_rank
            
    return "Ensign" # Default if no match found

def get_user_profile(user_id: str, nickname: Optional[str] = None, title: Optional[str] = None) -> UserProfile:
    """Returns the full LCARS profile for a user, syncing rank from title if available."""
    profile = USER_PROFILES.get(str(user_id))
    
    if not profile:
        # Dynamic profile based on title
        rank = resolve_rank_from_title(title)
        station, is_core = resolve_station_from_title(title)
        
        # 12-Level Security Clearance Mapping
        rank_to_clearance = {
            "Fleet Admiral": 12,
            "Admiral": 11,
            "Vice Admiral": 10,
            "Rear Admiral": 10,
            "Commodore": 9,
            "Captain": 8,
            "Commander": 7,
            "Lt. Commander": 6,
            "Lieutenant": 5,
            "Lieutenant J.G.": 4,
            "Ensign": 3,
            "Crewman": 2,
            "Civilian": 1
        }
        
        clearance = rank_to_clearance.get(rank, 1)
            
        # Station Boost: Core station officers get at least level 5 clearance for ops
        if is_core and clearance < 5:
            clearance = 5
            
        profile = {
            "name": nickname or "Unknown",
            "rank": rank,
            "department": "OPERATIONS", # Default department
            "clearance": clearance,
            "station": station,
            "is_core_officer": is_core
        }
    
    return profile

def format_profile_for_ai(profile: UserProfile) -> str:
    """Formats the profile for inclusion in AI prompts."""
    return (
        f"Name: {profile['name']}, "
        f"Rank: {profile['rank']}, "
        f"Station: {profile['station']}, "
        f"Core Officer: {'YES' if profile['is_core_officer'] else 'NO'}, "
        f"Clearance Level: {profile['clearance']}"
    )
