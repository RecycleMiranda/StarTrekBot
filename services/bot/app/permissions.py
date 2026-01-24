from typing import Dict, Optional, TypedDict

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
    "bridge": "Bridge", "桥位": "Bridge", "驾驶": "Bridge",
    "ops": "Operations", "运行": "Operations", "调度": "Operations",
    "engineering": "Engineering", "工程": "Engineering", "机舱": "Engineering",
    "chief": "Chief", "首席": "Chief",
    "tactical": "Tactical", "战术": "Tactical",
    "medical officer": "Medical", "医官": "Medical"
}

# LCARS Ranks Map (Keywords -> Standard Canon Rank)
# Star Trek uses Navy-style ranks.
RANK_MAP = {
    # Admirals
    "fleet admiral": "Fleet Admiral", "旗舰上将": "Fleet Admiral", "五星上将": "Fleet Admiral",
    "admiral": "Admiral", "上将": "Admiral", "将军": "Admiral",
    "vice admiral": "Vice Admiral", "中将": "Vice Admiral",
    "rear admiral": "Rear Admiral", "少将": "Rear Admiral",
    "commodore": "Commodore", "准将": "Commodore",
    
    # Officers
    "captain": "Captain", "舰长": "Captain", "上校": "Captain",
    "commander": "Commander", "副舰长": "Commander", "中校": "Commander",
    "lt. commander": "Lt. Commander", "少校": "Lt. Commander", "中校(副)": "Lt. Commander",
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
        "clearance": 4,
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
        
        # Simple clearance logic based on rank
        clearance = 1
        if rank in ["Fleet Admiral", "Admiral", "Vice Admiral", "Rear Admiral", "Commodore"]:
            clearance = 4 if rank == "Fleet Admiral" else 3
        elif rank in ["Captain", "Commander", "Lt. Commander"]:
            clearance = 2
            
        # Station Boost: Core station officers get at least level 2 clearance for ops
        if is_core and clearance < 2:
            clearance = 2
            
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
