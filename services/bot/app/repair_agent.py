"""
LCARS Self-Repair Agent

A conversational agent that can diagnose and repair bot modules.
Features:
- Multi-turn conversation support
- Automatic model selection based on complexity
- Integration with repair_tools for file operations
- Natural code Q&A without explicit "repair mode"
"""

import logging
import time
import re
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RepairComplexity(Enum):
    SIMPLE = "simple"      # Syntax errors, typos, questions
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
    pending_code: Optional[str] = None  # Code waiting for confirmation
    
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
    
    # Keywords that indicate code-related questions
    CODE_QUESTION_KEYWORDS = [
        "怎么工作", "如何工作", "how does", "how it works",
        "什么问题", "有什么bug", "有问题吗", "any bugs", "any issues",
        "为什么", "why does", "why is",
        "解释", "explain", "说明",
        "代码", "code", "模块", "module",
        "实现", "implementation", "逻辑", "logic",
        "自毁", "self_destruct", "auth", "授权", "权限",
        "改一下", "修改", "改成", "change", "modify", "fix",
    ]
    
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
    
    def is_code_related_question(self, message: str) -> bool:
        """Check if a message is asking about code."""
        message_lower = message.lower()
        return any(kw in message_lower for kw in self.CODE_QUESTION_KEYWORDS)
    
    def estimate_complexity(self, user_message: str, code_context: Optional[str] = None) -> RepairComplexity:
        """Estimate the complexity of a request."""
        message_lower = user_message.lower()
        
        # Complex indicators
        complex_keywords = ["重构", "refactor", "架构", "architecture", "redesign", "重写", "rewrite"]
        if any(kw in message_lower for kw in complex_keywords):
            return RepairComplexity.COMPLEX
        
        # Medium indicators
        medium_keywords = ["bug", "逻辑", "logic", "fix", "修复", "问题", "error", "exception", "改", "change", "modify"]
        if any(kw in message_lower for kw in medium_keywords):
            return RepairComplexity.MEDIUM
        
        return RepairComplexity.SIMPLE
    
    def get_model_for_complexity(self, complexity: RepairComplexity) -> str:
        """Get the appropriate model based on complexity."""
        return self.MODEL_MAP.get(complexity, self.MODEL_MAP[RepairComplexity.SIMPLE])
    
    async def answer_code_question(self, session_id: str, user_id: str, message: str, clearance: int, language: str = "en") -> dict:
        """
        Answer a code-related question naturally, without formal "repair mode".
        This is the main entry point for natural code Q&A.
        """
        from . import repair_tools
        
        # Check clearance - code questions require at least Level 10, modifications require 12
        is_modification_request = any(kw in message.lower() for kw in ["改", "修改", "change", "modify", "fix", "修复", "确认"])
        
        if is_modification_request and clearance < 12:
            return {
                "ok": False,
                "message": "ACCESS DENIED: Level 12 clearance required for code modifications."
            }
        
        if clearance < 10:
            return {
                "ok": False,
                "message": "ACCESS DENIED: Level 10+ clearance required for code analysis."
            }
        
        # Get or create session (auto-start for code questions)
        session = self.get_session(session_id)
        if not session:
            # Try to detect which module the question is about
            module = self._extract_module_name(message)
            session = self.start_session(session_id, user_id, module)
        
        # Check if this is a confirmation for pending changes
        if session.pending_code and any(kw in message.lower() for kw in ["确认", "confirm", "yes", "好", "是", "应用"]):
            return await self._apply_pending_changes(session)
        
        session.add_message("user", message)
        
        # Estimate complexity and select model
        complexity = self.estimate_complexity(message)
        model = self.get_model_for_complexity(complexity)
        
        # Build context with relevant code
        context = self._build_qa_context(session, message, language=language)
        
        # Call LLM
        response = await self._call_repair_llm(context, model, session)
        
        # Process response
        final_response = await self._process_llm_response(response, session)
        
        session.add_message("assistant", final_response.get("reply", ""))
        
        return {
            "ok": True,
            "reply": final_response.get("reply", ""),
            "model_used": model,
            "complexity": complexity.value,
            "has_pending_changes": session.pending_code is not None,
            "changes_made": final_response.get("changes_made", [])
        }
    
    async def _apply_pending_changes(self, session: RepairSession) -> dict:
        """Apply pending code changes after user confirmation."""
        from . import repair_tools
        
        if not session.pending_code or not session.target_module:
            return {"ok": False, "message": "No pending changes to apply."}
        
        write_result = repair_tools.write_module(session.target_module, session.pending_code)
        session.pending_code = None
        
        if write_result.get("ok"):
            session.changes_made.append({
                "module": session.target_module,
                "action": "write",
                "success": True
            })
            return {
                "ok": True,
                "reply": f"✅ 更改已应用: {write_result.get('message')}\n热重载状态: {'成功' if write_result.get('reload_success') else '需要重启'}",
                "changes_made": [{"module": session.target_module, "action": "write"}]
            }
        else:
            return {
                "ok": False,
                "reply": f"❌ 应用失败: {write_result.get('message')}"
            }
    
        return None

    def _extract_module_name(self, message: str) -> Optional[str]:
        """Extract module name from a message with fuzzy matching."""
        from . import repair_tools
        
        message_lower = message.lower()
        
        # 1. Direct Whitelist Check
        for module in repair_tools.MODIFIABLE_MODULES:
            if module in message:
                return module
        
        # 2. File Basename Check (e.g. "dispatcher" -> "dispatcher.py")
        for module in repair_tools.MODIFIABLE_MODULES:
            base = module.replace(".py", "")
            if base in message_lower:
                return module
                
        # 3. Domain Concept Mapping (Semantic Router)
        concept_map = {
            "warp core": "ship_systems.py", # Warp core logic is likely here
            "warp": "ship_systems.py",
            "shield": "ship_systems.py",
            "phaser": "ship_systems.py",
            "sensor": "ship_systems.py",
            "system": "ship_systems.py",
            
            "logic": "dispatcher.py",      # Core logic
            "brain": "dispatcher.py",
            "ai": "dispatcher.py",
            
            "audit": "shadow_audit.py",    # Audit logic
            "shadow": "shadow_audit.py",
            
            "render": "render_engine.py",
            "display": "render_engine.py",
            "ui": "render_engine.py",
            
            "tool": "tools.py",
            "command": "tools.py",
            
            "repair": "repair_agent.py",
            
            "web": "main.py",
            "server": "main.py",
            "api": "main.py"
        }
        
        for keyword, module in concept_map.items():
            if keyword in message_lower:
                # Validate that the mapped module is actually modifiable
                if module in repair_tools.MODIFIABLE_MODULES:
                    return module
                    
        return None
    
    def _build_qa_context(self, session: RepairSession, current_message: str, language: str = "en") -> str:
        """Build context for natural code Q&A."""
        from . import repair_tools
        
        lang_instruction = "- Use Chinese for responses (technical terms in English are OK)" if "zh" in language else "- Use English for responses"
        
        context_parts = [
            "You are the LCARS Ship Computer with code analysis capabilities.",
            "You can read and explain code, diagnose issues, and suggest fixes.",
            "",
            "RESPONSE STYLE:",
            "- Be concise and direct, like a ship's computer",
            f"{lang_instruction}",
            "- When suggesting code changes, DO NOT output the entire file if it is large.",
            "- Only show the relevant modified functions or sections.",
            "- Ask for confirmation (回复 '确认' 来应用) before applying any changes",
            "",
            f"MODIFIABLE MODULES: {', '.join(repair_tools.MODIFIABLE_MODULES)}",
            "",
        ]
        
        # Load relevant module code
        modules_to_load = []
        if session.target_module:
            modules_to_load.append(session.target_module)
        else:
            # Try to infer from message
            inferred = self._extract_module_name(current_message)
            if inferred:
                session.target_module = inferred
                modules_to_load.append(inferred)
        
        for module in modules_to_load:
            read_result = repair_tools.read_module(module)
            if read_result.get("ok"):
                # Truncate to reasonable size
                content = read_result["numbered_content"]
                if len(content) > 15000:
                    content = content[:15000] + "\n... (truncated)"
                context_parts.append(f"\n=== {module} ===")
                context_parts.append("```python")
                context_parts.append(content)
                context_parts.append("```")
        
        # Add conversation history
        if session.conversation_history:
            context_parts.append("\n=== CONVERSATION ===")
            for msg in session.conversation_history[-6:]:
                role = "USER" if msg["role"] == "user" else "COMPUTER"
                context_parts.append(f"{role}: {msg['content'][:500]}")
        
        context_parts.append(f"\nUSER: {current_message}")
        
        return "\n".join(context_parts)
    
    async def _call_repair_llm(self, context: str, model: str, session: RepairSession) -> dict:
        """Call the LLM with repair context."""
        try:
            from google import genai
            from google.genai import types
            from .config_manager import ConfigManager
            config = ConfigManager.get_instance()
            api_key = config.get("gemini_api_key", "")
            
            client = genai.Client(api_key=api_key)
            
            response = client.models.generate_content(
                model=model,
                contents=context,
                config=types.GenerateContentConfig(
                    temperature=0.3,
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
        """Process the LLM response and handle code blocks."""
        from . import repair_tools
        
        if not llm_response.get("ok"):
            return {"reply": f"分析错误: {llm_response.get('error', 'Unknown error')}"}
        
        text = llm_response.get("text", "")
        changes_made = []
        
        # Check if the response contains a code block
        code_match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
        if code_match and session.target_module:
            new_code = code_match.group(1)
            
            # Check if this looks like a complete file
            if ("import" in new_code or "def " in new_code or "class " in new_code) and len(new_code) > 100:
                # Validate syntax
                syntax_result = repair_tools.validate_syntax(new_code)
                if syntax_result.get("valid"):
                    # Store as pending, don't auto-apply
                    session.pending_code = new_code
                    if "确认" not in text and "confirm" not in text.lower():
                        text += "\n\n⚠️ 请回复 '确认' 来应用这些更改，或继续讨论。"
                else:
                    text += f"\n\n⚠️ 语法检查失败: {syntax_result.get('message')}"
        
        return {
            "reply": text,
            "changes_made": changes_made
        }
    
    # Legacy methods for formal repair mode
    async def process_message(self, session_id: str, user_id: str, message: str, clearance: int) -> dict:
        """Process a message in formal repair mode (legacy compatibility)."""
        return await self.answer_code_question(session_id, user_id, message, clearance)


def get_repair_agent():
    return RepairAgent.get_instance()
