"""
LCARS Self-Repair Tools

Provides low-level file operations for the Self-Repair System:
- Read module source code
- Write module with backup and validation
- Hot reload modules
- Rollback to previous versions
"""

import os
import sys
import ast
import shutil
import importlib
import logging
import subprocess
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

# Base path for the bot application
APP_BASE = Path(__file__).parent
BACKUP_DIR = APP_BASE / ".backup"

# Whitelist of modules that can be modified
MODIFIABLE_MODULES = {
    "self_destruct.py",
    "auth_system.py",
    "tools.py",
    "quota_manager.py",
    "permissions.py",
}

# Blacklist of modules that must never be modified
PROTECTED_MODULES = {
    "main.py",
    "dispatcher.py",
    "rp_engine_gemini.py",
    "repair_agent.py",
    "repair_tools.py",  # Can't modify itself!
}


def is_module_accessible(module_name: str) -> tuple[bool, str]:
    """Check if a module can be accessed by the repair system."""
    # Normalize the name
    if not module_name.endswith(".py"):
        module_name = module_name + ".py"
    
    if module_name in PROTECTED_MODULES:
        return False, f"PROTECTED: {module_name} is a core system module and cannot be modified."
    
    if module_name not in MODIFIABLE_MODULES:
        return False, f"RESTRICTED: {module_name} is not in the modifiable whitelist."
    
    module_path = APP_BASE / module_name
    if not module_path.exists():
        return False, f"NOT FOUND: {module_name} does not exist."
    
    return True, "OK"


