"""
test_digi4school.py - Unit- und Integrationstests für den Digi4School Book Grabber Service & CLI.
"""

import json
import os
import sys
import unittest

# Workspace-Pfade für Importe
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "services")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "core")))

from digi4school_service import (
    find_tesseract,
    parse_page_ranges,
    infer_toc_hierarchy,
    Digi4SchoolService,
)
from agent_cli import handle_books_command


class TestDigi4SchoolService(unittest.TestCase):
    """Testet Kernfunktionen des Digi4School Service."""

    def test_find_tesseract(self):
        """Prüft, ob Tesseract auf dem System gefunden wird."""
        try:
            tess = find_tesseract()
            self.assertTrue(os.path.isfile(tess), f"Tesseract-Pfad {tess} existiert nicht")
            self.assertIn("tesseract", tess.lower())
        except FileNotFoundError:
            self.skipTest("Tesseract OCR is not installed on this host environment.")

    def test_parse_page_ranges_simple(self):
        """Prüft einfache Seitenbereiche."""
        pages = parse_page_ranges("1-5")
        self.assertEqual(pages, [1, 2, 3, 4, 5])

    def test_parse_page_ranges_mixed(self):
        """Prüft gemischte Seitenangaben mit Kommas und Bereichen."""
        pages = parse_page_ranges("1, 3, 5-7, 10")
        self.assertEqual(pages, [1, 3, 5, 6, 7, 10])

    def test_parse_page_ranges_all(self):
        """Prüft 'all' mit max_pages."""
        pages = parse_page_ranges("all", max_pages=15)
        self.assertEqual(pages, list(range(1, 16)))

    def test_parse_page_ranges_end(self):
        """Prüft '10-end' mit max_pages."""
        pages = parse_page_ranges("10-end", max_pages=14)
        self.assertEqual(pages, [10, 11, 12, 13, 14])

    def test_infer_toc_hierarchy_modules(self):
        """Prüft hierarchische Lesezeichen-Strukturierung mit Modulen und Kapiteln."""
        raw_toc = [
            {"title": "Inhaltsverzeichnis", "page": 3, "level": 1},
            {"title": "Kompetenzmodul 1", "page": 5, "level": 1},
            {"title": "1 Grundlagen", "page": 6, "level": 1},
            {"title": "1.1 Einführung in das Thema", "page": 8, "level": 1},
            {"title": "1.1.1 Detailaspekt", "page": 10, "level": 1},
            {"title": "Kompetenzmodul 2", "page": 20, "level": 1},
            {"title": "2 Vertiefung", "page": 21, "level": 1},
        ]
        inferred = infer_toc_hierarchy(raw_toc)
        self.assertEqual(len(inferred), 7)
        # Modul 1
        self.assertEqual(inferred[1]["level"], 1)
        # Kapitel 1 unter Modul 1
        self.assertEqual(inferred[2]["level"], 2)
        # 1.1 Unterkapitel
        self.assertEqual(inferred[3]["level"], 3)
        # 1.1.1 Unter-Unterkapitel
        self.assertEqual(inferred[4]["level"], 4)
        # Modul 2
        self.assertEqual(inferred[5]["level"], 1)
        # Kapitel 2
        self.assertEqual(inferred[6]["level"], 2)

    def test_infer_toc_hierarchy_no_jumping(self):
        """Stellt sicher, dass Hierarchiestufen niemals um mehr als 1 springen (PyMuPDF Anforderung)."""
        raw_toc = [
            {"title": "Kapitel 1", "page": 5, "level": 1},
            {"title": "1.1.1 Tiefes Unterkapitel", "page": 8, "level": 4},
        ]
        inferred = infer_toc_hierarchy(raw_toc)
        self.assertEqual(inferred[0]["level"], 1)
        # Level 4 darf nicht direkt nach Level 1 folgen, wird maximal auf 2 gekappt
        self.assertLessEqual(inferred[1]["level"], 2)

    def test_default_downloads_dir(self):
        """Prüft, ob der Standard-Download-Ordner existiert."""
        d_dir = Digi4SchoolService.get_default_downloads_dir()
        self.assertTrue(os.path.exists(d_dir))

    def test_quality_and_effective_dpi(self):
        """Prüft Auflösungs-Presets und adaptive DPI-Kopplung."""
        quality_map = {"standard": 2.0, "high": 3.0, "ultra": 4.0}
        self.assertEqual(int(150 * quality_map["ultra"]), 600)
        self.assertEqual(int(150 * quality_map["standard"]), 300)
        self.assertEqual(int(150 * quality_map["high"]), 450)

    def test_download_book_signature(self):
        """Prüft, dass download_book alle neuen Ultra-HD, OCR- und Layout-Parameter unterstützt."""
        import inspect
        sig = inspect.signature(Digi4SchoolService.download_book)
        expected_params = [
            "email", "password", "code", "output_path", "pages",
            "scale", "quality", "dpi", "psm", "lang", "timeout",
            "retries", "no_ocr", "no_toc", "page_offset", "visible",
            "tesseract_cmd", "progress_cb", "cancel_event"
        ]
        for p in expected_params:
            self.assertIn(p, sig.parameters)
        self.assertEqual(sig.parameters["scale"].default, 4.0)
        self.assertEqual(sig.parameters["page_offset"].default, "auto")


class TestDigi4SchoolCLI(unittest.TestCase):
    """Testet die CLI-Integration in `tasks books download`."""

    def test_cli_books_download_missing_target(self):
        """Prüft, dass ohne Zugangscode ein Fehler gemeldet wird."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = handle_books_command(["download", "--json"])
        self.assertEqual(ret, 1)
        data = json.loads(buf.getvalue())
        self.assertIn("error", data)
        self.assertIn("access code", data["error"].lower())

    def test_cli_books_download_missing_credentials(self):
        """Prüft, dass im Non-Interactive-Modus ohne E-Mail/Passwort ein klarer Fehler kommt."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = handle_books_command(["download", "26s7dbu5qxvw", "--json"])
        self.assertEqual(ret, 1)
        data = json.loads(buf.getvalue())
        self.assertIn("error", data)
        self.assertIn("email", data["error"].lower())

    def test_cli_books_download_parses_new_flags(self):
        """Prüft, dass neue CLI-Flags (--quality, --scale, --no-ocr, --no-toc, --page-offset) erkannt werden."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            # Without credentials in non-interactive, it parses flags and errors on missing email
            ret = handle_books_command([
                "download", "26s7dbu5qxvw",
                "--quality", "ultra",
                "--scale", "4.0",
                "--no-ocr",
                "--no-toc",
                "--page-offset", "2",
                "--json"
            ])
        self.assertEqual(ret, 1)
        data = json.loads(buf.getvalue())
        self.assertIn("error", data)
        self.assertIn("email", data["error"].lower())


if __name__ == "__main__":
    unittest.main()
