"""
test_auth_logins.py - Unit tests for Moodle and WebUntis login logic,
URL resolution, credential normalization, and error reporting.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import src

from auth import (
    AuthResult,
    clean_school_username,
    login_moodle_http,
    login_moodle_direct,
    _humanize_request_error,
    _is_network_connectivity_error,
    get_platform_login_status,
    has_missing_logins,
    is_moodle_logged_in,
    is_teams_logged_in,
    is_untis_logged_in,
    logout_moodle,
    logout_teams,
    logout_untis,
    logout_git,
    is_git_logged_in,
)
from config import (
    load_enabled_platforms,
    save_enabled_platforms,
    is_platform_enabled,
)
from untis_service import (
    clean_school_identifier,
    resolve_webuntis_server,
    login_untis_direct,
    authenticate_untis_api,
)


class TestAuthLogins(unittest.TestCase):

    def test_auth_result_behavior(self):
        res_ok = AuthResult(True, "OK")
        res_fail = AuthResult(False, "Invalid password")

        # Test boolean evaluation
        self.assertTrue(bool(res_ok))
        self.assertFalse(bool(res_fail))

        # Test tuple unpacking
        ok, msg = res_ok
        self.assertTrue(ok)
        self.assertEqual(msg, "OK")

        fail, err_msg = res_fail
        self.assertFalse(fail)
        self.assertEqual(err_msg, "Invalid password")

        # Test properties
        self.assertEqual(res_ok.success, True)
        self.assertEqual(res_fail.message, "Invalid password")

    def test_clean_school_username(self):
        # Normal username
        self.assertEqual(clean_school_username("end240102"), "end240102")
        self.assertEqual(clean_school_username("  end240102  "), "end240102")
        # Email address stripping
        self.assertEqual(clean_school_username("end240102@spengergasse.at"), "end240102")
        self.assertEqual(clean_school_username("max.mustermann@spengergasse.at"), "max.mustermann")
        self.assertEqual(clean_school_username("user@school.edu"), "user")
        # Empty
        self.assertEqual(clean_school_username(""), "")
        self.assertEqual(clean_school_username(None), "")

    def test_clean_school_identifier(self):
        # Plain school names
        self.assertEqual(clean_school_identifier("spengergasse"), "spengergasse")
        self.assertEqual(clean_school_identifier("  spengergasse  "), "spengergasse")
        # Domains
        self.assertEqual(clean_school_identifier("spengergasse.webuntis.com"), "spengergasse")
        # Full URLs
        self.assertEqual(clean_school_identifier("https://spengergasse.webuntis.com/WebUntis/?school=spengergasse"), "spengergasse")
        self.assertEqual(clean_school_identifier("https://spengergasse.webuntis.com/WebUntis"), "spengergasse")
        self.assertEqual(clean_school_identifier("http://mein-gymnasium.webuntis.com/"), "mein-gymnasium")
        # Empty
        self.assertEqual(clean_school_identifier(""), "")

    @patch("requests.Session")
    def test_login_moodle_http_success(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # GET response with logintoken
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.text = '<input type="hidden" name="logintoken" value="test_token_12345">'
        mock_session.get.return_value = mock_get_resp

        # POST response with successful redirect to /my/
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.url = "https://moodle.spengergasse.at/my/"
        mock_post_resp.text = "Dashboard - Welcome user"
        mock_session.post.return_value = mock_post_resp

        # Set cookies on mock session
        cookie_mock = MagicMock()
        cookie_mock.name = "MoodleSession"
        cookie_mock.value = "session_cookie_val_abc"
        cookie_mock.domain = "moodle.spengergasse.at"
        cookie_mock.path = "/"
        cookie_mock.secure = True
        mock_session.cookies = [cookie_mock]

        with patch("auth.save_moodle_cookies") as mock_save_cookies:
            res = login_moodle_http("end240102@spengergasse.at", "secret_pass", moodle_url="https://moodle.spengergasse.at")
            self.assertTrue(res.success)
            self.assertEqual(res.message, "OK")
            mock_save_cookies.assert_called_once()
            # Verify payload contained cleaned username and extracted logintoken
            call_kwargs = mock_session.post.call_args[1]
            data = call_kwargs["data"]
            self.assertEqual(data["username"], "end240102")
            self.assertEqual(data["logintoken"], "test_token_12345")

    @patch("requests.Session")
    def test_login_moodle_http_invalid_credentials(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # GET response
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.text = '<input type="hidden" name="logintoken" value="tok">'
        mock_session.get.return_value = mock_get_resp

        # POST response indicating login failure
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.url = "https://moodle.spengergasse.at/login/index.php"
        mock_post_resp.text = '<div class="alert alert-danger loginerrors">Ungültige Anmeldedaten, bitte versuchen Sie es noch einmal.</div>'
        mock_session.post.return_value = mock_post_resp
        mock_session.cookies = []

        res = login_moodle_http("end240102", "wrong_pass")
        self.assertFalse(res.success)
        self.assertIn("Ungültige Anmeldedaten", res.message)

    @patch("untis_service.requests.post")
    def test_resolve_webuntis_server_variations(self, mock_post):
        # Mock probe response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        # 1. Plain school
        base, sch = resolve_webuntis_server(school="spengergasse")
        self.assertEqual(sch, "spengergasse")
        self.assertIn("spengergasse.webuntis.com", base)

        # 2. School with .webuntis.com domain (must not become double .webuntis.com)
        base2, sch2 = resolve_webuntis_server(school="spengergasse.webuntis.com")
        self.assertEqual(sch2, "spengergasse")
        self.assertNotIn("webuntis.com.webuntis.com", base2)
        self.assertIn("spengergasse.webuntis.com", base2)

        # 3. Full URL in school parameter
        base3, sch3 = resolve_webuntis_server(school="https://spengergasse.webuntis.com/WebUntis/?school=spengergasse")
        self.assertEqual(sch3, "spengergasse")
        self.assertEqual(base3, "https://spengergasse.webuntis.com/WebUntis")

    @patch("untis_service.authenticate_untis_api")
    def test_login_untis_direct_propagation(self, mock_auth):
        # Success case
        mock_auth.return_value = (True, "sess_123", 456, "OK")
        with patch("untis_service.save_untis_credentials"), patch("untis_service.save_untis_school"), patch("untis_service.sync_untis_data"):
            res = login_untis_direct("end240102@spengergasse.at", "pass", school="spengergasse")
            self.assertTrue(res.success)
            self.assertEqual(res.message, "OK")
            # Verify cleaned username was passed to authenticate_untis_api
            user_arg = mock_auth.call_args[0][3]
            self.assertEqual(user_arg, "end240102")

        # Failure case with error message
        mock_auth.return_value = (False, None, None, "WebUntis API: bad credentials")
        res_fail = login_untis_direct("end240102", "wrong_pass", school="spengergasse")
        self.assertFalse(res_fail.success)
        self.assertEqual(res_fail.message, "WebUntis API: bad credentials")

    @patch("requests.Session")
    def test_login_moodle_http_connection_refused(self, mock_session_cls):
        import requests
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='moodle.spengergasse.at', port=443): Max retries exceeded with url: /login/index.php "
            "(Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object>: Failed to establish a new connection: "
            "[WinError 10061] Es konnte keine Verbindung hergestellt werden, da der Zielcomputer die Verbindung verweigerte'))"
        )

        res = login_moodle_http("end240102", "secret")
        self.assertFalse(res.success)
        self.assertEqual(res.message, "Connection refused: Moodle server is offline or requires school VPN.")

    @patch("requests.Session")
    def test_login_moodle_http_timeout(self, mock_session_cls):
        import requests
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.Timeout("Read timed out")

        res = login_moodle_http("end240102", "secret")
        self.assertFalse(res.success)
        self.assertEqual(res.message, "Connection timeout: Moodle server is not responding.")

    @patch("requests.Session")
    def test_login_moodle_http_dns_failure(self, mock_session_cls):
        import requests
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.ConnectionError(
            "Failed to resolve 'moodle.spengergasse.at' ([Errno 11001] getaddrinfo failed)"
        )

        res = login_moodle_http("end240102", "secret")
        self.assertFalse(res.success)
        self.assertEqual(res.message, "Moodle server not found: Check URL or internet connection.")

    @patch("auth.login_moodle_http")
    @patch("playwright.sync_api.sync_playwright", create=True)
    def test_login_moodle_direct_skips_playwright_on_connection_error(self, mock_pw, mock_http):
        mock_http.return_value = AuthResult(False, "Connection refused: Moodle server is offline or requires school VPN.")

        res = login_moodle_direct("end240102", "secret")
        self.assertFalse(res.success)
        self.assertEqual(res.message, "Connection refused: Moodle server is offline or requires school VPN.")
        mock_pw.assert_not_called()

    def test_humanize_request_error_edge_cases(self):
        import requests
        # SSL
        err_ssl = requests.exceptions.SSLError("SSL: CERTIFICATE_VERIFY_FAILED")
        self.assertIn("SSL certificate verification failed", _humanize_request_error(err_ssl, "Moodle"))

        # Generic ConnectionError
        err_conn = requests.exceptions.ConnectionError("Remote end closed connection without response")
        self.assertIn("Could not connect to Moodle server", _humanize_request_error(err_conn, "Moodle"))

        # Connectivity check helper
        self.assertTrue(_is_network_connectivity_error("Connection refused: Moodle server is offline or requires school VPN."))
        self.assertTrue(_is_network_connectivity_error("Connection timeout: Moodle server is not responding."))
        self.assertFalse(_is_network_connectivity_error("Ungültige Anmeldedaten."))
        self.assertFalse(_is_network_connectivity_error("Invalid credentials."))

    @patch("auth.is_moodle_logged_in")
    @patch("auth.is_teams_logged_in")
    @patch("auth.is_untis_logged_in")
    def test_platform_login_status_and_missing_logins(self, mock_untis, mock_teams, mock_moodle):
        # Case 1: All logged in
        mock_moodle.return_value = True
        mock_teams.return_value = True
        mock_untis.return_value = True
        status = get_platform_login_status()
        self.assertEqual(status, {"moodle": True, "teams": True, "untis": True})
        self.assertFalse(has_missing_logins())

        # Case 2: Teams missing
        mock_teams.return_value = False
        status = get_platform_login_status()
        self.assertEqual(status, {"moodle": True, "teams": False, "untis": True})
        self.assertTrue(has_missing_logins())

        # Case 3: All missing
        mock_moodle.return_value = False
        mock_untis.return_value = False
        status = get_platform_login_status()
        self.assertEqual(status, {"moodle": False, "teams": False, "untis": False})
        self.assertTrue(has_missing_logins())

    @patch("auth.is_moodle_logged_in")
    @patch("auth.is_teams_logged_in")
    @patch("auth.is_untis_logged_in")
    @patch("auth.is_platform_enabled")
    def test_has_missing_logins_with_disabled_platform(self, mock_enabled, mock_untis, mock_teams, mock_moodle):
        mock_moodle.return_value = True
        mock_teams.return_value = True
        mock_untis.return_value = False  # Untis not logged in

        # If Untis is enabled, missing logins is True
        mock_enabled.side_effect = lambda p: True
        self.assertTrue(has_missing_logins())

        # If Untis is disabled, missing logins should be False!
        mock_enabled.side_effect = lambda p: False if p == "untis" else True
        self.assertFalse(has_missing_logins())

    @patch("os.path.exists")
    @patch("os.remove")
    def test_logout_moodle(self, mock_remove, mock_exists):
        mock_exists.return_value = True
        mock_task_mgr = MagicMock()

        ok, msg = logout_moodle(mock_task_mgr)
        self.assertTrue(ok)
        self.assertIn("Moodle logged out", msg)
        mock_task_mgr.clear_platform_tasks.assert_called_once_with("moodle")
        self.assertTrue(mock_remove.called)

    @patch("os.path.exists")
    @patch("os.remove")
    @patch("shutil.rmtree")
    def test_logout_teams(self, mock_rmtree, mock_remove, mock_exists):
        mock_exists.return_value = True
        mock_task_mgr = MagicMock()

        ok, msg = logout_teams(mock_task_mgr)
        self.assertTrue(ok)
        self.assertIn("Microsoft Teams logged out", msg)
        mock_task_mgr.clear_platform_tasks.assert_called_once_with("teams")
        self.assertTrue(mock_remove.called)
        self.assertTrue(mock_rmtree.called)

    @patch("builtins.open")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("os.remove")
    @patch("shutil.rmtree")
    def test_logout_untis(self, mock_rmtree, mock_remove, mock_exists, mock_makedirs, mock_open):
        mock_exists.return_value = True
        ok, msg = logout_untis()
        self.assertTrue(ok)
        self.assertIn("WebUntis logged out", msg)
        self.assertTrue(mock_rmtree.called)

    @patch("git_sync_service.GitSyncService.disconnect")
    def test_logout_git(self, mock_disconnect):
        mock_disconnect.return_value = (True, "Git disconnected")
        ok, msg = logout_git()
        self.assertTrue(ok)
        self.assertEqual(msg, "Git disconnected")

    def test_config_enabled_platforms(self):
        with patch("builtins.open"), patch("os.path.exists", return_value=True), patch("json.load", return_value={"enabled_platforms": {"moodle": True, "untis": False}}):
            platforms = load_enabled_platforms()
            self.assertTrue(platforms.get("moodle"))
            self.assertFalse(platforms.get("untis"))
            self.assertTrue(platforms.get("teams"))  # Default fallback


if __name__ == "__main__":
    unittest.main()
