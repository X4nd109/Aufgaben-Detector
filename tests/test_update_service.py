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
from tui_app import SettingsModal, UpdateReminderModal, AufgabenDetectorApp


class TestUpdateService(unittest.TestCase):
    def test_get_app_version(self):
        """Prüft die zentrale Versionskonfiguration."""
        self.assertEqual(APP_VERSION, "1.0.6")
        self.assertEqual(get_app_version(prefix=True), "v1.0.6")
        self.assertEqual(get_app_version(prefix=False), "1.0.6")

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

    @patch("urllib.request.urlopen")
    def test_check_for_updates_asset_detection(self, mock_urlopen):
        """Prüft, dass Installer-Assets aus den GitHub-Release-Daten korrekt extrahiert werden."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_data = {
            "tag_name": "v1.0.6",
            "name": "Aufgaben-Detector v1.0.6",
            "html_url": "https://github.com/X4nd109/Aufgaben-Detector/releases/tag/v1.0.6",
            "assets": [
                {
                    "name": "source_code.zip",
                    "browser_download_url": "https://github.com/.../source_code.zip",
                    "size": 1024,
                },
                {
                    "name": "AufgabenDetector_Setup.exe",
                    "browser_download_url": "https://github.com/.../AufgabenDetector_Setup.exe",
                    "size": 45000000,
                },
            ],
        }
        mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = check_for_updates(current_version="1.0.4")
        self.assertIsNotNone(res)
        self.assertEqual(res["installer_name"], "AufgabenDetector_Setup.exe")
        self.assertEqual(res["installer_url"], "https://github.com/.../AufgabenDetector_Setup.exe")
        self.assertEqual(res["installer_size"], 45000000)

    @patch("urllib.request.urlopen")
    def test_download_update_installer_success(self, mock_urlopen):
        """Prüft erfolgreichen Chunk-Download mit Progress-Callback."""
        import tempfile
        import os
        from src.services.update_service import download_update_installer

        data_chunk = b"X" * 1024
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "2048"}
        mock_resp.read.side_effect = [data_chunk, data_chunk, b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        progress_reports = []
        def on_prog(cur, tot, pct):
            progress_reports.append((cur, tot, pct))

        with tempfile.TemporaryDirectory() as tmp_dir:
            target_exe = os.path.join(tmp_dir, "test_setup.exe")
            ok = download_update_installer(
                "https://example.com/setup.exe",
                target_exe,
                progress_callback=on_prog,
                chunk_size=1024,
            )
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(target_exe))
            self.assertEqual(os.path.getsize(target_exe), 2048)
            self.assertTrue(len(progress_reports) >= 2)
            self.assertEqual(progress_reports[-1][2], 100.0)

    @patch("urllib.request.urlopen")
    def test_download_update_installer_cancellation(self, mock_urlopen):
        """Prüft sauberen Abbruch über threading.Event."""
        import tempfile
        import threading
        import os
        from src.services.update_service import download_update_installer

        cancel_evt = threading.Event()
        cancel_evt.set()  # Sofort abgebrochen

        with tempfile.TemporaryDirectory() as tmp_dir:
            target_exe = os.path.join(tmp_dir, "test_setup.exe")
            ok = download_update_installer(
                "https://example.com/setup.exe",
                target_exe,
                cancel_event=cancel_evt,
            )
            self.assertFalse(ok)
            self.assertFalse(os.path.exists(target_exe))
            self.assertFalse(os.path.exists(target_exe + ".part"))

    @patch("subprocess.Popen")
    def test_launch_update_and_restart(self, mock_popen):
        """Prüft Skript-Generierung und Runner-Aufruf mit /NOTASKS=1 und /UPDATE=1."""
        import tempfile
        import os
        from src.services.update_service import launch_update_and_restart, get_update_temp_dir

        with tempfile.TemporaryDirectory() as fake_app:
            installer_path = os.path.join(fake_app, "AufgabenDetector_Setup.exe")
            ok = launch_update_and_restart(installer_path, app_dir=fake_app)
            self.assertTrue(ok)

            cmd_file = os.path.join(get_update_temp_dir(), "apply_update.cmd")
            self.assertTrue(os.path.exists(cmd_file))
            with open(cmd_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("/NOTASKS=1", content)
            self.assertIn("/UPDATE=1", content)
            self.assertIn("/VERYSILENT", content)
            self.assertIn(f'/DIR="{fake_app}"', content)
            self.assertIn("setup.bat", content)
            self.assertIn("run.bat", content)
            mock_popen.assert_called_once()


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

    @patch("src.ui.tui_app.download_update_installer", return_value=True)
    @patch("src.ui.tui_app.launch_update_and_restart", return_value=True)
    async def test_update_reminder_modal_install_flow(self, mock_launch, mock_download):
        """Prüft den Klick auf 'Jetzt aktualisieren' und UI-Statuswechsel."""
        info = {
            "current_version": "1.0.2",
            "latest_version": "1.0.3",
            "tag_name": "v1.0.3",
            "name": "Aufgaben-Detector v1.0.3",
            "html_url": "https://github.com/X4nd109/Aufgaben-Detector/releases/tag/v1.0.3",
            "installer_url": "https://github.com/.../AufgabenDetector_Setup.exe",
            "installer_name": "AufgabenDetector_Setup.exe",
            "installer_size": 45000000,
        }
        modal = UpdateReminderModal(info)
        app = AufgabenDetectorApp(self.mgr, sync_on_startup=False)
        async with app.run_test() as pilot:
            await app.push_screen(modal)
            btn_install = modal.query_one("#btn_update_install")
            self.assertIsNotNone(btn_install)
            btn_install.press()
            await pilot.pause()
            self.assertTrue(modal._is_downloading or mock_launch.called)
