import json
from typing import Dict, Any, Union

def format_report_to_text(report: Union[str, Dict[str, Any]]) -> str:
    """
    Formats a structured LCARS report (dict) or a plain string into a 
    clean, Star Trek style text block.
    """
    if isinstance(report, str):
        # Already a string, return as is (maybe clean whitespace)
        return report.strip()
    
    if not isinstance(report, dict):
        return str(report)

    # It's a structured report dict
    title = report.get("title", "LCARS STATUS REPORT").upper()
    sections = report.get("sections", [])
    
    # Building the text-based Star Trek report
    output = [f"== {title} =="]
    
    for section in sections:
        cat = section.get("category", "GENERAL").upper()
        content = section.get("content", "N/A")
        output.append(f"\n[{cat}]")
        output.append(content)
        
    output.append("\n== END REPORT ==")
    
    return "\n".join(output)
