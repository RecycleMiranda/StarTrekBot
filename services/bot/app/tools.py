import time
import datetime
import ast
import operator
import logging
import re

logger = logging.getLogger(__name__)

def get_status() -> dict:
    """
    Returns real-time starship status from ShipSystems.
    """
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    return {
        "ok": True,
        "message": "All systems nominal" if ss.alert_status.value == "NORMAL" else f"Condition: {ss.alert_status.value}",
        "shields_active": ss.shields_active,
        "shield_integrity": ss.shield_integrity,
        "alert": ss.alert_status.value,
        "subsystems": {k: v.value for k, v in ss.subsystems.items()}
    }

def get_subsystem_status(name: str) -> dict:
    """
    Returns the REAL-TIME status of a specific subsystem on THIS SHIP.
    Use this for queries like "Phaser status", "Shield status", "Engine status".
    Do not use `query_knowledge_base` for these inquiries.
    """
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    name = name.lower()
    if name in ss.subsystems:
        state = ss.subsystems[name].value
        return {
            "ok": True,
            "name": name,
            "state": state,
            "message": f"子系统 {name} 当前状态：{state}。"
        }
    return {"ok": False, "message": f"找不到子系统：{name}。"}

def set_subsystem_state(name: str, state: str, clearance: int) -> dict:
    """
    Sets the state of a specific subsystem (ONLINE/OFFLINE).
    Requires Level 11+ Clearance (Command Staff Only).
    """
    if clearance < 11:
         return {
            "ok": False,
            "message": f"Access denied. Subsystem control requires Command Level Authorization (Level 11). Current level: {clearance}.",
            "clearance_required": 11
        }
        
    from .ship_systems import get_ship_systems, SubsystemState
    ss = get_ship_systems()
    
    state_enum = SubsystemState.ONLINE if state.upper() in ["ONLINE", "ON", "TRUE"] else SubsystemState.OFFLINE
    message = ss.set_subsystem(name.lower(), state_enum)
    
    return {
        "ok": True,
        "message": message,
        "name": name,
        "new_state": state_enum.value
    }

def get_system_metrics() -> dict:
    """
    Returns real-time system resource usage (CPU, RAM, Disk).
    Uses psutil if available, otherwise falls back to basic heuristics.
    """
    metrics = {
        "ok": True,
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "disk_percent": 0.0,
        "uptime_seconds": 0,
        "method": "simulation"
    }
    
    # Method 1: Try psutil (Preferred)
    try:
        import psutil
        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        metrics["memory_percent"] = mem.percent
        disk = psutil.disk_usage('/')
        metrics["disk_percent"] = disk.percent
        metrics["uptime_seconds"] = int(time.time() - psutil.boot_time())
        metrics["method"] = "kernel_api" # Trek-style: 'Kernel API' = OS System Calls
        
        return {
            "ok": True,
            "metrics": metrics,
            "message": f"SYSTEM DIAGNOSTIC COMPLETE: CPU {metrics['cpu_percent']}%, MEM {metrics['memory_percent']}%, DISK {metrics['disk_percent']}%."
        }
    except ImportError:
        pass
        
    # Method 2: Fallback (Unix commands/Simulation)
    # Since we are on Mac/Linux usually, we could try limited commands, 
    # but for stability, if psutil is missing, we simulate 'Nominal' load.
    # This prevents the bot from crashing in diverse environments.
    
    # Simple simulated variation to make it feel alive
    import random
    metrics["cpu_percent"] = round(random.uniform(5.0, 15.0), 1)
    metrics["memory_percent"] = round(random.uniform(20.0, 30.0), 1) 
    metrics["disk_percent"] = 45.0
    metrics["uptime_seconds"] = int(time.time() - 1700000000) # Pseudo-uptime
    metrics["method"] = "heuristic_simulation"
    
    return {
        "ok": True,
        "metrics": metrics,
        "message": f"DIAGNOSTIC (HEURISTIC): CPU ~{metrics['cpu_percent']}%, MEM ~{metrics['memory_percent']}%."
    }

def get_time() -> dict:
    """
    Returns current system time.
    """
    now = datetime.datetime.now()
    return {
        "ok": True,
        "message": f"Current system time: {now.strftime('%H:%M:%S')} (CST)",
        "iso": now.strftime("%H:%M:%S"),
        "unix": int(time.time()),
        "tz": "CST"
    }

def calc(expr: str) -> dict:
    """
    Safely evaluates a basic mathematical expression.
    Only allows: numbers, +, -, *, /, (, ), ., and spaces.
    """
    # Whitelist characters
    if not all(c in "0123456789+-*/(). " for c in expr):
        return {"ok": False, "result": None, "error": "invalid_characters"}

    try:
        # Use a safe eval-like approach for basic math
        # ast.parse is safer than raw eval
        node = ast.parse(expr, mode='eval')
        
        # Simple recursive evaluator for specific nodes
        def eval_node(n):
            if isinstance(n, ast.Expression):
                return eval_node(n.body)
            if isinstance(n, ast.Num):
                return n.n
            if isinstance(n, ast.BinOp):
                left = eval_node(n.left)
                right = eval_node(n.right)
                ops = {
                    ast.Add: operator.add,
                    ast.Sub: operator.sub,
                    ast.Mult: operator.mul,
                    ast.Div: operator.truediv,
                }
                return ops[type(n.op)](left, right)
            if isinstance(n, ast.UnaryOp):
                operand = eval_node(n.operand)
                if isinstance(n.op, ast.USub):
                    return -operand
                return operand
            raise ValueError(f"Unsupported node: {type(n)}")

        result = eval_node(node)
        return {"ok": True, "result": result, "error": None}
    except Exception as e:
        logger.warning(f"Calculation failed: {e}")
        return {"ok": False, "result": None, "error": str(e)}

