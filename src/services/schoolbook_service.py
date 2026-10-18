"""
schoolbook_service.py - Verwaltung und Schnellzugriff auf lokale PDF- und Web-Schulbücher.
Speichert Verknüpfungen rein lokal in data/schoolbooks.json (ohne Git-Synchronisation).
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from config import SCHOOLBOOKS_FILE, APP_SCHOOLBOOKS_FILE
except ImportError:
    # Fallback für Standalone- oder Test-Kontexte
    _workspace = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _data_dir = os.path.join(_workspace, "data")
    os.makedirs(_data_dir, exist_ok=True)
    SCHOOLBOOKS_FILE = os.path.join(_data_dir, "schoolbooks.json")
    APP_SCHOOLBOOKS_FILE = SCHOOLBOOKS_FILE

logger = logging.getLogger("SchoolbookService")

# Windows flag: keine schwarze CMD-Konsole im Hintergrund aufpoppen lassen
_NO_WINDOW_FLAG = 0x08000000 if sys.platform == "win32" else 0


class SchoolbookService:
    """Service zur Verwaltung und schnellen Ausführung von Schulbüchern (PDF & Web)."""

    @staticmethod
    def _get_active_file() -> str:
        """Gibt den primären Speicherpfad zurück und stellt Verzeichnis sicher."""
        primary = SCHOOLBOOKS_FILE
        target_dir = os.path.dirname(primary)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        return primary

    @staticmethod
    def _get_fallback_file() -> Optional[str]:
        """Gibt den Fallback-Speicherpfad zurück."""
        return APP_SCHOOLBOOKS_FILE

    @classmethod
    def load_books(cls) -> List[Dict[str, Any]]:
        """
        Lädt alle gespeicherten Schulbücher aus der lokalen JSON-Datei.
        Gibt eine Liste von Buch-Dictionaries zurück.
        """
        for p in [cls._get_active_file(), cls._get_fallback_file()]:
            if p and os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            return data
                except Exception as e:
                    logger.warning(f"Error reading from {p}: {e}")
        return []

    @classmethod
    def save_books(cls, books: List[Dict[str, Any]]) -> bool:
        """
        Speichert die Bücherliste atomar in die Konfigurationspfade.
        """
        target = cls._get_active_file()
        temp_file = f"{target}.tmp.{os.getpid()}"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(books, f, indent=2, ensure_ascii=False)
            if os.path.exists(target):
                os.replace(temp_file, target)
            else:
                os.rename(temp_file, target)

            # Falls Fallback abweicht, Kopie anlegen
            fallback = cls._get_fallback_file()
            if fallback and fallback != target:
                try:
                    app_dir = os.path.dirname(fallback)
                    if app_dir:
                        os.makedirs(app_dir, exist_ok=True)
                    with open(fallback, "w", encoding="utf-8") as f2:
                        json.dump(books, f2, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error(f"Error saving schoolbooks: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            return False

    @classmethod
    def add_pdf_book(cls, file_path: str, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Verknüpft ein lokales PDF-Schulbuch.
        Titel wird automatisch aus dem Dateinamen abgeleitet (ohne .pdf), falls nicht übergeben.
        """
        abs_path = os.path.abspath(os.path.expanduser(file_path.strip()))
        if not title or not title.strip():
            base_name = os.path.basename(abs_path)
            if base_name.lower().endswith(".pdf"):
                title = base_name[:-4]
            else:
                title = base_name

        books = cls.load_books()

        # Prüfen, ob bereits vorhanden (nach Pfad)
        for b in books:
            if b.get("type") == "pdf" and os.path.abspath(b.get("path", "")) == abs_path:
                b["title"] = title.strip()
                b["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                cls.save_books(books)
                return b

        book_id = f"sb_pdf_{int(time.time())}_{len(books) + 1}"
        entry = {
            "id": book_id,
            "title": title.strip(),
            "type": "pdf",
            "path": abs_path,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        books.append(entry)
        cls.save_books(books)
        return entry

    @classmethod
    def add_web_book(cls, url: str, title: str) -> Dict[str, Any]:
        """
        Verknüpft ein Online-Schulbuch über eine Web-URL.
        """
        clean_url = url.strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = "https://" + clean_url

        clean_title = title.strip() if title else ""
        if not clean_title:
            parsed = urllib.parse.urlparse(clean_url)
            clean_title = parsed.netloc or "Online Schoolbook"

        books = cls.load_books()

        # Prüfen, ob URL bereits vorhanden
        for b in books:
            if b.get("type") == "web" and b.get("path", "").strip() == clean_url:
                b["title"] = clean_title
                b["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                cls.save_books(books)
                return b

        book_id = f"sb_web_{int(time.time())}_{len(books) + 1}"
        entry = {
            "id": book_id,
            "title": clean_title,
            "type": "web",
            "path": clean_url,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        books.append(entry)
        cls.save_books(books)
        return entry

    @classmethod
    def remove_book(cls, identifier: str) -> bool:
        """
        Entfernt ein Schulbuch anhand von ID oder exaktem/teilweisem Titel.
        """
        ident_clean = str(identifier).strip().lower()
        if not ident_clean:
            return False

        books = cls.load_books()
        initial_len = len(books)

        # 1. Nach exakter ID
        books = [b for b in books if b.get("id", "").strip().lower() != ident_clean]
        if len(books) < initial_len:
            cls.save_books(books)
            return True

        # 2. Nach exaktem Titel
        books = [b for b in books if b.get("title", "").strip().lower() != ident_clean]
        if len(books) < initial_len:
            cls.save_books(books)
            return True

        # 3. Nach Pfad
        books = [b for b in books if os.path.basename(b.get("path", "")).lower() != ident_clean]
        if len(books) < initial_len:
            cls.save_books(books)
            return True

        return False

    @classmethod
    def find_book(cls, identifier: str) -> Optional[Dict[str, Any]]:
        """Findet ein Buch anhand von ID, Titel oder Pfad."""
        ident_clean = str(identifier).strip().lower()
        if not ident_clean:
            return None

        books = cls.load_books()
        for b in books:
            if b.get("id", "").lower() == ident_clean:
                return b
            if b.get("title", "").lower() == ident_clean:
                return b
        # Teilsuche
        for b in books:
            if ident_clean in b.get("title", "").lower() or ident_clean in b.get("path", "").lower():
                return b
        return None

    @classmethod
    def open_book(cls, identifier_or_book: Union[str, Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Öffnet das angegebene Schulbuch im Standard-Programm des Betriebssystems.
        PDFs -> os.startfile / System-Viewer
        Web -> Standard-Webbrowser
        Gibt (success: bool, message: str) zurück.
        """
        if isinstance(identifier_or_book, dict):
            book = identifier_or_book
        else:
            book = cls.find_book(identifier_or_book)

        if not book:
            return False, f"Schoolbook '{identifier_or_book}' not found."

        b_type = book.get("type", "pdf")
        path = book.get("path", "").strip()
        title = book.get("title", "Schoolbook")

        if b_type == "pdf":
            if not os.path.exists(path):
                return False, f"PDF file not found:\n'{path}'"
            try:
                if sys.platform == "win32":
                    os.startfile(path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
                return True, f"'{title}' opened in PDF viewer."
            except Exception as e:
                return False, f"Error opening PDF: {e}"

        elif b_type == "web":
            if not path:
                return False, "No URL configured."
            try:
                webbrowser.open(path)
                return True, f"'{title}' opened in browser."
            except Exception as e:
                return False, f"Error opening link: {e}"

        return False, f"Unknown book type: {b_type}"

    @classmethod
    def pick_pdf_file(cls, dialog_title: str = "Select PDF Schoolbook") -> Optional[str]:
        """
        Öffnet einen nativen Windows Datei-Auswahldialog zur Wahl einer PDF-Datei.
        Verwendet Tkinter mit Topmost-Root und Fallback auf PowerShell Forms.
        """
        # Versuch 1: Tkinter
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askopenfilename(
                title=dialog_title,
                filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")],
            )
            root.destroy()
            if selected and os.path.exists(selected):
                return os.path.abspath(selected)
            if selected == "":
                return None  # Benutzer hat abgebrochen
        except Exception as e:
            logger.debug(f"Tkinter filedialog nicht verfügbar oder fehlgeschlagen: {e}")

        # Versuch 2: PowerShell Windows Forms Fallback
        if sys.platform == "win32":
            try:
                ps_script = f"""
                [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null
                $dlg = New-Object System.Windows.Forms.OpenFileDialog
                $dlg.Title = '{dialog_title}'
                $dlg.Filter = 'PDF Documents (*.pdf)|*.pdf|All Files (*.*)|*.*'
                if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
                    Write-Output $dlg.FileName
                }}
                """
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    creationflags=_NO_WINDOW_FLAG,
                    timeout=60,
                )
                chosen = res.stdout.strip()
                if chosen and os.path.exists(chosen):
                    return os.path.abspath(chosen)
            except Exception as e2:
                logger.error(f"PowerShell Dateiauswahl fehlgeschlagen: {e2}")

        return None
