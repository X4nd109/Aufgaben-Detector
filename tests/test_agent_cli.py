"""
test_agent_cli.py - Unit-Tests für die Agent-CLI Schnittstelle.
"""

import io
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
for _sub in [_SRC_DIR, os.path.join(_SRC_DIR, "core"), os.path.join(_SRC_DIR, "services"), os.path.join(_SRC_DIR, "ui")]:
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

from agent_cli import (
    normalize_argv,
    is_agent_cli_command,
    run_agent_cli,
    resolve_task,
    format_task_list_text,
    format_task_list_json,
    format_task_detail_text,
    format_guide_text,
    save_last_cli_task_ids,
    load_last_cli_task_ids,
)
from models import Task
from task_manager import TaskManager


class TestAgentCLI(unittest.TestCase):
    def setUp(self):
        self.sample_task1 = Task(
            id="test_task_1",
            platform="moodle",
            course="AM",
            course_full="Angewandte Mathematik",
            title="Mathe Übungsblatt 1",
            due_date_str="Morgen 23:59",
            status="offen",
            status_display="Open",
            url="https://moodle.test/1",
            details_loaded=True,
            teacher="BIM"
        )
        self.sample_task2 = Task(
            id="test_task_2",
            platform="teams",
            course="SEW",
            course_full="Softwareentwicklung",
            title="Python Programmieren",
            due_date_str="15.10. 12:00",
            status="completed",
            status_display="Completed",
            url="https://teams.test/2",
            details_loaded=True,
            teacher="EIJ"
        )

    def test_normalize_argv(self):
        """Testet die Normalisierung verschiedener Schreibweisen und Flags."""
        self.assertEqual(normalize_argv(["-list"]), ["list"])
        self.assertEqual(normalize_argv(["--list"]), ["list"])
        self.assertEqual(normalize_argv(["-show", "1"]), ["show", "1"])
        self.assertEqual(normalize_argv(["--show", "test_id"]), ["show", "test_id"])
        self.assertEqual(normalize_argv(["-download", "1"]), ["download", "1"])
        self.assertEqual(normalize_argv(["--download", "2"]), ["download", "2"])
        self.assertEqual(normalize_argv(["-add", "--title", "A", "--subject", "B"]), ["add", "--title", "A", "--subject", "B"])
        self.assertEqual(normalize_argv(["-done", "1"]), ["done", "1"])
        self.assertEqual(normalize_argv(["--complete", "1"]), ["done", "1"])
        self.assertEqual(normalize_argv(["-delete", "1"]), ["delete", "1"])
        self.assertEqual(normalize_argv(["-restore", "1"]), ["restore", "1"])
        self.assertEqual(normalize_argv(["-sync"]), ["sync"])
        self.assertEqual(normalize_argv(["--guide"]), ["guide"])
        self.assertEqual(normalize_argv(["-h"]), ["guide"])
        self.assertEqual(normalize_argv(["--help"]), ["guide"])
        self.assertEqual(normalize_argv(["-skill"]), ["skill"])
        self.assertEqual(normalize_argv(["--skill"]), ["skill"])
        self.assertEqual(normalize_argv(["--json"]), ["list", "--json"])
        self.assertEqual(normalize_argv(["-json"]), ["list", "--json"])

    def test_is_agent_cli_command(self):
        """Testet die Erkennung von CLI-Befehlen."""
        self.assertTrue(is_agent_cli_command(["list"]))
        self.assertTrue(is_agent_cli_command(["-list"]))
        self.assertTrue(is_agent_cli_command(["--list"]))
        self.assertTrue(is_agent_cli_command(["show", "1"]))
        self.assertTrue(is_agent_cli_command(["-show", "1"]))
        self.assertTrue(is_agent_cli_command(["download", "1"]))
        self.assertTrue(is_agent_cli_command(["add"]))
        self.assertTrue(is_agent_cli_command(["done", "1"]))
        self.assertTrue(is_agent_cli_command(["delete", "1"]))
        self.assertTrue(is_agent_cli_command(["restore", "1"]))
        self.assertTrue(is_agent_cli_command(["sync"]))
        self.assertTrue(is_agent_cli_command(["guide"]))
        self.assertTrue(is_agent_cli_command(["--help"]))
        self.assertTrue(is_agent_cli_command(["-h"]))
        self.assertTrue(is_agent_cli_command(["skill"]))
        self.assertTrue(is_agent_cli_command(["-skill"]))
        self.assertTrue(is_agent_cli_command(["--skill"]))
        self.assertTrue(is_agent_cli_command(["--json"]))

        self.assertFalse(is_agent_cli_command([]))
        self.assertFalse(is_agent_cli_command(["--teams-login"]))
        self.assertFalse(is_agent_cli_command(["--moodle-login"]))
        self.assertFalse(is_agent_cli_command(["--untis-sync"]))

    def test_format_task_list_text(self):
        """Testet die kompakte Textausgabe der Aufgabenliste."""
        output = format_task_list_text([self.sample_task1], total_count=1, status_filter="open")
        self.assertIn("test_task_1", output)
        self.assertIn("AM", output)
        self.assertIn("Mathe Übungsblatt 1", output)
        self.assertIn("Listed 1 task(s)", output)

    def test_format_task_list_json(self):
        """Testet die strukturierte JSON-Ausgabe der Aufgabenliste."""
        output_str = format_task_list_json([self.sample_task1, self.sample_task2])
        data = json.loads(output_str)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], "test_task_1")
        self.assertEqual(data[0]["course"], "AM")
        self.assertEqual(data[1]["id"], "test_task_2")
        self.assertEqual(data[1]["status"], "completed")

    def test_format_task_detail_text(self):
        """Testet die Detailansicht als Text."""
        mock_mgr = MagicMock()
        output = format_task_detail_text(self.sample_task1, mock_mgr)
        self.assertIn("Title:       Mathe Übungsblatt 1", output)
        self.assertIn("ID:          test_task_1", output)
        self.assertIn("Subject:     AM (Angewandte Mathematik)", output)
        self.assertIn("Teacher:     BIM", output)

    def test_format_guide_text(self):
        """Testet, dass der Agent-Guide wichtige Befehle enthält."""
        guide = format_guide_text()
        self.assertIn("tasks list", guide)
        self.assertIn("tasks show", guide)
        self.assertIn("tasks download", guide)
        self.assertIn("tasks add", guide)
        self.assertIn("tasks done", guide)
        self.assertIn("tasks delete", guide)
        self.assertIn("tasks sync", guide)

    def test_last_cli_task_ids_cache(self):
        """Testet das Speichern und Laden der zuletzt aufgelisteten IDs."""
        test_ids = ["task_alpha", "task_beta", "task_gamma"]
        save_last_cli_task_ids(test_ids)
        loaded = load_last_cli_task_ids()
        self.assertEqual(loaded, test_ids)

    def test_resolve_task_by_id_and_index(self):
        """Testet das Auflösen einer Aufgabe per ID und per Index."""
        mock_mgr = MagicMock()
        mock_mgr.tasks = [self.sample_task1, self.sample_task2]
        mock_mgr.get_deleted_tasks.return_value = []
        mock_mgr.get_filtered_tasks.return_value = [self.sample_task1, self.sample_task2]

        save_last_cli_task_ids(["test_task_1", "test_task_2"])

        # 1. Per Index 1
        resolved_1 = resolve_task(mock_mgr, "1")
        self.assertIsNotNone(resolved_1)
        self.assertEqual(resolved_1.id, "test_task_1")

        # 2. Per Index 2
        resolved_2 = resolve_task(mock_mgr, "2")
        self.assertIsNotNone(resolved_2)
        self.assertEqual(resolved_2.id, "test_task_2")

        # 3. Per exakter ID
        resolved_id = resolve_task(mock_mgr, "test_task_1")
        self.assertEqual(resolved_id.id, "test_task_1")

        # 4. Per Präfix
        resolved_pre = resolve_task(mock_mgr, "test_task_2")
        self.assertEqual(resolved_pre.id, "test_task_2")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_run_agent_cli_guide(self, mock_stdout):
        """Testet das Ausführen von `tasks guide`."""
        exit_code = run_agent_cli(["guide"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Agent CLI Reference", mock_stdout.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_run_agent_cli_add_and_validation(self, mock_stdout):
        """Testet das Hinzufügen einer Aufgabe und Validierung."""
        # Ohne Parameter -> Fehler
        exit_code_err = run_agent_cli(["add"])
        self.assertEqual(exit_code_err, 1)
        self.assertIn("Error: --title and --subject are required", mock_stdout.getvalue())

    def test_find_best_course_match(self):
        """Testet das Auffinden von Kursen per Fachkürzel und Name."""
        from agent_cli import find_best_course_match
        best, all_m = find_best_course_match("sesd")
        self.assertIsNotNone(best)
        self.assertEqual(best["subject"], "SESD")
        self.assertIn("11856", best["url"])

        # Unbekannter Kurs
        none_match, _ = find_best_course_match("unbekanntesfachxyz123")
        self.assertIsNone(none_match)

    @patch("config.load_full_school_config", return_value={"student_class": "3AHWII"})
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_run_agent_cli_courses(self, mock_stdout, mock_cfg):
        """Testet den `tasks courses` Befehl."""
        exit_code = run_agent_cli(["courses"])
        self.assertEqual(exit_code, 0)
        output = mock_stdout.getvalue()
        self.assertIn("PLATFORM", output)
        self.assertIn("SESD", output)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_run_agent_cli_open_json(self, mock_stdout):
        """Testet `tasks open sesd --json --no-browse`."""
        exit_code = run_agent_cli(["open", "sesd", "--json", "--no-browse"])
        self.assertEqual(exit_code, 0)
        data = json.loads(mock_stdout.getvalue())
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("subject"), "SESD")
        self.assertIn("moodle", data.get("platform"))
        self.assertIn("11856", data.get("url"))

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_run_agent_cli_open_flag_syntax(self, mock_stdout):
        """Testet die Flag-Syntax `-open sesd`."""
        exit_code = run_agent_cli(["-open", "sesd", "--no-browse"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Opening [Moodle]", mock_stdout.getvalue())
        self.assertIn("SESD", mock_stdout.getvalue())


    def test_run_agent_cli_skill_sync_and_status(self):
        """Testet 'tasks skill sync' und 'tasks skill status'."""
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Status vor der Installation (nicht installiert)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                exit_code = run_agent_cli(["skill", "status", "--target", tmpdir, "--json"])
                self.assertEqual(exit_code, 0)
                data = json.loads(mock_stdout.getvalue())
                self.assertFalse(data.get("installed"))

            # 2. Installation / Sync
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                exit_code = run_agent_cli(["skill", "sync", "--target", tmpdir, "--json"])
                self.assertEqual(exit_code, 0)
                data = json.loads(mock_stdout.getvalue())
                self.assertTrue(data.get("success"))
                self.assertTrue(os.path.exists(os.path.join(tmpdir, "SKILL.md")))

            # 3. Status nach Installation (installiert und in sync)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                exit_code = run_agent_cli(["skill", "status", "--target", tmpdir, "--json"])
                self.assertEqual(exit_code, 0)
                data = json.loads(mock_stdout.getvalue())
                self.assertTrue(data.get("installed"))
                self.assertTrue(data.get("in_sync"))


if __name__ == "__main__":
    unittest.main()