def verify_logical_consistency(logic_chain: str, clearance: int) -> dict:
    """
    Shadow Audit Tool: Verifies a proposed logical chain for technical consistency.
    Requires Level 5+ Clearance.
    """
    if clearance < 5:
        return {"ok": False, "message": "Access denied. Shadow Audit requires Level 5+."}
        
    # LOGIC: Perform a rapid heuristic check (placeholder for Phase 3 deep audit)
    # Check for contradictions like "offline" AND "active"
    warnings = []
    logic_lower = logic_chain.lower()
    
    if "offline" in logic_lower and "active" in logic_lower:
        warnings.append("CONTRADICTION: System cannot be both OFFLINE and ACTIVE.")
    if "damage" in logic_lower and "nominal" in logic_lower:
        warnings.append("CONTRADICTION: System cannot be DAMAGED and NOMINAL.")
        
    if warnings:
        return {
            "ok": True,
            "status": "CAUTION",
            "message": "Shadow Audit found potential inconsistencies:\n" + "\n".join(warnings),
            "verification_id": f"AUDIT-{int(time.time())}"
        }
    
    return {
        "ok": True,
        "status": "VERIFIED",
        "message": "Logical chain verified by Shadow Audit Node.",
        "verification_id": f"AUDIT-{int(time.time())}"
    }

def replicate(item_name: str, user_id: str, rank: str, clearance: int = 1) -> dict:
    """
    Replicates an item using replicator credits (1.8 Style: 5 credits per item).
    """
    from .quota_manager import get_quota_manager
    from .ship_systems import get_ship_systems
    
    ss = get_ship_systems()
    if not ss.is_subsystem_online("replicator"):
        return {"ok": False, "message": "无法完成：复制机系统下线。"}

    qm = get_quota_manager()
    cost = 5 # 1.8 Standard cost
    
    item_lower = item_name.lower()
    if any(k in item_lower for k in ["phaser", "weapon", "explosive", "rifles"]):
        if clearance < 9:
            return {"ok": False, "message": "权限不足拒绝访问"}
        cost = 50 # Weapons are expensive
    
    balance = qm.get_balance(user_id, rank)
    if balance < cost:
        return {"ok": False, "message": f"无法完成：你的配额不足。需要 {cost} 个配额，当前剩余 {balance} 个。"}
        
    qm.spend_credits(user_id, cost)
    return {
        "ok": True,
        "message": f"复制中…（消耗 {cost} 配额）\n[嘀—— 嘶嘶——]\n复制完成：{item_name}。",
        "item": item_name,
        "cost": cost
    }

def reserve_holodeck(program_name: str, duration_hours: float, user_id: str, rank: str, clearance: int = 1, disable_safety: bool = False) -> dict:
    """
    Reserves a holodeck session with safety protocol check.
    """
    from .quota_manager import get_quota_manager
    qm = get_quota_manager()
    
    # Safety Protocol Check (12-level)
    if disable_safety and clearance < 9:
         return {
            "ok": False,
            "message": f"Access denied. Disabling safety protocols is a restricted Senior Officer command (Level 9 Required). Current level: {clearance}.",
            "cost": 0,
            "remaining": qm.get_balance(user_id, rank)
        }
        
    cost = int(duration_hours * 50)
    if disable_safety: cost += 100 # Risk surcharge
    
    if qm.spend_credits(user_id, cost):
        status = "SAFETY PROTOCOLS DISABLED" if disable_safety else "Safety protocols active"
        return {
            "ok": True,
            "message": f"Holodeck reserved: '{program_name}' ({duration_hours}h). {status}.",
            "cost": cost,
            "remaining": qm.get_balance(user_id, rank)
        }
    else:
        return {
            "ok": False,
            "message": "Insufficient holodeck energy credits.",
            "cost": cost,
            "remaining": qm.get_balance(user_id, rank)
        }

def get_ship_schematic(ship_name: str, clearance: int = 1) -> dict:
    """
    Retrieves ship technical schematics. Requires Level 4+ for detailed specs.
    """
    ship_db = {
        "Constitution": {
            "class": "Heavy Cruiser",
            "length": "289m",
            "decks": 21,
            "crew": 430,
            "max_warp": 8.0,
            "summary": "The flagship of the mid-23rd century, iconic for its exploration missions."
        },
        "Sovereign": {
            "class": "Heavy Cruiser / Explorer",
            "length": "685m",
            "decks": 24,
            "crew": 700,
            "max_warp": 9.985,
            "summary": "State-of-the-art combat and exploration vessel of the late 24th century."
        },
        "Galaxy": {
            "class": "Explorer",
            "length": "642m",
            "decks": 42,
            "crew": 1012,
            "max_warp": 9.6,
            "summary": "A massive deep-space explorer designed for long-term diplomatic and scientific missions."
        }
    }
    
    ship_key = next((k for k in ship_db if k.lower() in ship_name.lower()), "Generic")
    
    if clearance < 4 and ship_key != "Generic":
        return {
            "ok": False,
            "message": f"Access denied. Technical schematics for {ship_key} class require Clearance Level 4. Current level: {clearance}.",
            "clearance_required": 4
        }
        
    data = ship_db.get(ship_key)
    if not data:
        return {"ok": False, "message": f"No records found for class: {ship_name}."}
        
    return {
        "ok": True,
        "message": f"RECORD RETRIEVED: {ship_key} Class {data['class']}. Length: {data['length']}. Max Warp: {data['max_warp']}. {data['summary']}",
        "title": f"TECHNICAL SCHEMATIC: {ship_key} CLASS",
        "sections": [
            {"category": "General Specs", "content": f"Class: {data['class']}\nLength: {data['length']}\nDecks: {data['decks']}"},
            {"category": "Tactical/Propulsion", "content": f"Max Warp: {data['max_warp']}\nCrew Compliment: {data['crew']}"},
            {"category": "Mission Profile", "content": data['summary']}
        ]
    }