def read_module(module_name: str) -> dict:
    """
    Read a module's source code with line numbers.
    Returns the content and metadata.
    """
    accessible, reason = is_module_accessible(module_name)
    if not accessible:
        return {"ok": False, "message": reason}
    
    if not module_name.endswith(".py"):
        module_name = module_name + ".py"
    
    module_path = APP_BASE / module_name
    
    try:
        with open(module_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.split("\n")
        numbered_content = "\n".join(f"{i+1:4d}: {line}" for i, line in enumerate(lines))
        
        return {
            "ok": True,
            "module": module_name,
            "path": str(module_path),
            "content": content,
            "numbered_content": numbered_content,
            "line_count": len(lines),
            "size_bytes": len(content.encode("utf-8")),
            "message": f"Successfully read {module_name} ({len(lines)} lines)"
        }
    except Exception as e:
        logger.error(f"[RepairTools] Failed to read {module_name}: {e}")
        return {"ok": False, "message": f"READ ERROR: {str(e)}"}


def validate_syntax(content: str) -> dict:
    """
    Validate Python syntax without executing the code.
    """
    try:
        ast.parse(content)
        return {"ok": True, "valid": True, "message": "Syntax is valid."}
    except SyntaxError as e:
        return {
            "ok": True,
            "valid": False,
            "message": f"SYNTAX ERROR at line {e.lineno}: {e.msg}",
            "line": e.lineno,
            "offset": e.offset,
            "error": e.msg
        }


def backup_module(module_name: str) -> dict:
    """
    Create a timestamped backup of a module.
    """
    if not module_name.endswith(".py"):
        module_name = module_name + ".py"
    
    module_path = APP_BASE / module_name
    if not module_path.exists():
        return {"ok": False, "message": f"Module {module_name} not found."}
    
    # Create backup directory if needed
    BACKUP_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{module_name}.{timestamp}.bak"
    backup_path = BACKUP_DIR / backup_name
    
    try:
        shutil.copy2(module_path, backup_path)
        logger.info(f"[RepairTools] Backed up {module_name} to {backup_path}")
        return {
            "ok": True,
            "backup_path": str(backup_path),
            "message": f"Backup created: {backup_name}"
        }
    except Exception as e:
        logger.error(f"[RepairTools] Backup failed: {e}")
        return {"ok": False, "message": f"BACKUP ERROR: {str(e)}"}


def list_backups(module_name: str) -> dict:
    """
    List all available backups for a module.
    """
    if not module_name.endswith(".py"):
        module_name = module_name + ".py"
    
    if not BACKUP_DIR.exists():
        return {"ok": True, "backups": [], "message": "No backups found."}
    
    backups = []
    for f in BACKUP_DIR.glob(f"{module_name}.*.bak"):
        stat = f.stat()
        backups.append({
            "name": f.name,
            "path": str(f),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    
    backups.sort(key=lambda x: x["modified"], reverse=True)
    
    return {
        "ok": True,
        "backups": backups,
        "count": len(backups),
        "message": f"Found {len(backups)} backup(s) for {module_name}"
    }


def rollback_module(module_name: str, backup_index: int = 0) -> dict:
    """
    Restore a module from backup.
    backup_index: 0 = most recent, 1 = second most recent, etc.
    """
    accessible, reason = is_module_accessible(module_name)
    if not accessible:
        return {"ok": False, "message": reason}
    
    if not module_name.endswith(".py"):
        module_name = module_name + ".py"
    
    backups_result = list_backups(module_name)
    if not backups_result["ok"] or not backups_result["backups"]:
        return {"ok": False, "message": f"No backups available for {module_name}"}
    
    if backup_index >= len(backups_result["backups"]):
        return {"ok": False, "message": f"Backup index {backup_index} out of range. Only {len(backups_result['backups'])} backup(s) available."}
    
    backup = backups_result["backups"][backup_index]
    backup_path = Path(backup["path"])
    module_path = APP_BASE / module_name
    
    try:
        shutil.copy2(backup_path, module_path)
        logger.info(f"[RepairTools] Rolled back {module_name} from {backup_path}")
        
        # Try to hot reload
        reload_result = hot_reload_module(module_name)
        
        return {
            "ok": True,
            "restored_from": backup["name"],
            "reload_success": reload_result.get("ok", False),
            "message": f"Restored {module_name} from {backup['name']}"
        }
    except Exception as e:
        logger.error(f"[RepairTools] Rollback failed: {e}")
        return {"ok": False, "message": f"ROLLBACK ERROR: {str(e)}"}

def git_sync_changes(file_path: Path, message: str) -> dict:
    """
    Commit and push a file to git.
    """
    try:
        # Check if inside git repo
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], 
            cwd=file_path.parent, 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        # Add
        subprocess.run(["git", "add", str(file_path)], cwd=repo_root, check=True)
        
        # Commit
        subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True)
        
        # Push 
        # Note: This might block or fail if no credentials. 
        # running with timeout to avoid hanging.
        subprocess.run(["git", "push", "origin", "main"], cwd=repo_root, check=True, timeout=10)
        
        logger.info(f"[RepairTools] Git sync successful for {file_path}")
        return {"ok": True, "message": "Changes committed and pushed to git."}
        
    except subprocess.CalledProcessError as e:
        logger.error(f"[RepairTools] Git error: {e}")
        return {"ok": False, "message": f"Git sync failed (local write ok): {e}"}
    except Exception as e:
        logger.error(f"[RepairTools] Git unexpected error: {e}")
        return {"ok": False, "message": f"Git sync failed: {e}"}


def write_module(module_name: str, content: str, create_backup: bool = True) -> dict:
    """
    Write new content to a module with validation and optional backup.
    """
    accessible, reason = is_module_accessible(module_name)
    if not accessible:
        return {"ok": False, "message": reason}
    
    if not module_name.endswith(".py"):
        module_name = module_name + ".py"
    
    # Validate syntax first
    syntax_result = validate_syntax(content)
    if syntax_result.get("valid") is False:
        return {
            "ok": False,
            "message": f"SYNTAX ERROR: {syntax_result.get('message')}. Code not written."
        }
    
    module_path = APP_BASE / module_name
    
    # Create backup if requested
    if create_backup and module_path.exists():
        backup_result = backup_module(module_name)
        if not backup_result["ok"]:
            return {"ok": False, "message": f"Backup failed, aborting write: {backup_result['message']}"}
    
    try:
        with open(module_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"[RepairTools] Wrote {len(content)} bytes to {module_name}")
        
        # Try to hot reload
        reload_result = hot_reload_module(module_name)
        
        # Try to git sync
        git_msg = f"Auto-repair: Updated {module_name} via Diagnostic Mode"
        git_result = git_sync_changes(module_path, git_msg)
        
        return {
            "ok": True,
            "module": module_name,
            "bytes_written": len(content),
            "reload_success": reload_result.get("ok", False),
            "reload_message": reload_result.get("message", ""),
            "git_sync": git_result,
            "message": f"Successfully wrote and reloaded {module_name}. {git_result.get('message', '')}"
        }
    except Exception as e:
        logger.error(f"[RepairTools] Write failed: {e}")
        return {"ok": False, "message": f"WRITE ERROR: {str(e)}"}


def hot_reload_module(module_name: str) -> dict:
    """
    Hot reload a module using importlib.
    """
    if not module_name.endswith(".py"):
        module_name = module_name + ".py"
    
    # Convert file name to module path
    module_import_name = f"app.{module_name[:-3]}"  # Remove .py, add app. prefix
    
    try:
        if module_import_name in sys.modules:
            module = sys.modules[module_import_name]
            importlib.reload(module)
            logger.info(f"[RepairTools] Hot reloaded {module_import_name}")
            return {"ok": True, "message": f"Hot reloaded {module_name}"}
        else:
            # Module not loaded yet, just import it
            importlib.import_module(module_import_name)
            logger.info(f"[RepairTools] Imported {module_import_name}")
            return {"ok": True, "message": f"Imported {module_name}"}
    except Exception as e:
        logger.error(f"[RepairTools] Hot reload failed: {e}")
        return {"ok": False, "message": f"RELOAD ERROR: {str(e)}"}


def get_module_outline(module_name: str) -> dict:
    """
    Get a structural outline of a module (classes, functions, imports).
    """
    read_result = read_module(module_name)
    if not read_result["ok"]:
        return read_result
    
    content = read_result["content"]
    
    try:
        tree = ast.parse(content)
        
        outline = {
            "imports": [],
            "classes": [],
            "functions": [],
            "globals": []
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    outline["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                outline["imports"].append(f"from {node.module}")
            elif isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                outline["classes"].append({"name": node.name, "line": node.lineno, "methods": methods})
            elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                # Top-level function
                outline["functions"].append({"name": node.name, "line": node.lineno})
        
        return {
            "ok": True,
            "module": module_name,
            "outline": outline,
            "message": f"Outline: {len(outline['classes'])} classes, {len(outline['functions'])} functions"
        }
    except Exception as e:
        return {"ok": False, "message": f"PARSE ERROR: {str(e)}"}
