"""
test_dependency_checker.py - Unit tests for dependency checking and warning banner.
"""

import io
import unittest
from unittest.mock import MagicMock, patch

import dependency_checker


class TestDependencyChecker(unittest.TestCase):
    """Test suite for dependency verification, banner formatting, and auto-installation."""

    def test_required_packages_definition(self):
        """Verifies that all core required packages are listed with valid import names."""
        self.assertIn("textual", dependency_checker.REQUIRED_PACKAGES)
        self.assertIn("rich", dependency_checker.REQUIRED_PACKAGES)
        self.assertIn("requests", dependency_checker.REQUIRED_PACKAGES)
        self.assertIn("playwright", dependency_checker.REQUIRED_PACKAGES)
        self.assertIn("fpdf2", dependency_checker.REQUIRED_PACKAGES)
        self.assertIn("PyMuPDF", dependency_checker.REQUIRED_PACKAGES)
        self.assertIn("Pillow", dependency_checker.REQUIRED_PACKAGES)
        self.assertIn("pytesseract", dependency_checker.REQUIRED_PACKAGES)

    @patch("importlib.util.find_spec")
    def test_check_missing_requirements_all_present(self, mock_find_spec):
        """When all packages are installed, check_missing_requirements returns an empty list."""
        mock_find_spec.return_value = MagicMock()
        missing = dependency_checker.check_missing_requirements()
        self.assertEqual(missing, [])

    @patch("importlib.util.find_spec")
    def test_check_missing_requirements_some_missing(self, mock_find_spec):
        """When specific packages are missing, they are accurately identified."""
        def side_effect(module_name):
            if module_name in ("textual", "fitz", "pymupdf"):
                return None
            return MagicMock()

        mock_find_spec.side_effect = side_effect
        missing = dependency_checker.check_missing_requirements()
        missing_dists = [m[0] for m in missing]

        self.assertIn("textual", missing_dists)
        self.assertIn("PyMuPDF", missing_dists)
        self.assertNotIn("rich", missing_dists)
        self.assertNotIn("requests", missing_dists)

    def test_format_warning_banner_content_and_style(self):
        """Verifies banner formatting, border characters, English text, and install command."""
        missing = [
            ("textual", "textual", "Textual TUI framework"),
            ("pytesseract", "pytesseract", "OCR engine for searchable schoolbook PDFs"),
        ]
        cmd = "python -m pip install -r requirements.txt"
        banner = dependency_checker.format_warning_banner(missing, cmd)

        self.assertIn("[!] WARNING: Missing Required Dependencies", banner)
        self.assertIn("+", banner)
        self.assertIn("-", banner)
        self.assertIn("* textual", banner)
        self.assertIn("* pytesseract", banner)
        self.assertIn("Windows Installation Command:", banner)
        self.assertIn(cmd, banner)

    @patch("dependency_checker.check_missing_requirements")
    def test_ensure_dependencies_noop_when_all_installed(self, mock_check):
        """ensure_dependencies returns True without side-effects if all packages are installed."""
        mock_check.return_value = []
        result = dependency_checker.ensure_dependencies()
        self.assertTrue(result)

    @patch("dependency_checker.check_missing_requirements")
    @patch("sys.stdin.isatty", return_value=False)
    @patch("sys.stderr", new_callable=io.StringIO)
    def test_ensure_dependencies_non_interactive_exits(self, mock_stderr, mock_isatty, mock_check):
        """Non-interactive execution exits with code 1 without blocking on input."""
        mock_check.return_value = [("textual", "textual", "Textual TUI framework")]
        with self.assertRaises(SystemExit) as cm:
            dependency_checker.ensure_dependencies()
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Non-interactive environment detected", mock_stderr.getvalue())

    @patch("dependency_checker.check_missing_requirements")
    @patch("dependency_checker.run_pip_install", return_value=0)
    @patch("builtins.input", return_value="y")
    @patch("sys.stdin.isatty", return_value=True)
    @patch("sys.stdout.isatty", return_value=True)
    def test_ensure_dependencies_user_confirms_success(
        self, mock_stdout_tty, mock_stdin_tty, mock_input, mock_pip, mock_check
    ):
        """When user accepts installation and pip succeeds, returns True."""
        mock_check.return_value = [("textual", "textual", "Textual TUI framework")]
        result = dependency_checker.ensure_dependencies()
        self.assertTrue(result)
        mock_pip.assert_called_once()

    @patch("dependency_checker.check_missing_requirements")
    @patch("builtins.input", return_value="n")
    @patch("sys.stdin.isatty", return_value=True)
    @patch("sys.stdout.isatty", return_value=True)
    @patch("sys.stderr", new_callable=io.StringIO)
    def test_ensure_dependencies_user_declines(
        self, mock_stderr, mock_stdout_tty, mock_stdin_tty, mock_input, mock_check
    ):
        """When user declines installation, exits cleanly with code 1."""
        mock_check.return_value = [("textual", "textual", "Textual TUI framework")]
        with self.assertRaises(SystemExit) as cm:
            dependency_checker.ensure_dependencies()
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Installation declined", mock_stderr.getvalue())

    @patch("dependency_checker.check_missing_requirements")
    @patch("dependency_checker.run_pip_install", return_value=42)
    @patch("builtins.input", return_value="y")
    @patch("sys.stdin.isatty", return_value=True)
    @patch("sys.stdout.isatty", return_value=True)
    @patch("sys.stderr", new_callable=io.StringIO)
    def test_ensure_dependencies_pip_failure_exits(
        self, mock_stderr, mock_stdout_tty, mock_stdin_tty, mock_input, mock_pip, mock_check
    ):
        """When pip install fails, exits with pip's exit code."""
        mock_check.return_value = [("textual", "textual", "Textual TUI framework")]
        with self.assertRaises(SystemExit) as cm:
            dependency_checker.ensure_dependencies()
        self.assertEqual(cm.exception.code, 42)
        self.assertIn("Installation failed (exit code 42)", mock_stderr.getvalue())

    @patch("dependency_checker.check_missing_requirements")
    @patch("builtins.input", side_effect=KeyboardInterrupt)
    @patch("sys.stdin.isatty", return_value=True)
    @patch("sys.stdout.isatty", return_value=True)
    def test_ensure_dependencies_keyboard_interrupt(
        self, mock_stdout_tty, mock_stdin_tty, mock_input, mock_check
    ):
        """When user cancels with Ctrl+C, exits cleanly with code 1."""
        mock_check.return_value = [("textual", "textual", "Textual TUI framework")]
        with self.assertRaises(SystemExit) as cm:
            dependency_checker.ensure_dependencies()
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