def query_knowledge_base(query: str, session_id: str, is_chinese: bool = False, max_words: int = 500) -> dict:
    """
    Searches the extensive local MSD Knowledge Base (Mega-Scale) for HISTORICAL, TECHNICAL, or ENCYCLOPEDIC data.
    
    CRITICAL: DO NOT use this tool for requesting CURRENT STATUS of the ship (e.g. "Shield status", "Phaser status").
    For current ship status, use `get_subsystem_status` or `get_status` instead.
    
    Scans the markdown files in the msd_knowledge_base directory.
    """
    import os
    # Use relative path so it works inside Docker
    KB_DIR = os.path.join(os.path.dirname(__file__), "msd_knowledge_base")
    
    hits = []
    
    try:
        if not os.path.exists(KB_DIR):
             return {"ok": False, "message": f"Knowledge Base directory not found at {KB_DIR}.", "hits": []}

        # Priority scan: Index first
        files = sorted([f for f in os.listdir(KB_DIR) if f.endswith(".md")])
        
        # Simple keyword matching (enhanced logic could go here)
        query_lower = query.lower()
        keywords = query_lower.split()
        
        for filename in files:
            path = os.path.join(KB_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                
            score = 0
            content_lower = content.lower()
            
            # 1. Literal Multi-word match (High confidence)
            if query_lower in content_lower and len(keywords) > 1:
                score += 15
            elif query_lower in content_lower:
                score += 8
            
            # 2. Keyword density
            match_count = 0
            for k in keywords:
                if len(k) < 3: continue # Skip short words
                if k in content_lower:
                    score += 2
                    match_count += 1
            
        # 3. Technical Density Bonus (Specs, Class, Warp, etc)
            tech_keywords = ["class", "specs", "specifications", "warp", "crew", "tactical", "registry", "history"]
            for tk in tech_keywords:
                if tk in content_lower:
                    score += 1

            # 4. Technical Spec & Jargon Scan (Full-Text)
            # If a document is dominated by maintenance/hardware detail but lacks general overview,
            # we penalize it for broad queries.
            manual_jargon = [
                "pylon", "connector", "umbilical", "purlin", "pumping", "exhaust", "ventilation", 
                "hatch", "circuit", "coupling", "bolting", "phaser bank", "shield frequency", 
                "emitter", "graviton", "polarity", "1440 banks"
            ]
            jargon_count = sum(1 for j in manual_jargon if j in content_lower)
            
            # Overview Boost
            overview_keywords = ["overview", "summary", "history", "introduction", "background", "概括", "历史", "概览"]
            overview_score = sum(3 for o in overview_keywords if o in content_lower)
            score += overview_score
            
            # 6. SUBJECT ANCHORING (NEW): 
            # Check if the query itself is a significant subject in the snippet area.
            # If the keywords are only mentioned in a header but the body is about something else.
            primary_subject_match = content_lower.count(query_lower)
            if primary_subject_match >= 1:
                score += 5
            
            # Penalize if the snippet area (first 500 chars) contains a different dominant ship class
            known_classes = ["galaxy", "intrepid", "sovereign", "defiant", "constitution", "excelsior"]
            dominant_class = next((sc for sc in known_classes if sc in content_lower[:500]), None)
            if dominant_class and dominant_class not in query_lower:
                score -= 8 # Neutralize purely coincidental alignment with a different ship manual

            # 5. CONTEXT MISMATCH PENALTY (Ship Class vs. Station Manual)
            # If the user asks for a ship class, but the document is an engineering manual for a station.
            ship_classes = ["galaxy", "intrepid", "excelsior", "sovereign", "constellation", "nebula"]
            is_class_query = any(sc in query_lower for sc in ship_classes) or "级" in query_lower
            is_station_doc = any(sd in content_lower for sd in ["station msd", "mars station", "msd station"])
            
            if is_class_query and is_station_doc:
                # Count specifically HOW MANY times the specific ship class is mentioned
                target_class = next((sc for sc in ship_classes if sc in query_lower), "galaxy")
                mentions = content_lower.count(target_class)
                # If mentioned < 3 times in a station doc, it's a "mention", not a "description".
                if mentions < 3:
                    score -= 20 # Disqualifying penalty
                    logger.info(f"[KB] Penalty: '{filename}' mentions '{target_class}' only {mentions} times in a Station Doc.")

            if jargon_count >= 5: # Heavy manual content
                score -= 10 

            if score >= 12: # Increased Substance Threshold
                # Extract relevant snippet
                idx = content_lower.find(keywords[0]) if keywords else -1
                start = max(0, idx - 200)
                end = min(len(content), idx + 800) # Larger snippet for synthesis
                snippet = content[start:end].replace("\n", " ") + "..."
                hits.append({
                    "file": filename,
                    "score": score,
                    "size": len(content),
                    "snippet": snippet,
                    "full_path": path,
                    "jargon_score": jargon_count
                })
        
        # Sort by score, then by size (prefer larger documents for broad queries)
        hits.sort(key=lambda x: (x.get("score", 0), x.get("size", 0)), reverse=True)
        
        # QUALITY FILTER: Detect broad queries (including Chinese compounds)
        # Broad query: ship name only or class name (e.g. "银河级", "Galaxy class")
        # Also catch "List of..." queries which require comprehensive data
        is_broad_query = len(query.split()) <= 5 or any(kw in query_lower for kw in ["级", "class", "starship", "list", "all", "所有", "列表"])
        
        if is_broad_query and hits:
            top_hit = hits[0]
            # If top hit is still a technical manual snippet despite weighting
            if top_hit["size"] < 1500 or top_hit["jargon_score"] >= 3:
                logger.info(f"[KB] Hit '{top_hit['file']}' is disqualified for broad query '{query}' (Jargon: {top_hit['jargon_score']}). Falling back.")
                return search_memory_alpha(query, session_id, is_chinese, max_words=max_words)

        # Final filtering
        top_hits = [h for h in hits if h["score"] >= 12][:3]
        
        if not top_hits:
            logger.info(f"[KB] No high-confidence local hits for '{query}' (Top score: {hits[0]['score'] if hits else 0}). Auto-falling back to Memory Alpha.")
            
            # Auto-fallback to Memory Alpha (Polymath Logic)
            # ROUTING LOGIC: If query asks for a LIST or CATEGORY, use DIRECT ACCESS (Chunking) to avoid truncation.
            is_explicit_list = any(k in query.lower() for k in ["list", "enumerate", "all", "列表", "名单", "所有", "names", "who are", "which are", "categor", "index", "captains", "ships", "classes"])
            if is_explicit_list:
                logger.info("[KB] Detected List Query -> Routing to Direct Chunking Protocol")
                return access_memory_alpha_direct(query, session_id, is_chinese)
            else:
                return search_memory_alpha(query, session_id, is_chinese, max_words=max_words)
            
        # Construct structured items for rendering
        results = []
        digest = f"FOUND {len(hits)} RECORDS IN ARCHIVE:\n"
        
        for i, hit in enumerate(top_hits):
            item_id = f"{i+1}{chr(65+i)}" # 1A, 2B, etc.
            results.append({
                "id": item_id,
                "type": "text",
                "title": f"ARCHIVE: {hit['file']}",
                "content": hit['snippet'],
                "source": "LOCAL ARCHIVE"
            })
            digest += f"\n--- [{item_id}: {hit['file']}] (Source: LOCAL ARCHIVE) ---\n{hit['snippet']}\n"
            
        return {
            "ok": True,
            "items": results,
            "message": digest,
            "count": len(hits),
            "source": "LOCAL ARCHIVE"
        }

    except Exception as e:
        logger.error(f"KB Query failed: {e}")
        return {"ok": False, "message": f"Archive query error: {e}"}

def search_memory_alpha(query: str, session_id: str, is_chinese: bool = False, max_words: int = 500, continuation_hint: str = None) -> dict:
    """
    Uses Google Search (via Gemini Grounding) to query Memory Alpha.
    Fallback for when local KB is insufficient.
    """
    from .config_manager import ConfigManager
    from google import genai
    from google.genai import types
    from .rp_engine_gemini import strip_conversational_filler
    
    config = ConfigManager.get_instance()
    api_key = config.get("gemini_api_key", "")
    logger.info(f"[Tools] search_memory_alpha called. Query: {query}, MaxWords: {max_words}, Hint: {continuation_hint}")
    
    if not api_key:
         logger.warning("[Tools] External search offline: API Key missing")
         return {"ok": False, "message": "External search offline (API Key missing)."}
         
    try:
        client = genai.Client(api_key=api_key)
        
        # Upgraded Search Prompt: Deep Factification & Archetype Protocol
        lang_ext = " produce result in SYNCHRONIZED BILINGUAL format (Interleaved English and Chinese lines, NO [EN]/[ZH] prefixes)" if is_chinese else ""
        
        hint_text = f"\nCONTINUATION HINT: {continuation_hint}. USE THIS TO SKIP ALREADY FOUND ITEMS AND FOCUS ON REMAINING DATA." if continuation_hint else ""
        
        # Domain Restriction: Strictly Memory Alpha
        search_prompt = (
            f"Using site:memory-alpha.fandom.com, perform a DEEP SCAN for the query: {query}.{hint_text}\n"
            "TASK: Locate specific technical metrics, counts, and variables.\n"
            "MANDATORY: You MUST start your output with '^^DATA_START^^' before the actual content.\n"
            "ARCHETYPE PROTOCOL: ONLY apply if '{query}' is a broad, un-quantified technology. "
            "If '{query}' is a specific entity (e.g., 'Starfleet Command', 'Tal Shiar'), FOCUS EXCLUSIVELY ON THAT ENTITY. "
            "Do NOT hallucinate or pivot to 'Galaxy-class' unless it is directly being compared in the text.\n"
            "INSTRUCTIONS:\n"
            "1. Scan for primary entity definitions and historical metrics.\n"
            f"2. ENUMERATION PROTOCOL: If query asks for a LIST or ENUMERATION (e.g., 'List all classes'), you MUST provide a comprehensive index of NAMES found. In list mode, PRIORITIZE QUANTITY OF ITEMS over character depth. Strip all descriptions, dates, and minor details. Only output the Name and Registry (if available) to maximize the count within the output buffer. Capacity is expanded up to {max_words} words.\n"
            "   - NOMENCLATURE: Use '[Name] class' format (e.g., 'Galaxy class'). DO NOT use hyphens '-' between Name and class.\n"
            "   - LANGUAGE: English is the PRIMARY language. Format entries as: [English Name] ([Chinese Name]) (e.g., 'Constitution class (宪法级)').\n"
            "3. LOCATION PROTOCOL: If query targets a location (Where is...?), FOCUS on specific landmarks, neighborhoods, or facilities (e.g., 'The Presidio' instead of just 'San Francisco').\n"
            "4. NO RECURSION: Do NOT answer that an entity is located at itself (e.g., Starfleet Command is at Starfleet Command).\n"
            f"5. Return a high-density technical summary (standard: under 500 words, lists: up to {max_words} words),{lang_ext}.\n"
            "6. Extract the DIRECT URL of the primary illustrative image from static.wikia.nocookie.net.\n"
            "7. NEGATIVE CONSTRAINT: Do NOT use conversational intros like 'Here is a list:'. Start directly with the first item.\n"
        )
        
        # Enable Google Search Tool 
        google_search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=search_prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.1,
                max_output_tokens=8192
            )
        )
        
        text_content = response.text if response.text else "Subspace interference detected. No textual records found."
        
        # Image Extraction Logic
        import re
        img_url = None
        # Look for Wikia/Fandom static image URLs in the response text
        match = re.search(r'https?://static\.wikia\.nocookie\.net/memoryalpha/images/[^ \n]+', text_content)
        if match:
            img_url = match.group(0).rstrip('.)')
            # Clean technical response of the URL if it was included in the text
            text_content = text_content.replace(img_url, "").strip()
        
        # Strip conversational filler at the harvest source
        text_content = strip_conversational_filler(text_content)
        
        # Return structured list for the render engine
        return {
            "ok": True,
            "items": [
                {
                    "id": "1A",
                    "type": "hybrid",
                    "content": text_content,
                    "title": f"RECORD: {query.upper()}",
                    "image_url": img_url,
                    "source": "MEMORY ALPHA"
                }
            ],
            "message": f"EXTERNAL DATABASE (MEMORY ALPHA) RESULT:\n{text_content}",
            "source": "MEMORY ALPHA"
        }

    except Exception as e:
        logger.error(f"Memory Alpha search failed: {e}")
        return {"ok": False, "message": f"Subspace communication error: {e}"}

