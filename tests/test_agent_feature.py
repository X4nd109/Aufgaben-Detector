"""
test_agent_feature.py - Unit tests for Agentic Coding Tool integration,
file export to custom project folders, clipboard path copying, and TUI/CLI integration.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.models import Task, TaskAttachment
from core.config import (
    load_agent_coding_tool,
    save_agent_coding_tool,
)
from services.ai_agent_service import (
    launch_coding_tool,
    export_task_to_folder,
    run_agent_workflow,
)
from core.agent_cli import run_agent_cli, is_agent_cli_command


class TestAgentFeature(unittest.TestCase):

    def setUp(self):
        self.sample_task = Task(
            id="test_agent_task_1",
            platform="moodle",
            course="AMEC",
            course_full="Angewandte Mechatronik",
            title="Aufgabe 04: Motorregelung mit PID",
            due_date_str="Montag, 27. Okt., 23:59",
            status="offen",
            status_display="Noch offen",
            url="https://moodle.spengergasse.at/mod/assign/view.php?id=9999",
            teacher="KRD",
            description="Programmiere einen PID-Regler in C++ für die Drehzahlregelung.",
            attachments=[
                TaskAttachment(name="pid_schaltplan.pdf", url="https://moodle.spengergasse.at/pid1"),
            ],
            details_loaded=True,
        )

    def test_config_agent_coding_tool_persistence(self):
        original = load_agent_coding_tool()
        try:
            fake_exe = r"C:\Tools\Antigravity\antigravity.exe"
            save_agent_coding_tool(fake_exe, auto_push=False)
            self.assertEqual(load_agent_coding_tool(), fake_exe)

            # Test clearing
            save_agent_coding_tool(None, auto_push=False)
            self.assertIsNone(load_agent_coding_tool())
        finally:
            save_agent_coding_tool(original, auto_push=False)

    @patch("subprocess.Popen")
    @patch("os.path.exists")
    def test_launch_coding_tool(self, mock_exists, mock_popen):
        mock_exists.return_value = True
        result = launch_coding_tool(r"C:\Tools\Antigravity\antigravity.exe")
        self.assertTrue(result)
        mock_popen.assert_called_once()

    def test_launch_coding_tool_nonexistent(self):
        result = launch_coding_tool(r"C:\Nonexistent\Tool\tool.exe")
        self.assertFalse(result)

    @patch("subprocess.Popen")
    @patch("services.ai_agent_service.copy_to_clipboard")
    @patch("os.path.exists")
    def test_run_agent_workflow(self, mock_exists, mock_clip, mock_popen):
        mock_exists.return_value = True
        mock_clip.return_value = True

        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = MagicMock()
            mgr.download_task_files.return_value = [os.path.join(tmpdir, "angabe.md")]

            success, files, msg = run_agent_workflow(
                self.sample_task,
                mgr,
                tmpdir,
                exe_path=r"C:\Tools\Antigravity\antigravity.exe",
                launch_tool=True,
            )
            self.assertTrue(success)
            self.assertEqual(len(files), 1)
            self.assertIn("Files exported", msg)
            mock_clip.assert_called_with(os.path.abspath(tmpdir))
            mock_popen.assert_called_once()

    def test_is_agent_cli_command(self):
        self.assertTrue(is_agent_cli_command(["agent", "1"]))
        self.assertTrue(is_agent_cli_command(["ai-agent", "moodle_1"]))
        self.assertTrue(is_agent_cli_command(["--agent", "1"]))

    def test_cli_agent_command(self):
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmpdir:
            out = io.StringIO()
            with redirect_stdout(out):
                ret = run_agent_cli(["agent", "1", "--dir", tmpdir, "--no-launch", "--json"])
            self.assertEqual(ret, 0)
            data = json.loads(out.getvalue())
            self.assertTrue(data.get("success"))
            self.assertIn("directory", data)
            self.assertEqual(os.path.abspath(tmpdir), data.get("directory"))

    def test_task_detail_modal_contains_agent_button(self):
        from tui_app import TaskDetailModal
        mgr = MagicMock()
        modal = TaskDetailModal(self.sample_task, mgr)
        binding_keys = [b.key for b in modal.BINDINGS]
        self.assertIn("g", binding_keys)

    def test_ai_config_choice_modal(self):
        from tui_app import AiConfigChoiceModal
        modal = AiConfigChoiceModal()
        self.assertIsNotNone(modal)
        modal.dismiss = MagicMock()
        modal.action_choose_explain()
        modal.dismiss.assert_called_with("explain")
        modal.action_choose_agent()
        modal.dismiss.assert_called_with("agent")

    def test_ai_agent_config_modal(self):
        from tui_app import AiAgentConfigModal
        modal = AiAgentConfigModal()
        self.assertIsNotNone(modal)
        # Test clear
        modal.action_clear()
        self.assertEqual(modal.current_tool_path, "")


if __name__ == "__main__":
    unittest.main()
