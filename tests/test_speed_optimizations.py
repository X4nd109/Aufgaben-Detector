"""
test_speed_optimizations.py - Unit and integration tests for task detail speed optimizations.
"""

import os
import sys
import time
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import src

from models import Task, TaskAttachment
import moodle_service
from moodle_service import (
    MoodlePageParser,
    fetch_moodle_task_details_http,
    fetch_moodle_task_details,
    html_to_markdown,
    parse_moodle_calendar_events,
    parse_moodle_assign_index,
    fetch_moodle_tasks_http,
    fetch_moodle_tasks,
)

import teams_service
from teams_service import format_teams_description, extract_teams_attachments
from task_manager import TaskManager, parse_deadline_for_sorting
from auth import get_saved_moodle_cookies


class TestMoodleHttpDetails(unittest.TestCase):
    def test_parser_with_intro_and_table_and_attachments(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Aufgabe 1</title></head>
        <body>
            <div class="page-header-headings"><h1>Test Hausaufgabe 1</h1></div>
            <div class="activity-description" id="intro">
                <div class="no-overflow">
                    <p>Hier ist die <strong>Aufgabenbeschreibung</strong>:</p>
                    <ul>
                        <li>Erster Schritt</li>
                        <li>Zweiter Schritt</li>
                    </ul>
                </div>
            </div>
            <table class="generaltable submissionstatustable">
                <tbody>
                    <tr><th class="header">Abgabestatus</th><td class="cell">Zur Bewertung abgegeben</td></tr>
                    <tr><th class="header">Fälligkeitsdatum</th><td class="cell">Donnerstag, 1. Okt. 2026, 23:59</td></tr>
                    <tr><th class="header">Verbleibende Zeit</th><td class="cell">2 Tage 5 Stunden</td></tr>
                </tbody>
            </table>
            <div class="files">
                <a href="https://moodle.spengergasse.at/theme/image.php/boost/core/123/icon">Icon</a>
                <a href="https://moodle.spengergasse.at/pluginfile.php/12345/mod_assign/intro/Angabe.pdf?forcedownload=1">Angabe.pdf</a>
            </div>
        </body>
        </html>
        """
        parser = MoodlePageParser()
        parser.feed(html)

        self.assertEqual(parser.title.strip(), "Test Hausaufgabe 1")
        intro_md = html_to_markdown("".join(parser.intro_html_parts).strip())
        self.assertIn("Hier ist die **Aufgabenbeschreibung**:", intro_md)
        self.assertIn("* Erster Schritt", intro_md)

        # Status map
        self.assertIn("abgabestatus", parser.status_map)
        self.assertEqual(parser.status_map["abgabestatus"], "Zur Bewertung abgegeben")
        self.assertIn("fälligkeitsdatum", parser.status_map)

        # Attachments (icon excluded, Angabe.pdf included)
        self.assertEqual(len(parser.attachments), 1)
        self.assertEqual(parser.attachments[0].name, "Angabe.pdf")
        self.assertIn("pluginfile.php", parser.attachments[0].url)

    def test_parser_overdue_and_not_submitted(self):
        html = """
        <div id="intro"><p>Einfacher Text</p></div>
        <table class="submissionstatustable">
            <tr><th>Abgabestatus</th><td>Keine Abgabe</td></tr>
            <tr><th>Fälligkeitsdatum</th><td>Gestern, 27. Sept., 23:59</td></tr>
            <tr><th>Verbleibende Zeit</th><td>Die Aufgabe ist überfällig um: 1 Tag</td></tr>
        </table>
        """
        parser = MoodlePageParser()
        parser.feed(html)

        task = Task(
            id="m_test",
            platform="moodle",
            course="SWP",
            course_full="Softwareentwicklung",
            title="SWP Test",
            due_date_str="",
            status="offen",
            status_display="",
            url="https://moodle.spengergasse.at/mod/assign/view.php?id=9999"
        )

        status_disp = parser.status_map.get("abgabestatus")
        if status_disp:
            task.status_display = status_disp
            s_lower = status_disp.lower()
            if any(neg in s_lower for neg in ["keine", "kein", "nichts", "nicht", "not"]):
                task.status = "offen"
            elif any(kw in s_lower for kw in ["abgegeben", "submitted"]):
                task.status = "abgegeben"

        rem_val = parser.status_map.get("verbleibende zeit")
        if rem_val and any(kw in rem_val.lower() for kw in ["überfällig", "ueberfaellig", "overdue"]):
            task.status = "ueberfaellig"

        self.assertEqual(task.status, "ueberfaellig")
        self.assertEqual(task.status_display, "Keine Abgabe")

    def test_parser_moodle4_activity_dates(self):
        html = """
        <div class="page-header-headings"><h1>BET Ü1: Kalkulatorische Abschreibung</h1></div>
        <div data-region="activity-dates" class="activity-dates">
            <div class="date-item">
                <span class="date-item-label">Geöffnet:</span> Dienstag, 22. September 2026, 00:00
            </div>
            <div class="date-item">
                <span class="date-item-label">Fällig:</span> Donnerstag, 1. Oktober 2026, 00:00
            </div>
        </div>
        <div class="activity-description" id="intro">
            <p>Löse die Aufgabe im Buch.</p>
        </div>
        <table class="generaltable table table-striped table-bordered table-hover">
            <tbody>
                <tr><th>Abgabestatus</th><td>Bisher wurden keine Aufgaben abgegeben</td></tr>
                <tr><th>Verbleibende Zeit</th><td>Verbleibend: 2 Tage 16 Stunden</td></tr>
            </tbody>
        </table>
        """
        parser = MoodlePageParser()
        parser.feed(html)

        self.assertEqual(parser.title, "BET Ü1: Kalkulatorische Abschreibung")
        self.assertEqual(parser.due_date, "Donnerstag, 1. Oktober 2026, 00:00")
        self.assertIn("Löse die Aufgabe im Buch.", "".join(parser.intro_html_parts))

    def test_parser_title_with_nested_tags(self):
        html = "<h1>Aufgabe 1: <span>Einführung</span> in <b>Python</b></h1>"
        parser = MoodlePageParser()
        parser.feed(html)
        self.assertEqual(parser.title, "Aufgabe 1: Einführung in Python")

    def test_parser_no_intro_pollution_by_generalbox(self):
        html = """
        <div id="intro"><p>Echte Angabe</p></div>
        <table class="submissionstatustable"><tr><th>Status</th><td>Offen</td></tr></table>
        <div class="box py-3 generalbox"><p>Footer oder Kommentare</p></div>
        """
        parser = MoodlePageParser()
        parser.feed(html)
        intro_text = "".join(parser.intro_html_parts)
        self.assertIn("Echte Angabe", intro_text)
        self.assertNotIn("Footer oder Kommentare", intro_text)

    def test_parser_relative_attachment_url(self):
        html = '<a href="/pluginfile.php/4567/mod_assign/intro/sheet.pdf">sheet.pdf</a>'
        parser = MoodlePageParser(base_url="https://moodle.spengergasse.at/mod/assign/view.php?id=100")
        parser.feed(html)
        self.assertEqual(len(parser.attachments), 1)
        self.assertEqual(parser.attachments[0].name, "sheet.pdf")
        self.assertEqual(parser.attachments[0].url, "https://moodle.spengergasse.at/pluginfile.php/4567/mod_assign/intro/sheet.pdf")

    @patch("moodle_service.get_saved_moodle_cookies")
    @patch("requests.Session.get")
    def test_fetch_moodle_task_details_http_mocked_success(self, mock_get, mock_cookies):
        mock_cookies.return_value = [{"name": "MoodleSession", "value": "xyz123"}]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://moodle.spengergasse.at/mod/assign/view.php?id=555"
        mock_resp.encoding = "utf-8"
        mock_resp.text = """
        <div class="page-header-headings"><h1>SWP Assignment 5</h1></div>
        <div data-region="activity-dates" class="activity-dates">
            <div class="date-item"><span class="date-item-label">Fällig:</span> Freitag, 2. Okt. 2026, 23:59</div>
        </div>
        <div id="intro"><p>Implementiere das Observer-Pattern.</p></div>
        <table class="submissionstatustable">
            <tr><th>Abgabestatus</th><td>Keine Abgabe</td></tr>
        </table>
        <a href="https://moodle.spengergasse.at/pluginfile.php/555/mod_assign/intro/observer.zip">observer.zip</a>
        """
        mock_get.return_value = mock_resp

        task = Task(
            id="moodle_555",
            platform="moodle",
            course="SWP",
            course_full="Softwareentwicklung",
            title="",
            due_date_str="Keine Frist",
            status="offen",
            status_display="Offen",
            url="https://moodle.spengergasse.at/mod/assign/view.php?id=555"
        )
        success = fetch_moodle_task_details_http(task)
        self.assertTrue(success)
        self.assertTrue(task.details_loaded)
        self.assertEqual(task.title, "SWP Assignment 5")
        self.assertEqual(task.due_date_str, "Freitag, 2. Okt. 2026, 23:59")
        self.assertIn("Observer-Pattern", task.description)
        self.assertEqual(len(task.attachments), 1)
        self.assertEqual(task.attachments[0].name, "observer.zip")

    @patch("moodle_service.get_saved_moodle_cookies")
    @patch("requests.Session.get")
    def test_fetch_moodle_task_details_http_expired_or_login(self, mock_get, mock_cookies):
        mock_cookies.return_value = [{"name": "MoodleSession", "value": "expired"}]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://moodle.spengergasse.at/login/index.php"
        mock_resp.text = '<form id="login">Anmelden</form>'
        mock_get.return_value = mock_resp

        task = Task(
            id="moodle_555", platform="moodle", course="SWP", course_full="SWP",
            title="Task", due_date_str="Keine Frist", status="offen", status_display="Offen",
            url="https://moodle.spengergasse.at/mod/assign/view.php?id=555"
        )
        success = fetch_moodle_task_details_http(task)
        self.assertFalse(success)
        self.assertFalse(task.details_loaded)

    @patch("moodle_service.fetch_moodle_task_details_http")
    @patch("moodle_service.sync_playwright")
    def test_fetch_moodle_task_details_fallback(self, mock_playwright, mock_http):
        mock_http.return_value = False
        task = Task(
            id="m_fallback", platform="moodle", course="SWP", course_full="SWP",
            title="Task Fallback", due_date_str="Keine Frist", status="offen", status_display="Offen",
            url="https://moodle.spengergasse.at/mod/assign/view.php?id=777"
        )
        # Mock Playwright context
        mock_browser = MagicMock()
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_ctx
        mock_ctx.new_page.return_value = mock_page

        with patch("moodle_service.ensure_moodle_session", return_value=False):
            fetch_moodle_task_details(task)
            # Confirmed fallback was triggered
            mock_http.assert_called_once_with(task)
            mock_browser.close.assert_called()

    def test_live_moodle_http_fetch_if_authenticated(self):
        cookies = get_saved_moodle_cookies()
        if not cookies:
            self.skipTest("Keine gespeicherten Moodle-Cookies verfügbar")

        task = Task(
            id="moodle_389152",
            platform="moodle",
            course="BET",
            course_full="Betriebstechnik",
            title="BET Ü1",
            due_date_str="Keine Frist",
            status="offen",
            status_display="Offen",
            url="https://moodle.spengergasse.at/mod/assign/view.php?id=389152"
        )
        t0 = time.time()
        success = fetch_moodle_task_details_http(task)
        elapsed = time.time() - t0

        if not success:
            self.skipTest("Gespeicherte Moodle-Session ist auf dem Live-Server abgelaufen")

        self.assertTrue(success, "HTTP-Abruf sollte erfolgreich sein")
        self.assertTrue(task.details_loaded)
        self.assertGreater(len(task.description), 10)
        self.assertEqual(task.due_date_str, "Donnerstag, 1. Oktober 2026, 00:00")
        self.assertLess(elapsed, 3.0, f"HTTP-Abruf sollte blitzschnell sein (<3s), dauerte {elapsed:.2f}s")


class TestTeamsAcceleration(unittest.TestCase):
    def test_format_teams_description_dict(self):
        raw = {"content": "<div><h1>Projekt</h1><p>Bitte <b>PDF</b> hochladen.</p></div>"}
        out = format_teams_description(raw)
        self.assertIn("Projekt", out)
        self.assertIn("Bitte", out)
        self.assertNotIn("<div>", out)
        self.assertNotIn("<p>", out)

    def test_format_teams_description_with_images_and_scripts(self):
        raw = "<p>Siehe Grafik: <img src='test.png'> und <style>body{}</style><script>alert(1)</script> fertig.</p>"
        out = format_teams_description(raw)
        self.assertIn("[Bild]", out)
        self.assertNotIn("alert", out)
        self.assertNotIn("body{}", out)
        self.assertIn("fertig.", out)

    def test_format_teams_description_with_lists_and_entities(self):
        raw = "<p>Teil 1&amp;2&nbsp;abgeben:</p><ul><li>Schritt A</li><li>Schritt B</li></ul>"
        out = format_teams_description(raw)
        self.assertIn("Teil 1&2 abgeben:", out)
        self.assertIn("* Schritt A", out)
        self.assertIn("* Schritt B", out)
        self.assertNotIn("&amp;", out)
        self.assertNotIn("&nbsp;", out)

    def test_empty_teams_instructions_not_marked_details_loaded(self):
        # Empty dict or empty content
        desc = format_teams_description({"content": ""})
        self.assertEqual(desc, "")
        self.assertFalse(bool(desc.strip()))

        desc2 = format_teams_description({})
        self.assertEqual(desc2, "")

    def test_extract_teams_attachments(self):
        resources = [
            {"resource": {"displayName": "Handout.docx", "downloadUrl": "https://example.com/handout.docx"}},
            {"resource": {"displayName": "Dataset.csv", "webUrl": "https://example.com/dataset.csv"}}
        ]
        atts = extract_teams_attachments(resources, default_url="https://teams.microsoft.com")
        self.assertEqual(len(atts), 2)
        self.assertEqual(atts[0].name, "Handout.docx")
        self.assertEqual(atts[0].url, "https://example.com/handout.docx")
        self.assertEqual(atts[1].name, "Dataset.csv")
        self.assertEqual(atts[1].url, "https://example.com/dataset.csv")

    def test_teams_payload_sets_details_at_sync(self):
        item = {
            "id": "abc-123",
            "displayName": "UFW Fallstudie",
            "instructions": {"content": "<p>Bearbeiten Sie Fallstudie 4.</p>"},
            "resources": [{"resource": {"displayName": "Fallstudie4.pdf", "downloadUrl": "https://example.com/f4.pdf"}}]
        }
        desc = format_teams_description(item.get("instructions"))
        atts = extract_teams_attachments(item.get("resources"))
        details_loaded = bool(desc.strip() or atts)

        task = Task(
            id=f"teams_{item['id']}",
            platform="teams",
            course="UFW",
            course_full="3AHWII UFW",
            title=item["displayName"],
            due_date_str="Morgen",
            status="offen",
            status_display="Zugewiesen",
            url="https://teams.microsoft.com",
            description=desc,
            attachments=atts,
            details_loaded=details_loaded
        )

        self.assertTrue(task.details_loaded)
        self.assertIn("Bearbeiten Sie Fallstudie 4.", task.description)
        self.assertEqual(len(task.attachments), 1)
        self.assertEqual(task.attachments[0].name, "Fallstudie4.pdf")

    @patch("teams_service.check_teams_session", return_value=True)
    @patch("teams_service.sync_playwright")
    def test_fetch_teams_tasks_reactive_break_on_intercept(self, mock_playwright, mock_session):
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_page.url = "https://teams.microsoft.com"
        mock_ctx.pages = [mock_page]
        mock_playwright.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = mock_ctx

        def fake_goto(url, **kwargs):
            for call in mock_page.on.call_args_list:
                event_name, handler = call[0]
                if event_name == "response":
                    mock_resp = MagicMock()
                    mock_resp.url = "https://assignments.edu.cloud.microsoft/api/v1.0/assignments"
                    mock_resp.headers = {"content-type": "application/json"}
                    mock_resp.json.return_value = {
                        "value": [{
                            "id": "teams-react-1",
                            "displayName": "Schnelle Aufgabe",
                            "dueDateTime": "2026-10-01T12:00:00Z",
                            "classDisplayName": "SWP 3AHWII",
                            "status": "assigned"
                        }]
                    }
                    handler(mock_resp)

        mock_page.goto.side_effect = fake_goto
        mock_page.query_selector.return_value = None

        t0 = time.time()
        tasks = teams_service.fetch_teams_tasks()
        elapsed = time.time() - t0

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "teams_teams-react-1")
        self.assertEqual(tasks[0].title, "Schnelle Aufgabe")
        self.assertLess(elapsed, 1.5, f"Teams fetch should break reactively, took {elapsed:.2f}s")


class TestBackgroundPrefetcher(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_cache = os.path.join(self.temp_dir.name, "test_cache.json")
        self.patch_cache = patch("task_manager.CACHE_FILE", self.temp_cache)
        self.patch_cache.start()

        self.mgr = TaskManager(autostart_prefetch=False)
        self.mgr.tasks = [
            Task(
                id="t1", platform="moodle", course="SWP", course_full="SWP",
                title="Task 1 (Completed)", due_date_str="Gestern", status="abgegeben",
                status_display="Abgegeben", url="https://example.com/1",
                due_timestamp=1000.0, details_loaded=False
            ),
            Task(
                id="t2", platform="moodle", course="SWP", course_full="SWP",
                title="Task 2 (Open Soon)", due_date_str="Heute", status="offen",
                status_display="Offen", url="https://example.com/2",
                due_timestamp=2000.0, details_loaded=False
            ),
            Task(
                id="t3", platform="moodle", course="SWP", course_full="SWP",
                title="Task 3 (Open Later)", due_date_str="Morgen", status="offen",
                status_display="Offen", url="https://example.com/3",
                due_timestamp=3000.0, details_loaded=False
            ),
        ]

    def tearDown(self):
        self.mgr.stop_background_prefetch()
        self.patch_cache.stop()
        self.temp_dir.cleanup()

    def test_instant_return_when_details_already_loaded(self):
        t = self.mgr.tasks[1]
        t.details_loaded = True
        t.description = "Already loaded"

        t0 = time.time()
        res = self.mgr.load_task_details(t)
        elapsed = time.time() - t0

        self.assertEqual(res.description, "Already loaded")
        self.assertLess(elapsed, 0.05, f"Expected 0s instant return, took {elapsed:.4f}s")

    def test_prefetch_priority_logic(self):
        t_teams = Task(
            id="t_teams", platform="teams", course="UFW", course_full="UFW",
            title="Teams Open Task", due_date_str="Morgen", status="offen",
            status_display="Offen", url="https://teams.microsoft.com",
            due_timestamp=2500.0, details_loaded=False
        )
        candidates = [t for t in self.mgr.tasks if not t.details_loaded] + [t_teams]
        def prefetch_priority(t: Task):
            is_done = 1 if t.is_completed else 0
            is_fast = 0 if t.platform == "moodle" else 1
            is_over = 0 if t.is_overdue else 1
            ts = t.due_timestamp or 9999999999
            return (is_done, is_fast, is_over, ts)

        candidates.sort(key=prefetch_priority)
        self.assertEqual(candidates[0].id, "t2")
        self.assertEqual(candidates[1].id, "t3")
        self.assertEqual(candidates[2].id, "t_teams")
        self.assertEqual(candidates[3].id, "t1")

    def test_prefetch_worker_does_not_infinite_loop_on_failing_task(self):
        # t2 will fail HTTP and Playwright, t3 will succeed
        failing_task = self.mgr.tasks[1]
        succeeding_task = self.mgr.tasks[2]

        def fake_moodle_http(task):
            if task.id == failing_task.id:
                return False
            task.details_loaded = True
            task.description = "Success"
            return True

        with patch("moodle_service.fetch_moodle_task_details_http", side_effect=fake_moodle_http):
            with patch("moodle_service.fetch_moodle_task_details", side_effect=lambda t: t):
                self.mgr.start_background_prefetch()
                # Wait up to 3 seconds for prefetcher to process both candidates and finish
                t_wait = time.time()
                while time.time() - t_wait < 3.0:
                    if succeeding_task.details_loaded:
                        break
                    time.sleep(0.1)

                self.assertTrue(succeeding_task.details_loaded, "Succeeding task must be loaded even if earlier task fails")
                self.assertFalse(failing_task.details_loaded)

    def test_save_cache_preserves_last_sync(self):
        initial_sync_time = 1700000000.0
        self.mgr.last_sync = initial_sync_time
        with patch("builtins.open", unittest.mock.mock_open()):
            with patch("json.dump") as mock_dump:
                self.mgr.save_cache()
                saved_data = mock_dump.call_args[0][0]
                self.assertEqual(saved_data["last_sync"], initial_sync_time)

    def test_sync_preserves_cached_due_date_when_new_sync_is_keine_frist(self):
        # Previously cached task has real deadline loaded from details
        cached_task = Task(
            id="moodle_101", platform="moodle", course="BET", course_full="BET",
            title="BET Task", due_date_str="Donnerstag, 1. Oktober 2026, 00:00",
            status="offen", status_display="Offen", url="https://example.com/bet",
            details_loaded=True, description="Angabe"
        )
        self.mgr.tasks = [cached_task]

        # New sync returns the task from calendar with "Keine Frist"
        new_synced_task = Task(
            id="moodle_101", platform="moodle", course="BET", course_full="BET",
            title="BET Task", due_date_str="Keine Frist",
            status="offen", status_display="Offen", url="https://example.com/bet",
            details_loaded=False
        )

        with patch("moodle_service.fetch_moodle_tasks", return_value=[new_synced_task]):
            with patch("teams_service.fetch_teams_tasks", return_value=[]):
                self.mgr.sync()
                res = self.mgr.tasks[0]
                self.assertEqual(res.due_date_str, "Donnerstag, 1. Oktober 2026, 00:00")
                self.assertTrue(res.details_loaded)

    def test_cache_thread_safety(self):
        errors = []

        def worker(thread_id):
            try:
                for i in range(10):
                    self.mgr.get_filtered_tasks(status_filter="all")
                    with self.mgr._cache_lock:
                        if self.mgr.tasks:
                            self.mgr.tasks[0].status_display = f"Worker {thread_id} run {i}"
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        self.assertEqual(len(errors), 0, f"Thread safety errors occurred: {errors}")

    def test_prefetch_thread_lifecycle(self):
        self.assertFalse(self.mgr._prefetch_thread and self.mgr._prefetch_thread.is_alive())
        self.mgr.start_background_prefetch()
        self.assertTrue(self.mgr._prefetch_thread.is_alive())
        self.mgr.stop_background_prefetch()
        self.assertFalse(self.mgr._prefetch_thread.is_alive())


class TestMoodleHttpTasksFetch(unittest.TestCase):
    def test_parse_moodle_calendar_events_success(self):
        html_content = """
        <div data-type="event" data-course-id="12418" class="event mt-3" data-event-component="mod_assign">
            <h3 class="name d-inline-block">PRE301-Ü1: 635-Methode ist fällig.</h3>
            <span class="date text-danger">Heute, 28. September, 08:00</span>
            <a href="https://moodle.spengergasse.at/course/view.php?id=12418">SWP - Softwareentwicklung</a>
            <a href="https://moodle.spengergasse.at/mod/assign/view.php?id=376997&amp;action=editsubmission" class="card-link">Zur Aktivität gehen</a>
        </div>
        <div data-type="event" data-course-id="11856" class="event mt-3" data-event-component="mod_assign">
            <h3 class="name d-inline-block">TryHackMe Security is due.</h3>
            <span class="date">Morgen, 29. September, 17:00</span>
            <a href="https://moodle.spengergasse.at/course/view.php?id=11856">SESD - Security</a>
            <a href="/mod/assign/view.php?id=359544" class="card-link">Zur Aktivität gehen</a>
        </div>
        """
        events = parse_moodle_calendar_events(html_content, base_url="https://moodle.spengergasse.at")
        self.assertEqual(len(events), 2)

        self.assertEqual(events[0]["id"], "moodle_376997")
        self.assertEqual(events[0]["title"], "PRE301-Ü1: 635-Methode")
        self.assertEqual(events[0]["date_str"], "Heute, 28. September, 08:00")
        self.assertEqual(events[0]["course_full"], "SWP - Softwareentwicklung")
        self.assertEqual(events[0]["url"], "https://moodle.spengergasse.at/mod/assign/view.php?id=376997")

        self.assertEqual(events[1]["id"], "moodle_359544")
        self.assertEqual(events[1]["title"], "TryHackMe Security")
        self.assertEqual(events[1]["date_str"], "Morgen, 29. September, 17:00")
        self.assertEqual(events[1]["url"], "https://moodle.spengergasse.at/mod/assign/view.php?id=359544")

    def test_parse_moodle_calendar_events_ignores_non_assign(self):
        html_content = """
        <div data-type="event" class="event mt-3">
            <h3 class="name">Schulautonome Tage</h3>
            <span class="date">26. Oktober</span>
            <a href="https://moodle.spengergasse.at/calendar/view.php?view=day">Kalender</a>
        </div>
        """
        events = parse_moodle_calendar_events(html_content)
        self.assertEqual(len(events), 0)

    def test_parse_moodle_assign_index(self):
        html_content = """
        <table class="course-overview-table table">
            <thead><tr><th>Name</th><th>Fälligkeitsdatum</th><th>Status</th><th>Abgabestatus</th></tr></thead>
            <tbody>
                <tr>
                    <td><a href="/mod/assign/view.php?id=1234">Aufgabe 1\nBeschreibung</a></td>
                    <td>Freitag, 2. Okt., 23:59</td>
                    <td>-</td>
                    <td>Zur Bewertung abgegeben</td>
                </tr>
                <tr>
                    <td><a href="/mod/assign/view.php?id=5678">Aufgabe 2</a></td>
                    <td>Montag, 5. Okt., 08:00</td>
                    <td>-</td>
                    <td>Keine Abgabe</td>
                </tr>
            </tbody>
        </table>
        """
        assigns = parse_moodle_assign_index(html_content, course_name="SWP 3AHWII", base_url="https://moodle.spengergasse.at")
        self.assertEqual(len(assigns), 2)
        self.assertEqual(assigns[0]["id"], "moodle_1234")
        self.assertEqual(assigns[0]["title"], "Aufgabe 1")
        self.assertEqual(assigns[0]["due_date"], "Freitag, 2. Okt., 23:59")
        self.assertEqual(assigns[0]["status"], "abgegeben")
        self.assertEqual(assigns[0]["course_full"], "SWP 3AHWII")

        self.assertEqual(assigns[1]["id"], "moodle_5678")
        self.assertEqual(assigns[1]["status"], "offen")

    def test_parse_moodle_assign_index_without_due_date_column(self):
        html_content = """
        <table class="generaltable">
            <thead><tr><th>Name</th><th>Abgabestatus</th><th>Bewertung</th></tr></thead>
            <tbody>
                <tr>
                    <td><a href="/mod/assign/view.php?id=8888">Kleine Konstruktionsübung</a></td>
                    <td>Keine Abgabe</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td><a href="/mod/assign/view.php?id=8889">Übung 01: Winken</a></td>
                    <td>Zur Bewertung abgegeben</td>
                    <td>-</td>
                </tr>
            </tbody>
        </table>
        """
        assigns = parse_moodle_assign_index(html_content, course_name="SPL 3AHWII", base_url="https://moodle.spengergasse.at")
        self.assertEqual(len(assigns), 2)
        # due_date must NOT be "Keine Abgabe"!
        self.assertEqual(assigns[0]["due_date"], "Keine Frist")
        self.assertEqual(assigns[0]["status"], "offen")
        self.assertEqual(assigns[0]["status_display"], "Keine Abgabe")

        self.assertEqual(assigns[1]["due_date"], "Keine Frist")
        self.assertEqual(assigns[1]["status"], "abgegeben")
        self.assertEqual(assigns[1]["status_display"], "Zur Bewertung abgegeben")

    def test_parse_moodle_assign_index_with_topic_column(self):
        html_content = """
        <table class="generaltable">
            <thead><tr><th>Thema</th><th>Aktivität</th><th>Fälligkeitsdatum</th><th>Abgabestatus</th></tr></thead>
            <tbody>
                <tr>
                    <td>Projektmanagement</td>
                    <td><a href="/mod/assign/view.php?id=9991">Projektantrag</a></td>
                    <td>Montag, 12. Okt., 08:00</td>
                    <td>Keine Abgabe</td>
                </tr>
            </tbody>
        </table>
        """
        assigns = parse_moodle_assign_index(html_content, course_name="SWP", base_url="https://moodle.spengergasse.at")
        self.assertEqual(len(assigns), 1)
        self.assertEqual(assigns[0]["title"], "Projektantrag")
        self.assertEqual(assigns[0]["due_date"], "Montag, 12. Okt., 08:00")
        self.assertEqual(assigns[0]["status"], "offen")

    @patch("moodle_service.get_saved_moodle_cookies")
    @patch("requests.Session.get")
    @patch("moodle_service.check_moodle_task_status_http")
    def test_fetch_moodle_tasks_http_success(self, mock_status, mock_get, mock_cookies):
        mock_cookies.return_value = [{"name": "MoodleSession", "value": "valid_token"}]

        resp = MagicMock()
        resp.status_code = 200
        resp.url = "https://moodle.spengergasse.at/calendar/view.php?view=upcoming"
        resp.encoding = "utf-8"
        resp.text = """
        <div data-type="event" class="event">
            <h3 class="name">AMEC Labor 2 ist fällig.</h3>
            <span class="date">Dienstag, 29. Sept., 12:00</span>
            <a href="https://moodle.spengergasse.at/course/view.php?id=12233">AMEC - 3AHWII</a>
            <a href="https://moodle.spengergasse.at/mod/assign/view.php?id=99001" class="card-link">Link</a>
        </div>
        """
        mock_get.return_value = resp
        mock_status.return_value = ("offen", "Keine Abgabe")

        tasks = fetch_moodle_tasks_http(deep_scan=False)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "moodle_99001")
        self.assertEqual(tasks[0].title, "AMEC Labor 2")
        self.assertEqual(tasks[0].course, "AMEC")
        self.assertEqual(tasks[0].status, "offen")
        self.assertEqual(tasks[0].status_display, "Keine Abgabe")

    @patch("moodle_service.get_saved_moodle_cookies")
    @patch("requests.Session.get")
    def test_fetch_moodle_tasks_http_expired_session_raises(self, mock_get, mock_cookies):
        mock_cookies.return_value = [{"name": "MoodleSession", "value": "expired"}]
        resp = MagicMock()
        resp.status_code = 200
        resp.url = "https://moodle.spengergasse.at/login/index.php"
        resp.text = '<form id="login">Login</form>'
        mock_get.return_value = resp

        with self.assertRaises(RuntimeError):
            fetch_moodle_tasks_http(deep_scan=False)

    @patch("moodle_service.fetch_moodle_tasks_http")
    @patch("moodle_service.sync_playwright")
    def test_fetch_moodle_tasks_fallback_to_playwright(self, mock_playwright, mock_http):
        mock_http.side_effect = RuntimeError("Session expired")

        mock_browser = MagicMock()
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_ctx
        mock_ctx.new_page.return_value = mock_page

        with patch("moodle_service.ensure_moodle_session", return_value=False):
            tasks = fetch_moodle_tasks(deep_scan=False)
            mock_http.assert_called_once()
            mock_browser.close.assert_called()
            self.assertEqual(tasks, [])


class TestParallelLiveSync(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_cache = os.path.join(self.temp_dir.name, "test_cache.json")
        self.patch_cache = patch("task_manager.CACHE_FILE", self.temp_cache)
        self.patch_cache.start()
        self.mgr = TaskManager(autostart_prefetch=False)

    def tearDown(self):
        self.mgr.stop_background_prefetch()
        self.patch_cache.stop()
        self.temp_dir.cleanup()

    def test_sync_runs_moodle_and_teams_in_parallel(self):
        def fake_moodle(**kwargs):
            time.sleep(0.3)
            return [
                Task(id="m1", platform="moodle", course="SWP", course_full="SWP",
                     title="Moodle Task", due_date_str="Morgen", status="offen",
                     status_display="Offen", url="https://moodle.spengergasse.at/1")
            ]

        def fake_teams():
            time.sleep(0.3)
            return [
                Task(id="t1", platform="teams", course="UFW", course_full="UFW",
                     title="Teams Task", due_date_str="Morgen", status="offen",
                     status_display="Zugewiesen", url="https://teams.microsoft.com/1")
            ]

        with patch("moodle_service.fetch_moodle_tasks", side_effect=fake_moodle):
            with patch("teams_service.fetch_teams_tasks", side_effect=fake_teams):
                t0 = time.time()
                m_cnt, t_cnt = self.mgr.sync(deep_scan=False)
                elapsed = time.time() - t0

                self.assertEqual(m_cnt, 1)
                self.assertEqual(t_cnt, 1)
                self.assertEqual(len(self.mgr.tasks), 2)
                # If sequential: 0.3 + 0.3 = 0.6s. Since parallel: < 0.55s!
                self.assertLess(elapsed, 0.55, f"Sync should run in parallel, took {elapsed:.2f}s")

    def test_sync_resilient_to_service_exception(self):
        def failing_moodle(**kwargs):
            raise ConnectionError("Moodle unreachable")

        def working_teams():
            return [
                Task(id="t_ok", platform="teams", course="UFW", course_full="UFW",
                     title="Teams Task OK", due_date_str="Morgen", status="offen",
                     status_display="Zugewiesen", url="https://teams.microsoft.com/ok")
            ]

        with patch("moodle_service.fetch_moodle_tasks", side_effect=failing_moodle):
            with patch("teams_service.fetch_teams_tasks", side_effect=working_teams):
                m_cnt, t_cnt = self.mgr.sync()
                self.assertEqual(m_cnt, 0)
                self.assertEqual(t_cnt, 1)
                self.assertEqual(len(self.mgr.tasks), 1)
                self.assertEqual(self.mgr.tasks[0].id, "t_ok")

    def test_sync_restarts_background_prefetch(self):
        with patch("moodle_service.fetch_moodle_tasks", return_value=[]):
            with patch("teams_service.fetch_teams_tasks", return_value=[]):
                with patch.object(self.mgr, "start_background_prefetch") as mock_prefetch:
                    self.mgr.sync()
                    mock_prefetch.assert_called_once()

    def test_sync_preserves_cached_tasks_when_one_service_fails(self):
        # Cache contains an existing Moodle task
        old_moodle_task = Task(
            id="m_old", platform="moodle", course="SWP", course_full="SWP",
            title="Old Moodle Task", due_date_str="Morgen", status="offen",
            status_display="Offen", url="https://moodle.spengergasse.at/old",
            details_loaded=True, description="Alt"
        )
        self.mgr.tasks = [old_moodle_task]

        def failing_moodle(**kwargs):
            raise ConnectionError("Moodle unreachable")

        def working_teams():
            return [
                Task(id="t_new", platform="teams", course="UFW", course_full="UFW",
                     title="Teams Task New", due_date_str="Morgen", status="offen",
                     status_display="Zugewiesen", url="https://teams.microsoft.com/new")
            ]

        with patch("moodle_service.fetch_moodle_tasks", side_effect=failing_moodle):
            with patch("teams_service.fetch_teams_tasks", side_effect=working_teams):
                m_cnt, t_cnt = self.mgr.sync(start_prefetch=False)
                # m_cnt should honestly be 0 (0 new fetched from Moodle)
                self.assertEqual(m_cnt, 0)
                self.assertEqual(t_cnt, 1)
                # Both tasks should be present (cached moodle + new teams)
                task_ids = [t.id for t in self.mgr.tasks]
                self.assertIn("m_old", task_ids)
                self.assertIn("t_new", task_ids)
                self.assertEqual(len(self.mgr.tasks), 2)

    def test_sync_deduplicates_duplicate_task_ids(self):
        # Simulate Moodle or Teams returning duplicate task IDs
        dup1 = Task(id="m_dup", platform="moodle", course="SWP", course_full="SWP",
                    title="Dup Task", due_date_str="Morgen", status="offen",
                    status_display="Offen", url="https://moodle.spengergasse.at/dup")
        dup2 = Task(id="m_dup", platform="moodle", course="SWP", course_full="SWP",
                    title="Dup Task", due_date_str="Morgen", status="offen",
                    status_display="Offen", url="https://moodle.spengergasse.at/dup")

        with patch("moodle_service.fetch_moodle_tasks", return_value=[dup1, dup2]):
            with patch("teams_service.fetch_teams_tasks", return_value=[]):
                m_cnt, t_cnt = self.mgr.sync(start_prefetch=False)
                m_tasks = [t for t in self.mgr.tasks if t.platform == "moodle"]
                self.assertEqual(len(m_tasks), 1)
                self.assertEqual(m_tasks[0].id, "m_dup")


    def test_sync_start_prefetch_suppression(self):
        with patch("moodle_service.fetch_moodle_tasks", return_value=[]):
            with patch("teams_service.fetch_teams_tasks", return_value=[]):
                with patch.object(self.mgr, "start_background_prefetch") as mock_prefetch:
                    self.mgr.sync(start_prefetch=False)
                    mock_prefetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()