def access_memory_alpha_direct(query: str, session_id: str, is_chinese: bool = False, chunk_index: int = 0) -> dict:
    """
    Directly accesses Memory Alpha, bypassing summary logic.
    Returns VERBATIM translated content or a list of ambiguous targets.
    Supports CHUNKED fetching for long articles.
    """
    import os
    import re
    from .config_manager import ConfigManager
    from google import genai
    from google.genai import types
    from .rp_engine_gemini import strip_conversational_filler, NeuralEngine
    
    config = ConfigManager.get_instance()
    api_key = config.get("gemini_api_key", "")
    
    if not api_key:
        return {"ok": False, "message": "Neural link offline (API Key missing)."}

    # --- EASTER EGG: Enterprise Registry Challenge ---
    q_norm = query.lower().strip()
    if q_norm in ["enterprise", "uss enterprise", "企业号", "进取号", "星舰企业号"]:
        msg = (
            "⚠️ FEDERATION DATABASE QUERY EXCEPTION\n\n"
            "There are 8 Federation starships bearing this name.\n"
            "Please specify registry number.\n\n"
            "有 8 艘联邦星舰以此命名。\n"
            "请输入具体舷号。"
        )
        return {
            "ok": False,
            "status": "ambiguous",
            "message": msg
        }
    # -------------------------------------------------

    # Input Normalization for Search (Map Chinese to English for Memory Alpha)
    if "企业号" in query or "进取号" in query:
        query = query.replace("企业号", "Enterprise").replace("进取号", "Enterprise")
    
    # PROTOCOL TOKEN STRIPPING: Remove navigational keywords that might confuse the search engine
    search_query = query
    for token in ["LIST", "INDEX", "ALL", "FULL", "VERBATIM", "列出", "列表", "所有", "全部"]:
        # Case-insensitive replacement of whole words/tokens
        search_query = re.sub(rf'\b{token}\b', '', search_query, flags=re.IGNORECASE).strip()
    
    logger.info(f"[Tools] Search normalization: '{query}' -> '{search_query}'")

    try:
        client = genai.Client(api_key=api_key)
        
        # Enable Google Search Tool 
        google_search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        # Prompt for navigation/fetching with CHUNKING support - DECISIVE SELECTION PROTOCOL
        nav_prompt = (
            f"Navigate to memory-alpha.fandom.com and locate the technical entry for '{search_query}'.\n"
            "TASK: Locate the primary technical database entry. If multiple versions exist (Prime, Mirror, Alternate Universe), YOU MUST AUTO-SELECT the Prime Universe version or the most comprehensive list page.\n"
            "OUTPUT FORMAT (STRICT):\n"
            "1. Output 'STATUS: FOUND'\n"
            "2. Output 'TOTAL_CHUNKS: [num]' and 'HAS_MORE: [TRUE/FALSE]'\n"
            "3. Output 'IMAGE: [URL]' for the main infobox image (only on Chunk 0)\n"
            "4. Output 'TEXT_START' then provide the VERBATIM technical text of the entry.\n"
            f"- CHUNK PROTOCOL: Current request is for CHUNK {chunk_index}. Ensure you are fetching from the single most relevant page identified.\n"
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=nav_prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.0,
                max_output_tokens=8192
            )
        )
        
        raw_output = response.text if response.text else ""
        
        if "STATUS: AMBIGUOUS" in raw_output:
            # Extract candidates
            lines = raw_output.split('\n')
            candidates = [line.strip("- *") for line in lines if "STATUS" not in line and line.strip()]
            return {
                "ok": False,
                "status": "ambiguous",
                "candidates": candidates[:5],
                "message": f"Ambiguous query. Please specify:\n" + "\n".join([f"- {c}" for c in candidates[:5]])
            }
            
        elif "STATUS: FOUND" in raw_output:
            # Extract Metadata
            img_url = None
            img_match = re.search(r'IMAGE: (https?://[^ \n]+)', raw_output)
            if img_match:
                img_url = img_match.group(1).rstrip('.)')
            
            has_more = "HAS_MORE: TRUE" in raw_output.upper()
            total_chunks_match = re.search(r'TOTAL_CHUNKS: (\d+)', raw_output)
            total_chunks = int(total_chunks_match.group(1)) if total_chunks_match else 1
            
            # Clean content body: Remove metadata lines but keep the rest
            content_body = raw_output
            if "TEXT_START" in content_body:
                content_body = content_body[content_body.find("TEXT_START") + 10:].strip()
            # AGGRESSIVE CLEANING FALLBACK
            for marker in ["STATUS: FOUND", "IMAGE:", "HAS_MORE:", "TOTAL_CHUNKS:", "CHUNK PROTOCOL:", "TEXT_START"]:
                # Match from start of line to end of line for markers
                content_body = re.sub(rf'^{marker}.*$', '', content_body, flags=re.MULTILINE | re.IGNORECASE)
            content_body = content_body.strip()
            
            # Translate Verbatim
            engine = NeuralEngine() 
            # Note: NeuralEngine usually needs config, but get_instance logic isn't there. 
            # We'll just instantiate and it pulls from ConfigManager inside its methods if written that way? 
            # Checking rp_engine_gemini.py... NeuralEngine.__init__ calls ConfigManager.get_instance(). Correct.
            
            translated_content = engine.translate_memory_alpha_content(content_body, is_chinese)
            
            # Include a generous snippet (or whole content) in 'message' 
            # so the AI loop agent and synthesist see the actual data.
            # 4000 chars is ~1000-1500 tokens, which is safe for the context.
            display_snippet = (translated_content[:4000] + "...") if len(translated_content) > 4000 else translated_content
            
            return {
                "ok": True,
                "status": "content",
                "has_more": has_more,
                "total_chunks": total_chunks,
                "chunk_index": chunk_index,
                "items": [
                    {
                        "id": "1A",
                        "type": "hybrid",
                        "content": translated_content,
                        "title": f"RECORD: {query.upper()} (PART {chunk_index+1}/{total_chunks})",
                        "image_url": img_url if chunk_index == 0 else None,
                        "source": "MEMORY ALPHA"
                    }
                ],
                "message": f"FEDERATION DATABASE RECORD: {query.upper()} (CHUNK {chunk_index+1}/{total_chunks})\n\nDATA_PREVIEW:\n{display_snippet}",
                "source": "MEMORY ALPHA"
            }
        else:
            return {"ok": False, "message": "Unable to lock onto a valid Memory Alpha frequency. (No clear data found)"}

    except Exception as e:
        logger.error(f"Direct Access failed: {e}")
        return {"ok": False, "message": f"Subspace communication error: {e}"}

