"""
LCARS Self-Repair Agent

A conversational agent that can diagnose and repair bot modules.
Features:
- Multi-turn conversation support
- Automatic model selection based on complexity
- Integration with repair_tools for file operations
"""

import logging
import time
import json
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RepairComplexity(Enum):
    SIMPLE = "simple"      # Syntax errors, typos
    MEDIUM = "medium"      # Logic bugs, small refactors
    COMPLEX = "complex"    # Architecture changes, multi-file


@dataclass
class RepairSession:
    """Tracks a repair session's state."""
    session_id: str
    user_id: str
    target_module: Optional[str] = None
    complexity: RepairComplexity = RepairComplexity.SIMPLE
    conversation_history: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    changes_made: List[Dict] = field(default_factory=list)
    
    SESSION_TIMEOUT = 600  # 10 minutes
    
    def is_expired(self) -> bool:
        return time.time() - self.last_activity > self.SESSION_TIMEOUT
    
    def touch(self):
        self.last_activity = time.time()
    
    def add_message(self, role: str, content: str):
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        self.touch()


class RepairAgent:
    """Manages repair sessions and coordinates with LLM for code analysis."""
    
    _instance = None
    
    # Model selection based on complexity
    MODEL_MAP = {
        RepairComplexity.SIMPLE: "gemini-2.0-flash-lite",
        RepairComplexity.MEDIUM: "gemini-2.0-flash",
        RepairComplexity.COMPLEX: "gemini-2.5-pro-preview-05-06",
    }
    
    def __init__(self):
        self.sessions: Dict[str, RepairSession] = {}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_session(self, session_id: str) -> Optional[RepairSession]:
        session = self.sessions.get(session_id)
        if session and session.is_expired():
            del self.sessions[session_id]
            return None
        return session
    
    def start_session(self, session_id: str, user_id: str, target_module: Optional[str] = None) -> RepairSession:
        """Start a new repair session."""
        session = RepairSession(
            session_id=session_id,
            user_id=user_id,
            target_module=target_module
        )
        self.sessions[session_id] = session
        logger.info(f"[RepairAgent] Started repair session {session_id} for module {target_module}")
        return session
    
    def end_session(self, session_id: str) -> dict:
        """End a repair session."""
        session = self.sessions.pop(session_id, None)
        if session:
            return {
                "ok": True,
                "changes_made": len(session.changes_made),
                "message": f"Repair session ended. {len(session.changes_made)} changes were made."
            }
        return {"ok": False, "message": "No active repair session."}
    
    def estimate_complexity(self, user_message: str, code_context: Optional[str] = None) -> RepairComplexity:
        """
        Estimate the complexity of a repair request.
        Simple heuristics, can be enhanced with LLM classification.
        """
        message_lower = user_message.lower()
        
        # Complex indicators
        complex_keywords = ["重构", "refactor", "架构", "architecture", "redesign", "重写", "rewrite"]
        if any(kw in message_lower for kw in complex_keywords):
            return RepairComplexity.COMPLEX
        
        # Medium indicators
        medium_keywords = ["bug", "逻辑", "logic", "fix", "修复", "问题", "error", "exception"]
        if any(kw in message_lower for kw in medium_keywords):
            return RepairComplexity.MEDIUM
        
        # Default to simple for quick queries
        return RepairComplexity.SIMPLE
    
    def get_model_for_session(self, session: RepairSession) -> str:
        """Get the appropriate model based on session complexity."""
        return self.MODEL_MAP.get(session.complexity, self.MODEL_MAP[RepairComplexity.SIMPLE])
    
    async def process_message(self, session_id: str, user_id: str, message: str, clearance: int) -> dict:
        """
        Process a message in repair mode.
        Returns the agent's response.
        """
        from . import repair_tools
        
        # Check clearance
        if clearance < 12:
            return {
                "ok": False,
                "message": "ACCESS DENIED: Level 12 clearance required for repair mode.",
                "exit_repair_mode": True
            }
        
        # Get or create session
        session = self.get_session(session_id)
        if not session:
            # Check if this is a session start command
            if any(kw in message.lower() for kw in ["诊断", "修复", "repair", "diagnose", "检查"]):
                # Extract module name if present
                module = self._extract_module_name(message)
                session = self.start_session(session_id, user_id, module)
            else:
                return {
                    "ok": False,
                    "message": "No active repair session. Say '诊断 <module_name>' to start.",
                    "in_repair_mode": False
                }
        
        session.add_message("user", message)
        
        # Update complexity estimate
        session.complexity = self.estimate_complexity(message)
        
        # Check for exit commands
        if any(kw in message.lower() for kw in ["退出", "exit", "结束", "done", "完成"]):
            result = self.end_session(session_id)
            result["exit_repair_mode"] = True
            return result
        
        # Build context for LLM
        context = self._build_repair_context(session, message)
        
        # Call LLM
        model = self.get_model_for_session(session)
        response = await self._call_repair_llm(context, model, session)
        
        # Parse and execute any tool calls from the response
        final_response = await self._process_llm_response(response, session)
        
        session.add_message("assistant", final_response.get("reply", ""))
        
        return {
            "ok": True,
            "reply": final_response.get("reply", ""),
            "model_used": model,
            "complexity": session.complexity.value,
            "in_repair_mode": True,
            "changes_made": final_response.get("changes_made", [])
        }
    
    def _extract_module_name(self, message: str) -> Optional[str]:
        """Extract module name from a message."""
        from . import repair_tools
        
        # Check for any whitelisted module names
        for module in repair_tools.MODIFIABLE_MODULES:
            base_name = module.replace(".py", "")
            if module in message or base_name in message:
                return module
        return None
    
    def _build_repair_context(self, session: RepairSession, current_message: str) -> str:
        """Build the context string for the LLM."""
        from . import repair_tools
        
        context_parts = [
            "You are the LCARS Self-Repair Agent. You can diagnose and fix code in the StarTrekBot system.",
            "",
            "AVAILABLE TOOLS:",
            "- read_module(name): Read a module's source code",
            "- write_module(name, content): Write new content to a module (creates backup)",
            "- get_module_outline(name): Get structural overview of a module",
            "- rollback_module(name): Restore from backup",
            "- list_backups(name): List available backups",
            "",
            f"MODIFIABLE MODULES: {', '.join(repair_tools.MODIFIABLE_MODULES)}",
            "",
            "RULES:",
            "1. Always read a module before suggesting changes",
            "2. Explain what you're going to change before doing it",
            "3. When writing changes, provide the COMPLETE new file content",
            "4. If unsure, ask clarifying questions",
            "",
        ]
        
        if session.target_module:
            context_parts.append(f"CURRENT TARGET: {session.target_module}")
            
            # Load current module content
            read_result = repair_tools.read_module(session.target_module)
            if read_result.get("ok"):
                context_parts.append(f"\nCURRENT CODE ({session.target_module}):")
                context_parts.append("```python")
                context_parts.append(read_result["numbered_content"][:10000])  # Limit size
                context_parts.append("```")
        
        context_parts.append("\nCONVERSATION HISTORY:")
        for msg in session.conversation_history[-10:]:  # Last 10 messages
            role = "USER" if msg["role"] == "user" else "AGENT"
            context_parts.append(f"{role}: {msg['content']}")
        
        context_parts.append(f"\nCURRENT REQUEST: {current_message}")
        
        return "\n".join(context_parts)
    
    async def _call_repair_llm(self, context: str, model: str, session: RepairSession) -> dict:
        """Call the LLM with repair context."""
        try:
            from google import genai
            from google.genai import types
            import os
            
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            
            response = client.models.generate_content(
                model=model,
                contents=context,
                config=types.GenerateContentConfig(
                    temperature=0.3,  # Lower temperature for code work
                    max_output_tokens=8000,
                )
            )
            
            return {
                "ok": True,
                "text": response.text,
                "model": model
            }
        except Exception as e:
            logger.error(f"[RepairAgent] LLM call failed: {e}")
            return {
                "ok": False,
                "error": str(e)
            }
    
    async def _process_llm_response(self, llm_response: dict, session: RepairSession) -> dict:
        """Process the LLM response and execute any tool calls."""
        from . import repair_tools
        
        if not llm_response.get("ok"):
            return {"reply": f"LLM ERROR: {llm_response.get('error', 'Unknown error')}"}
        
        text = llm_response.get("text", "")
        changes_made = []
        
        # Check if the response contains a code block to write
        if "```python" in text and session.target_module:
            # Extract the code block
            import re
            code_match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
            if code_match:
                new_code = code_match.group(1)
                
                # Check if this looks like a complete file (has imports or class/function definitions)
                if "import" in new_code or "def " in new_code or "class " in new_code:
                    # Ask for confirmation first (in the response)
                    if "确认" not in text.lower() and "confirm" not in text.lower():
                        # Add confirmation request to the response
                        text += "\n\n请回复 '确认' 来应用这些更改。"
                    elif session.conversation_history and "确认" in session.conversation_history[-1].get("content", "").lower():
                        # User confirmed, apply changes
                        write_result = repair_tools.write_module(session.target_module, new_code)
                        if write_result.get("ok"):
                            changes_made.append({
                                "module": session.target_module,
                                "action": "write",
                                "success": True
                            })
                            session.changes_made.append(changes_made[-1])
                            text += f"\n\n✅ 已应用更改: {write_result.get('message')}"
                        else:
                            text += f"\n\n❌ 应用失败: {write_result.get('message')}"
        
        return {
            "reply": text,
            "changes_made": changes_made
        }


def get_repair_agent():
    return RepairAgent.get_instance()
