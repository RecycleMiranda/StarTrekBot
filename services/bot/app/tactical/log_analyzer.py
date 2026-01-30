import os
import re
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

class LogAnalyzer:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        self.page_size = 20

    def get_log_path(self, log_type: str) -> Optional[str]:
        mapping = {
            "tactical": os.path.join(self.log_dir, "tactical", "SENSOR_LOGS.md"),
            "arsenal": os.path.join(self.log_dir, "tactical", "ARSENAL_LEDGER.log"),
            "routing": os.path.join(self.log_dir, "data", "router_log.jsonl"),
            "comms": os.path.join(self.log_dir, "data", "send_log.jsonl")
        }
        path = mapping.get(log_type.lower())
        if path and os.path.exists(path):
            return path
        return None

    def read_segmented(self, log_type: str, page: int = 0, page_size: Optional[int] = None) -> Dict[str, Any]:
        """Reads a specific segment of the log file (pagination)."""
        path = self.get_log_path(log_type)
        if not path:
            return {"error": f"Log type '{log_type}' not found or unreachable.", "data": []}

        p_size = page_size or self.page_size
        start_line = page * p_size
        
        lines = []
        with open(path, "r", encoding="utf-8") as f:
            # Skip to start line
            for i, line in enumerate(f):
                if i < start_line:
                    continue
                if i >= start_line + p_size:
                    break
                lines.append(line.strip())

        return {
            "log": log_type,
            "page": page,
            "page_size": p_size,
            "data": lines,
            "has_next": len(lines) == p_size
        }

    def filter_logs(self, log_type: str, keyword: Optional[str] = None, event_type: Optional[str] = None) -> List[str]:
        """Applies filters to the log file and returns matching entries."""
        path = self.get_log_path(log_type)
        if not path:
            return []

        results = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                # Event Type Filtering (for Markdown/Log formats)
                if event_type and event_type.upper() not in line.upper():
                    continue
                
                # Keyword Filtering
                if keyword and keyword.lower() not in line.lower():
                    continue
                
                results.append(line.strip())
        
        return results

    def generate_summary(self, log_type: str, limit: int = 50) -> str:
        """Generates a high-level summary of the most recent N log entries."""
        data = self.read_segmented(log_type, page=0, page_size=limit)["data"]
        if not data:
            return "No data available for summary."

        # Analysis Logic
        if log_type == "tactical":
            locks = len([l for l in data if "TACTICAL_LOCK" in l])
            impacts = len([l for l in data if "BDA_REPORT" in l])
            acquisitions = len([l for l in data if "ACQUISITION" in l])
            
            summary = f"### [Tactical Analysis Report]\n"
            summary += f"- **Contacts Acquired**: {acquisitions}\n"
            summary += f"- **Tactical Locks Established**: {locks}\n"
            summary += f"- **Confirmed Weapon Impacts**: {impacts}\n"
            summary += f"- **Operational Status**: AI 'Sun Tzu' active and processing OODA loops."
            return summary
        
        return f"Summary for {log_type} contains {len(data)} entries."

if __name__ == "__main__":
    # Internal Test
    # services/bot/app/tactical/log_analyzer.py -> services/bot/app/
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    analyzer = LogAnalyzer(base_path)
    
    print("\n--- Segmented Read Test (Page 0) ---")
    print(analyzer.read_segmented("tactical", page=0, page_size=5))
    
    print("\n--- Filter Test (Event: ACQUISITION) ---")
    print(analyzer.filter_logs("tactical", event_type="ACQUISITION")[:3])
    
    print("\n--- Summary Generation Test ---")
    print(analyzer.generate_summary("tactical"))
