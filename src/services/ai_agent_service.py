"""
ai_agent_service.py - Service zum Exportieren von Aufgaben in Agent-Projekte
und Starten von Agentic Coding Tools (Antigravity, Cursor, VS Code, etc.).
"""

import os
import subprocess
import sys
from typing import List, Optional, Tuple

from core.config import load_agent_coding_tool
from core.models import Task
from core.task_manager import TaskManager
from services.ai_explain_service import copy_to_clipboard


def launch_coding_tool(exe_path: str) -> bool:
    """
    Startet die Executable des konfigurierten Coding-Tools als unabhängigen
    Hintergrundprozess (detached), ohne die Anwendung zu blockieren.
    """
    if not exe_path or not os.path.exists(exe_path):
        return False

    try:
        flags = 0
        if sys.platform == "win32":
            # DETACHED_PROCESS = 0x00000008
            flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

        subprocess.Popen(
            [exe_path],
            close_fds=True,
            creationflags=flags,
            shell=False,
        )
        return True
    except Exception as e:
        print(f"Error launching coding tool '{exe_path}': {e}", file=sys.stderr)
        return False


def export_task_to_folder(task: Task, mgr: TaskManager, target_dir: str) -> List[str]:
    """
    Lädt alle Anhänge und die 'angabe.md' der Aufgabe direkt in das angegebene Verzeichnis herunter.
    """
    os.makedirs(target_dir, exist_ok=True)
    return mgr.download_task_files(task, dest_dir=target_dir)


def run_agent_workflow(
    task: Task,
    mgr: TaskManager,
    target_dir: str,
    exe_path: Optional[str] = None,
    launch_tool: bool = True,
) -> Tuple[bool, List[str], str]:
    """
    Führt den kompletten Agent-Workflow aus:
    1. Herunterladen aller Aufgaben-Dateien & angabe.md in target_dir.
    2. Absoluten Verzeichnispfad in die System-Zwischenablage kopieren.
    3. Start des Agentic Coding Tools (falls launch_tool=True).

    Rückgabe:
        (success, list_of_downloaded_files, status_message)
    """
    if not target_dir:
        return False, [], "No target directory specified."

    clean_dir = os.path.abspath(os.path.expanduser(target_dir))
    os.makedirs(clean_dir, exist_ok=True)

    # 1. Dateien herunterladen
    files = export_task_to_folder(task, mgr, clean_dir)

    # 2. Pfad in die Zwischenablage kopieren
    copy_to_clipboard(clean_dir)

    # 3. Coding Tool starten
    tool = exe_path or load_agent_coding_tool()
    launched = False
    if launch_tool:
        if tool and os.path.exists(tool):
            launched = launch_coding_tool(tool)
        elif tool:
            return False, files, f"Coding tool not found at: '{tool}'"

    tool_name = os.path.splitext(os.path.basename(tool))[0] if tool else "Coding Tool"
    if launched:
        msg = f"✓ Files exported, path copied & {tool_name} launched!"
    else:
        msg = f"✓ Files exported & path copied to clipboard ({clean_dir})"

    return True, files, msg