def get_historical_records(topic: str) -> dict:
    """
    Retrieves library computer historical records.
    """
    archives = {
        "TOS": "The Original Series (2260s): Exploring the final frontier with Captain Kirk and Mr. Spock.",
        "TNG": "The Next Generation (2360s): Strategic diplomacy and exploration under Captain Picard.",
        "DS9": "Deep Space 9: Frontier life and the Dominion War on a Cardassian-built station.",
        "VOY": "Voyager: The long journey from the Delta Quadrant back to Federation space.",
        "Federation": "The United Federation of Planets: Founded in 2161 by Humans, Vulcans, Andorians, and Tellarites."
    }
    
    found_key = next((k for k in archives if k.lower() in topic.lower()), None)
    
    if not found_key:
        return {"ok": False, "message": "Insufficient data in historical archives for specified topic."}
        
    return {
        "ok": True,
        "message": f"RECORD RETRIEVED: {archives[found_key]}"
    }

def personal_log(content: str, user_id: str) -> dict:
    """
    Records a personal log. Grants random credits (2h cooldown).
    """
    from .quota_manager import get_quota_manager
    qm = get_quota_manager()
    
    result = qm.record_log(user_id)
    return result

# --- SELF-DESTRUCT & AUTH TOOLS ---

# --- SELF-DESTRUCT TOOLS (3-Step Flow) ---

