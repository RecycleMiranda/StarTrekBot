import os
import time
import logging
import uuid
import threading
from typing import List, Optional
from dataclasses import dataclass, asdict
from .protocol_manager import get_protocol_manager
from . import rp_engine_gemini

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
DIAGNOSTIC_REPORT_PATH = os.path.join(REPO_ROOT, "DIAGNOSTIC_REPORT.md")
AUDIT_HISTORY_PATH = os.path.join(REPO_ROOT, "AUDIT_HISTORY.md")
APP_DIR_FULL = os.path.join(REPO_ROOT, "services", "bot", "app")

@dataclass
class DiagnosticEntry:
    id: str
    timestamp: float
    component: str
    error_msg: str
    stack_trace: Optional[str] = None
    original_query: Optional[str] = None
    diagnosis: Optional[str] = "Pending Investigation..."
    suggested_fix: Optional[str] = "Computing..."
    status: str = "ACTIVE" # ACTIVE, RESOLVED, ARCHIVED

class DiagnosticManager:
    _instance = None

    def __init__(self):
        self.active_faults: List[DiagnosticEntry] = []
        # Ensure report exists
        if not os.path.exists(DIAGNOSTIC_REPORT_PATH):
            self._write_report()
            
        # PROACTIVE MONITORING: Guardian Thread
        threading.Thread(target=self._guardian_loop, daemon=True).start()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def report_fault(self, component: str, error: Exception, query: str = None, traceback_str: str = None) -> str:
        fault_id = f"ERR-0x{uuid.uuid4().hex[:4].upper()}"
        entry = DiagnosticEntry(
            id=fault_id,
            timestamp=time.time(),
            component=component,
            error_msg=str(error),
            stack_trace=traceback_str,
            original_query=query
        )
        self.active_faults.append(entry)
        
        logger.info(f"[ADS] Logged fault {fault_id} for {component}")
        
        # Initial write
        self._write_report()
        
        # Trigger async AI diagnosis
        threading.Thread(target=self._run_async_diagnosis, args=(entry,), daemon=True).start()
        
        return fault_id

    def _run_async_diagnosis(self, entry: DiagnosticEntry):
        """Asynchronously calls LLM to diagnose the fault."""
        try:
            logger.info(f"[ADS] Starting AI Diagnosis for {entry.id}")
            
            prompt = f"""故障诊断任务: {entry.id}
发生组件: {entry.component}
错误信息: {entry.error_msg}
原始用户指令: {entry.original_query}
错误堆栈:
{entry.stack_trace}

请作为星舰总工程师，给出此故障的病理诊断和修复建议。
格式要求:
1. 诊断结论 (极简)
2. 建议代码修复方案 (使用 diff 语法)
"""
            # Use gemini to synthesize (reuse existing engine if possible or simple direct call)
            # For simplicity, we use a basic generation call
            result = rp_engine_gemini.generate_technical_diagnosis(prompt)
            
            entry.diagnosis = result.get("diagnosis", "Unknown pathology.")
            entry.suggested_fix = result.get("suggested_fix", "# No fix found.")
            
            # Update report
            self._write_report()
            
            # Sync to GitHub
            pm = get_protocol_manager()
            pm.git_sync(f"ADS: Diagnosed fault {entry.id}", extra_files=[DIAGNOSTIC_REPORT_PATH])

            # --- AUTO-HEALING TRIGGER: Subspace Bypass Hotfix ---
            # User Directive: Attempt repair regardless of fault type
            logger.info(f"[ADS] Fault {entry.id} captured. Attempting Subspace Bypass Hotfix.")
            
            # Identify module from component name (e.g. SendQueue.QQSender -> sender_qq.py)
            component_parts = entry.component.split(".")
            module_hint = component_parts[-1].lower() if component_parts else ""
            
            # Mapping logic for common components to files
            module_map = {
                "qqsender": "sender_qq.py",
                "sendqueue": "send_queue.py",
                "agenticloop": "dispatcher.py",
                "dispatcher": "dispatcher.py",
                "rp_engine": "rp_engine_gemini.py"
            }
            
            module = module_map.get(module_hint)
            if not module:
                # Fallback: simple heuristic
                module = module_hint + ".py"

            from . import repair_agent
            ra = repair_agent.RepairAgent.get_instance()
            
            # Run Autopilot
            import asyncio
            # We need a loop if we are in a thread
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Diagnosis info to pass
            repair_context = f"Error: {entry.error_msg}\nLocation: {entry.component}\nTrace: {entry.stack_trace}"
            
            repair_res = loop.run_until_complete(ra.async_autopilot_repair(module, repair_context))
                
                if repair_res.get("ok"):
                    logger.info(f"[ADS] Autopilot successfully applied bypass to {module}")
                    entry.status = "BYPASS_ACTIVE"
                    self._write_report()
                    registry_path = self._register_bypass(entry, module)
                    
                    # SYNC TO GITHUB: Final closure of the bypass event
                    pm = get_protocol_manager()
                    pm.git_sync(
                        f"ADS: Autonomous Subspace Bypass patch applied for {entry.id}", 
                        extra_files=[
                            DIAGNOSTIC_REPORT_PATH, 
                            registry_path, 
                            str(os.path.join(APP_DIR_FULL, module)) # Use full path to the patched file
                        ]
                    )
                else:
                    logger.warning(f"[ADS] Autopilot failed for {entry.id}: {repair_res.get('message')}")

        except Exception as e:
            logger.error(f"[ADS] AI Diagnosis failed for {entry.id}: {e}")

    def _register_bypass(self, entry: DiagnosticEntry, module: str) -> str:
        """Registers the bypass in BYPASS_REGISTRY.md"""
        registry_path = os.path.join(REPO_ROOT, "BYPASS_REGISTRY.md")
        line = f"| {entry.id} | {module} | {time.strftime('%Y-%m-%d %H:%M:%S')} | [ACTIVE] |\n"
        
        if not os.path.exists(registry_path):
            with open(registry_path, "w", encoding="utf-8") as f:
                f.write("# LCARS 子空间旁路注册表 (Subspace Bypass Registry)\n\n| Fault ID | Module | timestamp | Status |\n|---|---|---|---|\n")
        
        with open(registry_path, "a", encoding="utf-8") as f:
            f.write(line)
        
        return registry_path

    def _write_report(self):
        content = "# LCARS 自动诊断报告 (Auto-Diagnostic Report)\n\n"
        content += "> [!IMPORTANT]\n"
        content += "> 本文件由 ADS (Auto-Diagnostic Routine) 自动维护。请参考诊断结论进行修复。\n\n"
        
        content += "## 活跃故障 (Active Faults)\n"
        if not self.active_faults:
            content += "当前无活跃故障。系统运行良好。\n"
        else:
            for f in self.active_faults:
                content += f"### {f.id} | {f.component}\n"
                content += f"- **发生时间**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(f.timestamp))}\n"
                content += f"- **错误信息**: `{f.error_msg}`\n"
                content += f"- **原始指令**: `{f.original_query or 'N/A'}`\n"
                content += f"- **AI 诊断**: {f.diagnosis}\n"
                content += f"- **建议方案**:\n\n```diff\n{f.suggested_fix}\n```\n\n"
                content += "---\n"
        
        content += "\n\n*Generated by LCARS Engineering Subroutine (Version 2.0)*\n"
        
        try:
            with open(DIAGNOSTIC_REPORT_PATH, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"[ADS] Failed to write report file: {e}")

    def clear_fault(self, fault_id: str):
        """Moves a fault to historical audit."""
        found = None
        for f in self.active_faults:
            if f.id == fault_id:
                found = f
                break
        
        if found:
            self.active_faults.remove(found)
            self._write_report()
            # Append to AUDIT_HISTORY.md
            self._append_to_audit(found)
            
            pm = get_protocol_manager()
            pm.git_sync(f"ADS: Cleared and audited fault {fault_id}", extra_files=[DIAGNOSTIC_REPORT_PATH, AUDIT_HISTORY_PATH])
            return True
        return False

    def _append_to_audit(self, entry: DiagnosticEntry):
        audit_line = f"\n### {entry.id} | {entry.component} (RESOLVED)\n"
        audit_line += f"- **Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry.timestamp))}\n"
        audit_line += f"- **Resolution**: Fixed and audited.\n"
        
        try:
            with open(AUDIT_HISTORY_PATH, "a", encoding="utf-8") as f:
                f.write(audit_line)
        except Exception as e:
            logger.error(f"[ADS] Failed to write audit history: {e}")

    def _guardian_loop(self):
        """Active background monitoring for performance anomalies. (ADS 2.0)"""
        logger.info("[ADS] Guardian Loop initiated.")
        while True:
            try:
                # 1. Check for session congestion in OpsRegistry
                from .ops_registry import OpsRegistry, TaskState
                ops = OpsRegistry.get_instance()
                
                # Use a simplified check for this mock/logic
                active_tasks = [] # Mock for now or real access
                # Logic: If tasks > 5 for a single session, it's a congestion
                
                # 2. Heartbeat Check
                # If no heartbeat for 60s, something is wrong
                
                time.sleep(30) # Poll every 30s
            except Exception as e:
                logger.error(f"[ADS] Guardian error: {e}")
                time.sleep(10)

def get_diagnostic_manager():
    return DiagnosticManager.get_instance()
