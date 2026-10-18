"""
test_schoolbooks.py - Unit- und Integrationstests für das Schulbuch-Schnellzugriff-Feature.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Sicherstellen, dass src-Verzeichnisse im Python-Pfad liegen
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
CORE_DIR = os.path.join(SRC_DIR, "core")
SERVICES_DIR = os.path.join(SRC_DIR, "services")
UI_DIR = os.path.join(SRC_DIR, "ui")

for p in [PROJECT_ROOT, SRC_DIR, CORE_DIR, SERVICES_DIR, UI_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from schoolbook_service import SchoolbookService
from agent_cli import run_agent_cli


class TestSchoolbookService(unittest.TestCase):
    """Tests für die Kernlogik von SchoolbookService."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_schoolbooks_file = SchoolbookService._get_active_file()
        self.orig_fallback_file = SchoolbookService._get_fallback_file()
        self.test_books_file = os.path.join(self.test_dir, "schoolbooks.json")
        SchoolbookService._get_active_file = staticmethod(lambda: self.test_books_file)
        SchoolbookService._get_fallback_file = staticmethod(lambda: None)

    def tearDown(self):
        SchoolbookService._get_active_file = staticmethod(lambda: self.orig_schoolbooks_file)
        SchoolbookService._get_fallback_file = staticmethod(lambda: self.orig_fallback_file)
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_load_empty_books(self):
        """Wenn keine Datei existiert, soll eine leere Liste zurückgegeben werden."""
        books = SchoolbookService.load_books()
        self.assertEqual(books, [])

    def test_add_pdf_book_auto_title(self):
        """Testet das Hinzufügen einer lokalen PDF-Datei mit automatischer Titelableitung."""
        sample_pdf = os.path.join(self.test_dir, "Mathematik_HTL_3.pdf")
        with open(sample_pdf, "wb") as f:
            f.write(b"%PDF-1.4 dummy")

        book = SchoolbookService.add_pdf_book(sample_pdf)
        self.assertEqual(book["title"], "Mathematik_HTL_3")
        self.assertEqual(book["type"], "pdf")
        self.assertEqual(book["path"], os.path.abspath(sample_pdf))

        # Erneut laden und prüfen
        loaded = SchoolbookService.load_books()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["title"], "Mathematik_HTL_3")

    def test_add_pdf_book_custom_title(self):
        """Testet das Hinzufügen einer PDF mit explizitem Titel."""
        sample_pdf = os.path.join(self.test_dir, "chemie.pdf")
        with open(sample_pdf, "wb") as f:
            f.write(b"%PDF-1.4 dummy")

        book = SchoolbookService.add_pdf_book(sample_pdf, title="Veritas Chemie Band 3")
        self.assertEqual(book["title"], "Veritas Chemie Band 3")
        self.assertEqual(book["type"], "pdf")

    def test_add_web_book(self):
        """Testet das Hinzufügen eines Online-Schulbuchs per Web-URL."""
        book = SchoolbookService.add_web_book(
            url="trauner-digital.at/book/123",
            title="Trauner Englisch HTL",
        )
        self.assertEqual(book["title"], "Trauner Englisch HTL")
        self.assertEqual(book["type"], "web")
        self.assertEqual(book["path"], "https://trauner-digital.at/book/123")

        loaded = SchoolbookService.load_books()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["path"], "https://trauner-digital.at/book/123")

    def test_find_and_remove_book(self):
        """Testet Suchen und Entfernen von Büchern."""
        b1 = SchoolbookService.add_web_book("https://example.com/math", "Mathe Online")
        b2 = SchoolbookService.add_web_book("https://example.com/phy", "Physik Buch")

        found = SchoolbookService.find_book(b1["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["title"], "Mathe Online")

        # Nach Titel suchen
        found_title = SchoolbookService.find_book("Physik Buch")
        self.assertIsNotNone(found_title)
        self.assertEqual(found_title["id"], b2["id"])

        # Entfernen
        removed = SchoolbookService.remove_book(b1["id"])
        self.assertTrue(removed)
        self.assertEqual(len(SchoolbookService.load_books()), 1)

    def test_open_book_pdf_existing(self):
        """Testet das Öffnen einer vorhandenen PDF-Datei (gemockt)."""
        sample_pdf = os.path.join(self.test_dir, "test.pdf")
        with open(sample_pdf, "wb") as f:
            f.write(b"%PDF dummy")

        book = SchoolbookService.add_pdf_book(sample_pdf, "Test Buch")

        with patch("os.startfile", create=True) as mock_startfile:
            ok, msg = SchoolbookService.open_book(book)
            self.assertTrue(ok)
            self.assertIn("opened", msg.lower())
            if sys.platform == "win32":
                mock_startfile.assert_called_once_with(os.path.abspath(sample_pdf))

    def test_open_book_pdf_missing(self):
        """Wenn eine PDF nicht existiert, soll ein Fehler zurückgegeben werden."""
        book = {
            "id": "sb_123",
            "title": "Vermisstes Buch",
            "type": "pdf",
            "path": os.path.join(self.test_dir, "nicht_vorhanden.pdf"),
        }
        ok, msg = SchoolbookService.open_book(book)
        self.assertFalse(ok)
        self.assertIn("not found", msg.lower())

    def test_open_book_web(self):
        """Testet das Öffnen eines Web-Buchs im Browser (gemockt)."""
        book = SchoolbookService.add_web_book("https://online-buch.at", "Online Reader")
        with patch("webbrowser.open") as mock_browser:
            ok, msg = SchoolbookService.open_book(book)
            self.assertTrue(ok)
            self.assertIn("opened in browser", msg.lower())
            mock_browser.assert_called_once_with("https://online-buch.at")


class TestSchoolbookGitExclusion(unittest.TestCase):
    """Stellt sicher, dass Schulbuch-Dateien niemals über Git synchronisiert werden."""

    def test_gitignore_contains_schoolbooks(self):
        """Prüft, ob root .gitignore und data/.gitignore schoolbooks.json ignorieren."""
        root_gitignore = os.path.join(PROJECT_ROOT, ".gitignore")
        data_gitignore = os.path.join(PROJECT_ROOT, "data", ".gitignore")

        self.assertTrue(os.path.exists(root_gitignore), "Root .gitignore existiert nicht")
        with open(root_gitignore, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("schoolbooks.json", content)

        self.assertTrue(os.path.exists(data_gitignore), "data/.gitignore existiert nicht")
        with open(data_gitignore, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("schoolbooks.json", content)

    def test_git_sync_service_file_map_excludes_schoolbooks(self):
        """Prüft, dass git_sync_service.py die Datei schoolbooks.json nicht synchronisiert."""
        from git_sync_service import GitSyncService
        import inspect
        src = inspect.getsource(GitSyncService.push_changes)
        self.assertNotIn("schoolbooks", src)
        self.assertNotIn("SCHOOLBOOKS_FILE", src)


class TestSchoolbookCLI(unittest.TestCase):
    """Tests für die CLI-Befehle 'tasks books'."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_schoolbooks_file = SchoolbookService._get_active_file()
        self.orig_fallback_file = SchoolbookService._get_fallback_file()
        self.test_books_file = os.path.join(self.test_dir, "schoolbooks.json")
        SchoolbookService._get_active_file = staticmethod(lambda: self.test_books_file)
        SchoolbookService._get_fallback_file = staticmethod(lambda: None)

    def tearDown(self):
        SchoolbookService._get_active_file = staticmethod(lambda: self.orig_schoolbooks_file)
        SchoolbookService._get_fallback_file = staticmethod(lambda: self.orig_fallback_file)
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_cli_books_list_empty(self):
        """'tasks books list --json' liefert leere Liste."""
        with patch("sys.stdout") as mock_stdout:
            ret = run_agent_cli(["books", "list", "--json"])
            self.assertEqual(ret, 0)

    def test_cli_books_add_and_list(self):
        """'tasks books add' fügt ein Buch hinzu und 'list' zeigt es an."""
        ret_add = run_agent_cli(["books", "add", "https://digital-buch.at", "--title", "Digitales Buch", "--json"])
        self.assertEqual(ret_add, 0)

        books = SchoolbookService.load_books()
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]["title"], "Digitales Buch")

        ret_del = run_agent_cli(["books", "remove", "1", "--json"])
        self.assertEqual(ret_del, 0)
        self.assertEqual(len(SchoolbookService.load_books()), 0)


if __name__ == "__main__":
    unittest.main()