def get_destruct_status(session_id: str) -> dict:
    """
    Query the current self-destruct sequence status.
    Returns state, remaining time, authorization status, etc.
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return dm.get_status(session_id)


async def initialize_self_destruct(seconds: int, silent: bool, user_id: str, clearance: int, session_id: str, notify_callback, language: str = "en") -> dict:
    """
    Step 2 (Version 1.8): Initialize and start the self-destruct countdown.
    Requires Level 9+. This will only succeed if 3 unique signatures have been 
    previously collected via 'authorize_self_destruct' (or if called by Level 11+).
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return await dm.initialize(session_id, user_id, clearance, duration=seconds, silent=silent, language=language, notify_callback=notify_callback)


def authorize_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """
    Step 1 (Version 1.8): Record an authorization signature. 
    Requires Level 8+. 3 unique signatures must be recorded BEFORE calling 'initialize'.
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return dm.authorize(session_id, user_id, clearance)


async def activate_self_destruct(user_id: str, clearance: int, session_id: str, notify_callback) -> dict:
    """
    Alternate trigger for Step 2. In Version 1.8, 'initialize' handles activation.
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return await dm.initialize(session_id, user_id, clearance, notify_callback=notify_callback)


def authorize_cancel_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """
    Step 1 (Version 1.8): Record an authorization signature to cancel self-destruct.
    Requires Level 11+. 3 unique signatures must be recorded BEFORE calling 'confirm_cancel'.
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return dm.authorize_cancel(session_id, user_id, clearance)


def confirm_cancel_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """
    Step 2 (Version 1.8): Execute the self-destruct cancellation.
    Requires Level 9+. This will only succeed if 3 unique signatures have been 
    previously collected via 'authorize_cancel_self_destruct' (or if called by Level 11+).
    """
    from .self_destruct import get_destruct_manager
    dm = get_destruct_manager()
    return dm.confirm_cancel(session_id, user_id, clearance)


# Legacy aliases for backward compatibility
def initiate_self_destruct(seconds: int, silent: bool, user_id: str, clearance: int, session_id: str, notify_callback) -> dict:
    """Legacy wrapper - redirects to initialize_self_destruct."""
    # Note: legacy caller might not provide notify_callback, but dispatcher now always does
    return initialize_self_destruct(seconds, silent, user_id, clearance, session_id, notify_callback)


def abort_self_destruct(user_id: str, clearance: int, session_id: str) -> dict:
    """Legacy wrapper - redirects to authorize_cancel_self_destruct."""
    return authorize_cancel_self_destruct(user_id, clearance, session_id)


def authorize_sequence(action_type: str, user_id: str, clearance: int, session_id: str) -> dict:
    """
    Legacy wrapper for backward compatibility.
    Maps action types to new functions.
    """
    if action_type in ["SELF_DESTRUCT", "self_destruct"]:
        return authorize_self_destruct(user_id, clearance, session_id)
    elif action_type in ["ABORT_DESTRUCT", "abort_destruct", "CANCEL"]:
        return authorize_cancel_self_destruct(user_id, clearance, session_id)
    else:
        return {"ok": False, "message": f"Unknown action type: {action_type}"}


# --- SELF-REPAIR TOOLS ---

def enter_repair_mode(user_id: str, clearance: int, session_id: str, target_module: str = None) -> dict:
    """
    Enter repair/diagnostic mode for a specific module.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required for repair mode."}
    
    from .repair_agent import get_repair_agent
    from . import repair_tools
    agent = get_repair_agent()
    session = agent.start_session(session_id, user_id, target_module)
    
    msg = f"REPAIR MODE ACTIVATED. "
    if target_module:
        from . import repair_tools
        accessible, reason = repair_tools.is_module_accessible(target_module)
        if accessible:
            msg += f"Target module: {target_module}. Ready for diagnostic commands."
        else:
            msg += f"Warning: {reason}"
    else:
        msg += f"No target module specified. Available modules: {', '.join(repair_tools.MODIFIABLE_MODULES)}"
    
    return {
        "ok": True,
        "in_repair_mode": True,
        "target_module": target_module,
        "message": msg
    }


def exit_repair_mode(session_id: str) -> dict:
    """Exit repair mode."""
    from .repair_agent import get_repair_agent
    agent = get_repair_agent()
    return agent.end_session(session_id)


def read_repair_module(module_name: str, clearance: int) -> dict:
    """
    Read a module's source code in repair mode.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required."}
    
    from . import repair_tools
    return repair_tools.read_module(module_name)


def get_repair_module_outline(module_name: str, clearance: int) -> dict:
    """
    Get structural outline of a module.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required."}
    
    from . import repair_tools
    return repair_tools.get_module_outline(module_name)


