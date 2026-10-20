"""
Unit tests for src/core/win_dialogs.py and high-DPI Explorer dialog integration.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.core.win_dialogs import (
    enable_high_dpi_awareness,
    pick_directory,
    pick_file,
)
from src.services.directory_service import DirectoryService
from src.services.schoolbook_service import SchoolbookService


class TestWinDialogs(unittest.TestCase):
    """Tests for Windows High-DPI dialog helpers and service integrations."""

    def test_enable_high_dpi_awareness(self):
        """Verifies that DPI awareness activation runs cleanly without raising errors."""
        res = enable_high_dpi_awareness()
        if sys.platform == "win32":
            # On Windows, at least one of SetProcessDpiAwarenessContext, SetProcessDpiAwareness, or SetProcessDPIAware succeeds
            self.assertTrue(res)
        else:
            self.assertFalse(res)

    def test_enable_high_dpi_awareness_non_windows(self):
        """Verifies that non-windows platform returns False immediately."""
        with patch("sys.platform", "linux"):
            self.assertFalse(enable_high_dpi_awareness())

    def test_pick_file_native_com_success(self):
        """Tests pick_file when native COM succeeds and returns a valid path."""
        dummy_pdf = os.path.abspath(__file__)
        with patch("src.core.win_dialogs._pick_file_com", return_value=dummy_pdf) as mock_com:
            res = pick_file(dialog_title="Select PDF", filter_name="PDF", filter_ext="*.pdf")
            self.assertEqual(res, dummy_pdf)
            mock_com.assert_called_once()

    def test_pick_file_native_com_cancel(self):
        """Tests pick_file when user cancels in native COM dialog."""
        with patch("src.core.win_dialogs._pick_file_com", return_value=None):
            # When COM returns None, it represents user cancellation
            # We also ensure tkinter does not pop up if COM successfully returned None (cancellation)
            with patch("tkinter.filedialog.askopenfilename") as mock_tk:
                res = pick_file(dialog_title="Select PDF")
                self.assertIsNone(res)
                mock_tk.assert_not_called()

    def test_pick_file_com_failure_falls_back_to_tkinter(self):
        """Tests fallback to Tkinter when native COM raises an exception."""
        dummy_pdf = os.path.abspath(__file__)
        with patch("src.core.win_dialogs._pick_file_com", side_effect=RuntimeError("COM init failed")):
            with patch("tkinter.Tk") as mock_tk_cls, \
                 patch("tkinter.filedialog.askopenfilename", return_value=dummy_pdf) as mock_ask:
                mock_root = MagicMock()
                mock_tk_cls.return_value = mock_root

                res = pick_file(dialog_title="Select PDF", filter_name="PDF", filter_ext="*.pdf")
                self.assertEqual(res, dummy_pdf)
                mock_ask.assert_called_once()
                mock_root.destroy.assert_called_once()

    def test_pick_file_tkinter_cancel_returns_none(self):
        """Tests that when user cancels in Tkinter fallback, pick_file returns None."""
        with patch("src.core.win_dialogs._pick_file_com", side_effect=RuntimeError("COM init failed")):
            with patch("tkinter.Tk") as mock_tk_cls, \
                 patch("tkinter.filedialog.askopenfilename", return_value="") as mock_ask:
                mock_root = MagicMock()
                mock_tk_cls.return_value = mock_root

                res = pick_file(dialog_title="Select PDF")
                self.assertIsNone(res)
                mock_ask.assert_called_once()

    def test_pick_directory_native_com_success(self):
        """Tests pick_directory when native COM succeeds and returns a valid directory."""
        dummy_dir = os.path.abspath(os.path.dirname(__file__))
        with patch("src.core.win_dialogs._pick_directory_com", return_value=dummy_dir) as mock_com:
            res = pick_directory(dialog_title="Select Folder")
            self.assertEqual(res, dummy_dir)
            mock_com.assert_called_once()

    def test_pick_directory_native_com_cancel(self):
        """Tests pick_directory when user cancels in native COM folder dialog."""
        with patch("src.core.win_dialogs._pick_directory_com", return_value=None):
            with patch("tkinter.filedialog.askdirectory") as mock_tk:
                res = pick_directory(dialog_title="Select Folder")
                self.assertIsNone(res)
                mock_tk.assert_not_called()

    def test_pick_directory_com_failure_falls_back_to_tkinter(self):
        """Tests fallback to Tkinter askdirectory when native COM raises an exception."""
        dummy_dir = os.path.abspath(os.path.dirname(__file__))
        with patch("src.core.win_dialogs._pick_directory_com", side_effect=RuntimeError("COM error")):
            with patch("tkinter.Tk") as mock_tk_cls, \
                 patch("tkinter.filedialog.askdirectory", return_value=dummy_dir) as mock_ask:
                mock_root = MagicMock()
                mock_tk_cls.return_value = mock_root

                res = pick_directory(dialog_title="Select Folder")
                self.assertEqual(res, dummy_dir)
                mock_ask.assert_called_once()
                mock_root.destroy.assert_called_once()

    def test_schoolbook_service_delegates_to_win_dialogs(self):
        """Verifies SchoolbookService.pick_pdf_file delegates to win_dialogs.pick_file."""
        dummy_pdf = os.path.abspath(__file__)
        with patch("src.core.win_dialogs.pick_file", return_value=dummy_pdf) as mock_pick:
            res = SchoolbookService.pick_pdf_file(dialog_title="Custom Book Title")
            self.assertEqual(res, dummy_pdf)
            mock_pick.assert_called_once_with(
                dialog_title="Custom Book Title",
                filter_name="PDF Documents",
                filter_ext="*.pdf",
            )

    def test_directory_service_delegates_to_win_dialogs(self):
        """Verifies DirectoryService.pick_directory delegates to win_dialogs.pick_directory."""
        dummy_dir = os.path.abspath(os.path.dirname(__file__))
        with patch("src.core.win_dialogs.pick_directory", return_value=dummy_dir) as mock_pick:
            res = DirectoryService.pick_directory(dialog_title="Custom Folder Title")
            self.assertEqual(res, dummy_dir)
            mock_pick.assert_called_once_with(dialog_title="Custom Folder Title")


if __name__ == "__main__":
    unittest.main()
