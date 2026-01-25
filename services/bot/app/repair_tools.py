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