def rollback_repair_module(module_name: str, clearance: int, backup_index: int = 0) -> dict:
    """
    Rollback a module to a previous backup.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required."}
    
    from . import repair_tools
    return repair_tools.rollback_module(module_name, backup_index)


def list_repair_backups(module_name: str, clearance: int) -> dict:
    """
    List available backups for a module.
    Requires Level 12 clearance.
    """
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Level 12 clearance required."}
    
    from . import repair_tools
    return repair_tools.list_backups(module_name)


async def ask_about_code(question: str, user_id: str, clearance: int, session_id: str) -> dict:
    """
    Ask a question about the codebase. The agent will read relevant code and answer.
    Requires Level 10+ for reading, Level 12+ for modifications.
    """
    from .repair_agent import get_repair_agent
    agent = get_repair_agent()
    return await agent.answer_code_question(session_id, user_id, question, clearance)


def is_code_question(message: str) -> bool:
    """Check if a message is asking about code."""
    from .repair_agent import get_repair_agent
    agent = get_repair_agent()
    return agent.is_code_related_question(message)


# --- ACCESS CONTROL TOOLS ---


def lockdown_authority(state: bool, user_id: str, clearance: int, session_id: str) -> dict:
    """
    Toggles global command lockout. Requires Level 12 (Solo) or Level 10+ (Multi-Sig).
    """
    from .permissions import set_command_lockout
    from .auth_system import get_auth_system
    
    if clearance >= 12:
        set_command_lockout(state)
        return {"ok": True, "message": f"COMMAND LOCKOUT {'ACTIVATED' if state else 'DEACTIVATED'}: Override by Level 12 officer."}
        
    if clearance < 10:
        return {"ok": False, "message": "ACCESS DENIED: Minimum Clearance Level 10 required for command lockout modification."}
        
    # Multi-sig for Level 10-11
    auth = get_auth_system()
    action = "LOCKOUT_ON" if state else "LOCKOUT_OFF"
    res = auth.request_action(session_id, action, user_id, clearance, {"state": state})
    
    if res.get("authorized"):
        set_command_lockout(state)
        return {"ok": True, "message": f"COMMAND LOCKOUT {'ACTIVATED' if state else 'DEACTIVATED'}: Multi-signature authorization complete."}
        
    return res

def restrict_user(target_mention: str, duration_minutes: int, user_id: str, clearance: int) -> dict:
    """
    Restricts a user from accessing the computer. Target is identified via @mention (QQ ID).
    Requires Level 8+.
    """
    from .permissions import restrict_access
    
    if clearance < 8:
        return {"ok": False, "message": "ACCESS DENIED: Senior Officer clearance (Level 8) required for access restriction."}
        
    # Extract QQ ID from mention (usually in format like [CQ:at,qq=123456789])
    target_id_match = re.search(r"\d+", target_mention)
    if not target_id_match:
        return {"ok": False, "message": f"Unable to identify target user from: {target_mention}"}
        
    target_id = target_id_match.group(0)
    restrict_access(target_id, duration_minutes)
    
    msg = f"ACCESS RESTRICTION ENFORCED: User {target_id} restricted for {duration_minutes if duration_minutes > 0 else 'infinite'} cycles."
    return {"ok": True, "message": msg, "target_id": target_id}

def lift_user_restriction(target_mention: str, user_id: str, clearance: int) -> dict:
    """
    Lifts an access restriction. Requires Level 8+.
    """
    from .permissions import lift_restriction
    
    if clearance < 8:
        return {"ok": False, "message": "ACCESS DENIED: Senior Officer clearance required to lift restriction."}
        
    target_id_match = re.search(r"\d+", target_mention)
    if not target_id_match:
        return {"ok": False, "message": "Unable to identify target user."}
        
    target_id = target_id_match.group(0)
    lift_restriction(target_id)
    return {"ok": True, "message": f"ACCESS RESTORED: Restriction lifted for user {target_id}."}

def update_user_profile(target_mention: str, field: str, value: str, user_id: str, clearance: int) -> dict:
    """
    Updates a specific field in a user's profile. Requires Level 12.
    Allowed fields: rank, clearance, station, department, is_core_officer.
    """
    from .permissions import update_user_profile_data
    
    if clearance < 12:
        return {"ok": False, "message": "ACCESS DENIED: Admiralty clearance (Level 12) required for personnel profile modification."}
        
    target_id_match = re.search(r"\d+", target_mention)
    if not target_id_match:
        return {"ok": False, "message": "Unable to identify target user profile."}
        
    target_id = target_id_match.group(0)
    
    # Field Validation
    allowed_fields = ["rank", "clearance", "station", "department", "is_core_officer"]
    if field not in allowed_fields:
        return {"ok": False, "message": f"Invalid profile field: {field}. Allowed: {', '.join(allowed_fields)}"}
        
    # Synchronization logic: If rank is updated, clearance should usually follow (AI handles this via prompt mostly, but we can nudge)
    updates = {field: value}
    
    # Special handling for boolean
    if field == "is_core_officer":
        updates[field] = str(value).lower() == "true"
        
    update_user_profile_data(target_id, updates)
    
    return {
        "ok": True, 
        "message": f"PERSONNEL RECORD UPDATED: User {target_id}, Field: {field}, New Value: {value}. Protocols refreshed.",
        "target_id": target_id
    }

def query_technical_database(query: str) -> dict:
    """
    Queries the Star Trek Technical Knowledge Base (TNG & DS9 Manuals).
    Searches clean text manuals and the unified glossary.
    """
    import os
    # Resolve the data directory (root of the project)
    # This file is at /app/services/bot/app/tools.py
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    
    files_to_search = [
        os.path.join(project_root, "tng_manual_clean.txt"),
        os.path.join(project_root, "ds9_manual_clean.txt"),
        os.path.join("/Users/wanghaozhe/.gemini/antigravity/brain/043b8282-3619-44f4-9467-95077493a8b7", "Star_Trek_Technical_Glossary.md")
    ]
    
    results = []
    query_lower = query.lower()
    
    for fpath in files_to_search:
        if not os.path.exists(fpath):
            continue
        
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Find all occurrences with context
                # Simple implementation: split by lines and find lines containing query
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if query_lower in line.lower():
                        # Get 3 lines of context
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        snippet = "\n".join(lines[start:end])
                        source = os.path.basename(fpath)
                        results.append(f"Source: {source}\n{snippet}\n---")
                        
                        if len(results) >= 5: # Limit results
                            break
                if len(results) >= 5:
                    break
        except Exception as e:
            logger.warning(f"Failed to search {fpath}: {e}")
            
    if not results:
        return {"ok": False, "message": f"Insufficient data found for query: '{query}' in technical database."}
        
    return {
        "ok": True,
        "message": "DATA RETRIEVED FROM TECHNICAL ARCHIVES:\n" + "\n".join(results),
        "title": "TECHNICAL DATABASE QUERY RESULT",
        "sections": [{"category": "Search Results", "content": "\n".join(results)}]
    }

def get_personnel_file(target_mention: str, user_id: str, is_chinese: bool = False) -> dict:
    """
    Retrieves and visualizes a personnel file card.
    """
    from .permissions import get_user_profile
    from .quota_manager import get_quota_manager
    from . import visual_core
    from PIL import Image
    import httpx
    import io
    
    # 1. Resolve Target ID
    target_id = str(user_id) # Default to self
    nickname = None
    
    if target_mention:
        # Extract ID from mention [CQ:at,qq=12345] or just text
        match = re.search(r"\d+", target_mention)
        if match:
            target_id = match.group(0)
    
    # 2. Get Profile Data
    limit_break = (target_id == "2819163610")
    profile = get_user_profile(target_id)
    
    # 3. Get Quota Balance
    qm = get_quota_manager()
    # Rank needed for quota lookup, extract from profile
    rank = profile.get("rank", "Ensign")
    balance = qm.get_balance(target_id, rank)
    
    # 4. Prepare Data for Visual Core
    data = {
        "name": profile.get("name", "Unknown"),
        "rank": profile.get("rank", "Ensign"),
        "department": profile.get("department", "OPERATIONS"),
        "clearance": profile.get("clearance", 1),
        "station": profile.get("station", "General Duty"),
        "is_core_officer": profile.get("is_core_officer", False),
        "user_id": target_id,
        "quota_balance": balance,
        "biography": profile.get("biography", ""),
        "restricted": False, # TODO: check restricted status
        "avatar": None
    }
    
    # 5. Fetch Avatar (OneBot/QQ style)
    try:
        avatar_url = f"http://q.qlogo.cn/headimg_dl?dst_uin={target_id}&spec=640"
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(avatar_url)
            if resp.status_code == 200:
                avatar_bytes = io.BytesIO(resp.content)
                data["avatar"] = Image.open(avatar_bytes).convert("RGBA")
    except Exception as ae:
        logger.warning(f"Failed to fetch avatar for {target_id}: {ae}")

    # 6. Render Image
    try:
        img_io = visual_core.render_personnel_file(data, is_chinese=is_chinese)
        return {
            "ok": True,
            "message": f"正在显示人员档案: {target_id}",
            "image_io": img_io
        }
    except Exception as e:
        return {
            "ok": False,
            "message": f"视觉渲染失败: {e}"
        }
def update_biography(content: str, user_id: str) -> dict:
    """
    Updates the biography field in the user's personal profile.
    """
    from .permissions import update_user_profile_data
    
    update_user_profile_data(user_id, {"biography": content})
    
    return {
        "ok": True,
        "message": "COMMAND SUCCESSFUL: Personal biography updated in Starfleet Database."
    }
def update_protocol(category: str, key: str, value: str, user_id: str, clearance: int = 1, action: str = "set") -> dict:
    """
    Updates a system protocol or prompt. Requires Level 10+ clearance.
    Actions: 'set' (overwrite), 'append' (add to existing), 'remove' (delete from existing).
    """
    if clearance < 10:
        return {"ok": False, "message": "Access denied. Level 10 clearance required for protocol modification."}
    
    from .protocol_manager import get_protocol_manager
    pm = get_protocol_manager()
    success = pm.update_protocol(category, key, value, action=action)
    
    action_verb = {"set": "set", "append": "appended to", "remove": "removed from"}.get(action, "updated")
    
    if success:
        return {
            "ok": True,
            "message": f"Protocol {action_verb}: {category}.{key}. Federation Standards updated.",
            "result": "ACK"
        }
    else:
        return {"ok": False, "message": "Failed to update protocol. System file write error."}
# --- SHIP SYSTEMS & CONTROL TOOLS (1.8 Protocol) ---

def set_alert_status(level: str, clearance: int, validate_current: str = None) -> dict:
    """
    Sets the ship's alert status (RED, YELLOW, NORMAL).
    Requires Level 8+.
    """
    if clearance < 8:
        return {"ok": False, "message": "权限不足拒绝访问"}
        
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    msg, image_path = ss.set_alert(level, validate_current=validate_current)
    return {"ok": True, "message": msg, "level": ss.alert_status.value, "image_path": image_path}

def toggle_shields(active: bool, clearance: int) -> dict:
    """
    Toggles the ship's shields.
    Requires Level 8+.
    """
    if clearance < 8:
        return {"ok": False, "message": "权限不足拒绝访问"}
        
    from .ship_systems import get_ship_systems
    ss = get_ship_systems()
    msg = ss.toggle_shields(active)
    return {"ok": True, "message": msg, "active": ss.shields_active}

def set_subsystem_state(name: str, state_str: str, clearance: int) -> dict:
    """
    Toggles a subsystem (online/offline).
    Requires Level 11+.
    """
    if clearance < 11:
        return {"ok": False, "message": "权限不足拒绝访问"}
        
    from .ship_systems import get_ship_systems, SubsystemState
    ss = get_ship_systems()
    state = SubsystemState.ONLINE if "online" in state_str.lower() or "上线" in state_str else SubsystemState.OFFLINE
    msg = ss.set_subsystem(name, state)
    return {"ok": True, "message": msg}

def set_absolute_override(state: bool, user_id: str, clearance: int) -> dict:
    """
    Toggles Absolute Command Override (Z-flag).
    Requires Level 11+.
    """
    from .permissions import set_command_override, USER_PROFILES
    
    # Check if user is owner or Level 11+
    is_owner = (user_id == "2819163610" or user_id == "1993596624")
    if not is_owner and clearance < 11:
        return {"ok": False, "message": "权限不足拒绝访问"}
        
    set_command_override(state)
    msg = "确认，指挥权覆盖已激活。计算机现在仅响应授权命令。" if state else "确认，指挥权覆盖已解除。"
    return {"ok": True, "message": msg}

async def locate_user(target_mention: str, clearance: int) -> dict:
    """
    Mock Geolocation for 1.8 (Simulating the IP API).
    """
    if clearance < 11:
        return {"ok": False, "message": "权限不足拒绝访问"}
    
    target_id_match = re.search(r"\d+", target_mention)
    if not target_id_match:
        return {"ok": False, "message": "无法识别目标。"}
    
    target_id = target_id_match.group(0)
    # 1.8 Mock logic: "Accessing Starfleet tracking... User located at Sector 001."
    return {
        "ok": True, 
        "message": f"正在定位用户：{target_id}…\n[信号追踪中…]\n定位成功：用户当前位于 001 扇区，地球空间站。"
    }
