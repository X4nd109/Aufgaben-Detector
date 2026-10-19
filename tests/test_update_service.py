"""
test_update_service.py - Tests für Versions-Parsing, GitHub-Release-Check und Update-Modals.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

from textual.widgets import Label
from src.core.config import APP_VERSION, get_app_version
from src.services.update_service import parse_version, is_newer_version, check_for_updates
from src.ui.tui_app import SettingsModal, UpdateReminderModal, AufgabenDetectorApp


class TestUpdateService(unittest.TestCase):
    def test_get_app_version(self):
        """Prüft die zentrale Versionskonfiguration."""
        self.assertEqual(APP_VERSION, "1.0.4")
        self.assertEqual(get_app_version(prefix=True), "v1.0.4")
        self.assertEqual(get_app_version(prefix=False), "1.0.4")

    def test_parse_version(self):
        """Prüft das Parsen diverser Versions-Strings in Zahlentupel."""
        self.assertEqual(parse_version("1.0.2"), (1, 0, 2))
        self.assertEqual(parse_version("v1.0.2"), (1, 0, 2))
        self.assertEqual(parse_version("V2.10.3"), (2, 10, 3))
        self.assertEqual(parse_version("v1.0"), (1, 0))
        self.assertEqual(parse_version("3"), (3,))
        self.assertEqual(parse_version(""), (0,))
        self.assertEqual(parse_version("abc"), (0,))

    def test_is_newer_version(self):
        """Prüft die semantische Versionsvergleichslogik."""
        # Neuere Versionen
        self.assertTrue(is_newer_version("1.0.3", "1.0.2"))
        self.assertTrue(is_newer_version("v1.0.3", "1.0.2"))
        self.assertTrue(is_newer_version("v1.1.0", "1.0.2"))
        self.assertTrue(is_newer_version("v2.0.0", "1.0.2"))
        self.assertTrue(is_newer_version("1.0.2.1", "1.0.2"))

        # Gleiche Versionen
        self.assertFalse(is_newer_version("1.0.2", "1.0.2"))
        self.assertFalse(is_newer_version("v1.0.2", "1.0.2"))
        self.assertFalse(is_newer_version("v1.0.2", "v1.0.2"))

        # Ältere Versionen
        self.assertFalse(is_newer_version("1.0.1", "1.0.2"))
        self.assertFalse(is_newer_version("v1.0.0", "1.0.2"))
        self.assertFalse(is_newer_version("0.9.9", "1.0.2"))
        self.assertFalse(is_newer_version("1.0", "1.0.2"))

    @patch("urllib.request.urlopen")
    def test_check_for_updates_newer_available(self, mock_urlopen):
        """Prüft erfolgreiche Erkennung eines neueren Releases."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_data = {
            "tag_name": "v1.0.3",
            "name": "Aufgaben-Detector v1.0.3",
            "html_url": "https://github.com/X4nd109/Aufgaben-Detector/releases/tag/v1.0.3",
            "body": "Bug fixes and improvements",
            "published_at": "2026-10-19T18:00:00Z",
        }
        mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = check_for_updates(current_version="1.0.2")
        self.assertIsNotNone(res)
        self.assertEqual(res["latest_version"], "1.0.3")
        self.assertEqual(res["current_version"], "1.0.2")
        self.assertEqual(res["tag_name"], "v1.0.3")
        self.assertIn("releases/tag/v1.0.3", res["html_url"])

    @patch("urllib.request.urlopen")
    def test_check_for_updates_already_latest(self, mock_urlopen):
        """Prüft, dass bei identischer Version kein Update gemeldet wird."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_data = {
            "tag_name": "v1.0.2",
            "name": "Aufgaben-Detector v1.0.2",
            "html_url": "https://github.com/X4nd109/Aufgaben-Detector/releases/tag/v1.0.2",
        }
        mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = check_for_updates(current_version="1.0.2")
        self.assertIsNone(res)

    @patch("urllib.request.urlopen")
    def test_check_for_updates_network_error(self, mock_urlopen):
        """Prüft, dass Netzwerkfehler geräuschlos abgefangen werden."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        res = check_for_updates(current_version="1.0.2")
        self.assertIsNone(res)

        mock_urlopen.side_effect = TimeoutError("Request timed out")
        res = check_for_updates(current_version="1.0.2")
        self.assertIsNone(res)


class TestUpdateUI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mgr = MagicMock()
        self.mgr.get_filtered_tasks.return_value = []

    async def test_settings_modal_version_tag(self):
        """Prüft, dass im SettingsModal die Versionsanzeige vorhanden und korrekt formatiert ist."""
        modal = SettingsModal()
        app = AufgabenDetectorApp(self.mgr, sync_on_startup=False)
        async with app.run_test() as pilot:
            await app.push_screen(modal)
            version_label = modal.query_one("#settings_version_tag", Label)
            self.assertIsNotNone(version_label)
            self.assertEqual(str(version_label.render()), f"v{APP_VERSION}")

    async def test_update_reminder_modal_dismiss(self):
        """Prüft Anzeige und Schließen des UpdateReminderModals."""
        info = {
            "current_version": "1.0.2",
            "latest_version": "1.0.3",
            "tag_name": "v1.0.3",
            "name": "Aufgaben-Detector v1.0.3",
            "html_url": "https://github.com/X4nd109/Aufgaben-Detector/releases/tag/v1.0.3",
        }
        modal = UpdateReminderModal(info)
        app = AufgabenDetectorApp(self.mgr, sync_on_startup=False)
        async with app.run_test() as pilot:
            await app.push_screen(modal)
            # Dismiss button drücken
            btn_dismiss = modal.query_one("#btn_update_dismiss")
            self.assertIsNotNone(btn_dismiss)
            btn_dismiss.press()
            await pilot.pause()
            # Modal geschlossen
            self.assertFalse(modal.is_active)

    @patch("webbrowser.open")
    async def test_update_reminder_modal_open_browser(self, mock_browser_open):
        """Prüft den Button zum Öffnen der GitHub-Release-Seite."""
        info = {
            "current_version": "1.0.2",
            "latest_version": "1.0.3",
            "tag_name": "v1.0.3",
            "name": "Aufgaben-Detector v1.0.3",
            "html_url": "https://github.com/X4nd109/Aufgaben-Detector/releases/tag/v1.0.3",
        }
        modal = UpdateReminderModal(info)
        app = AufgabenDetectorApp(self.mgr, sync_on_startup=False)
        async with app.run_test() as pilot:
            await app.push_screen(modal)
            btn_open = modal.query_one("#btn_update_open")
            btn_open.press()
            await pilot.pause()
            mock_browser_open.assert_called_once_with("https://github.com/X4nd109/Aufgaben-Detector/releases/tag/v1.0.3")
