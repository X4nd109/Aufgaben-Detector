"""
tui_app.py - Moderne, interaktive Terminal-Benutzeroberfläche mit echten Maus-Buttons für den Aufgaben Detector.
Basiert auf Textual & Rich. Unterstützt vollständige Mausbedienung sowie Tastatur-Shortcuts.
"""

import datetime
import os
import re
import sys
import threading
import time
import urllib.parse
import webbrowser
from typing import List, Optional, Set, Dict, Tuple

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

from rich.text import Text
from rich.markup import escape
from textual.app import App, ComposeResult, RenderResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual import events
from textual.events import Resize, MouseDown, Click
from textual.geometry import Size
from textual.reactive import reactive
from textual.screen import Screen, ModalScreen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Header, Input, Label, Markdown, Static, TextArea, LoadingIndicator, ProgressBar, Select
from textual.command import CommandPalette, Provider, DiscoveryHit, Hit, Hits, CommandInput, SearchIcon, CommandList
import urllib.parse

try:
    from schoolbook_service import SchoolbookService
except ImportError:
    from src.services.schoolbook_service import SchoolbookService

try:
    from digi4school_service import Digi4SchoolService, find_tesseract
except ImportError:
    from src.services.digi4school_service import Digi4SchoolService, find_tesseract

from auth import (
    check_teams_session,
    login_moodle_direct,
    login_teams_direct,
    setup_moodle_interactive,
    setup_teams_interactive,
    test_teams_session_live,
    get_existing_untis_credentials,
)
from config import (
    ALLOWED_THEMES,
    CONFIG_DIR,
    DEFAULT_THEME,
    DOWNLOADS_DIR,
    load_saved_theme,
    save_saved_theme,
    UNTIS_GROUP,
    UNTIS_URL,
    save_untis_group,
    _load_untis_group,
    load_excuse_profile,
    save_excuse_profile,
    load_full_school_config,
    save_full_school_config,
    save_single_exam_note,
    load_exam_notes,
    sanitize_filename,
    get_task_download_dir,
    load_all_course_links,
    clean_browser_profile_caches,
    AUTO_CLEAN_BROWSER_CACHE,
    close_all_active_browser_contexts,
)
from models import (
    Task,
    SubjectAbsenceSummary,
    MissedLesson,
    DailyAbsenceSummary,
    UntisExam,
)
from task_manager import TaskManager
from untis_service import (
    load_untis_cache,
    sync_untis_data,
    open_untis_login_window,
    login_untis_direct,
    save_untis_cache,
    get_daily_absence_summaries,
    load_untis_exams_cache,
    save_untis_exams_cache,
    get_next_upcoming_exam,
    save_custom_exam,
    delete_custom_exam,
    lookup_untis_lesson_details,
)
from excuse_service import create_excuse_pdf, open_pdf_in_system_viewer
import ui


def get_windows_console_window_size() -> Optional[tuple[int, int]]:
    """Ermittelt unter Windows die tatsächlichen Dimensionen des sichtbaren Terminalfensters."""
    if sys.platform != "win32":
        return None
    try:
        class COORD(ctypes.Structure):
            _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

        class SMALL_RECT(ctypes.Structure):
            _fields_ = [
                ("Left", wintypes.SHORT),
                ("Top", wintypes.SHORT),
                ("Right", wintypes.SHORT),
                ("Bottom", wintypes.SHORT),
            ]

        class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
            _fields_ = [
                ("dwSize", COORD),
                ("dwCursorPosition", COORD),
                ("wAttributes", wintypes.WORD),
                ("srWindow", SMALL_RECT),
                ("dwMaximumWindowSize", COORD),
            ]

        csbi = CONSOLE_SCREEN_BUFFER_INFO()
        kernel32 = ctypes.windll.kernel32

        # 1. Versuche Standard-Output Handle
        h = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if h and h != -1 and kernel32.GetConsoleScreenBufferInfo(h, ctypes.byref(csbi)):
            w = int(csbi.srWindow.Right - csbi.srWindow.Left + 1)
            h_win = int(csbi.srWindow.Bottom - csbi.srWindow.Top + 1)
            if w > 0 and h_win > 0:
                return (w, h_win)

        # 2. Fallback: Öffne CONOUT$ direkt (funktioniert auch bei umgeleiteter stdout)
        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 1
        FILE_SHARE_WRITE = 2
        OPEN_EXISTING = 3
        h_con = kernel32.CreateFileW(
            "CONOUT$",
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if h_con and h_con != -1:
            try:
                if kernel32.GetConsoleScreenBufferInfo(h_con, ctypes.byref(csbi)):
                    w = int(csbi.srWindow.Right - csbi.srWindow.Left + 1)
                    h_win = int(csbi.srWindow.Bottom - csbi.srWindow.Top + 1)
                    if w > 0 and h_win > 0:
                        return (w, h_win)
            finally:
                kernel32.CloseHandle(h_con)

        # 3. Fallback über shutil
        import shutil
        s = shutil.get_terminal_size()
        if s.columns > 0 and s.lines > 0:
            return (s.columns, s.lines)
    except Exception:
        pass

    return None


def ensure_terminal_window_size(target_cols: int = 136, min_height_px: int = 750) -> None:
    """
    Sorgt dafür, dass das Terminal-Fenster (Windows Terminal oder Console Host)
    beim Start auf mindestens target_cols Spalten und eine passende Mindesthöhe
    skaliert wird, ohne dass es zu Render-Desyncs in Textual / ConPTY kommt.
    """
    if os.name != "nt" or sys.platform != "win32":
        return

    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        # 1. Aktuelle Terminalgröße ermitteln
        win_size = get_windows_console_window_size()
        cur_cols = win_size[0] if win_size else 0
        cur_lines = win_size[1] if win_size else 0
        target_lines = max(cur_lines, 35)

        # 2. Direkte Win32-Konsolenpuffer-Anpassung via CONOUT$ (für conhost / Standard-Konsole)
        class COORD(ctypes.Structure):
            _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

        class SMALL_RECT(ctypes.Structure):
            _fields_ = [
                ("Left", wintypes.SHORT),
                ("Top", wintypes.SHORT),
                ("Right", wintypes.SHORT),
                ("Bottom", wintypes.SHORT),
            ]

        class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
            _fields_ = [
                ("dwSize", COORD),
                ("dwCursorPosition", COORD),
                ("wAttributes", wintypes.WORD),
                ("srWindow", SMALL_RECT),
                ("dwMaximumWindowSize", COORD),
            ]

        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 1
        FILE_SHARE_WRITE = 2
        OPEN_EXISTING = 3
        h_con = kernel32.CreateFileW(
            "CONOUT$",
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if h_con and h_con != -1:
            try:
                csbi = CONSOLE_SCREEN_BUFFER_INFO()
                if kernel32.GetConsoleScreenBufferInfo(h_con, ctypes.byref(csbi)):
                    c_w = csbi.srWindow.Right - csbi.srWindow.Left + 1
                    c_h = csbi.srWindow.Bottom - csbi.srWindow.Top + 1
                    if c_w < target_cols or c_h < target_lines:
                        max_coord = COORD(300, 100)
                        try:
                            kernel32.GetLargestConsoleWindowSize.restype = COORD
                            mc = kernel32.GetLargestConsoleWindowSize(h_con)
                            if mc.X > 0 and mc.Y > 0:
                                max_coord = mc
                        except Exception:
                            pass

                        clamped_cols = min(target_cols, max_coord.X)
                        clamped_lines = min(target_lines, max_coord.Y)

                        new_buf_x = max(csbi.dwSize.X, clamped_cols)
                        new_buf_y = max(csbi.dwSize.Y, clamped_lines)
                        kernel32.SetConsoleScreenBufferSize(h_con, COORD(new_buf_x, new_buf_y))

                        rect = SMALL_RECT(0, 0, clamped_cols - 1, clamped_lines - 1)
                        if kernel32.SetConsoleWindowInfo(h_con, True, ctypes.byref(rect)):
                            kernel32.SetConsoleScreenBufferSize(h_con, COORD(clamped_cols, new_buf_y))
            finally:
                kernel32.CloseHandle(h_con)

        # 3. VT-Modus auf stdout aktivieren, bevor ANSI VT Resize-Sequenzen gesendet werden
        try:
            h_out = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            if h_out and h_out != -1:
                mode = wintypes.DWORD()
                if kernel32.GetConsoleMode(h_out, ctypes.byref(mode)):
                    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                    if not (mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING):
                        kernel32.SetConsoleMode(h_out, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
                    sys.stdout.write(f"\x1b[8;{target_lines};{target_cols}t")
                    sys.stdout.flush()
        except Exception:
            pass

        # 4. Windows Terminal / GUI Window Handle finden und per SetWindowPos skalieren
        hwnd_target = None

        # a) Vordergrund-Fenster prüfen
        hwnd_fg = user32.GetForegroundWindow()
        if hwnd_fg:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd_fg, buf, 256)
            if buf.value in ("CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass"):
                hwnd_target = hwnd_fg
            else:
                GA_ROOT = 2
                h_root = user32.GetAncestor(hwnd_fg, GA_ROOT)
                if h_root:
                    user32.GetClassNameW(h_root, buf, 256)
                    if buf.value in ("CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass"):
                        hwnd_target = h_root

        # b) Console Window bzw. Root-Ancestor (Windows Terminal Host)
        if not hwnd_target:
            h_con_win = kernel32.GetConsoleWindow()
            if h_con_win:
                buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h_con_win, buf, 256)
                if buf.value == "ConsoleWindowClass":
                    hwnd_target = h_con_win
                else:
                    GA_ROOT = 2
                    h_root = user32.GetAncestor(h_con_win, GA_ROOT)
                    if h_root:
                        hwnd_target = h_root

        # 5. Fenstergröße anpassen, falls erforderlich
        if hwnd_target:
            global _CACHED_TERMINAL_HWND
            _CACHED_TERMINAL_HWND = hwnd_target
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd_target, ctypes.byref(rect)):
                cur_w = rect.right - rect.left
                cur_h = rect.bottom - rect.top

                col_width_px = 10.0
                if win_size and win_size[0] > 0:
                    measured = (cur_w - 40) / win_size[0]
                    if 7.0 <= measured <= 24.0:
                        col_width_px = measured

                min_width_px = int(target_cols * col_width_px + 48)

                max_screen_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
                max_screen_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN

                target_w = min(max(cur_w, min_width_px), max(max_screen_w - 40, 800))
                target_h = min(max(cur_h, min_height_px), max(max_screen_h - 60, 600))

                if cur_w < target_w or cur_h < target_h:
                    x = rect.left
                    y = rect.top
                    if x + target_w > max_screen_w:
                        x = max(0, max_screen_w - target_w - 20)
                    if y + target_h > max_screen_h:
                        y = max(0, max_screen_h - target_h - 40)

                    SWP_NOZORDER = 0x0004
                    SWP_NOACTIVATE = 0x0010
                    user32.SetWindowPos(
                        hwnd_target,
                        0,
                        x,
                        y,
                        target_w,
                        target_h,
                        SWP_NOZORDER | SWP_NOACTIVATE,
                    )
                    # Warte kurz, bis Windows Terminal / ConPTY den neuen Buffer asynchron stabilisiert hat
                    for _ in range(4):
                        time.sleep(0.04)
                        updated = get_windows_console_window_size()
                        if updated and updated[0] >= target_cols:
                            break

        # Terminal-Titel auf 'tasks' setzen
        if sys.platform == "win32":
            try:
                ctypes.windll.kernel32.SetConsoleTitleW("tasks")
            except Exception:
                pass
        try:
            sys.stdout.write("\033]0;tasks\007")
            sys.stdout.flush()
        except Exception:
            pass
    except Exception:
        pass


_CACHED_TERMINAL_HWND: Optional[int] = None


def get_terminal_window_hwnd() -> Optional[int]:
    """Finds the HWND of the console window or hosting terminal (e.g. Windows Terminal, ConHost)."""
    global _CACHED_TERMINAL_HWND
    if _CACHED_TERMINAL_HWND:
        try:
            if ctypes.windll.user32.IsWindow(_CACHED_TERMINAL_HWND):
                return _CACHED_TERMINAL_HWND
        except Exception:
            pass

    if sys.platform != "win32":
        return None

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 1. Prüfe GetConsoleWindow()
        h_con_win = kernel32.GetConsoleWindow()
        if h_con_win:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h_con_win, buf, 256)
            if buf.value == "ConsoleWindowClass":
                _CACHED_TERMINAL_HWND = h_con_win
                return h_con_win
            GA_ROOT = 2
            h_root = user32.GetAncestor(h_con_win, GA_ROOT)
            if h_root:
                _CACHED_TERMINAL_HWND = h_root
                return h_root

        # 2. Prüfe Vordergrund-Fenster
        hwnd_fg = user32.GetForegroundWindow()
        if hwnd_fg:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd_fg, buf, 256)
            if buf.value in ("CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass"):
                _CACHED_TERMINAL_HWND = hwnd_fg
                return hwnd_fg
            GA_ROOT = 2
            h_root = user32.GetAncestor(hwnd_fg, GA_ROOT)
            if h_root:
                user32.GetClassNameW(h_root, buf, 256)
                if buf.value in ("CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass"):
                    _CACHED_TERMINAL_HWND = h_root
                    return h_root

        return None
    except Exception:
        return None


def is_app_window_foreground(app: Optional[App] = None, terminal_hwnd: Optional[int] = None) -> bool:
    """Checks whether the application's terminal window is currently focused / active."""
    # 1. Wenn Textual mitteilt, dass die App keinen Fokus hat (über VT FocusIn/FocusOut)
    if app is not None and hasattr(app, "app_focus") and not app.app_focus:
        return False

    if sys.platform != "win32":
        return True

    try:
        user32 = ctypes.windll.user32
        hwnd_fg = user32.GetForegroundWindow()
        if not hwnd_fg:
            return False

        # Wenn terminal_hwnd bekannt ist
        target_h = terminal_hwnd or get_terminal_window_hwnd()
        if target_h:
            if hwnd_fg == target_h:
                return True
            GA_ROOT = 2
            if user32.GetAncestor(hwnd_fg, GA_ROOT) == target_h:
                return True

        # Prüfe ob der Prozess des Vordergrundfensters direkt zu unserem Prozess gehört
        fg_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd_fg, ctypes.byref(fg_pid))
        if fg_pid.value == os.getpid():
            return True

        # Prüfe ConsoleProcessList
        kernel32 = ctypes.windll.kernel32
        p_list = (wintypes.DWORD * 32)()
        cnt = kernel32.GetConsoleProcessList(p_list, 32)
        if cnt > 0 and fg_pid.value in list(p_list)[:cnt]:
            return True

        return False
    except Exception:
        return True


FULL_WEEKDAYS = {
    "monday": 0, "montag": 0,
    "tuesday": 1, "dienstag": 1,
    "wednesday": 2, "mittwoch": 2,
    "thursday": 3, "donnerstag": 3,
    "friday": 4, "freitag": 4,
    "saturday": 5, "samstag": 5,
    "sunday": 6, "sonntag": 6,
}

ABBR_WEEKDAYS = {
    "mon": 0, "mo": 0,
    "tue": 1, "di": 1,
    "wed": 2, "mi": 2,
    "thu": 3, "do": 3,
    "fri": 4, "fr": 4,
    "sat": 5, "sa": 5,
    "sun": 6, "so": 6,
}


GERMAN_WEEKDAYS = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"
]


def format_german_weekday_date(dt: datetime.date, time_suffix: str = "") -> str:
    """Formats date as German Weekday, Day.Month.Year [HH:MM], e.g. 'Montag, 4.10.2026 08:00'."""
    wk = GERMAN_WEEKDAYS[dt.weekday()]
    date_part = f"{wk}, {dt.day}.{dt.month}.{dt.year}"
    clean_t = time_suffix.strip().lstrip(",").strip()
    return f"{date_part} {clean_t}" if clean_t else date_part


def resolve_natural_date_string(val: str, today: Optional[datetime.date] = None, allow_short_abbr: bool = False) -> str:
    """
    Replaces natural language expressions like 'Tomorrow', 'Tuesday', 'Dienstag',
    'Next Friday', 'Morgen', etc. OR numeric dates into the formatted string:
    'Montag, 4.10.2026' (or 'Montag, 4.10.2026 08:00' if time is provided).
    Preserves trailing time specifiers.
    """
    if not val:
        return val
    if today is None:
        today = datetime.date.today()

    val_s = val.strip()

    # If already formatted as German Weekday, Day.Month.Year [HH:MM]
    already_pattern = r"^(?:" + "|".join(GERMAN_WEEKDAYS) + r"),\s+\d{1,2}\.\d{1,2}\.\d{4}(?:\s+\d{1,2}:\d{2})?$"
    if re.match(already_pattern, val_s):
        return val_s

    # Extract time suffix if present:
    time_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", val_s)
    time_str = time_match.group(0) if time_match else ""

    # Check for numeric date (e.g. 4.10. or 4.10.2026 or 2026-10-04)
    has_numeric = bool(re.search(r"\b\d{1,2}\.\d{1,2}\.?(?:\d{2,4})?\b", val_s) or re.search(r"\b\d{4}-\d{2}-\d{2}\b", val_s))
    if has_numeric:
        # ISO format YYYY-MM-DD
        m_iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", val_s)
        if m_iso:
            try:
                dt = datetime.date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
                return format_german_weekday_date(dt, time_str)
            except Exception:
                pass

        # Full format DD.MM.YYYY or DD.MM.YY
        m_full = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b", val_s)
        if m_full:
            y = int(m_full.group(3))
            if y < 100:
                y += 2000
            try:
                dt = datetime.date(y, int(m_full.group(2)), int(m_full.group(1)))
                return format_german_weekday_date(dt, time_str)
            except Exception:
                pass

        # Short format DD.MM. or DD.MM
        m_short = re.search(r"\b(\d{1,2})\.(\d{1,2})\.?(?!\d)", val_s)
        if m_short and (allow_short_abbr or val.endswith(" ") or time_str or val.strip().endswith(".")):
            try:
                d, m = int(m_short.group(1)), int(m_short.group(2))
                y = today.year
                cand = datetime.date(y, m, d)
                if (today - cand).days > 180:
                    cand = datetime.date(y + 1, m, d)
                return format_german_weekday_date(cand, time_str)
            except Exception:
                pass
        return val

    # Natural words (Tomorrow, Dienstag, Next Tuesday, etc.)
    pattern = r"^(?:(?:next|am|nächsten|naechsten)\s+)?([a-zA-ZäöüÄÖÜß]+)(.*)$"
    m = re.match(pattern, val_s, re.IGNORECASE)
    if not m:
        return val

    keyword = m.group(1).lower()
    suffix = m.group(2).strip()

    allow_abbr = allow_short_abbr or bool(suffix)
    target_date = None

    if keyword in ("tomorrow", "morgen"):
        target_date = today + datetime.timedelta(days=1)
    elif keyword in ("today", "heute"):
        target_date = today
    elif keyword in ("übermorgen", "uebermorgen"):
        target_date = today + datetime.timedelta(days=2)
    elif keyword in ("yesterday", "gestern"):
        target_date = today - datetime.timedelta(days=1)
    elif keyword in FULL_WEEKDAYS:
        target_wd = FULL_WEEKDAYS[keyword]
        days_ahead = (target_wd - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        target_date = today + datetime.timedelta(days=days_ahead)
    elif allow_abbr and keyword in ABBR_WEEKDAYS:
        target_wd = ABBR_WEEKDAYS[keyword]
        days_ahead = (target_wd - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        target_date = today + datetime.timedelta(days=days_ahead)

    if target_date:
        return format_german_weekday_date(target_date, suffix)
    return val


def parse_flexible_date_input(val: str) -> Optional[tuple[str, str, int]]:
    """
    Parses flexible human-entered date strings into (YYYY-MM-DD, date_display, days_until).
    date_display is formatted as 'Montag, 4.10.2026'.
    Supports:
    - DD.MM.YYYY, DD.MM.YY, YYYY-MM-DD
    - DD.MM. or DD.MM (e.g. 5.10. or 5.10)
    - Formatted strings like 'Montag, 4.10.2026' or 'Montag, 4.10.2026 08:00'
    - 'tomorrow' / 'morgen', 'today' / 'heute', and all weekdays ('Tuesday', 'Dienstag', etc.)
    """
    val = val.strip()
    if not val:
        return None
    today = datetime.date.today()

    parsed_date = None

    # Check for ISO format
    m_iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", val)
    if m_iso:
        try:
            parsed_date = datetime.date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        except Exception:
            pass

    # Check for DD.MM.YYYY or DD.MM.YY
    if not parsed_date:
        m_full = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b", val)
        if m_full:
            y = int(m_full.group(3))
            if y < 100:
                y += 2000
            try:
                parsed_date = datetime.date(y, int(m_full.group(2)), int(m_full.group(1)))
            except Exception:
                pass

    # Check for DD.MM. or DD.MM
    if not parsed_date:
        m_short = re.search(r"\b(\d{1,2})\.(\d{1,2})\.?(?!\d)", val)
        if m_short:
            try:
                d, m = int(m_short.group(1)), int(m_short.group(2))
                y = today.year
                cand = datetime.date(y, m, d)
                if (today - cand).days > 180:
                    cand = datetime.date(y + 1, m, d)
                parsed_date = cand
            except Exception:
                pass

    # Natural language fallback (Tomorrow, Tuesday, etc.)
    if not parsed_date:
        resolved = resolve_natural_date_string(val, allow_short_abbr=True)
        if resolved != val:
            return parse_flexible_date_input(resolved)

    if parsed_date:
        days_until = (parsed_date - today).days
        date_display = format_german_weekday_date(parsed_date)
        return parsed_date.strftime("%Y-%m-%d"), date_display, days_until
    return None


class AddTaskModal(ModalScreen[Optional[Task]]):
    """Dialog to manually add a new homework assignment with optional WebUntis autofill."""

    DEFAULT_CSS = """
    AddTaskModal {
        align: center middle;
    }
    #add_dialog {
        width: 65;
        max-height: 90%;
        height: auto;
        border: thick #a6e3a1;
        background: #1e1e2e;
        padding: 1 2;
    }
    #add_title {
        text-align: center;
        text-style: bold;
        color: #a6e3a1;
        margin-bottom: 1;
    }
    .add_label {
        color: #cdd6f4;
        text-style: bold;
        margin-top: 1;
    }
    .add_input {
        margin-bottom: 1;
        width: 100%;
    }
    #btn_add_autofill {
        width: 100%;
        margin-bottom: 1;
    }
    #add_status {
        color: #f38ba8;
        text-align: center;
        margin: 1 0;
        min-height: 1;
    }
    #add_buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #add_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self):
        super().__init__()
        self.auto_group: str = _load_untis_group() or "X"
        self._lookup_counter: int = 0
        self._last_looked_up: Optional[tuple[str, str]] = None
        self._auto_filled_time: bool = False
        self._auto_filled_teacher: bool = False
        self._auto_filling: bool = False
        self._resolving_natural_date: bool = False
        self._autofill_timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="add_dialog"):
            yield Label("➕ Add Homework / Task", id="add_title")
            with VerticalScroll():
                yield Label("Subject / Course:", classes="add_label")
                yield Input(placeholder="e.g. SWP, SWP PM, D, E, AMEC, NW2", id="inp_add_subject", classes="add_input")
                yield Label("Assignment Title:", classes="add_label")
                yield Input(placeholder="e.g. Exercise 4, Portfolio, Lab Report", id="inp_add_title", classes="add_input")
                yield Label("Due Date (DD.MM.YYYY or e.g. 5.10.):", classes="add_label")
                yield Input(placeholder="e.g. 5.10. or 24.10.2026 or Tomorrow", id="inp_add_due", classes="add_input")
                yield Button("🔍 Autofill from Untis Timetable", id="btn_add_autofill", variant="primary")
                yield Label("Due Time (optional):", classes="add_label")
                yield Input(placeholder="Auto-filled from Untis or e.g. 08:00 or 23:59", id="inp_add_time", classes="add_input")
                yield Label("Teacher (optional):", classes="add_label")
                yield Input(placeholder="Auto-filled from Untis or e.g. BIM, WAW", id="inp_add_teacher", classes="add_input")
                yield Label("Description (optional):", classes="add_label")
                yield Input(placeholder="Optional details / instructions", id="inp_add_desc", classes="add_input")
                yield Label("", id="add_status")
            with Horizontal(id="add_buttons"):
                yield Button("💾 Save [Enter]", id="btn_add_save", variant="success")
                yield Button("↩️ Cancel [ESC]", id="btn_add_cancel", variant="default")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "inp_add_due" and not self._resolving_natural_date:
            resolved = resolve_natural_date_string(event.value, allow_short_abbr=False)
            if resolved != event.value:
                self._resolving_natural_date = True
                try:
                    event.input.value = resolved
                finally:
                    self._resolving_natural_date = False
                return

        if event.input.id in ["inp_add_subject", "inp_add_due"]:
            if getattr(self, "_autofill_timer", None) is not None:
                try:
                    self._autofill_timer.stop()
                except Exception:
                    pass
                self._autofill_timer = None
            try:
                self._autofill_timer = self.set_timer(1.0, lambda: self._trigger_untis_lookup(explicit=False))
            except Exception:
                pass
        elif event.input.id == "inp_add_time" and not self._auto_filling:
            self._auto_filled_time = False
        elif event.input.id == "inp_add_teacher" and not self._auto_filling:
            self._auto_filled_teacher = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_add_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_add_save":
            self._save_task()
        elif event.button.id == "btn_add_autofill":
            if getattr(self, "_autofill_timer", None) is not None:
                try:
                    self._autofill_timer.stop()
                except Exception:
                    pass
                self._autofill_timer = None
            self._trigger_untis_lookup(explicit=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._save_task()

    _parse_date_input = staticmethod(parse_flexible_date_input)

    def _trigger_untis_lookup(self, explicit: bool = False) -> None:
        if getattr(self, "_autofill_timer", None) is not None:
            try:
                self._autofill_timer.stop()
            except Exception:
                pass
            self._autofill_timer = None
        try:
            subj = self.query_one("#inp_add_subject", Input).value.strip()
            date_raw = self.query_one("#inp_add_due", Input).value.strip()
        except Exception:
            return

        resolved_date = resolve_natural_date_string(date_raw, allow_short_abbr=True)
        if resolved_date != date_raw:
            self._resolving_natural_date = True
            try:
                self.query_one("#inp_add_due", Input).value = resolved_date
            finally:
                self._resolving_natural_date = False
            date_raw = resolved_date

        if not subj or not date_raw:
            if explicit:
                self.query_one("#add_status", Label).update("[yellow]Please enter Subject and Due Date first.[/yellow]")
            return

        parsed_date_info = self._parse_date_input(date_raw)
        if not parsed_date_info:
            if explicit:
                self.query_one("#add_status", Label).update("[red]Invalid date format! Use e.g. 5.10. or 24.10.2026[/red]")
            return

        date_iso, date_display, _ = parsed_date_info

        if (subj, date_iso) == self._last_looked_up and not explicit:
            return

        self._lookup_counter += 1
        current_req = self._lookup_counter

        if explicit:
            self.query_one("#add_status", Label).update("[yellow]Checking WebUntis timetable...[/yellow]")

        app = self.app

        def worker():
            data = lookup_untis_lesson_details(date_iso, subj, preferred_group=self.auto_group)
            if self._lookup_counter != current_req:
                return

            def update_ui():
                self._last_looked_up = (subj, date_iso)
                if data:
                    time_inp = self.query_one("#inp_add_time", Input)
                    teacher_inp = self.query_one("#inp_add_teacher", Input)
                    due_inp = self.query_one("#inp_add_due", Input)

                    lesson_time = data.get("start_time") or data.get("time_str") or ""
                    self._auto_filling = True
                    try:
                        if not time_inp.value or self._auto_filled_time:
                            time_inp.value = lesson_time
                            self._auto_filled_time = True
                        if not teacher_inp.value or self._auto_filled_teacher:
                            teacher_inp.value = data.get("teacher", "")
                            self._auto_filled_teacher = True

                        if lesson_time:
                            p_info = self._parse_date_input(due_inp.value or date_iso)
                            if p_info:
                                _, d_disp, _ = p_info
                                self._resolving_natural_date = True
                                try:
                                    due_inp.value = f"{d_disp} {lesson_time}"
                                finally:
                                    self._resolving_natural_date = False
                    finally:
                        self._auto_filling = False

                    if data.get("group"):
                        self.auto_group = data["group"]

                    self.query_one("#add_status", Label).update(
                        f"[green]✓ Untis: {lesson_time} | {data.get('teacher', '')}[/green]"
                    )
                    app.notify(
                        f"✓ Untis: {lesson_time} | {data.get('teacher', '')}",
                        severity="information",
                    )
                elif explicit:
                    self.query_one("#add_status", Label).update(
                        f"[yellow]No Untis lesson found for '{subj}' on {date_display}.[/yellow]"
                    )
            app.call_from_thread(update_ui)

        threading.Thread(target=worker, daemon=True, name="UntisTaskAutofillWorker").start()

    def _save_task(self) -> None:
        if getattr(self, "_autofill_timer", None) is not None:
            try:
                self._autofill_timer.stop()
            except Exception:
                pass
            self._autofill_timer = None
        subject = self.query_one("#inp_add_subject", Input).value.strip()
        title = self.query_one("#inp_add_title", Input).value.strip()
        due_raw = self.query_one("#inp_add_due", Input).value.strip()
        resolved_due = resolve_natural_date_string(due_raw, allow_short_abbr=True)
        if resolved_due != due_raw:
            self._resolving_natural_date = True
            try:
                self.query_one("#inp_add_due", Input).value = resolved_due
            finally:
                self._resolving_natural_date = False
        due_str = resolved_due
        time_str = self.query_one("#inp_add_time", Input).value.strip()
        teacher = self.query_one("#inp_add_teacher", Input).value.strip()
        desc = self.query_one("#inp_add_desc", Input).value.strip()

        if not subject or not title:
            self.query_one("#add_status", Label).update("[red]Please enter at least Subject and Assignment title.[/red]")
            return

        from config import normalize_subject_name, extract_teacher
        clean_subject = normalize_subject_name(subject)
        if not teacher:
            teacher = extract_teacher("", clean_subject, title, desc)
            if teacher == "-":
                teacher = ""

        # Time handling: if time_str exists and due_str doesn't already contain a time, combine them
        if time_str:
            has_time = bool(re.search(r"\b\d{1,2}:\d{2}\b", due_str))
            if not has_time and due_str:
                due_str = f"{due_str} {time_str}"
            elif not due_str:
                due_str = time_str

        if not due_str:
            due_str = "No deadline"

        from task_manager import parse_deadline_for_sorting
        due_ts = parse_deadline_for_sorting(due_str)

        task_id = f"manual_{int(time.time() * 1000)}"
        new_task = Task(
            id=task_id,
            platform="manual",
            course=clean_subject,
            course_full=subject,
            title=title,
            due_date_str=due_str,
            status="offen",
            status_display="Open",
            url="",
            teacher=teacher,
            description=desc,
            details_loaded=True,
            due_timestamp=due_ts,
        )
        self.dismiss(new_task)

    def action_cancel(self) -> None:
        if getattr(self, "_autofill_timer", None) is not None:
            try:
                self._autofill_timer.stop()
            except Exception:
                pass
            self._autofill_timer = None
        self.dismiss(None)

    def key_escape(self) -> None:
        if getattr(self, "_autofill_timer", None) is not None:
            try:
                self._autofill_timer.stop()
            except Exception:
                pass
            self._autofill_timer = None
        self.dismiss(None)


class StatusFilterModal(ModalScreen[Optional[str]]):
    """Selection dialog for status filter with clickable buttons."""

    DEFAULT_CSS = """
    StatusFilterModal {
        align: center middle;
    }
    #status_dialog {
        width: 52;
        height: auto;
        border: thick #89b4fa;
        background: #1e1e2e;
        padding: 1 2;
    }
    #status_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #89b4fa;
    }
    .status_btn {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="status_dialog"):
            yield Label("⚡ Select Status Filter", id="status_title")
            yield Button("🟢 Open only", id="btn_st_open", classes="status_btn", variant="success")
            yield Button("🔴 Overdue only", id="btn_st_overdue", classes="status_btn", variant="error")
            yield Button("⚪ Completed only", id="btn_st_completed", classes="status_btn", variant="default")
            yield Button("🔵 All assignments", id="btn_st_all", classes="status_btn", variant="primary")
            yield Button("↩️ Back [ESC]", id="btn_st_cancel", classes="status_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mapping = {
            "btn_st_open": "open_only",
            "btn_st_overdue": "overdue",
            "btn_st_completed": "completed",
            "btn_st_all": "all",
            "btn_st_cancel": None,
        }
        self.dismiss(mapping.get(event.button.id))

    def key_escape(self) -> None:
        self.dismiss(None)


class PlatformFilterModal(ModalScreen[Optional[str]]):
    """Selection dialog for platform filter (Moodle, Teams, All, Manual)."""

    DEFAULT_CSS = """
    PlatformFilterModal {
        align: center middle;
    }
    #plat_dialog {
        width: 62;
        max-height: 90%;
        height: auto;
        border: thick #cba6f7;
        background: #1e1e2e;
        padding: 1 2;
    }
    #plat_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #cba6f7;
    }
    .plat_row {
        height: 3;
        margin-bottom: 1;
        align: center middle;
    }
    .plat_row Button {
        width: 1fr;
        margin: 0 1;
        min-width: 4;
    }
    #plat_cancel_row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("1", "choose_all", "All Platforms", show=False),
        Binding("2", "choose_moodle", "Moodle", show=False),
        Binding("3", "choose_teams", "Teams", show=False),
        Binding("4", "choose_manual", "Manual", show=False),
        Binding("escape", "cancel", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="plat_dialog"):
            yield Label("🌐 Platform Filter", id="plat_title")
            with Horizontal(classes="plat_row"):
                yield Button("🌐 All", id="btn_plat_all", variant="primary", tooltip="All [1]")
                yield Button("🟧 Moodle", id="btn_plat_moodle", variant="warning", tooltip="Moodle [2]")
            with Horizontal(classes="plat_row"):
                yield Button("🟦 Teams", id="btn_plat_teams", variant="primary", tooltip="Teams [3]")
                yield Button("✏️ Manual", id="btn_plat_manual", variant="success", tooltip="Manual [4]")
            with Horizontal(id="plat_cancel_row"):
                yield Button("↩️ Back [ESC]", id="btn_plat_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        mapping = {
            "btn_plat_all": "all",
            "btn_plat_moodle": "moodle",
            "btn_plat_teams": "teams",
            "btn_plat_manual": "manual",
            "btn_plat_cancel": None,
        }
        self.dismiss(mapping.get(bid))

    def action_choose_all(self) -> None:
        self.dismiss("all")

    def action_choose_moodle(self) -> None:
        self.dismiss("moodle")

    def action_choose_teams(self) -> None:
        self.dismiss("teams")

    def action_choose_manual(self) -> None:
        self.dismiss("manual")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


class TimeframeFilterModal(ModalScreen[Optional[str]]):
    """Selection dialog for max due date duration filter (1 Week, 2 Weeks, 4 Weeks, 8 Weeks, All)."""

    DEFAULT_CSS = """
    TimeframeFilterModal {
        align: center middle;
    }
    #tf_dialog {
        width: 56;
        height: auto;
        border: thick #a6e3a1;
        background: #1e1e2e;
        padding: 1 2;
    }
    #tf_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #a6e3a1;
    }
    .tf_btn {
        width: 100%;
        margin-bottom: 1;
    }
    #tf_cancel_row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("1", "choose_1w", "1 Week", show=False),
        Binding("2", "choose_2w", "2 Weeks", show=False),
        Binding("3", "choose_4w", "4 Weeks", show=False),
        Binding("4", "choose_8w", "8 Weeks", show=False),
        Binding("5", "choose_all", "All", show=False),
        Binding("escape", "cancel", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="tf_dialog"):
            yield Label("⏳ Max Duration Until Due", id="tf_title")
            yield Button("🗓️ 1 Week", id="btn_tf_1w", classes="tf_btn", variant="primary", tooltip="1 Week [1]")
            yield Button("🗓️ 2 Weeks (Default)", id="btn_tf_2w", classes="tf_btn", variant="success", tooltip="2 Weeks [2]")
            yield Button("🗓️ 4 Weeks", id="btn_tf_4w", classes="tf_btn", variant="primary", tooltip="4 Weeks [3]")
            yield Button("🗓️ 8 Weeks", id="btn_tf_8w", classes="tf_btn", variant="primary", tooltip="8 Weeks [4]")
            yield Button("🌐 All (No Limit)", id="btn_tf_all", classes="tf_btn", variant="default", tooltip="All [5]")
            with Horizontal(id="tf_cancel_row"):
                yield Button("↩️ Back [ESC]", id="btn_tf_cancel", classes="tf_btn", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        mapping = {
            "btn_tf_1w": "1_week",
            "btn_tf_2w": "2_weeks",
            "btn_tf_4w": "4_weeks",
            "btn_tf_8w": "8_weeks",
            "btn_tf_all": "all",
            "btn_tf_cancel": None,
        }
        self.dismiss(mapping.get(bid))

    def action_choose_1w(self) -> None:
        self.dismiss("1_week")

    def action_choose_2w(self) -> None:
        self.dismiss("2_weeks")

    def action_choose_4w(self) -> None:
        self.dismiss("4_weeks")

    def action_choose_8w(self) -> None:
        self.dismiss("8_weeks")

    def action_choose_all(self) -> None:
        self.dismiss("all")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


class FilterMenuModal(ModalScreen[Optional[str]]):
    """Unified filter hub for Status, Max. Dauer, Subject, and Platform."""

    DEFAULT_CSS = """
    FilterMenuModal {
        align: center middle;
    }
    #filter_dialog {
        width: 62;
        max-height: 90%;
        height: auto;
        border: thick #89b4fa;
        background: #1e1e2e;
        padding: 1 2;
    }
    #filter_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #89b4fa;
    }
    #filter_info {
        text-align: center;
        color: #a6adc8;
        margin-bottom: 1;
    }
    .filter_btn {
        width: 100%;
        margin-bottom: 1;
    }
    #filter_cancel_row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("1", "choose_status", "Status", show=False),
        Binding("2", "choose_timeframe", "Duration", show=False),
        Binding("3", "choose_subject", "Subject", show=False),
        Binding("4", "choose_platform", "Platform", show=False),
        Binding("5", "choose_reset", "Reset", show=False),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        current_status: str = "open_only",
        current_subject: str = "all",
        current_platform: str = "all",
        current_timeframe: str = "2_weeks",
    ):
        super().__init__()
        self.current_status = current_status
        self.current_subject = current_subject
        self.current_platform = current_platform
        self.current_timeframe = current_timeframe

    def compose(self) -> ComposeResult:
        with Vertical(id="filter_dialog"):
            yield Label("🔍 Filter Menu", id="filter_title")
            st_disp = {
                "open_only": "Open only",
                "all": "All",
                "completed_only": "Completed",
                "overdue_only": "Overdue",
            }.get(self.current_status, self.current_status)
            plat_disp = {
                "all": "All",
                "moodle": "Moodle",
                "teams": "Teams",
                "manual": "Manual",
            }.get(self.current_platform, self.current_platform)
            subj_disp = "All" if self.current_subject == "all" else self.current_subject
            tf_disp = {
                "1_week": "1 Week",
                "2_weeks": "2 Weeks",
                "4_weeks": "4 Weeks",
                "8_weeks": "8 Weeks",
                "all": "All",
            }.get(self.current_timeframe, self.current_timeframe)

            yield Label(
                f"Status: [bold cyan]{st_disp}[/] | Due Window: [bold cyan]{tf_disp}[/] | Subject: [bold cyan]{subj_disp}[/] | Platform: [bold cyan]{plat_disp}[/]",
                id="filter_info",
            )

            yield Button(f"⚡ Status Filter: {st_disp}", id="btn_filter_status", classes="filter_btn", variant="primary", tooltip="Status Filter [1]")
            yield Button(f"⏳ Max Duration: {tf_disp}", id="btn_filter_timeframe", classes="filter_btn", variant="success", tooltip="Max Duration Filter [2]")
            yield Button(f"📚 Subject Filter: {subj_disp}", id="btn_filter_subject", classes="filter_btn", variant="warning", tooltip="Subject Filter [3]")
            yield Button(f"🌐 Platform Filter: {plat_disp}", id="btn_filter_platform", classes="filter_btn", variant="primary", tooltip="Platform Filter [4]")
            yield Button("🔄 Reset All Filters", id="btn_filter_reset", classes="filter_btn", variant="error", tooltip="Reset All [5]")
            with Horizontal(id="filter_cancel_row"):
                yield Button("↩️ Close [ESC]", id="btn_filter_close", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_filter_status":
            self.dismiss("status")
        elif bid == "btn_filter_timeframe":
            self.dismiss("timeframe")
        elif bid == "btn_filter_subject":
            self.dismiss("subject")
        elif bid == "btn_filter_platform":
            self.dismiss("platform")
        elif bid == "btn_filter_reset":
            self.dismiss("reset")
        elif bid == "btn_filter_close":
            self.dismiss(None)

    def action_choose_status(self) -> None:
        self.dismiss("status")

    def action_choose_timeframe(self) -> None:
        self.dismiss("timeframe")

    def action_choose_subject(self) -> None:
        self.dismiss("subject")

    def action_choose_platform(self) -> None:
        self.dismiss("platform")

    def action_choose_reset(self) -> None:
        self.dismiss("reset")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


HOTKEYS_CATALOG: list[tuple[str, str]] = [
    # Main Screen
    ("Add task", "A"),
    ("Tests & Exams", "E"),
    ("Open course / schoolbook", "Backspace / /"),
    ("Filter menu", "F"),
    ("Status filter", "S"),
    ("Platform filter", "P"),
    ("Max duration filter", "D"),
    ("Sync tasks", "R"),
    ("Absences menu", "U"),
    ("Hidden tasks", "G"),
    ("Login menu", "L"),
    ("Settings menu", "O"),
    ("Change theme", "T / Ctrl+P"),
    ("Open task", "1-9 / Enter"),
    ("Quit app", "Q"),
    # Task Details Modal
    ("Details: Browser", "O"),
    ("Details: Download", "D"),
    ("Details: Status", "E"),
    ("Details: Hide", "L"),
    ("Details: Restore", "W"),
    # Absences Screen
    ("Absences: Sync", "R"),
    ("Absences: Group", "G"),
    ("Absences: Excuse", "E"),
    # Excuse Letter Modal
    ("Excuse: Toggle", "Space"),
    ("Excuse: All", "A"),
    ("Excuse: Open", "O"),
    ("Excuse: Clear", "C"),
    ("Excuse: PDF", "P"),
    # Tests & Exams Screen
    ("Exams: Sync", "R"),
    ("Exams: Past", "V"),
    ("Exams: Browser", "O"),
    ("Exams: Save", "Ctrl+S"),
    # General
    ("Back / Close menu", "Esc / Mouse Back"),
]


class HotkeysProvider(Provider):
    """Provider for fuzzy searching all application hotkeys in the CommandPalette."""

    def _format_item(self, desc: str, key: str, width: int = 46) -> str:
        spaces = max(4, width - len(desc) - len(key))
        return f"{desc}{' ' * spaces}{key}"

    async def discover(self) -> Hits:
        for desc, key in HOTKEYS_CATALOG:
            line = self._format_item(desc, key)
            yield DiscoveryHit(
                display=line,
                command=lambda: None,
                text=f"{desc} {key}",
            )

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for desc, key in HOTKEYS_CATALOG:
            full = f"{desc} {key}"
            score = matcher.match(full)
            if score > 0:
                line = self._format_item(desc, key)
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(line),
                    command=lambda: None,
                    text=full,
                )


class UnifiedQuickOpenProvider(Provider):
    """Provider für das blitzschnelle Suchen und Öffnen von Moodle/Teams-Kursen und Schulbüchern (PDF/Web)."""

    @property
    def current_mode(self) -> str:
        """Ermittelt den aktuellen Modus der Palette ('courses' oder 'books')."""
        if hasattr(self.app, "screen") and isinstance(self.app.screen, UnifiedCommandPalette):
            return getattr(self.app.screen, "active_mode", UnifiedCommandPalette.current_mode)
        return getattr(UnifiedCommandPalette, "current_mode", "courses")

    async def discover(self) -> Hits:
        mode = self.current_mode
        if mode == "courses":
            yield DiscoveryHit(
                display="🔄 [b]Reload & sync courses[/b] (/r)",
                command=lambda: getattr(self.app, "action_reload_courses", lambda: None)(),
                text="/r reload courses sync refresh",
                help="Reloads all courses from Moodle & Teams and refreshes the list",
            )
            courses = load_all_course_links()
            for c in courses:
                p_name = c["platform"].capitalize()
                line = f"\\[{p_name}] {c['display_title']}"
                url = c["url"]
                name = c["display_title"]
                yield DiscoveryHit(
                    display=line,
                    command=lambda u=url, n=name: getattr(self.app, "open_course_url", lambda _u, _n: None)(u, n),
                    text=f"{c['platform']} {c['subject']} {c['display_title']}",
                    help=url,
                )
        else:
            # Schoolbooks mode
            yield DiscoveryHit(
                display="📂 [b]Link local PDF[/b] (/link)",
                command=lambda: getattr(self.app, "action_link_schoolbook_file", lambda: None)(),
                text="/link link local PDF select file Explorer",
                help="Opens file explorer to select a PDF schoolbook on your computer",
            )
            yield DiscoveryHit(
                display="🌐 [b]Link online book[/b] (/link <URL> or /url)",
                command=lambda: getattr(self.app, "prompt_add_schoolbook_url", lambda: None)(""),
                text="/link /url link online book web link URL website",
                help="Type '/link <URL>' or click here to link an online schoolbook",
            )
            yield DiscoveryHit(
                display="📥 [b]Download Digi4School book[/b] (/download)",
                command=lambda: getattr(self.app, "prompt_digi4school_download", lambda _c="": None)(""),
                text="/download /d4s /digi4school download Digi4School schoolbook pdf grabber",
                help="Type '/download' or '/download <access code>' to download a book from Digi4School as OCR PDF",
            )
            books = SchoolbookService.load_books()
            if not books:
                yield DiscoveryHit(
                    display="ℹ️ [dim]No schoolbooks linked yet. Type '/link' or '/download'.[/dim]",
                    command=lambda: getattr(self.app, "action_link_schoolbook_file", lambda: None)(),
                    text="/link /download",
                    help="Type /link for local file or /download for Digi4School book",
                )
            else:
                for b in books:
                    title = b.get("title", "Schoolbook")
                    b_type = b.get("type", "pdf")
                    path = b.get("path", "")
                    badge = "📕 [PDF]" if b_type == "pdf" else "🌐 [WEB]"
                    display = f"{badge} {title}"
                    yield DiscoveryHit(
                        display=display,
                        command=lambda item=b: getattr(self.app, "open_schoolbook", lambda _b: None)(item),
                        text=f"{title} {path} {b_type}",
                        help=path,
                    )

    async def search(self, query: str) -> Hits:
        mode = self.current_mode
        q_clean = query.strip()
        q_lower = q_clean.lower()

        if mode == "courses":
            is_reload = (
                q_lower in ("/r", "r", "/reload", "reload", "/refresh", "refresh", "/sync", "sync", "/")
                or q_lower.startswith("/r")
                or q_lower.startswith("/")
            )
            courses = load_all_course_links()

            if is_reload:
                yield Hit(
                    score=1.0,
                    match_display="🔄 [b]Reload & refresh courses now[/b] (/r)",
                    command=lambda: getattr(self.app, "action_reload_courses", lambda: None)(),
                    text="/r reload courses",
                    help="Press [Enter] to freshly load all Moodle & Teams courses from the server",
                )
                for idx, c in enumerate(courses):
                    p_name = c["platform"].capitalize()
                    line = f"\\[{p_name}] {c['display_title']}"
                    url = c["url"]
                    name = c["display_title"]
                    full = f"{c['display_badge']} {c['subject']} {c['display_title']}"
                    yield Hit(
                        score=0.95 - (idx * 0.001),
                        match_display=line,
                        command=lambda u=url, n=name: getattr(self.app, "open_course_url", lambda _u, _n: None)(u, n),
                        text=full,
                        help=url,
                    )
            else:
                matcher = self.matcher(query)
                for c in courses:
                    full = f"{c['display_badge']} {c['subject']} {c['display_title']}"
                    score = matcher.match(full)
                    if score > 0:
                        p_name = c["platform"].capitalize()
                        line = f"\\[{p_name}] {c['display_title']}"
                        url = c["url"]
                        name = c["display_title"]
                        yield Hit(
                            score=score,
                            match_display=matcher.highlight(line),
                            command=lambda u=url, n=name: getattr(self.app, "open_course_url", lambda _u, _n: None)(u, n),
                            text=full,
                            help=url,
                        )
        else:
            # Schoolbooks Mode
            is_link_cmd = q_lower.startswith("/link") or q_lower.startswith("/url") or q_lower == "link" or q_lower == "url"
            is_unlink_cmd = (
                q_lower in ("/unlink", "unlink", "/del", "del", "/delete", "delete", "/remove", "remove")
                or q_lower.startswith("/unlink")
                or q_lower.startswith("/delete")
            )
            is_download_cmd = (
                q_lower in ("/download", "download", "/d4s", "d4s", "/digi4school", "digi4school", "/digi", "digi")
                or q_lower.startswith("/download")
                or q_lower.startswith("/d4s")
                or q_lower.startswith("/digi4school")
                or q_lower.startswith("/digi ")
            )

            # Check if a URL was provided in query
            url_match = re.search(r"https?://\S+", q_clean, re.IGNORECASE)

            if url_match:
                url_found = url_match.group(0)
                yield Hit(
                    score=1.0,
                    match_display=f"🌐 [b]Link online book:[/b] [cyan]{url_found}[/cyan]",
                    command=lambda u=url_found: getattr(self.app, "prompt_add_schoolbook_url", lambda _u: None)(u),
                    text=f"/link {url_found}",
                    help="Press [Enter] to enter a title and save the link",
                )
            elif q_clean == "/":
                # List all commands if only "/" is entered
                yield Hit(
                    score=1.0,
                    match_display="📂 [b]Select local PDF in file explorer...[/b] (/link)",
                    command=lambda: getattr(self.app, "action_link_schoolbook_file", lambda: None)(),
                    text="/link select local PDF",
                    help="Opens file explorer to select a local PDF file",
                )
                yield Hit(
                    score=0.99,
                    match_display="🌐 [b]Add online book via web link...[/b] (/url)",
                    command=lambda: getattr(self.app, "prompt_add_schoolbook_url", lambda: None)(""),
                    text="/url add online book web link",
                    help="Opens a dialog to enter URL and title",
                )
                yield Hit(
                    score=0.985,
                    match_display="📥 [b]Download Digi4School book...[/b] (/download)",
                    command=lambda: getattr(self.app, "prompt_digi4school_download", lambda _c="": None)(""),
                    text="/download /d4s /digi4school download Digi4School book",
                    help="Downloads a digital schoolbook via 12-digit access code",
                )
                yield Hit(
                    score=0.98,
                    match_display="🗑️ [b]Delete schoolbook link...[/b] (/unlink)",
                    command=lambda: getattr(self.app, "action_prompt_unlink_schoolbook", lambda: None)(),
                    text="/unlink remove delete schoolbook",
                    help="Press [Enter] to show linked books for removal",
                )
                books = SchoolbookService.load_books()
                for idx, b in enumerate(books):
                    title = b.get("title", "")
                    path = b.get("path", "")
                    b_type = b.get("type", "pdf")
                    badge = "📕 [PDF]" if b_type == "pdf" else "🌐 [WEB]"
                    display = f"{badge} {title}"
                    yield Hit(
                        score=0.95 - (idx * 0.001),
                        match_display=display,
                        command=lambda item=b: getattr(self.app, "open_schoolbook", lambda _b: None)(item),
                        text=f"{title} {path} {b_type}",
                        help=path,
                    )
            elif is_download_cmd:
                code_candidate = ""
                parts = q_clean.split(maxsplit=1)
                if len(parts) > 1:
                    code_candidate = parts[1].strip()

                code_info = f" (Code: [cyan]{code_candidate}[/cyan])" if code_candidate else ""
                yield Hit(
                    score=1.0,
                    match_display=f"📥 [b]Download Digi4School book[/b]{code_info}",
                    command=lambda c=code_candidate: getattr(self.app, "prompt_digi4school_download", lambda _c="": None)(c),
                    text=q_clean,
                    help="Downloads the book with Tesseract OCR and table of contents to Downloads",
                )
            elif is_link_cmd:
                yield Hit(
                    score=1.0,
                    match_display="📂 [b]Select local PDF in file explorer...[/b] (/link)",
                    command=lambda: getattr(self.app, "action_link_schoolbook_file", lambda: None)(),
                    text="/link select local PDF",
                    help="Opens file explorer to select a local PDF file",
                )
                yield Hit(
                    score=0.99,
                    match_display="🌐 [b]Add online book via web link...[/b] (/url)",
                    command=lambda: getattr(self.app, "prompt_add_schoolbook_url", lambda: None)(""),
                    text="/url add online book web link",
                    help="Opens a dialog to enter URL and title",
                )

            if is_unlink_cmd:
                books = SchoolbookService.load_books()
                for idx, b in enumerate(books):
                    b_id = b.get("id")
                    title = b.get("title", "Schoolbook")
                    yield Hit(
                        score=0.98 - (idx * 0.001),
                        match_display=f"🗑️ [red]Delete:[/red] {title}",
                        command=lambda bid=b_id, t=title: getattr(self.app, "action_delete_schoolbook", lambda _id, _t: None)(bid, t),
                        text=f"/unlink {title}",
                        help=f"Press [Enter] to remove the link to '{title}'",
                    )
            elif not url_match and not is_download_cmd:
                # Normale Suche über Buchtitel und Pfad/URL
                matcher = self.matcher(query)
                books = SchoolbookService.load_books()
                for b in books:
                    title = b.get("title", "")
                    path = b.get("path", "")
                    b_type = b.get("type", "pdf")
                    full = f"{title} {os.path.basename(path)} {b_type}"
                    score = matcher.match(full)
                    if score > 0:
                        badge = "📕 [PDF]" if b_type == "pdf" else "🌐 [WEB]"
                        display = f"{badge} {title}"
                        yield Hit(
                            score=score,
                            match_display=matcher.highlight(display),
                            command=lambda item=b: getattr(self.app, "open_schoolbook", lambda _b: None)(item),
                            text=full,
                            help=path,
                        )


# Rückwärtskompatibilität
CourseLinksProvider = UnifiedQuickOpenProvider


class UnifiedCommandPalette(CommandPalette):
    """
    Erweiterte Befehlspalette für schnelles Öffnen von Kursen und Schulbüchern.
    Umschalten zwischen Kurse und Schulbücher über die Tabulator-Taste.
    Zeigt als Header nur das gerade aktive Menü an ('Kurse' in Blau bzw. 'Schulbücher' in Rot).
    """

    current_mode: str = "courses"

    DEFAULT_CSS = (
        CommandPalette.DEFAULT_CSS
        + "\n"
        + CommandPalette.DEFAULT_CSS.replace("CommandPalette", "UnifiedCommandPalette")
        + """
        UnifiedCommandPalette #palette-mode-header {
            visibility: visible;
            width: 100%;
            height: auto;
            text-align: center;
            padding-top: 1;
            padding-bottom: 0;
            text-style: bold;
        }
        """
    )

    BINDINGS = [
        *CommandPalette.BINDINGS,
        Binding("tab", "switch_mode", "Modus wechseln", priority=True, show=False),
    ]

    def __init__(
        self,
        providers: list[type[Provider]] | None = None,
        placeholder: str = "",
        initial_mode: str = "courses",
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(providers=providers, placeholder=placeholder, id=id, classes=classes)
        self.active_mode = initial_mode
        UnifiedCommandPalette.current_mode = initial_mode

    def _get_header_text(self) -> str:
        if self.active_mode == "courses":
            return "[bold cyan]Courses[/bold cyan]"
        else:
            return "[bold red]Schoolbooks[/bold red]"

    def _get_placeholder(self) -> str:
        if self.active_mode == "courses":
            return "Search courses or /r to reload..."
        else:
            return "Search schoolbooks (/link, /url, /download)..."

    def compose(self) -> ComposeResult:
        with Vertical(id="--container"):
            yield Static(self._get_header_text(), id="palette-mode-header")
            with Horizontal(id="--input"):
                yield SearchIcon()
                yield CommandInput(placeholder=self._get_placeholder(), select_on_focus=False)
                if not self.run_on_select:
                    yield Button("▶")
            with Vertical(id="--results"):
                yield CommandList()
                yield LoadingIndicator()

    def _update_header(self) -> None:
        try:
            hdr = self.query_one("#palette-mode-header", Static)
            hdr.update(self._get_header_text())
        except Exception:
            pass

    def action_switch_mode(self) -> None:
        """Wechselt zwischen Kurse und Schulbücher, leert die Suchleiste und aktualisiert die Treffer."""
        self.active_mode = "books" if self.active_mode == "courses" else "courses"
        UnifiedCommandPalette.current_mode = self.active_mode
        self._update_header()

        try:
            inp = self.query_one(CommandInput)
            inp.placeholder = self._get_placeholder()
            if inp.value != "":
                inp.value = ""
            else:
                self._cancel_gather_commands()
                self._stop_no_matches_countdown()
                self._gather_commands("")
        except Exception:
            pass


class SchoolbookUrlModal(ModalScreen[Optional[dict]]):
    """Eingabedialog für Online-Schulbücher (URL und Name)."""

    DEFAULT_CSS = """
    SchoolbookUrlModal {
        align: center middle;
    }
    #book_url_dialog {
        width: 65;
        height: auto;
        border: thick #89b4fa;
        background: #1e1e2e;
        padding: 1 2;
    }
    #book_url_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #89b4fa;
    }
    .book_input_label {
        color: #cdd6f4;
        margin-top: 1;
    }
    .book_input {
        width: 100%;
        margin-bottom: 1;
    }
    #book_url_btn_row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #book_url_btn_row Button {
        margin: 0 1;
        min-width: 14;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, initial_url: str = "", initial_title: str = "") -> None:
        super().__init__()
        self.initial_url = initial_url
        self.initial_title = initial_title

    def compose(self) -> ComposeResult:
        with Vertical(id="book_url_dialog"):
            yield Label("🌐 Link Online Schoolbook", id="book_url_title")
            yield Label("Web Address (URL):", classes="book_input_label")
            yield Input(value=self.initial_url, placeholder="https://...", id="book_input_url", classes="book_input")
            yield Label("Book Title / Subject:", classes="book_input_label")
            yield Input(value=self.initial_title, placeholder="e.g. Trauner Digital English", id="book_input_name", classes="book_input")
            with Horizontal(id="book_url_btn_row"):
                yield Button("Save", variant="success", id="btn_save_book")
                yield Button("Cancel", variant="default", id="btn_cancel_book")

    def on_mount(self) -> None:
        if self.initial_url:
            self.query_one("#book_input_name", Input).focus()
        else:
            self.query_one("#book_input_url", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save_book":
            self._submit()
        elif event.button.id == "btn_cancel_book":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "book_input_url":
            self.query_one("#book_input_name", Input).focus()
        else:
            self._submit()

    def _submit(self) -> None:
        url = self.query_one("#book_input_url", Input).value.strip()
        title = self.query_one("#book_input_name", Input).value.strip()
        if not url:
            self.notify("Bitte gib eine gültige URL ein.", severity="warning")
            return
        if not title:
            try:
                parsed = urllib.parse.urlparse(url if url.startswith("http") else "https://" + url)
                title = parsed.netloc or "Online-Buch"
            except Exception:
                title = "Online-Buch"

        self.dismiss({"url": url, "title": title})


class Digi4SchoolDownloadModal(ModalScreen[Optional[dict]]):
    """Eingabedialog für Digi4School-Login und Zugangscode."""

    DEFAULT_CSS = """
    Digi4SchoolDownloadModal {
        align: center middle;
    }
    #digi_download_dialog {
        width: 68;
        height: auto;
        border: thick #f38ba8;
        background: #1e1e2e;
        padding: 1 2;
    }
    #digi_modal_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #f38ba8;
    }
    .digi_input_label {
        color: #cdd6f4;
        margin-top: 1;
    }
    .digi_input {
        width: 100%;
        margin-bottom: 1;
    }
    .digi_select {
        width: 100%;
        margin-bottom: 1;
    }
    #digi_download_btn_row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #digi_download_btn_row Button {
        margin: 0 1;
        min-width: 16;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, initial_code: str = "") -> None:
        super().__init__()
        self.initial_code = initial_code.strip()

    def compose(self) -> ComposeResult:
        with Vertical(id="digi_download_dialog"):
            yield Label("📥 Download Digi4School Book", id="digi_modal_title")
            yield Label("Digi4School Email:", classes="digi_input_label")
            yield Input(placeholder="your.email@example.com", id="digi_input_email", classes="digi_input")
            yield Label("Digi4School Password:", classes="digi_input_label")
            yield Input(placeholder="Password", password=True, id="digi_input_password", classes="digi_input")
            yield Label("12-Digit Book Access Code:", classes="digi_input_label")
            yield Input(value=self.initial_code, placeholder="e.g. 26s7dbu5qxvw", id="digi_input_code", classes="digi_input")
            yield Label("Render Quality:", classes="digi_input_label")
            yield Select(
                options=[
                    ("Ultra-HD (Scale 4.0x, ~600 DPI) [Sharpest]", "ultra"),
                    ("High-Res (Scale 3.0x, ~450 DPI) [Balanced]", "high"),
                    ("Standard (Scale 2.0x, ~300 DPI) [Fast]", "standard"),
                ],
                value="ultra",
                allow_blank=False,
                id="digi_select_quality",
                classes="digi_select",
            )
            with Horizontal(id="digi_download_btn_row"):
                yield Button("Start Download", variant="success", id="btn_start_digi_download")
                yield Button("Cancel", variant="default", id="btn_cancel_digi_download")

    def on_mount(self) -> None:
        self.query_one("#digi_input_email", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_start_digi_download":
            self._submit()
        elif event.button.id == "btn_cancel_digi_download":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "digi_input_email":
            self.query_one("#digi_input_password", Input).focus()
        elif event.input.id == "digi_input_password":
            self.query_one("#digi_input_code", Input).focus()
        elif event.input.id == "digi_input_code":
            self._submit()

    def _submit(self) -> None:
        email = self.query_one("#digi_input_email", Input).value.strip()
        password = self.query_one("#digi_input_password", Input).value.strip()
        code = self.query_one("#digi_input_code", Input).value.strip()
        quality_sel = self.query_one("#digi_select_quality", Select)
        quality = quality_sel.value if quality_sel.value != Select.NULL else "ultra"

        if not email:
            self.notify("Please enter your Digi4School email address.", severity="warning")
            return
        if not password:
            self.notify("Please enter your Digi4School password.", severity="warning")
            return
        if not code:
            self.notify("Please enter the 12-digit access code for the book.", severity="warning")
            return

        try:
            find_tesseract()
        except FileNotFoundError:
            self.notify(
                "⚠️ Tesseract OCR was not found!\n"
                "Please install via: winget install -e --id UB-Mannheim.TesseractOCR",
                severity="error",
                timeout=10,
            )
            return

        self.dismiss({"email": email, "password": password, "code": code, "quality": str(quality)})


class Digi4SchoolProgressModal(ModalScreen[Optional[dict]]):
    """Fortschrittsdialog für den Digi4School Buch-Download mit Live-Fortschritt und Fehler 911 Warnung."""

    DEFAULT_CSS = """
    Digi4SchoolProgressModal {
        align: center middle;
    }
    #d4s_progress_dialog {
        width: 78;
        height: auto;
        border: thick #f38ba8;
        background: #1e1e2e;
        padding: 1 2;
    }
    #d4s_prog_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #f38ba8;
    }
    #d4s_warning_banner {
        color: #f38ba8;
        text-style: bold;
        text-align: center;
        background: #313244;
        padding: 1;
        margin-bottom: 1;
        border: solid #f38ba8;
    }
    #d4s_status_lbl {
        color: #89b4fa;
        text-style: bold;
        text-align: center;
        margin-top: 1;
    }
    #d4s_detail_lbl {
        color: #a6adc8;
        text-align: center;
        margin-bottom: 0;
    }
    #d4s_eta_lbl {
        color: #a6e3a1;
        text-style: bold;
        text-align: center;
        margin-top: 1;
        margin-bottom: 1;
    }
    #d4s_prog_btn_row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #d4s_prog_btn_row Button {
        margin: 0 1;
        min-width: 16;
    }
    .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel_or_close", "Schließen"),
    ]

    def __init__(self, email: str, password: str, code: str, quality: str = "ultra") -> None:
        super().__init__()
        self.email = email
        self.password = password
        self.code = code
        self.quality = quality
        self.download_result: Optional[dict] = None
        self._cancel_async_event: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_running: bool = False
        self._start_time: float = time.time()
        self._phase_start: Optional[float] = None
        self._current_phase: str = ""

    def _format_time(self, seconds: float) -> str:
        """Formatiert Sekunden in lesbare Zeitangaben (z.B. '2m 15s' oder '45s')."""
        s = int(round(seconds))
        if s <= 0:
            return "0s"
        if s < 60:
            return f"{s}s"
        m = s // 60
        rem_s = s % 60
        if m < 60:
            return f"{m}m {rem_s:02d}s"
        h = m // 60
        rem_m = m % 60
        return f"{h}h {rem_m:02d}m"

    def compose(self) -> ComposeResult:
        with Vertical(id="d4s_progress_dialog"):
            yield Label("📥 Digi4School Book Download", id="d4s_prog_title")
            yield Label("⚠️ Do not open Digi4School in your browser during download!", id="d4s_warning_banner")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="d4s_pbar")
            quality_badge = f"[bold #f9e2af]{self.quality.upper()}[/]"
            yield Label(f"Quality: {quality_badge} | Initializing download...", id="d4s_status_lbl")
            yield Label("Please wait...", id="d4s_detail_lbl")
            yield Label("⏳ Calculating remaining time...", id="d4s_eta_lbl")
            with Horizontal(id="d4s_prog_btn_row"):
                yield Button("Cancel", variant="error", id="btn_cancel_d4s")
                yield Button("Show in Downloads folder", variant="success", id="btn_open_folder_d4s", classes="hidden")
                yield Button("Close", variant="default", id="btn_close_d4s", classes="hidden")

    def on_mount(self) -> None:
        self._is_running = True
        self._start_time = time.time()
        threading.Thread(target=self._run_download_thread, daemon=True).start()

    def _run_download_thread(self) -> None:
        import asyncio
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._cancel_async_event = asyncio.Event()

            def progress_callback(phase: str, cur: int, tot: int, msg: str):
                self.app.call_from_thread(self._on_progress_update, phase, cur, tot, msg)

            res = self._loop.run_until_complete(
                Digi4SchoolService.download_book(
                    email=self.email,
                    password=self.password,
                    code=self.code,
                    quality=self.quality,
                    progress_cb=progress_callback,
                    cancel_event=self._cancel_async_event,
                )
            )
            self._is_running = False
            self.app.call_from_thread(self._on_download_complete, res)
        except asyncio.CancelledError:
            self._is_running = False
            self.app.call_from_thread(self._on_download_cancelled)
        except Exception as e:
            self._is_running = False
            self.app.call_from_thread(self._on_download_error, str(e))
        finally:
            self._loop.close()

    def _on_progress_update(self, phase: str, cur: int, tot: int, msg: str) -> None:
        try:
            pbar = self.query_one("#d4s_pbar", ProgressBar)
            status_lbl = self.query_one("#d4s_status_lbl", Label)
            detail_lbl = self.query_one("#d4s_detail_lbl", Label)
            eta_lbl = self.query_one("#d4s_eta_lbl", Label)

            now = time.time()
            if phase != self._current_phase:
                self._current_phase = phase
                self._phase_start = now

            detail_lbl.update(msg)
            eta_str = ""

            if phase == "login":
                status_lbl.update("🔐 Logging into Digi4School...")
                pbar.update(total=100, progress=10)
                eta_str = "⏳ Estimated time remaining: ~1-2 min."
            elif phase == "resolving":
                status_lbl.update("🔍 Resolving e-book viewer...")
                pbar.update(total=100, progress=20)
                eta_str = "⏳ Estimated time remaining: Analyzing book structure..."
            elif phase == "pages":
                status_lbl.update(f"📄 Fetching pages ({cur}/{tot})...")
                pct = 20 + int((cur / max(1, tot)) * 40)
                pbar.update(total=100, progress=pct)

                if cur > 0 and tot > 0:
                    el = now - (self._phase_start or now)
                    rate = cur / max(0.001, el)
                    rem_sec = (tot - cur) / max(0.001, rate)
                    total_rem = rem_sec + (tot * 0.35)
                    eta_str = f"⏳ Estimated time remaining: ~{self._format_time(total_rem)} (Pages {cur}/{tot} | Elapsed: {self._format_time(now - self._start_time)})"
            elif phase == "ocr":
                status_lbl.update(f"⚙️ OCR text recognition ({cur}/{tot})...")
                pct = 60 + int((cur / max(1, tot)) * 30)
                pbar.update(total=100, progress=pct)

                if cur > 0 and tot > 0:
                    el = now - (self._phase_start or now)
                    rate = cur / max(0.001, el)
                    rem_sec = (tot - cur) / max(0.001, rate)
                    eta_str = f"⏳ Estimated time remaining: ~{self._format_time(rem_sec)} (OCR {cur}/{tot} | Elapsed: {self._format_time(now - self._start_time)})"
            elif phase == "toc":
                status_lbl.update("📑 Bookmarks & page numbers...")
                pbar.update(total=100, progress=95)
                eta_str = "⏳ Estimated time remaining: few seconds (table of contents)..."
            elif phase == "saving":
                status_lbl.update("💾 Saving PDF...")
                pbar.update(total=100, progress=98)
                eta_str = "⏳ Estimated time remaining: few seconds (writing PDF)..."
            elif phase == "finished":
                status_lbl.update("✓ Completed!")
                pbar.update(total=100, progress=100)
                eta_str = f"✨ Completed in {self._format_time(now - self._start_time)}"

            if eta_str:
                eta_lbl.update(eta_str)
        except Exception:
            pass

    def _on_download_complete(self, result: dict) -> None:
        self.download_result = result
        try:
            total_duration = self._format_time(time.time() - self._start_time)
            self.query_one("#d4s_prog_title", Label).update("✅ [bold green]Download successful![/bold green]")
            self.query_one("#d4s_status_lbl", Label).update(f"Saved: {result.get('title')}")
            self.query_one("#d4s_detail_lbl", Label).update(
                f"Path: {result.get('path')}\n"
                f"Pages: {result.get('pages')} | Size: {result.get('size_mb')} MB"
            )
            self.query_one("#d4s_eta_lbl", Label).update(f"✨ Total Duration: {total_duration}")
            self.query_one("#d4s_warning_banner", Label).update("[dim]Download completed. Saved to Downloads.[/dim]")

            self.query_one("#btn_cancel_d4s", Button).add_class("hidden")
            self.query_one("#btn_open_folder_d4s", Button).remove_class("hidden")
            self.query_one("#btn_close_d4s", Button).remove_class("hidden")
            self.notify(f"✓ Schoolbook '{result.get('title')}' downloaded!", severity="information", timeout=6)
        except Exception:
            pass

    def _on_download_cancelled(self) -> None:
        try:
            self.query_one("#d4s_prog_title", Label).update("⏹️ [bold yellow]Download Cancelled[/bold yellow]")
            self.query_one("#d4s_status_lbl", Label).update("The download was cancelled by the user.")
            self.query_one("#d4s_detail_lbl", Label).update("No complete PDF was generated.")
            self.query_one("#btn_cancel_d4s", Button).add_class("hidden")
            self.query_one("#btn_close_d4s", Button).remove_class("hidden")
            self.notify("Download cancelled.", severity="warning")
        except Exception:
            pass

    def _on_download_error(self, err_msg: str) -> None:
        try:
            self.query_one("#d4s_prog_title", Label).update("❌ [bold red]Download Error[/bold red]")
            self.query_one("#d4s_status_lbl", Label).update("The operation could not be completed.")
            self.query_one("#d4s_detail_lbl", Label).update(f"[red]{err_msg}[/red]")
            self.query_one("#btn_cancel_d4s", Button).add_class("hidden")
            self.query_one("#btn_close_d4s", Button).remove_class("hidden")
            self.notify(f"Error: {err_msg}", severity="error", timeout=8)
        except Exception:
            pass

    def _cancel_download(self) -> None:
        if self._is_running and self._cancel_async_event and self._loop:
            try:
                self.query_one("#d4s_status_lbl", Label).update("Cancelling download...")
                self._loop.call_soon_threadsafe(self._cancel_async_event.set)
            except Exception:
                self.dismiss(None)
        else:
            self.dismiss(self.download_result)

    def action_cancel_or_close(self) -> None:
        if self._is_running:
            self._cancel_download()
        else:
            self.dismiss(self.download_result)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel_d4s":
            self._cancel_download()
        elif event.button.id == "btn_close_d4s":
            self.dismiss(self.download_result)
        elif event.button.id == "btn_open_folder_d4s":
            downloads_dir = Digi4SchoolService.get_default_downloads_dir()
            try:
                if sys.platform == "win32":
                    os.startfile(downloads_dir)
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", downloads_dir])
            except Exception:
                pass
            self.dismiss(self.download_result)


class SettingsModal(ModalScreen[Optional[str]]):
    """Settings dialog for themes, account logins, hidden tasks, and preferences."""

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }
    #settings_dialog {
        width: 62;
        max-height: 90%;
        height: auto;
        border: thick #b4befe;
        background: #1e1e2e;
        padding: 1 2;
    }
    #settings_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #b4befe;
    }
    .settings_btn {
        width: 100%;
        margin-bottom: 1;
    }
    #settings_cancel_row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("1", "choose_theme", "Theme", show=False),
        Binding("2", "choose_login", "Login", show=False),
        Binding("3", "choose_hidden", "Hidden", show=False),
        Binding("4", "choose_school_config", "School Config", show=False),
        Binding("5", "choose_hotkeys", "Hotkeys", show=False),
        Binding("6", "choose_hotkeys", "Hotkeys", show=False),
        Binding("h", "choose_hotkeys", "Hotkeys", show=False),
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="settings_dialog"):
            yield Label("⚙️ Settings", id="settings_title")
            yield Button("🎨 Change Theme / Palette", id="btn_set_theme", classes="settings_btn", variant="primary", tooltip="Theme [1]")
            yield Button("🔑 Login", id="btn_set_login", classes="settings_btn", variant="warning", tooltip="Login [2]")
            yield Button("👁️ Hidden", id="btn_set_hidden", classes="settings_btn", variant="error", tooltip="Hidden [3]")
            yield Button("⚙️ School & Student Config", id="btn_set_school_config", classes="settings_btn", variant="primary", tooltip="School & Student Config [4]")
            yield Button("⌨️ Hotkeys", id="btn_set_hotkeys", classes="settings_btn", variant="default", tooltip="Hotkeys [5]")
            with Horizontal(id="settings_cancel_row"):
                yield Button("↩️ Close [ESC]", id="btn_set_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_set_theme":
            self.dismiss("change_theme")
        elif bid == "btn_set_login":
            self.dismiss("login_menu")
        elif bid == "btn_set_hidden":
            self.dismiss("show_trash")
        elif bid in ("btn_set_school_config", "btn_set_excuse_profile", "btn_set_group"):
            self.dismiss("school_config")
        elif bid == "btn_set_hotkeys":
            self.dismiss("show_hotkeys")
        elif bid == "btn_set_cancel":
            self.dismiss(None)

    def action_choose_theme(self) -> None:
        self.dismiss("change_theme")

    def action_choose_login(self) -> None:
        self.dismiss("login_menu")

    def action_choose_hidden(self) -> None:
        self.dismiss("show_trash")

    def action_choose_school_config(self) -> None:
        self.dismiss("school_config")

    def action_choose_group(self) -> None:
        self.dismiss("school_config")

    def action_choose_excuse_profile(self) -> None:
        self.dismiss("school_config")

    def action_choose_hotkeys(self) -> None:
        self.dismiss("show_hotkeys")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


class ThemeSelectModal(ModalScreen[Optional[str]]):
    """Auswahldialog für die 5 handverlesenen Terminal-Themes mit Tastenkürzeln und Klick-Buttons."""

    DEFAULT_CSS = """
    ThemeSelectModal {
        align: center middle;
    }
    #theme_dialog {
        width: 58;
        height: auto;
        border: thick #cba6f7;
        background: #1e1e2e;
        padding: 1 2;
    }
    #theme_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #cba6f7;
    }
    .theme_btn {
        width: 100%;
        margin-bottom: 1;
    }
    #theme_cancel_row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("1", "choose_catppuccin", "Catppuccin Mocha", show=False),
        Binding("2", "choose_dracula", "Dracula", show=False),
        Binding("3", "choose_tokyo_night", "Tokyo Night", show=False),
        Binding("4", "choose_nord", "Nord", show=False),
        Binding("5", "choose_monokai", "Monokai", show=False),
        Binding("escape", "cancel", "Back"),
    ]

    THEMES_INFO = [
        ("catppuccin-mocha", "🍵 Catppuccin Mocha (Modern & Smooth)", "btn_thm_catppuccin", "1"),
        ("dracula", "🧛 Dracula (Dark & High-Contrast)", "btn_thm_dracula", "2"),
        ("tokyo-night", "🌃 Tokyo Night (Clean & Vibrant)", "btn_thm_tokyo", "3"),
        ("nord", "❄️ Nord (Cool & Minimalist)", "btn_thm_nord", "4"),
        ("monokai", "🎨 Monokai (Classic Retro)", "btn_thm_monokai", "5"),
    ]

    def __init__(self, current_theme: str = "catppuccin-mocha"):
        super().__init__()
        self.current_theme = current_theme

    def compose(self) -> ComposeResult:
        with Vertical(id="theme_dialog"):
            yield Label("🎨 Choose Color Theme / Palette", id="theme_title")
            for t_id, t_name, btn_id, num in self.THEMES_INFO:
                is_active = (t_id == self.current_theme)
                prefix = "✓ " if is_active else ""
                label = f"[{num}] {prefix}{t_name}"
                variant = "success" if is_active else "default"
                yield Button(label, id=btn_id, classes="theme_btn", variant=variant)
            with Horizontal(id="theme_cancel_row"):
                yield Button("↩️ Back [ESC]", id="btn_theme_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid in ["btn_theme_cancel", "btn_cancel"]:
            self.dismiss(None)
        elif bid == "btn_thm_catppuccin":
            self.dismiss("catppuccin-mocha")
        elif bid == "btn_thm_dracula":
            self.dismiss("dracula")
        elif bid == "btn_thm_tokyo":
            self.dismiss("tokyo-night")
        elif bid == "btn_thm_nord":
            self.dismiss("nord")
        elif bid == "btn_thm_monokai":
            self.dismiss("monokai")

    def action_choose_catppuccin(self) -> None:
        self.dismiss("catppuccin-mocha")

    def action_choose_dracula(self) -> None:
        self.dismiss("dracula")

    def action_choose_tokyo_night(self) -> None:
        self.dismiss("tokyo-night")

    def action_choose_nord(self) -> None:
        self.dismiss("nord")

    def action_choose_monokai(self) -> None:
        self.dismiss("monokai")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


class SubjectFilterModal(ModalScreen[Optional[str]]):
    """Selection dialog for subject filter with clickable buttons."""

    DEFAULT_CSS = """
    SubjectFilterModal {
        align: center middle;
    }
    #subj_dialog {
        width: 60;
        max-height: 80%;
        border: thick #f9e2af;
        background: #1e1e2e;
        padding: 1 2;
    }
    #subj_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #f9e2af;
    }
    .subj_btn {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def __init__(self, subjects: List[str]):
        super().__init__()
        self.subjects = subjects

    def compose(self) -> ComposeResult:
        with Vertical(id="subj_dialog"):
            yield Label("📚 Filter by Subject", id="subj_title")
            with VerticalScroll():
                yield Button("🌟 All Subjects", id="btn_subj_all", classes="subj_btn", variant="primary")
                for idx, s in enumerate(self.subjects):
                    yield Button(f"📖 {s}", id=f"btn_subj_{idx}", classes="subj_btn")
            yield Button("↩️ Back [ESC]", id="btn_subj_cancel", classes="subj_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid in ["btn_subj_cancel", "btn_cancel"]:
            self.dismiss(None)
        elif bid == "btn_subj_all":
            self.dismiss("all")
        elif bid.startswith("btn_subj_"):
            try:
                idx = int(bid[9:])
                self.dismiss(self.subjects[idx])
            except (ValueError, IndexError):
                self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


class TaskDetailModal(ModalScreen[None]):
    """Vollständige interaktive Detailansicht einer Aufgabe mit Maus-Buttons."""

    DEFAULT_CSS = """
    TaskDetailModal {
        align: center middle;
    }
    #detail_dialog {
        width: 90%;
        height: 90%;
        border: thick #89b4fa;
        background: #1e1e2e;
        padding: 1 2;
    }
    #detail_header {
        height: auto;
        margin-bottom: 1;
        padding-bottom: 1;
        border-bottom: solid #313244;
    }
    #detail_title {
        text-style: bold;
        color: #89dceb;
    }
    #detail_meta {
        color: #a6adc8;
    }
    #detail_scroll {
        height: 1fr;
        border: solid #313244;
        background: #181825;
        padding: 1;
        margin-bottom: 1;
    }
    #detail_buttons {
        height: auto;
        width: 100%;
        align: left middle;
    }
    #detail_left_buttons {
        width: 1fr;
        height: auto;
        align: left middle;
    }
    #detail_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("o", "open_browser", "Open in browser"),
        Binding("d", "download_files", "Download files"),
        Binding("e", "toggle_status", "Toggle status"),
        Binding("l", "delete_task", "Hide"),
        Binding("w", "restore_task", "Restore"),
        Binding("escape", "close", "Close"),
        Binding("z", "close", "Close"),
    ]

    def __init__(self, task: Task, mgr: TaskManager, is_deleted: bool = False):
        super().__init__()
        self.target_task = task
        self.mgr = mgr
        self.is_deleted = is_deleted

    def compose(self) -> ComposeResult:
        with Vertical(id="detail_dialog"):
            with Vertical(id="detail_header"):
                if self.target_task.platform == "moodle":
                    p_badge = "🟧 Moodle"
                elif self.target_task.platform == "teams":
                    p_badge = "🟦 Teams"
                else:
                    p_badge = "✏️ Manual"
                yield Label(f"[{p_badge}] {self.target_task.title}", id="detail_title")

                teacher_str = f" | Teacher: {self.target_task.teacher}" if self.target_task.teacher else ""
                status_disp = "Completed" if self.target_task.is_completed else ("Overdue" if self.target_task.is_overdue else "Open")
                status_str = f"Status: {status_disp}"
                due_str = f"Due: {self.target_task.due_date_str}"
                meta_line = f"Subject: {self.target_task.course_full or self.target_task.course} | {status_str} | {due_str}{teacher_str}"
                yield Label(meta_line, id="detail_meta")

            with VerticalScroll(id="detail_scroll"):
                content = self.target_task.description.strip() if self.target_task.description else ""
                if not content:
                    content = "*No written assignment description provided.*"

                if self.target_task.attachments:
                    content += "\n\n---\n### 📎 Attached Files:\n"
                    for a in self.target_task.attachments:
                        content += f"* **{a.name}**\n"

                yield Markdown(content)

            with Horizontal(id="detail_buttons"):
                with Horizontal(id="detail_left_buttons"):
                    if self.target_task.platform in ["manual", "custom"]:
                        if self.target_task.is_completed:
                            yield Button("↩️ Mark as Open [E]", id="btn_det_status", variant="warning")
                            yield Button("🗑️ Delete [L]", id="btn_det_delete", variant="error")
                        else:
                            yield Button("✓ Mark as Completed [E]", id="btn_det_status", variant="success")
                    else:
                        yield Button("🌐 Browser [O]", id="btn_det_browser", variant="primary")
                        yield Button("📥 Download [D]", id="btn_det_download", variant="success")
                        if not self.is_deleted:
                            yield Button("🗑️ Hide [L]", id="btn_det_delete", variant="error")
                        else:
                            yield Button("✨ Restore [W]", id="btn_det_restore", variant="warning")
                yield Button("↩️ Close [ESC]", id="btn_det_close", variant="default")


    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_det_browser":
            self.action_open_browser()
        elif bid == "btn_det_download":
            self.action_download_files()
        elif bid == "btn_det_status":
            self.action_toggle_status()
        elif bid == "btn_det_delete":
            self.action_delete_task()
        elif bid == "btn_det_restore":
            self.action_restore_task()
        elif bid == "btn_det_close":
            self.action_close()

    def action_toggle_status(self) -> None:
        if self.target_task.platform not in ["manual", "custom"]:
            return
        updated = self.mgr.toggle_task_status(self.target_task.id)
        if updated:
            self.target_task = updated
            status_disp = "Completed" if self.target_task.is_completed else ("Overdue" if self.target_task.is_overdue else "Open")
            self.app.notify(f"Status updated to: {status_disp}", severity="information")
            teacher_str = f" | Teacher: {self.target_task.teacher}" if self.target_task.teacher else ""
            status_str = f"Status: {status_disp}"
            due_str = f"Due: {self.target_task.due_date_str}"
            meta_line = f"Subject: {self.target_task.course_full or self.target_task.course} | {status_str} | {due_str}{teacher_str}"
            self.query_one("#detail_meta", Label).update(meta_line)
            try:
                btn = self.query_one("#btn_det_status", Button)
                left_box = self.query_one("#detail_left_buttons", Horizontal)
                existing_del = list(self.query("#btn_det_delete"))
                if self.target_task.is_completed:
                    btn.label = "↩️ Mark as Open [E]"
                    btn.variant = "warning"
                    if not existing_del:
                        left_box.mount(Button("🗑️ Delete [L]", id="btn_det_delete", variant="error"))
                else:
                    btn.label = "✓ Mark as Completed [E]"
                    btn.variant = "success"
                    if existing_del:
                        existing_del[0].remove()
            except Exception:
                pass

    def action_open_browser(self) -> None:
        if self.target_task.platform in ["manual", "custom"]:
            return
        if self.target_task.url:
            ui.open_task_in_browser(self.target_task)
            self.app.notify(f"Opening '{self.target_task.title}' in browser...", severity="information")
        else:
            self.app.notify("No URL available for this assignment.", severity="warning")

    def action_download_files(self) -> None:
        if self.target_task.platform in ["manual", "custom"]:
            return
        self.app.notify("Downloading attachments...", severity="information")
        def dl_worker():
            files = self.mgr.download_task_files(self.target_task)
            def update_ui():
                if files:
                    self.app.notify(f"✓ {len(files)} file(s) saved to: {self.target_task.download_dir}", severity="information")
                    try:
                        os.startfile(self.target_task.download_dir)
                    except Exception:
                        pass
                else:
                    self.app.notify("No downloadable attachments found (angabe.md created).", severity="warning")
            self.app.call_from_thread(update_ui)

        threading.Thread(target=dl_worker, daemon=True, name="DownloadWorker").start()

    def action_delete_task(self) -> None:
        if self.target_task.platform in ["manual", "custom"]:
            if not self.target_task.is_completed:
                return
            self.mgr.delete_custom_task(self.target_task.id)
            self.app.notify(f"Manual task '{self.target_task.title}' was deleted.", severity="warning")
            self.dismiss()
            return

        self.mgr.delete_task(self.target_task.id)
        self.app.notify(f"Assignment '{self.target_task.title}' was hidden.", severity="warning")
        self.dismiss()

    def action_restore_task(self) -> None:
        self.mgr.restore_task(self.target_task.id)
        self.app.notify(f"Assignment '{self.target_task.title}' restored.", severity="information")
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


def format_status_english(task: Task) -> str:
    """Returns normalized English status string ('Completed', 'Overdue', or 'Open')."""
    if task.is_completed:
        return "Completed"
    if task.is_overdue:
        return "Overdue"
    dt = (task.status_display or "").lower()
    st = (task.status or "").lower()
    if any(kw in dt for kw in ["abgegeben", "erledigt", "completed", "done", "submitted", "bewertet", "zur bewertung", "zurückgegeben", "zurueckgegeben", "returned"]):
        return "Completed"
    if any(kw in dt for kw in ["überfällig", "ueberfaellig", "overdue", "verspätet", "late"]) or any(kw in st for kw in ["überfällig", "ueberfaellig", "overdue"]):
        return "Overdue"
    return "Open"


class TrashModal(ModalScreen[None]):
    """Papierkorb-Ansicht für ausgeblendete/gelöschte Aufgaben."""

    DEFAULT_CSS = """
    TrashModal {
        align: center middle;
    }
    #trash_dialog {
        width: 85%;
        height: 80%;
        border: thick #eba0ac;
        background: #1e1e2e;
        padding: 1 2;
    }
    #trash_title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #eba0ac;
    }
    #trash_table {
        height: 1fr;
        background: #181825;
        border: solid #313244;
        margin-bottom: 1;
    }
    #trash_buttons {
        height: auto;
        align: center middle;
    }
    #trash_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("w", "restore_all", "Restore all"),
        Binding("escape", "close", "Close"),
        Binding("z", "close", "Close"),
    ]

    def __init__(self, mgr: TaskManager):
        super().__init__()
        self.mgr = mgr
        self.deleted_tasks: List[Task] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="trash_dialog"):
            yield Label("🗑️ Hidden / Deleted Assignments", id="trash_title")
            dt = DataTable(id="trash_table", cursor_type="row")
            yield dt
            with Horizontal(id="trash_buttons"):
                yield Button("✨ Restore all [W]", id="btn_trash_restore_all", variant="success")
                yield Button("↩️ Back [ESC]", id="btn_trash_close", variant="default")

    def on_mount(self) -> None:
        dt = self.query_one(DataTable)
        dt.cell_padding = 2
        dt.add_columns("#", "Platform", "Subject", "Assignment", "Due Date", "Status")
        self.refresh_trash_table()

    def refresh_trash_table(self) -> None:
        dt = self.query_one(DataTable)
        dt.clear()
        self.deleted_tasks = self.mgr.get_deleted_tasks()
        for idx, t in enumerate(self.deleted_tasks, 1):
            if t.platform == "moodle":
                plat_badge = Text("🟧 Moodle", style="bold orange3")
            elif t.platform == "teams":
                plat_badge = Text("🟦 Teams", style="bold dodger_blue1")
            else:
                plat_badge = Text("✏️ Manual", style="bold medium_purple")
            disp_txt = format_status_english(t)
            dt.add_row(
                str(idx),
                plat_badge,
                Text(t.course, style="bold cyan"),
                t.title,
                t.due_date_str,
                Text(disp_txt, style="dim"),
                height=2,
                key=t.id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        task = next((t for t in self.deleted_tasks if t.id == row_key), None)
        if task:
            self.app.push_screen(TaskDetailModal(task, self.mgr, is_deleted=True), self._on_detail_closed)

    def _on_detail_closed(self, result=None) -> None:
        self.refresh_trash_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_trash_restore_all":
            self.action_restore_all()
        elif event.button.id == "btn_trash_close":
            self.action_close()

    def action_restore_all(self) -> None:
        for t in list(self.deleted_tasks):
            self.mgr.restore_task(t.id)
        self.app.notify("✓ All assignments restored!", severity="information")
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


class MoodleLoginModal(ModalScreen[bool]):
    """Interactive Moodle login dialog directly inside the terminal."""

    DEFAULT_CSS = """
    MoodleLoginModal {
        align: center middle;
    }
    #moodle_dialog {
        width: 65;
        height: auto;
        border: thick #fab387;
        background: #1e1e2e;
        padding: 1 2;
    }
    #moodle_title {
        text-align: center;
        text-style: bold;
        color: #fab387;
        margin-bottom: 1;
    }
    #moodle_desc {
        color: #a6adc8;
        margin-bottom: 1;
        text-align: center;
    }
    #moodle_status {
        color: #f9e2af;
        margin-top: 1;
        margin-bottom: 1;
        text-align: center;
    }
    .m_input {
        margin-bottom: 1;
    }
    #moodle_buttons {
        height: auto;
        align: center middle;
    }
    #moodle_buttons Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        from config import MOODLE_BASE_URL, _load_moodle_base_url
        current_url = _load_moodle_base_url() or MOODLE_BASE_URL
        with Vertical(id="moodle_dialog"):
            yield Label("🎓 Moodle Login", id="moodle_title")
            yield Label("Credentials are stored locally on your PC only.", id="moodle_desc")
            yield Input(value=current_url, placeholder="Moodle URL (z.B. https://moodle.spengergasse.at)", id="inp_m_url", classes="m_input")
            yield Input(placeholder="Username", id="inp_m_user", classes="m_input")
            yield Input(placeholder="Password", password=True, id="inp_m_pass", classes="m_input")
            yield Label("", id="moodle_status")
            with Horizontal(id="moodle_buttons"):
                yield Button("🔐 Log In", id="btn_m_submit", variant="primary")
                yield Button("↩️ Back [ESC]", id="btn_m_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_m_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_m_submit":
            self._start_login()

    def _start_login(self) -> None:
        url = self.query_one("#inp_m_url", Input).value.strip()
        u = self.query_one("#inp_m_user", Input).value.strip()
        p = self.query_one("#inp_m_pass", Input).value.strip()
        if not u or not p:
            self.query_one("#moodle_status", Label).update("[red]Please enter username and password.[/red]")
            return

        if not url:
            from config import MOODLE_BASE_URL
            url = MOODLE_BASE_URL

        self.query_one("#moodle_status", Label).update("[yellow]Checking Moodle credentials...[/yellow]")
        self.query_one("#btn_m_submit", Button).disabled = True

        def worker():
            success = login_moodle_direct(u, p, moodle_url=url)
            def update_ui():
                self.query_one("#btn_m_submit", Button).disabled = False
                if success:
                    self.app.notify("✓ Moodle successfully connected!", severity="information")
                    self.dismiss(True)
                else:
                    self.query_one("#moodle_status", Label).update("[red]✗ Login failed. Please check your credentials and URL.[/red]")
            self.app.call_from_thread(update_ui)

        threading.Thread(target=worker, daemon=True, name="MoodleLoginWorker").start()

    def key_escape(self) -> None:
        self.dismiss(False)


class TeamsSetupModal(ModalScreen[bool]):
    """Microsoft Teams Direct Login dialog (just like Moodle & Untis)."""

    DEFAULT_CSS = """
    TeamsSetupModal {
        align: center middle;
    }
    #teams_dialog {
        width: 68;
        height: auto;
        border: thick #74c7ec;
        background: #1e1e2e;
        padding: 1 2;
    }
    #teams_title {
        text-align: center;
        text-style: bold;
        color: #74c7ec;
        margin-bottom: 1;
    }
    #teams_desc {
        color: #a6adc8;
        margin-bottom: 1;
        text-align: center;
    }
    .t_input {
        margin-bottom: 1;
    }
    #teams_status {
        color: #f9e2af;
        margin: 1 0;
        text-align: center;
    }
    #teams_2fa_box {
        border: round #a6e3a1;
        background: #181825;
        padding: 1;
        margin-bottom: 1;
        display: none;
        align: center middle;
    }
    #teams_2fa_title {
        text-align: center;
        text-style: bold;
        color: #a6e3a1;
    }
    #teams_2fa_number {
        text-align: center;
        text-style: bold;
        color: #fab387;
        margin: 1 0;
    }
    #teams_2fa_desc {
        text-align: center;
        color: #cdd6f4;
        margin-bottom: 1;
    }
    #teams_2fa_input_row {
        height: auto;
        display: none;
        align: center middle;
        margin-top: 1;
    }
    #teams_2fa_input_row Input {
        width: 28;
        margin-right: 1;
    }
    #teams_btn_row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #teams_btn_row Button {
        margin: 0 1;
    }
    .t_sec_btn {
        width: 100%;
        margin-top: 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mfa_code_event = threading.Event()
        self._mfa_code_val = None

    def compose(self) -> ComposeResult:
        with Vertical(id="teams_dialog"):
            yield Label("👥 Microsoft Teams Login", id="teams_title")
            yield Label("Log in directly with your school email and password:", id="teams_desc")
            yield Input(placeholder="School email (e.g. name@spengergasse.at)", id="inp_t_email", classes="t_input")
            yield Input(placeholder="Password", password=True, id="inp_t_pass", classes="t_input")

            with Vertical(id="teams_2fa_box"):
                yield Label("🔔 Two-Factor Authentication (2FA)", id="teams_2fa_title")
                yield Label("", id="teams_2fa_number")
                yield Label("Approve the number in your Microsoft Authenticator app on your phone.", id="teams_2fa_desc")
                with Horizontal(id="teams_2fa_input_row"):
                    yield Input(placeholder="6-digit SMS / verification code", id="inp_t_code")
                    yield Button("Send Code", id="btn_t_submit_code", variant="success")

            yield Label("", id="teams_status")

            with Horizontal(id="teams_btn_row"):
                yield Button("🔐 Log in with Password", id="btn_t_login", variant="primary")
                yield Button("↩️ Back [ESC]", id="btn_t_cancel", variant="default")

            yield Button("🔑 Log in with Passkey / Browser", id="btn_t_passkey", classes="t_sec_btn", variant="warning")
            yield Button("🔍 Check existing session", id="btn_t_check", classes="t_sec_btn", variant="success")

    def on_mount(self) -> None:
        try:
            from auth import get_existing_moodle_credentials
            _, creds = get_existing_moodle_credentials()
            if creds and creds.get("username"):
                u = creds["username"].strip()
                if "@" in u:
                    self.query_one("#inp_t_email", Input).value = u
                elif u:
                    self.query_one("#inp_t_email", Input).value = f"{u}@spengergasse.at"
            else:
                self.query_one("#inp_t_email", Input).value = ""
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_t_cancel":
            self.dismiss(False)
        elif bid == "btn_t_login":
            self._start_direct_login()
        elif bid == "btn_t_submit_code":
            self._submit_mfa_code()
        elif bid == "btn_t_check":
            self._check_session()
        elif bid in ("btn_t_fresh", "btn_t_passkey"):
            self._run_interactive_browser()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("inp_t_email", "inp_t_pass"):
            self._start_direct_login()
        elif event.input.id == "inp_t_code":
            self._submit_mfa_code()

    def _submit_mfa_code(self) -> None:
        try:
            val = self.query_one("#inp_t_code", Input).value.strip()
            if val:
                self._mfa_code_val = val
                self._mfa_code_event.set()
                self.query_one("#teams_status", Label).update("[yellow]Submitting verification code...[/yellow]")
        except Exception:
            pass

    def _start_direct_login(self) -> None:
        email = self.query_one("#inp_t_email", Input).value.strip()
        pwd = self.query_one("#inp_t_pass", Input).value.strip()

        if not email or not pwd:
            self.query_one("#teams_status", Label).update("[red]Please enter your school email and password.[/red]")
            return

        self.query_one("#teams_status", Label).update("[yellow]Logging into Microsoft...[/yellow]")
        self.query_one("#btn_t_login", Button).disabled = True
        self.query_one("#btn_t_check", Button).disabled = True

        self._mfa_code_event.clear()
        self._mfa_code_val = None

        def worker():
            def on_status_cb(msg: str):
                self.app.call_from_thread(lambda: self.query_one("#teams_status", Label).update(f"[cyan]{msg}[/cyan]"))

            def on_mfa_num_cb(num: str):
                def update_box():
                    box = self.query_one("#teams_2fa_box", Vertical)
                    box.styles.display = "block"
                    self.query_one("#teams_2fa_number", Label).update(f"[bold yellow on black]   [  {num}  ]   [/bold yellow on black]")
                    self.query_one("#teams_2fa_desc", Label).update(f"Tap number [bold yellow]{num}[/bold yellow] in your Authenticator app on your smartphone!")
                self.app.call_from_thread(update_box)

            def on_mfa_code_cb():
                def show_input():
                    box = self.query_one("#teams_2fa_box", Vertical)
                    box.styles.display = "block"
                    self.query_one("#teams_2fa_number", Label).update("")
                    self.query_one("#teams_2fa_desc", Label).update("Enter the 6-digit verification code you received:")
                    row = self.query_one("#teams_2fa_input_row", Horizontal)
                    row.styles.display = "block"
                    self.query_one("#inp_t_code", Input).focus()
                self.app.call_from_thread(show_input)
                self._mfa_code_event.wait(timeout=120)
                return self._mfa_code_val

            success, msg = login_teams_direct(
                email=email,
                password=pwd,
                on_status=on_status_cb,
                on_mfa_number=on_mfa_num_cb,
                on_mfa_code_request=on_mfa_code_cb,
                headless=True,
                timeout_sec=180,
            )

            def on_done():
                self.query_one("#btn_t_login", Button).disabled = False
                self.query_one("#btn_t_check", Button).disabled = False
                if success:
                    self.app.notify("✓ Microsoft Teams successfully connected!", severity="information")
                    self.dismiss(True)
                else:
                    self.query_one("#teams_status", Label).update(f"[red]✗ {msg}[/red]")

            self.app.call_from_thread(on_done)

        threading.Thread(target=worker, daemon=True, name="TeamsDirectLoginWorker").start()

    def _check_session(self) -> None:
        self.query_one("#teams_status", Label).update("[yellow]Checking Teams session in background...[/yellow]")
        self.query_one("#btn_t_check", Button).disabled = True

        def worker():
            ok = test_teams_session_live()
            def update_ui():
                self.query_one("#btn_t_check", Button).disabled = False
                if ok:
                    try:
                        with open(TEAMS_STATUS_FILE, "w", encoding="utf-8") as f:
                            json.dump({"configured": True, "last_login": time.time()}, f)
                    except Exception:
                        pass
                    self.app.notify("✓ Teams session is active and valid!", severity="information")
                    self.dismiss(True)
                else:
                    self.query_one("#teams_status", Label).update("[red]! Session expired. Please enter email & password.[/red]")
            self.app.call_from_thread(update_ui)

        threading.Thread(target=worker, daemon=True, name="TeamsCheckWorker").start()

    def _run_interactive_browser(self) -> None:
        email = ""
        try:
            email = self.query_one("#inp_t_email", Input).value.strip()
        except Exception:
            pass
        if not email:
            email = ""

        self.query_one("#teams_status", Label).update("[yellow]Browser opened: Please log in with passkey in the Teams window...[/yellow]")
        try:
            self.query_one("#btn_t_passkey", Button).disabled = True
            self.query_one("#btn_t_login", Button).disabled = True
            self.query_one("#btn_t_check", Button).disabled = True
        except Exception:
            pass

        def worker():
            ok = setup_teams_interactive(console=None, fresh=True, email=email)
            def update_ui():
                try:
                    self.query_one("#btn_t_passkey", Button).disabled = False
                    self.query_one("#btn_t_login", Button).disabled = False
                    self.query_one("#btn_t_check", Button).disabled = False
                except Exception:
                    pass
                if ok:
                    self.app.notify("✓ Teams successfully connected!", severity="information")
                    self.dismiss(True)
                else:
                    self.query_one("#teams_status", Label).update("[yellow]Teams login not completed.[/yellow]")
            self.app.call_from_thread(update_ui)

        threading.Thread(target=worker, daemon=True, name="TeamsPasskeyLoginWorker").start()

    def key_escape(self) -> None:
        self.dismiss(False)


class LoginChoiceModal(ModalScreen[Optional[str]]):
    """Selection dialog for login (Teams, Moodle, WebUntis) with per-platform status indicators."""

    DEFAULT_CSS = """
    LoginChoiceModal {
        align: center middle;
    }
    #login_choice_dialog {
        width: 64;
        height: auto;
        border: thick #fab387;
        background: #1e1e2e;
        padding: 1 2;
    }
    #login_choice_title {
        text-align: center;
        text-style: bold;
        color: #fab387;
        margin-bottom: 1;
    }
    .login_choice_row {
        height: auto;
        align: left middle;
        margin-bottom: 1;
    }
    .login_choice_btn {
        width: 34;
    }
    .login_status_lbl {
        margin-left: 2;
        padding-top: 1;
        text-style: bold;
    }
    #btn_login_cancel {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("1", "choose_teams", "Teams Login", show=False),
        Binding("t", "choose_teams", "Teams Login", show=False),
        Binding("2", "choose_moodle", "Moodle Login", show=False),
        Binding("m", "choose_moodle", "Moodle Login", show=False),
        Binding("3", "choose_untis", "Untis Login", show=False),
        Binding("u", "choose_untis", "Untis Login", show=False),
        Binding("4", "choose_git", "Git Sync", show=False),
        Binding("g", "choose_git", "Git Sync", show=False),
        Binding("escape", "cancel", "Back"),
    ]

    def _is_teams_logged_in(self) -> bool:
        import json
        from config import TEAMS_STATUS_FILE, TEAMS_PROFILE_DIR
        if os.path.exists(TEAMS_STATUS_FILE):
            try:
                with open(TEAMS_STATUS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("configured", False):
                        return True
            except Exception:
                pass
        if os.path.isdir(TEAMS_PROFILE_DIR):
            def_dir = os.path.join(TEAMS_PROFILE_DIR, "Default")
            if os.path.isdir(def_dir) and len(os.listdir(def_dir)) > 3:
                return True
        return False

    def _is_moodle_logged_in(self) -> bool:
        from auth import get_saved_moodle_cookies, get_existing_moodle_credentials
        if get_saved_moodle_cookies():
            return True
        path, creds = get_existing_moodle_credentials()
        if creds and creds.get("username") and creds.get("password"):
            return True
        return False

    def _is_untis_logged_in(self) -> bool:
        import json
        from auth import get_existing_untis_credentials
        from config import UNTIS_CACHE_FILE
        path, creds = get_existing_untis_credentials()
        if creds and creds.get("username") and creds.get("password"):
            return True
        if os.path.exists(UNTIS_CACHE_FILE):
            try:
                with open(UNTIS_CACHE_FILE, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                    if isinstance(cdata, list) and len(cdata) > 0:
                        return True
            except Exception:
                pass
        return False

    def _is_git_logged_in(self) -> bool:
        try:
            from git_sync_service import is_git_configured
            return is_git_configured()
        except Exception:
            return False

    def compose(self) -> ComposeResult:
        teams_ok = self._is_teams_logged_in()
        moodle_ok = self._is_moodle_logged_in()
        untis_ok = self._is_untis_logged_in()
        git_ok = self._is_git_logged_in()

        teams_lbl = "[green]Signed in ✓[/green]" if teams_ok else "[red]Not signed in ✗[/red]"
        moodle_lbl = "[green]Signed in ✓[/green]" if moodle_ok else "[red]Not signed in ✗[/red]"
        untis_lbl = "[green]Signed in ✓[/green]" if untis_ok else "[red]Not signed in ✗[/red]"
        git_lbl = "[green]Connected ✓[/green]" if git_ok else "[dim]Not configured ✗[/dim]"

        with Vertical(id="login_choice_dialog"):
            yield Label("🔑 Select Login / Platform", id="login_choice_title")
            with Horizontal(classes="login_choice_row"):
                yield Button("👥 Teams Login [1/T]", id="btn_login_teams", classes="login_choice_btn", variant="primary")
                yield Label(teams_lbl, classes="login_status_lbl")
            with Horizontal(classes="login_choice_row"):
                yield Button("🎓 Moodle Login [2/M]", id="btn_login_moodle", classes="login_choice_btn", variant="warning")
                yield Label(moodle_lbl, classes="login_status_lbl")
            with Horizontal(classes="login_choice_row"):
                yield Button("📅 WebUntis Login [3/U]", id="btn_login_untis", classes="login_choice_btn", variant="success")
                yield Label(untis_lbl, classes="login_status_lbl")
            with Horizontal(classes="login_choice_row"):
                yield Button("🐙 Git Cloud-Sync [4/G]", id="btn_login_git", classes="login_choice_btn", variant="default")
                yield Label(git_lbl, classes="login_status_lbl")
            yield Button("↩️ Back [ESC]", id="btn_login_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_login_teams":
            self.dismiss("teams")
        elif bid == "btn_login_moodle":
            self.dismiss("moodle")
        elif bid == "btn_login_untis":
            self.dismiss("untis")
        elif bid == "btn_login_git":
            self.dismiss("git")
        elif bid == "btn_login_cancel":
            self.dismiss(None)

    def action_choose_teams(self) -> None:
        self.dismiss("teams")

    def action_choose_moodle(self) -> None:
        self.dismiss("moodle")

    def action_choose_untis(self) -> None:
        self.dismiss("untis")

    def action_choose_git(self) -> None:
        self.dismiss("git")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


class GitSetupModal(ModalScreen[bool]):
    """Git Cloud-Sync Setup dialog (Repo URL, Token, Branch, Test & Sync)."""

    DEFAULT_CSS = """
    GitSetupModal {
        align: center middle;
    }
    #git_setup_dialog {
        width: 68;
        height: auto;
        border: thick #a6e3a1;
        background: #1e1e2e;
        padding: 1 2;
    }
    #git_setup_title {
        text-align: center;
        text-style: bold;
        color: #a6e3a1;
        margin-bottom: 1;
    }
    #git_setup_desc {
        color: #cdd6f4;
        margin-bottom: 1;
        text-align: center;
    }
    .git_field_label {
        color: #fab387;
        text-style: bold;
        margin-top: 1;
    }
    .git_field {
        margin-bottom: 1;
    }
    #git_token_row {
        height: auto;
        align: left middle;
        margin-bottom: 1;
    }
    #inp_git_token {
        width: 48;
    }
    #btn_git_toggle_token {
        width: 14;
        margin-left: 1;
    }
    #git_status {
        margin: 1 0;
        text-align: center;
        text-style: bold;
    }
    #git_buttons_top {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #git_buttons_top Button {
        margin: 0 1;
    }
    #git_buttons_bottom {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #git_buttons_bottom Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="git_setup_dialog"):
            yield Label("🐙 Git Cloud-Sync Setup", id="git_setup_title")
            yield Label(
                "Synchronize assignments, exams & notes via private Git repository.",
                id="git_setup_desc",
            )
            yield Label("Repository HTTPS URL:", classes="git_field_label")
            yield Input(placeholder="https://github.com/user/my-backup.git", id="inp_git_url", classes="git_field")

            yield Label("Personal Access Token (PAT):", classes="git_field_label")
            with Horizontal(id="git_token_row"):
                yield Input(placeholder="ghp_xxxxxxxxxxxxxxxxxxxx (optional)", password=True, id="inp_git_token")
                yield Button("👁️ Show", id="btn_git_toggle_token", variant="default")

            yield Label("Branch:", classes="git_field_label")
            yield Input(value="main", placeholder="main", id="inp_git_branch", classes="git_field")

            yield Label("", id="git_status")

            with Horizontal(id="git_buttons_top"):
                yield Button("🚀 Test & Connect", id="btn_git_save_sync", variant="primary")
                yield Button("🗑️ Disconnect", id="btn_git_disconnect", variant="error")
            with Horizontal(id="git_buttons_bottom"):
                yield Button("↩️ Back [ESC]", id="btn_git_close", variant="default")

    def on_mount(self) -> None:
        from config import get_git_sync_config
        cfg = get_git_sync_config()
        if cfg.get("repo_url"):
            try:
                self.query_one("#inp_git_url", Input).value = cfg.get("repo_url", "")
            except Exception:
                pass
        if cfg.get("token"):
            try:
                self.query_one("#inp_git_token", Input).value = cfg.get("token", "")
            except Exception:
                pass
        if cfg.get("branch"):
            try:
                self.query_one("#inp_git_branch", Input).value = cfg.get("branch", "main")
            except Exception:
                pass

        if cfg.get("enabled") and cfg.get("repo_url"):
            last_s = cfg.get("last_sync") or "Never"
            if last_s != "Never":
                try:
                    dt = datetime.datetime.fromisoformat(last_s)
                    last_s = dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    pass
            self.query_one("#git_status", Label).update(f"[green]Connected ✓ (Last Sync: {last_s})[/green]")
        else:
            try:
                self.query_one("#btn_git_disconnect", Button).disabled = True
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_git_close":
            self.dismiss(False)
        elif bid == "btn_git_toggle_token":
            inp = self.query_one("#inp_git_token", Input)
            btn = self.query_one("#btn_git_toggle_token", Button)
            inp.password = not inp.password
            btn.label = "🔒 Hide" if not inp.password else "👁️ Show"
        elif bid == "btn_git_disconnect":
            self._disconnect_git()
        elif bid == "btn_git_save_sync":
            self._save_and_sync()

    def _disconnect_git(self) -> None:
        from git_sync_service import GitSyncService
        self.query_one("#git_status", Label).update("[yellow]Disconnecting Git connection...[/yellow]")
        ok, msg = GitSyncService.disconnect()
        self.app.notify(msg, severity="information")
        self.dismiss(True)

    def _save_and_sync(self) -> None:
        repo_url = self.query_one("#inp_git_url", Input).value.strip()
        token = self.query_one("#inp_git_token", Input).value.strip()
        branch = self.query_one("#inp_git_branch", Input).value.strip() or "main"

        if not repo_url:
            self.query_one("#git_status", Label).update("[red]Please enter a repository URL![/red]")
            return

        if not repo_url.startswith("http://") and not repo_url.startswith("https://"):
            self.query_one("#git_status", Label).update("[red]URL must start with https://![/red]")
            return

        self.query_one("#git_status", Label).update("[yellow]Connecting and synchronizing...[/yellow]")
        btn_save = self.query_one("#btn_git_save_sync", Button)
        btn_save.disabled = True

        def worker():
            try:
                from git_sync_service import GitSyncService
                ok, msg = GitSyncService.setup_repository(repo_url=repo_url, token=token, branch=branch)
            except Exception as e:
                ok, msg = False, f"Connection error: {e}"

            def update_ui():
                try:
                    btn_save.disabled = False
                    if ok:
                        self.app.notify(f"✓ {msg}", severity="information")
                        self.dismiss(True)
                    else:
                        self.query_one("#git_status", Label).update(f"[red]✗ {msg}[/red]")
                except Exception:
                    pass

            try:
                self.app.call_from_thread(update_ui)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name="GitSetupWorker").start()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def key_escape(self) -> None:
        self.dismiss(False)



class UntisSetupModal(ModalScreen[bool]):
    """WebUntis Direct API Setup & Login dialog."""

    DEFAULT_CSS = """
    UntisSetupModal {
        align: center middle;
    }
    #untis_dialog {
        width: 62;
        height: auto;
        border: thick #b4befe;
        background: #1e1e2e;
        padding: 1 2;
    }
    #untis_title {
        text-align: center;
        text-style: bold;
        color: #b4befe;
        margin-bottom: 1;
    }
    #untis_desc {
        color: #cdd6f4;
        margin-bottom: 1;
        text-align: center;
    }
    .untis_field {
        margin-bottom: 1;
    }
    #untis_status {
        margin: 1 0;
        text-align: center;
    }
    #untis_buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #untis_buttons Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="untis_dialog"):
            yield Label("📅 WebUntis API Connection", id="untis_title")
            yield Label("Sign in with your school account:", id="untis_desc")
            yield Input(placeholder="School name", id="inp_u_school", classes="untis_field")
            yield Input(placeholder="Username", id="inp_u_user", classes="untis_field")
            yield Input(placeholder="Password", password=True, id="inp_u_pass", classes="untis_field")
            yield Label("", id="untis_status")
            with Horizontal(id="untis_buttons"):
                yield Button("🔐 Log In", id="btn_u_login", variant="primary")
                yield Button("⚡ Use Moodle Account", id="btn_u_existing", variant="success")
                yield Button("↩️ Back [ESC]", id="btn_u_close", variant="default")

    def on_mount(self) -> None:
        from auth import get_existing_moodle_credentials, get_existing_untis_credentials
        path, creds = get_existing_moodle_credentials()
        if not creds:
            path, creds = get_existing_untis_credentials()
        if not creds:
            try:
                self.query_one("#btn_u_existing", Button).display = False
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_u_close":
            self.dismiss(False)
        elif bid == "btn_u_login":
            self._start_login()
        elif bid == "btn_u_existing":
            self._use_existing()

    def _start_login(self) -> None:
        sch = self.query_one("#inp_u_school", Input).value.strip()
        u = self.query_one("#inp_u_user", Input).value.strip()
        p = self.query_one("#inp_u_pass", Input).value.strip()
        if not sch:
            self.query_one("#untis_status", Label).update("[red]Please enter your school name.[/red]")
            return
        if not u or not p:
            self.query_one("#untis_status", Label).update("[red]Please enter username and password.[/red]")
            return

        self.query_one("#untis_status", Label).update("[yellow]Authenticating with WebUntis API...[/yellow]")
        self.query_one("#btn_u_login", Button).disabled = True

        def worker():
            from untis_service import login_untis_direct
            ok = login_untis_direct(u, p, school=sch)
            def update_ui():
                self.query_one("#btn_u_login", Button).disabled = False
                if ok:
                    self.app.notify("✓ WebUntis connected successfully!", severity="information")
                    self.dismiss(True)
                else:
                    self.query_one("#untis_status", Label).update("[red]✗ Login failed. Please check school and credentials.[/red]")
            self.app.call_from_thread(update_ui)

        threading.Thread(target=worker, daemon=True, name="UntisLoginWorker").start()

    def _use_existing(self) -> None:
        sch = self.query_one("#inp_u_school", Input).value.strip()
        if not sch:
            from config import _load_untis_school
            sch = _load_untis_school()
            if sch:
                self.query_one("#inp_u_school", Input).value = sch
            else:
                self.query_one("#untis_status", Label).update("[red]Please enter your school name.[/red]")
                return
        from auth import get_existing_moodle_credentials, get_existing_untis_credentials
        path, creds = get_existing_moodle_credentials()
        if not creds:
            path, creds = get_existing_untis_credentials()
        if not creds:
            self.query_one("#untis_status", Label).update("[red]No saved Moodle credentials found.[/red]")
            return

        u = creds.get("username", "").strip()
        p = creds.get("password", "").strip()
        self.query_one("#inp_u_user", Input).value = u
        self.query_one("#untis_status", Label).update("[yellow]Verifying Moodle credentials with WebUntis...[/yellow]")
        self.query_one("#btn_u_existing", Button).disabled = True

        def worker():
            from untis_service import login_untis_direct
            ok = login_untis_direct(u, p, school=sch)
            def update_ui():
                self.query_one("#btn_u_existing", Button).disabled = False
                if ok:
                    self.app.notify("✓ WebUntis connected successfully!", severity="information")
                    self.dismiss(True)
                else:
                    self.query_one("#untis_status", Label).update("[red]✗ Moodle credentials invalid for WebUntis.[/red]")
            self.app.call_from_thread(update_ui)

        threading.Thread(target=worker, daemon=True, name="UntisExistingWorker").start()

    def key_escape(self) -> None:
        self.dismiss(False)



class AbsencesScreen(ModalScreen[None]):
    """Full-screen view for WebUntis absences and missed lessons."""

    DEFAULT_CSS = """
    AbsencesScreen {
        layout: vertical;
        background: $background;
        padding: 0;
        overflow-y: hidden;
    }
    #abs_header {
        dock: top;
        height: 3;
        padding: 0 1;
        align: center middle;
    }
    #abs_title {
        text-style: bold;
        content-align: left middle;
        height: 100%;
        width: auto;
    }
    #abs_sub_info {
        text-style: bold;
        content-align: right middle;
        height: 100%;
        width: 1fr;
    }
    #abs_split_container {
        height: 1fr;
        layout: vertical;
        overflow-y: hidden;
        padding: 0;
        margin: 0;
    }
    #abs_subject_box {
        height: 1fr;
        padding: 0 1;
        margin: 0;
    }
    #abs_detail_box {
        height: 1fr;
        padding: 0 1;
        margin: 0;
    }
    .abs_box_title {
        text-style: bold;
        margin-bottom: 0;
    }
    #abs_subject_table {
        height: 1fr;
    }
    #abs_detail_table {
        height: 1fr;
    }
    #abs_button_bar {
        dock: bottom;
        height: 3;
        width: 100%;
        align: left middle;
        padding: 0 1;
        overflow-x: hidden;
        overflow-y: hidden;
    }
    #abs_left_buttons {
        width: 1fr;
        height: 100%;
        align: left middle;
    }
    #abs_button_bar Button {
        margin: 0 1;
        min-width: 4;
        height: 100%;
        content-align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Back to Tasks"),
        Binding("t", "dismiss_screen", "Back to Tasks"),
        Binding("r", "sync_untis", "Sync"),
        Binding("g", "toggle_group", "Toggle Group"),
        Binding("e", "excuse_letter", "Excuse Letter"),
    ]

    def __init__(self):
        super().__init__()
        self.summaries: List[SubjectAbsenceSummary] = []
        self.selected_subject: Optional[str] = None
        self._is_syncing: bool = False
        full_cfg = load_full_school_config()
        self.current_group: str = (full_cfg.get("untis_group") or "X").strip().upper()
        self.current_class: str = (full_cfg.get("student_class") or "1AHIT").strip()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="abs_header"):
            yield Label("📅 WebUntis Missed Lessons", id="abs_title")
            yield Label("", id="abs_sub_info")

        with Vertical(id="abs_split_container"):
            with Vertical(id="abs_subject_box"):
                yield Label("📚 Missed Hours per Subject", classes="abs_box_title")
                yield DataTable(id="abs_subject_table", cursor_type="row")
            with Vertical(id="abs_detail_box"):
                yield Label("Details", id="abs_detail_title", classes="abs_box_title")
                yield DataTable(id="abs_detail_table", cursor_type="row")

        with Horizontal(id="abs_button_bar"):
            with Horizontal(id="abs_left_buttons"):
                yield Button("🔄 Sync Untis", id="btn_abs_sync", variant="success", tooltip="Sync Untis [R]")
                yield Button("📝 Excuse Letter", id="btn_abs_excuse", variant="warning", tooltip="Excuse Letter [E]")
            yield Button("↩️ Back", id="btn_abs_back", variant="default", tooltip="Back to tasks [T/Esc]")


    def on_mount(self) -> None:
        sub_dt = self.query_one("#abs_subject_table", DataTable)
        sub_dt.cell_padding = 2
        sub_dt.add_columns("#", "Subject", "Missed Hours", "Last Missed Date")

        det_dt = self.query_one("#abs_detail_table", DataTable)
        det_dt.cell_padding = 2
        det_dt.add_columns("#", "Date", "Time", "Teacher", "Room", "Reason", "Status")

        self.summaries = load_untis_cache()
        self.refresh_tables()

    def refresh_tables(self) -> None:
        sub_dt = self.query_one("#abs_subject_table", DataTable)
        sub_dt.clear()

        full_cfg = load_full_school_config()
        self.current_group = (full_cfg.get("untis_group") or "X").strip().upper()
        self.current_class = (full_cfg.get("student_class") or "1AHIT").strip()

        total_hours = sum(s.total_hours for s in self.summaries)
        info_label = self.query_one("#abs_sub_info", Label)
        info_label.update(f"Missed Hours: [bold red]{total_hours}[/bold red]  |  Class: {self.current_class}  |  Group: {self.current_group}")

        if not self.summaries:
            self.refresh_detail_table(None)
            return

        for idx, s in enumerate(self.summaries, 1):
            hours_str = f"{s.total_hours} hour" if s.total_hours == 1 else f"{s.total_hours} hours"
            sub_dt.add_row(
                str(idx),
                Text(s.subject, style="bold cyan"),
                Text(hours_str, style="bold red" if s.total_hours >= 5 else "bold yellow"),
                s.last_date or "-",
                height=2,
                key=s.subject,
            )

        target = self.selected_subject or self.summaries[0].subject
        self.selected_subject = target
        self.refresh_detail_table(target)

    def refresh_detail_table(self, subject: Optional[str]) -> None:
        det_dt = self.query_one("#abs_detail_table", DataTable)
        det_dt.clear()

        title_lbl = self.query_one("#abs_detail_title", Label)
        title_lbl.update("Details")

        if not subject:
            return

        summary = next((s for s in self.summaries if s.subject == subject), None)
        if not summary:
            return

        for idx, m in enumerate(summary.missed_lessons, 1):
            time_str = f"{m.start_time} - {m.end_time}"
            status_style = "green" if any(w in m.absence_status.lower() for w in ["entschuldigt", "excused"]) else "yellow"
            det_dt.add_row(
                str(idx),
                Text(m.date, style="bold"),
                time_str,
                m.teacher or "-",
                m.room or "-",
                m.reason or "Absent",
                Text(m.absence_status, style=status_style),
                height=2,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "abs_subject_table" and event.row_key:
            subj = event.row_key.value
            self.selected_subject = subj
            self.refresh_detail_table(subj)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "abs_subject_table" and event.row_key:
            subj = event.row_key.value
            self.selected_subject = subj
            self.refresh_detail_table(subj)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_abs_back":
            self.action_dismiss_screen()
        elif bid == "btn_abs_sync":
            self.action_sync_untis()
        elif bid == "btn_abs_group":
            self.action_toggle_group()
        elif bid == "btn_abs_excuse":
            self.action_excuse_letter()

    def action_dismiss_screen(self) -> None:
        self.dismiss()

    def action_excuse_letter(self) -> None:
        self.app.push_screen(ExcuseLetterModal(self.summaries))

    def action_sync_untis(self) -> None:
        if self._is_syncing:
            return
        self._is_syncing = True
        self.app.notify("🔄 Synchronizing WebUntis absences and timetable...", severity="information")
        self.query_one("#btn_abs_sync", Button).disabled = True

        def worker():
            ok, msg, res = sync_untis_data(headless=True)
            def update_ui():
                self._is_syncing = False
                self.query_one("#btn_abs_sync", Button).disabled = False
                if ok:
                    self.summaries = res
                    self.refresh_tables()
                    self.app.notify(f"✓ {msg}", severity="information")
                else:
                    self.app.notify(f"! {msg}", severity="warning")
            self.app.call_from_thread(update_ui)

        threading.Thread(target=worker, daemon=True, name="UntisSyncWorker").start()

    def action_toggle_group(self) -> None:
        new_grp = "Y" if self.current_group.upper() == "X" else "X"
        self.current_group = new_grp
        save_untis_group(new_grp)
        try:
            self.query_one("#btn_abs_group", Button).label = f"⚙️ Group: {new_grp}"
        except Exception:
            pass
        self.refresh_tables()
        self.app.notify(f"Untis group set to {new_grp}. Re-syncing...", severity="information")
        self.action_sync_untis()


class SchoolConfigModal(ModalScreen[bool]):
    """Modal for configuring student and school profile across all modules."""

    DEFAULT_CSS = """
    SchoolConfigModal {
        align: center middle;
    }
    #school_config_dialog {
        width: 72;
        max-height: 90%;
        height: auto;
        border: thick #fab387;
        background: #1e1e2e;
        padding: 1 2;
    }
    #school_config_title {
        text-align: center;
        text-style: bold;
        color: #fab387;
        margin-bottom: 1;
    }
    #cfg_scroll {
        max-height: 16;
        height: auto;
        scrollbar-gutter: stable;
        padding-right: 1;
    }
    .cfg_section_title {
        color: #b4befe;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }
    .cfg_label {
        color: #cdd6f4;
        margin-top: 1;
        text-style: bold;
    }
    .cfg_input {
        margin-bottom: 0;
    }
    #cfg_group_row {
        height: auto;
        align: left middle;
        margin-top: 1;
        margin-bottom: 0;
    }
    #cfg_group_label {
        color: #cdd6f4;
        text-style: bold;
        margin-right: 2;
        height: 3;
        content-align: left middle;
    }
    #btn_cfg_group {
        min-width: 16;
    }
    #cfg_buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #cfg_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Back"),
        Binding("g", "toggle_group", "Toggle Group"),
    ]

    def __init__(self):
        super().__init__()
        self.config_data = load_full_school_config()
        self.current_group = "X" if "x" in str(self.config_data.get("untis_group", "X")).lower() else "Y"

    def compose(self) -> ComposeResult:
        with Vertical(id="school_config_dialog"):
            yield Label("⚙️ School & Student Configuration", id="school_config_title")
            with VerticalScroll(id="cfg_scroll"):
                yield Label("👤 Student Details", classes="cfg_section_title")
                yield Label("Student Name:", classes="cfg_label")
                yield Input(value=self.config_data.get("student_name", ""), placeholder="e.g. Max Mustermann", id="inp_cfg_name", classes="cfg_input")

                yield Label("Class:", classes="cfg_label")
                yield Input(value=self.config_data.get("student_class", ""), placeholder="e.g. 1AHIT", id="inp_cfg_class", classes="cfg_input")

                with Horizontal(id="cfg_group_row"):
                    yield Label("Group:", id="cfg_group_label")
                    yield Button(f"⚙️ Group: {self.current_group}", id="btn_cfg_group", variant="primary", tooltip="Click or press 'g' to toggle group")

                yield Label("🏫 School & Absence Details", classes="cfg_section_title")
                yield Label("Untis School Name:", classes="cfg_label")
                yield Input(value=self.config_data.get("untis_school", ""), placeholder="e.g. beispiel-schule", id="inp_cfg_school", classes="cfg_input")

                yield Label("Class Teacher:", classes="cfg_label")
                yield Input(value=self.config_data.get("teacher_name", ""), placeholder="e.g. Prof. Erika Musterlehrer", id="inp_cfg_teacher", classes="cfg_input")

                yield Label("School Address:", classes="cfg_label")
                yield Input(value=self.config_data.get("school_address", ""), placeholder="e.g. Musterstraße 1", id="inp_cfg_address", classes="cfg_input")

                yield Label("Postal Code & City:", classes="cfg_label")
                yield Input(value=self.config_data.get("school_district", ""), placeholder="e.g. A-1010 Wien", id="inp_cfg_district", classes="cfg_input")

            with Horizontal(id="cfg_buttons"):
                yield Button("💾 Save Configuration", id="btn_cfg_save", variant="success")
                yield Button("↩️ Back", id="btn_cfg_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("btn_cfg_save", "btn_ep_save"):
            self._save()
        elif bid in ("btn_cfg_cancel", "btn_ep_cancel"):
            self.dismiss(False)
        elif bid == "btn_cfg_group":
            self.action_toggle_group()

    def action_toggle_group(self) -> None:
        self.current_group = "Y" if self.current_group == "X" else "X"
        try:
            self.query_one("#btn_cfg_group", Button).label = f"⚙️ Group: {self.current_group}"
        except Exception:
            pass

    def _save(self) -> None:
        s_name = self.query_one("#inp_cfg_name", Input).value.strip()
        s_class = self.query_one("#inp_cfg_class", Input).value.strip()
        u_school = self.query_one("#inp_cfg_school", Input).value.strip()
        t_name = self.query_one("#inp_cfg_teacher", Input).value.strip()
        s_addr = self.query_one("#inp_cfg_address", Input).value.strip()
        s_dist = self.query_one("#inp_cfg_district", Input).value.strip()

        data = {
            "student_name": s_name,
            "student_class": s_class,
            "untis_group": self.current_group,
            "untis_school": u_school,
            "teacher_name": t_name,
            "school_address": s_addr,
            "school_district": s_dist,
        }
        save_full_school_config(data)
        self.app.notify("✓ School & student configuration saved!", severity="information")
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def key_escape(self) -> None:
        self.dismiss(False)


ExcuseProfileModal = SchoolConfigModal


class ExcuseLetterModal(ModalScreen[None]):
    """Modal for selecting absence days via checkboxes and generating the official PDF."""

    DEFAULT_CSS = """
    ExcuseLetterModal {
        align: center middle;
    }
    #excuse_dialog {
        width: 92%;
        max-width: 105;
        height: 85%;
        border: thick #89b4fa;
        background: #1e1e2e;
        padding: 1 2;
        layout: vertical;
    }
    #excuse_title {
        text-align: center;
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 0;
    }
    #excuse_profile_bar {
        height: 3;
        width: 100%;
        margin-bottom: 0;
        align: left middle;
    }
    #excuse_profile_info {
        width: 1fr;
        color: #a6adc8;
        content-align: left middle;
    }
    #excuse_actions_bar {
        height: 3;
        width: 100%;
        align: left middle;
        margin-bottom: 1;
    }
    #excuse_actions_bar Button {
        margin-right: 1;
        min-width: 12;
    }
    #excuse_table {
        height: 1fr;
        margin-bottom: 1;
    }
    #excuse_footer_bar {
        height: 3;
        width: 100%;
        align: left middle;
    }
    #excuse_footer_bar Button {
        margin-right: 1;
    }
    #excuse_count_lbl {
        width: 1fr;
        text-align: right;
        color: #fab387;
        text-style: bold;
        content-align: right middle;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_selected_row", "Toggle Row", show=False),
        Binding("a", "select_all", "Select All", show=False),
        Binding("o", "select_open", "Only Open", show=False),
        Binding("c", "clear_all", "Clear", show=False),
        Binding("p", "generate_pdf", "Generate PDF", show=False),
        Binding("escape", "cancel", "Back"),
    ]

    def __init__(self, summaries: Optional[List[SubjectAbsenceSummary]] = None):
        super().__init__()
        self.summaries = summaries or load_untis_cache()
        self.daily_absences: List[DailyAbsenceSummary] = get_daily_absence_summaries(self.summaries)
        self.profile = load_excuse_profile()
        open_dates = {d.date for d in self.daily_absences if any(w in d.status.lower() for w in ["offen", "open"])}
        if open_dates:
            self.selected_dates: Set[str] = set(open_dates)
        else:
            self.selected_dates = {d.date for d in self.daily_absences}

    def compose(self) -> ComposeResult:
        with Vertical(id="excuse_dialog"):
            yield Label("📝 WebUntis Excuse Letter Generator", id="excuse_title")

            with Horizontal(id="excuse_profile_bar"):
                yield Label("", id="excuse_profile_info")
                yield Button("⚙️ Edit Profile", id="btn_el_profile", variant="primary", tooltip="Edit Profile Settings")

            with Horizontal(id="excuse_actions_bar"):
                yield Button("☑️ Select All", id="btn_el_all", variant="default", tooltip="Select All")
                yield Button("⚡ Only Open", id="btn_el_open", variant="warning", tooltip="Only Open")
                yield Button("◻️ Clear All", id="btn_el_clear", variant="default", tooltip="Clear All")
                yield Label("", id="excuse_count_lbl")

            yield DataTable(id="excuse_table", cursor_type="row")

            with Horizontal(id="excuse_footer_bar"):
                yield Button("🖨️ Generate PDF", id="btn_el_generate", variant="success", tooltip="Generate & Open PDF")
                yield Button("↩️ Back", id="btn_el_back", variant="default", tooltip="Back")

    def on_mount(self) -> None:
        self._update_profile_label()
        dt = self.query_one("#excuse_table", DataTable)
        dt.cell_padding = 2
        dt.add_columns("Sel", "#", "Date", "Periods", "Duration", "Subjects", "Status")
        self.refresh_table()

    def _update_profile_label(self) -> None:
        info_lbl = self.query_one("#excuse_profile_info", Label)
        info_lbl.update(
            f"Student: [bold cyan]{self.profile.get('student_name', '')}[/] | "
            f"Class: [bold cyan]{self.profile.get('student_class', '')}[/] | "
            f"School: [bold cyan]{self.profile.get('school_address', '')}[/]"
        )

    def refresh_table(self) -> None:
        dt = self.query_one("#excuse_table", DataTable)
        dt.clear()

        total_sel_hours = 0
        total_sel_mins = 0

        for idx, d in enumerate(self.daily_absences, 1):
            is_sel = d.date in self.selected_dates
            sel_badge = Text("[X]", style="bold green") if is_sel else Text("[ ]", style="dim")
            if is_sel:
                total_sel_hours += d.school_hours
                total_sel_mins += d.school_hours * 50

            status_style = "green" if any(w in d.status.lower() for w in ["entschuldigt", "excused"]) else "yellow"
            subjs_str = ", ".join(d.subjects) if d.subjects else "-"

            dt.add_row(
                sel_badge,
                str(idx),
                Text(d.date_display, style="bold"),
                f"{d.school_hours} periods",
                d.duration_str,
                subjs_str,
                Text(d.status, style=status_style),
                height=2,
                key=d.date,
            )

        day_str = "day" if len(self.selected_dates) == 1 else "days"
        cnt_lbl = self.query_one("#excuse_count_lbl", Label)
        cnt_lbl.update(f"Selected: [bold green]{len(self.selected_dates)} {day_str}[/]")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key:
            d_str = event.row_key.value
            self._toggle_date(d_str)

    def _toggle_date(self, d_str: str) -> None:
        if d_str in self.selected_dates:
            self.selected_dates.remove(d_str)
        else:
            self.selected_dates.add(d_str)
        self.refresh_table()

    def action_toggle_selected_row(self) -> None:
        dt = self.query_one("#excuse_table", DataTable)
        if dt.cursor_row is not None and 0 <= dt.cursor_row < len(self.daily_absences):
            day = self.daily_absences[dt.cursor_row]
            self._toggle_date(day.date)

    def action_select_all(self) -> None:
        self.selected_dates = {d.date for d in self.daily_absences}
        self.refresh_table()

    def action_select_open(self) -> None:
        self.selected_dates = {d.date for d in self.daily_absences if any(w in d.status.lower() for w in ["offen", "open"])}
        self.refresh_table()

    def action_clear_all(self) -> None:
        self.selected_dates.clear()
        self.refresh_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_el_all":
            self.action_select_all()
        elif bid == "btn_el_open":
            self.action_select_open()
        elif bid == "btn_el_clear":
            self.action_clear_all()
        elif bid == "btn_el_profile":
            self.app.push_screen(ExcuseProfileModal(), self._on_profile_updated)
        elif bid == "btn_el_generate":
            self.action_generate_pdf()
        elif bid == "btn_el_back":
            self.dismiss()

    def _on_profile_updated(self, saved: bool) -> None:
        self.profile = load_excuse_profile()
        self._update_profile_label()

    def action_generate_pdf(self) -> None:
        if not self.selected_dates:
            self.app.notify("Please select at least one absence date with [X].", severity="warning")
            return

        selected_days = [d for d in self.daily_absences if d.date in self.selected_dates]
        selected_days.sort(key=lambda d: d.date)
        try:
            pdf_path = create_excuse_pdf(selected_days, profile=self.profile)
            opened = open_pdf_in_system_viewer(pdf_path)
            fn = os.path.basename(pdf_path)
            if opened:
                self.app.notify(f"✓ Excuse PDF generated and opened: {fn}", severity="information")
            else:
                self.app.notify(f"✓ Excuse PDF saved to Downloads: {fn}", severity="information")
        except Exception as e:
            self.app.notify(f"! Error generating PDF: {e}", severity="error")

    def action_cancel(self) -> None:
        self.dismiss()

    def key_escape(self) -> None:
        self.dismiss()


class AddExamModal(ModalScreen[Optional[UntisExam]]):
    """Dialog to manually add a custom test or exam."""

    DEFAULT_CSS = """
    AddExamModal {
        align: center middle;
    }
    #add_exam_dialog {
        width: 68;
        max-height: 90%;
        height: auto;
        border: thick #89b4fa;
        background: #1e1e2e;
        padding: 1 2;
    }
    #add_exam_title {
        text-align: center;
        text-style: bold;
        color: #89b4fa;
        margin-bottom: 1;
    }
    .add_exam_label {
        color: #cdd6f4;
        text-style: bold;
        margin-top: 1;
    }
    .add_exam_input {
        margin-bottom: 1;
        width: 100%;
    }
    #btn_add_exam_type {
        width: 100%;
        margin-bottom: 1;
    }
    #add_exam_status {
        color: #f38ba8;
        text-align: center;
        margin: 1 0;
        min-height: 1;
    }
    #add_exam_buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    #add_exam_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    TYPE_OPTIONS = [
        {"code": "TE", "name": "TEST", "label": "📘 Type: TEST", "display": "Test", "variant": "primary"},
        {"code": "SA", "name": "SA", "label": "📕 Type: SA", "display": "School Exam", "variant": "error"},
        {"code": "PR", "name": "PR", "label": "📙 Type: PR", "display": "Oral Exam", "variant": "warning"},
        {"code": "WDH", "name": "WDH", "label": "🟩 Type: WDH", "display": "Retest", "variant": "success"},
    ]

    def __init__(self):
        super().__init__()
        self.type_index: int = 0
        self.exam_type: str = self.TYPE_OPTIONS[0]["code"]
        self.auto_group: str = _load_untis_group() or "X"
        self._lookup_counter: int = 0
        self._last_looked_up: Optional[tuple[str, str]] = None
        self._auto_filled_time: bool = False
        self._auto_filled_teacher: bool = False
        self._auto_filled_room: bool = False
        self._resolving_natural_date: bool = False
        self._autofill_timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="add_exam_dialog"):
            yield Label("➕ Add Custom Test / Exam", id="add_exam_title")
            with VerticalScroll():
                yield Label("Exam Type:", classes="add_exam_label")
                initial_opt = self.TYPE_OPTIONS[self.type_index]
                yield Button(initial_opt["label"], id="btn_add_exam_type", variant=initial_opt["variant"])
                yield Label("Subject / Course:", classes="add_exam_label")
                yield Input(placeholder="e.g. E, AMEC, D, POS, SWP, SWP PM", id="inp_add_exam_subject", classes="add_exam_input")
                yield Label("Date (DD.MM.YYYY or YYYY-MM-DD):", classes="add_exam_label")
                yield Input(placeholder="e.g. 5.10. or 24.10.2026", id="inp_add_exam_date", classes="add_exam_input")
                yield Button("🔍 Autofill from Untis Timetable", id="btn_add_exam_autofill", variant="primary")
                yield Label("Time (Start - End):", classes="add_exam_label")
                yield Input(placeholder="Auto-filled from Untis or e.g. 08:00 - 08:50", id="inp_add_exam_time", classes="add_exam_input")
                yield Label("Teacher (optional):", classes="add_exam_label")
                yield Input(placeholder="Auto-filled from Untis or e.g. BIM, WAW", id="inp_add_exam_teacher", classes="add_exam_input")
                yield Label("Room (optional):", classes="add_exam_label")
                yield Input(placeholder="Auto-filled from Untis or e.g. C3.08", id="inp_add_exam_room", classes="add_exam_input")
                yield Label("Exam Topics / Stoff (optional):", classes="add_exam_label")
                yield Input(placeholder="e.g. Kapitel 1-3, SQL Queries", id="inp_add_exam_topics", classes="add_exam_input")
                yield Label("", id="add_exam_status")
            with Horizontal(id="add_exam_buttons"):
                yield Button("💾 Save [Enter]", id="btn_add_exam_save", variant="success")
                yield Button("↩️ Cancel [ESC]", id="btn_add_exam_cancel", variant="default")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "inp_add_exam_date" and not self._resolving_natural_date:
            resolved = resolve_natural_date_string(event.value, allow_short_abbr=False)
            if resolved != event.value:
                self._resolving_natural_date = True
                try:
                    event.input.value = resolved
                finally:
                    self._resolving_natural_date = False
                return

        if event.input.id in ["inp_add_exam_subject", "inp_add_exam_date"]:
            if getattr(self, "_autofill_timer", None) is not None:
                try:
                    self._autofill_timer.stop()
                except Exception:
                    pass
                self._autofill_timer = None
            try:
                self._autofill_timer = self.set_timer(1.0, lambda: self._trigger_untis_lookup(explicit=False))
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_add_exam_cancel":
            self.dismiss(None)
        elif bid == "btn_add_exam_save":
            self._save_exam()
        elif bid == "btn_add_exam_type":
            self._toggle_type()
        elif bid == "btn_add_exam_autofill":
            if getattr(self, "_autofill_timer", None) is not None:
                try:
                    self._autofill_timer.stop()
                except Exception:
                    pass
                self._autofill_timer = None
            self._trigger_untis_lookup(explicit=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._save_exam()

    def _toggle_type(self) -> None:
        self.type_index = (self.type_index + 1) % len(self.TYPE_OPTIONS)
        current = self.TYPE_OPTIONS[self.type_index]
        self.exam_type = current["code"]
        btn = self.query_one("#btn_add_exam_type", Button)
        btn.label = current["label"]
        btn.variant = current["variant"]

    def action_cancel(self) -> None:
        if getattr(self, "_autofill_timer", None) is not None:
            try:
                self._autofill_timer.stop()
            except Exception:
                pass
            self._autofill_timer = None
        self.dismiss(None)

    def key_escape(self) -> None:
        if getattr(self, "_autofill_timer", None) is not None:
            try:
                self._autofill_timer.stop()
            except Exception:
                pass
            self._autofill_timer = None
        self.dismiss(None)

    def _trigger_untis_lookup(self, explicit: bool = False) -> None:
        if getattr(self, "_autofill_timer", None) is not None:
            try:
                self._autofill_timer.stop()
            except Exception:
                pass
            self._autofill_timer = None
        try:
            subj = self.query_one("#inp_add_exam_subject", Input).value.strip()
            date_raw = self.query_one("#inp_add_exam_date", Input).value.strip()
        except Exception:
            return

        resolved_date = resolve_natural_date_string(date_raw, allow_short_abbr=True)
        if resolved_date != date_raw:
            self._resolving_natural_date = True
            try:
                self.query_one("#inp_add_exam_date", Input).value = resolved_date
            finally:
                self._resolving_natural_date = False
            date_raw = resolved_date

        if not subj or not date_raw:
            if explicit:
                self.query_one("#add_exam_status", Label).update("[yellow]Please enter Subject and Date first.[/yellow]")
            return

        parsed_date_info = self._parse_date_input(date_raw)
        if not parsed_date_info:
            if explicit:
                self.query_one("#add_exam_status", Label).update("[red]Invalid date format! Use e.g. 5.10. or 24.10.2026[/red]")
            return

        date_iso, date_display, _ = parsed_date_info
        if date_raw != date_display:
            self._resolving_natural_date = True
            try:
                self.query_one("#inp_add_exam_date", Input).value = date_display
            finally:
                self._resolving_natural_date = False

        if (subj, date_iso) == self._last_looked_up and not explicit:
            return

        self._lookup_counter += 1
        current_req = self._lookup_counter

        if explicit:
            self.query_one("#add_exam_status", Label).update("[yellow]Checking WebUntis timetable...[/yellow]")

        app = self.app

        def worker():
            data = lookup_untis_lesson_details(date_iso, subj, preferred_group=self.auto_group)
            if self._lookup_counter != current_req:
                return

            def update_ui():
                self._last_looked_up = (subj, date_iso)
                if data:
                    time_inp = self.query_one("#inp_add_exam_time", Input)
                    teacher_inp = self.query_one("#inp_add_exam_teacher", Input)
                    room_inp = self.query_one("#inp_add_exam_room", Input)

                    if not time_inp.value or self._auto_filled_time:
                        time_inp.value = data["time_str"]
                        self._auto_filled_time = True
                    if not teacher_inp.value or self._auto_filled_teacher:
                        teacher_inp.value = data["teacher"]
                        self._auto_filled_teacher = True
                    if not room_inp.value or self._auto_filled_room:
                        room_inp.value = data["room"]
                        self._auto_filled_room = True

                    if data.get("group"):
                        self.auto_group = data["group"]

                    self.query_one("#add_exam_status", Label).update(
                        f"[green]✓ Untis: {data['time_str']} | {data['teacher']} | {data['room']}[/green]"
                    )
                    app.notify(
                        f"✓ Untis: {data['time_str']} | {data['teacher']} | {data['room']}",
                        severity="information",
                    )
                elif explicit:
                    self.query_one("#add_exam_status", Label).update(
                        f"[yellow]No Untis lesson found for '{subj}' on {date_display}.[/yellow]"
                    )
            app.call_from_thread(update_ui)

        threading.Thread(target=worker, daemon=True, name="UntisAutofillWorker").start()

    def _save_exam(self) -> None:
        if getattr(self, "_autofill_timer", None) is not None:
            try:
                self._autofill_timer.stop()
            except Exception:
                pass
            self._autofill_timer = None
        subj = self.query_one("#inp_add_exam_subject", Input).value.strip()
        date_inp = self.query_one("#inp_add_exam_date", Input)
        date_raw = date_inp.value.strip()
        resolved_date = resolve_natural_date_string(date_raw, allow_short_abbr=True)
        if resolved_date != date_raw:
            self._resolving_natural_date = True
            try:
                date_inp.value = resolved_date
            finally:
                self._resolving_natural_date = False
            date_raw = resolved_date
        time_raw = self.query_one("#inp_add_exam_time", Input).value.strip()
        teacher_raw = self.query_one("#inp_add_exam_teacher", Input).value.strip()
        room_raw = self.query_one("#inp_add_exam_room", Input).value.strip()
        topics_raw = self.query_one("#inp_add_exam_topics", Input).value.strip()

        if not subj:
            self.query_one("#add_exam_status", Label).update("[red]Please enter a subject.[/red]")
            return
        if not date_raw:
            self.query_one("#add_exam_status", Label).update("[red]Please enter an exam date.[/red]")
            return

        parsed_date_info = self._parse_date_input(date_raw)
        if not parsed_date_info:
            self.query_one("#add_exam_status", Label).update("[red]Invalid date format! Use e.g. 24.10.2026 or 24.10.[/red]")
            return

        date_iso, date_display, days_until = parsed_date_info
        start_t, end_t = self._parse_time_input(time_raw)

        from config import normalize_subject_name
        clean_subj = normalize_subject_name(subj)
        group = self.auto_group or _load_untis_group() or "X"
        teachers = [t.strip() for t in teacher_raw.split(",") if t.strip()] if teacher_raw else []
        rooms = [r.strip() for r in room_raw.split(",") if r.strip()] if room_raw else []
        current_opt = self.TYPE_OPTIONS[self.type_index]
        exam_type_display = current_opt["display"]

        exam_id = f"custom_{date_iso.replace('-', '')}_{int(time.time() * 1000) % 1000000}_{clean_subj.lower().replace(' ', '_')}"

        new_exam = UntisExam(
            id=exam_id,
            exam_type=self.exam_type,
            exam_type_display=exam_type_display,
            subject=clean_subj,
            name=clean_subj,
            text=topics_raw if topics_raw else exam_type_display,
            date=date_iso,
            date_display=date_display,
            start_time=start_t,
            end_time=end_t,
            teachers=teachers,
            rooms=rooms,
            custom_topics=topics_raw,
            is_past=days_until < 0,
            days_until=days_until,
            url="",
            group=group,
            is_custom=True,
        )

        save_custom_exam(new_exam)
        self.dismiss(new_exam)

    _parse_date_input = staticmethod(parse_flexible_date_input)

    @staticmethod
    def _parse_time_input(val: str) -> tuple[str, str]:
        val = val.strip()
        if not val:
            return "08:00", "08:50"
        if "-" in val:
            parts = val.split("-", 1)
            s = parts[0].strip()
            e = parts[1].strip()
            return s, e
        parts = val.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            start_str = f"{h:02d}:{m:02d}"
            end_m = m + 50
            end_h = h + (end_m // 60)
            end_m = end_m % 60
            end_str = f"{end_h:02d}:{end_m:02d}"
            return start_str, end_str
        except Exception:
            return "08:00", "08:50"


class ExamDetailModal(ModalScreen[bool]):
    """Modal showing all details of an exam and allowing editing of custom topics/notes."""

    DEFAULT_CSS = """
    ExamDetailModal {
        align: center middle;
    }
    #exam_detail_dialog {
        width: 82;
        max-width: 95%;
        height: auto;
        max-height: 88%;
        border: thick #cba6f7;
        background: #1e1e2e;
        padding: 1 2;
        layout: vertical;
    }
    #exam_detail_title {
        text-align: center;
        text-style: bold;
        color: #cba6f7;
        margin-bottom: 1;
    }
    #exam_detail_meta {
        height: auto;
        background: #181825;
        border: solid #313244;
        padding: 1;
        margin-bottom: 1;
    }
    .exam_meta_row {
        color: #cdd6f4;
        margin-bottom: 0;
    }
    .exam_section_label {
        color: #89b4fa;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }
    #inp_exam_topics {
        height: 7;
        margin-bottom: 1;
        border: solid #45475a;
        background: #11111b;
    }
    #exam_detail_buttons {
        height: 3;
        width: 100%;
        align: center middle;
    }
    #exam_detail_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("o", "open_browser", "Browser"),
        Binding("d", "delete_exam", "Delete Exam"),
        Binding("escape", "cancel", "Back"),
        Binding("ctrl+s", "save_topics", "Save Notes"),
    ]

    def __init__(self, exam: UntisExam):
        super().__init__()
        self.exam = exam

    def compose(self) -> ComposeResult:
        with Vertical(id="exam_detail_dialog"):
            if self.exam.exam_type == "SA":
                badge_icon = "📕"
            elif self.exam.exam_type in ["TE", "TEST"]:
                badge_icon = "📘"
            elif self.exam.exam_type == "PR":
                badge_icon = "📙"
            elif self.exam.exam_type == "WDH":
                badge_icon = "🟩"
            else:
                badge_icon = "🟣"
            yield Label(f"{badge_icon} {self.exam.exam_type_display}: {self.exam.subject}", id="exam_detail_title")

            with Vertical(id="exam_detail_meta"):
                try:
                    dt = datetime.datetime.strptime(self.exam.date, "%Y-%m-%d").date()
                    weekdays = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
                    weekday_str = weekdays[dt.weekday()]
                except Exception:
                    weekday_str = ""
                if any(self.exam.date_display.startswith(w) for w in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Mo", "Tu", "We", "Th", "Fr", "Sa", "Su", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag", "Di", "Mi", "Do", "So"]):
                    full_date_str = self.exam.date_display
                else:
                    full_date_str = f"{weekday_str}, {self.exam.date_display}" if weekday_str else self.exam.date_display

                yield Label(f"📅 Date & Time:  [bold white]{full_date_str}[/] ({self.exam.start_time} - {self.exam.end_time})", classes="exam_meta_row")
                yield Label(f"⏳ Countdown:    [bold yellow]{self.exam.countdown_display}[/]", classes="exam_meta_row")
                teachers_str = ", ".join(self.exam.teachers) if self.exam.teachers else "-"
                yield Label(f"👨‍🏫 Teacher:      [bold white]{escape(teachers_str)}[/]", classes="exam_meta_row")
                rooms_str = ", ".join(self.exam.rooms) if self.exam.rooms else "-"
                yield Label(f"📍 Room:         [bold white]{escape(rooms_str)}[/]", classes="exam_meta_row")
                if self.exam.name and self.exam.name != self.exam.subject:
                    yield Label(f"🏷️ Untis Name:   [white]{escape(self.exam.name)}[/]", classes="exam_meta_row")
                if self.exam.text:
                    yield Label(f"ℹ️ Untis Note:   [white]{escape(self.exam.text)}[/]", classes="exam_meta_row")

            yield Label("✏️ Exam Topics / Notes:", classes="exam_section_label")
            ta = TextArea(self.exam.custom_topics or "", id="inp_exam_topics", soft_wrap=True)
            yield ta

            is_custom = getattr(self.exam, "is_custom", False) or str(self.exam.id).startswith("custom_")
            with Horizontal(id="exam_detail_buttons"):
                if is_custom:
                    yield Button("🗑️ Delete [D]", id="btn_exam_delete", variant="error")
                else:
                    yield Button("🌐 Browser [O]", id="btn_exam_browser", variant="primary")
                yield Button("💾 Save Notes [Ctrl+S]", id="btn_save_exam_topics", variant="success")
                yield Button("↩️ Back [ESC]", id="btn_cancel_exam_detail", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_exam_browser":
            self.action_open_browser()
        elif event.button.id == "btn_exam_delete":
            self.action_delete_exam()
        elif event.button.id == "btn_save_exam_topics":
            self.action_save_topics()
        elif event.button.id == "btn_cancel_exam_detail":
            self.dismiss(False)

    def action_open_browser(self) -> None:
        is_custom = getattr(self.exam, "is_custom", False) or str(self.exam.id).startswith("custom_")
        if is_custom:
            self.app.notify("No browser link for custom tests.", severity="warning")
            return
        import webbrowser
        from untis_service import get_exam_web_url
        url = get_exam_web_url(self.exam)
        if url:
            webbrowser.open(url)
            self.app.notify(f"Opening '{self.exam.subject}' test in browser...", severity="information")
        else:
            self.app.notify("No WebUntis URL available for this test.", severity="warning")

    def action_delete_exam(self) -> None:
        is_custom = getattr(self.exam, "is_custom", False) or str(self.exam.id).startswith("custom_")
        if not is_custom:
            self.app.notify("Only custom tests can be deleted.", severity="warning")
            return
        delete_custom_exam(self.exam.id)
        self.app.notify(f"🗑️ Test '{self.exam.subject}' deleted.", severity="information")
        self.dismiss(True)

    def action_save_topics(self) -> None:
        new_topic = self.query_one("#inp_exam_topics", TextArea).text.strip()
        save_single_exam_note(self.exam.id, new_topic)
        self.exam.custom_topics = new_topic
        if getattr(self.exam, "is_custom", False) or str(self.exam.id).startswith("custom_"):
            save_custom_exam(self.exam)
        self.app.notify("✓ Exam notes saved successfully!", severity="information")
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def key_escape(self) -> None:
        self.dismiss(False)


class ExamsScreen(Screen):
    """Full-screen view displaying all WebUntis tests, exams and assignments."""

    DEFAULT_CSS = """
    ExamsScreen {
        layout: vertical;
    }
    #exams_header {
        dock: top;
        height: 3;
        padding: 0 1;
        align: left middle;
    }
    #exams_title {
        width: auto;
        text-style: bold;
        color: #89b4fa;
    }
    #exams_sub_info {
        width: 1fr;
        content-align: right middle;
        color: #a6adc8;
    }
    #exams_table_container {
        height: 1fr;
        padding: 0 1;
    }
    #exams_table {
        height: 1fr;
    }
    #exams_button_bar {
        dock: bottom;
        height: 3;
        width: 100%;
        align: left middle;
        padding: 0 1;
        overflow-x: hidden;
        overflow-y: hidden;
    }
    #exams_left_buttons {
        width: 1fr;
        height: 100%;
        align: left middle;
    }
    #exams_button_bar Button {
        margin: 0 1;
        min-width: 4;
        height: 100%;
        content-align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Back to Tasks"),
        Binding("t", "dismiss_screen", "Back to Tasks"),
        Binding("a", "add_exam", "Add Test"),
        Binding("v", "toggle_past_exams", "Toggle Past Exams"),
        Binding("g", "toggle_group", "Toggle Group"),
        Binding("r", "sync_exams", "Sync Untis"),
    ]

    def __init__(self):
        super().__init__()
        self.show_past: bool = False
        full_cfg = load_full_school_config()
        self.current_group: str = (full_cfg.get("untis_group") or "X").strip().upper()
        self.current_class: str = (full_cfg.get("student_class") or "1AHIT").strip()
        self.exams: List[UntisExam] = []
        self._is_syncing: bool = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="exams_header"):
            yield Label("📝 WebUntis Tests & Exams", id="exams_title")
            yield Label("", id="exams_sub_info")

        with Vertical(id="exams_table_container"):
            dt = DataTable(id="exams_table", cursor_type="row")
            yield dt

        with Horizontal(id="exams_button_bar"):
            with Horizontal(id="exams_left_buttons"):
                yield Button("➕ Add [A]", id="btn_exams_add", variant="success", tooltip="Add Custom Test [A]")
                yield Button("🔄 Sync Untis", id="btn_exams_sync", variant="default", tooltip="Sync Untis [R]")
                yield Button("📅 Past Exams: OFF", id="btn_toggle_past_exams", variant="primary", tooltip="Toggle Past [V]")
            yield Button("↩️ Back", id="btn_exams_back", variant="default", tooltip="Back to tasks [T/Esc]")

    def on_mount(self) -> None:
        dt = self.query_one("#exams_table", DataTable)
        dt.cell_padding = 2
        dt.add_columns("#", "Type", "Subject", "Date", "Time", "Topic / Notes", "Teacher", "Room", "Countdown")
        self.reload_data()

    def reload_data(self) -> None:
        full_cfg = load_full_school_config()
        self.current_group = (full_cfg.get("untis_group") or "X").strip().upper()
        self.current_class = (full_cfg.get("student_class") or "1AHIT").strip()
        try:
            btn = self.query_one("#btn_exams_group", Button)
            btn.label = f"⚙️ Group: {self.current_group}"
        except Exception:
            pass
        self.exams = load_untis_exams_cache()
        self._populate_table()
        if not self.exams:
            self.action_sync_exams()

    def _populate_table(self) -> None:
        dt = self.query_one("#exams_table", DataTable)
        dt.clear()

        matching_exams = [e for e in self.exams if not e.group or e.group.upper() == self.current_group]
        visible_exams = [e for e in matching_exams if self.show_past or not e.is_past or e.days_until == 0]
        visible_exams.sort(key=lambda x: (x.date, x.start_time))
        total_cnt = len(matching_exams)
        upcoming_cnt = len([e for e in matching_exams if not e.is_past or e.days_until == 0])
        past_cnt = total_cnt - upcoming_cnt

        info_lbl = self.query_one("#exams_sub_info", Label)
        info_lbl.update(
            f"Total: [bold white]{total_cnt}[/]  |  "
            f"Upcoming: [bold cyan]{upcoming_cnt}[/]  |  "
            f"Past: [bold white]{past_cnt}[/]  |  "
            f"Class: {self.current_class}  |  "
            f"Group: {self.current_group}"
        )

        btn_toggle = self.query_one("#btn_toggle_past_exams", Button)
        if self.show_past:
            btn_toggle.label = "📅 Past Exams: ON"
            btn_toggle.variant = "success"
        else:
            btn_toggle.label = "📅 Past Exams: OFF"
            btn_toggle.variant = "primary"

        # Dynamische Breitenberechnung: Limitiert die Spalte Topic / Notes so,
        # dass alle Spalten (#, Type, Subject, Date, Time, Topic, Teacher, Room, Countdown)
        # sauber Platz haben und horizontales Scrollen vermieden wird.
        term_w = self.size.width if (self.size and self.size.width > 0) else 125
        max_topic_len = max(24, min(36, term_w - 94))

        for idx, ex in enumerate(visible_exams, start=1):
            if ex.exam_type == "SA":
                type_styled = Text("SA", style="bold red")
            elif ex.exam_type in ["TE", "TEST"]:
                type_styled = Text("TEST", style="bold cyan")
            elif ex.exam_type == "PR":
                type_styled = Text("PR", style="bold yellow")
            elif ex.exam_type == "WDH":
                type_styled = Text("WDH", style="bold green")
            else:
                type_styled = Text(ex.exam_type or "EXAM", style="bold magenta")

            # Dim row if past
            dim_style = "dim" if ex.is_past and ex.days_until < 0 else ""

            subj_text = Text(ex.subject, style=f"bold white {dim_style}".strip())

            try:
                dt_obj = datetime.datetime.strptime(ex.date, "%Y-%m-%d").date()
                weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
                wk = weekdays[dt_obj.weekday()]
                date_str = f"{wk}, {dt_obj.day:02d}.{dt_obj.month:02d}."
            except Exception:
                date_str = ex.date_display
            date_styled = Text(date_str, style=f"white {dim_style}".strip())

            time_str = f"{ex.start_time} - {ex.end_time}"
            time_styled = Text(time_str, style=f"dim {dim_style}".strip())

            # Topic / Notes: Einzeilig halten (keine 2. Zeile), mit "..." kürzen
            raw_text = ""
            is_custom = False
            text_style = f"white {dim_style}".strip()

            if ex.custom_topics and ex.custom_topics.strip():
                raw_text = ex.custom_topics.strip()
                is_custom = True
                text_style = f"bold green {dim_style}".strip()
            elif ex.text and ex.text.strip():
                raw_text = ex.text.strip()
                text_style = f"white {dim_style}".strip()
            elif ex.name and ex.name.strip() and ex.name.strip() != ex.subject.strip():
                raw_text = ex.name.strip()
                text_style = f"white {dim_style}".strip()

            # Alle Zeilenumbrüche und überschüssige Leerzeichen entfernen, damit niemals eine 2. Zeile entsteht
            clean_text = " ".join(raw_text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").split())

            if clean_text:
                prefix = "✏️ " if is_custom else ""
                prefix_len = 3 if is_custom else 0
                avail_chars = max(10, max_topic_len - prefix_len)

                if len(clean_text) > avail_chars:
                    display_text = clean_text[: max(0, avail_chars - 3)].rstrip() + "..."
                else:
                    display_text = clean_text

                topic_str = f"{prefix}{display_text}"
                topic_styled = Text(topic_str, style=text_style, no_wrap=True, overflow="ellipsis")
            else:
                topic_styled = Text("- none -", style=f"italic dim {dim_style}".strip(), no_wrap=True)

            teachers_str = ", ".join(ex.teachers) if ex.teachers else "-"
            teachers_styled = Text(teachers_str, style=f"white {dim_style}".strip())

            rooms_str = ", ".join(ex.rooms) if ex.rooms else "-"
            rooms_styled = Text(rooms_str, style=f"white {dim_style}".strip())

            if ex.is_past and ex.days_until < 0:
                cd_styled = Text(ex.countdown_display, style="dim")
            elif ex.days_until == 0:
                cd_styled = Text(ex.countdown_display, style="bold red")
            elif ex.days_until <= 3:
                cd_styled = Text(ex.countdown_display, style="bold yellow")
            else:
                cd_styled = Text(ex.countdown_display, style="bold cyan")

            dt.add_row(
                Text(str(idx), style="dim"),
                type_styled,
                subj_text,
                date_styled,
                time_styled,
                topic_styled,
                teachers_styled,
                rooms_styled,
                cd_styled,
                key=ex.id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        ex = next((e for e in self.exams if e.id == row_key), None)
        if ex:
            self._open_exam_detail(ex)

    def _open_exam_detail(self, exam: UntisExam) -> None:
        def on_saved(saved: bool) -> None:
            if saved:
                self.reload_data()
        self.app.push_screen(ExamDetailModal(exam), on_saved)

    def on_resize(self, event: Resize) -> None:
        if self.is_mounted and hasattr(self, "exams") and self.exams:
            self._populate_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_exams_add":
            self.action_add_exam()
        elif bid == "btn_toggle_past_exams":
            self.action_toggle_past_exams()
        elif bid == "btn_exams_group":
            self.action_toggle_group()
        elif bid == "btn_exams_sync":
            self.action_sync_exams()
        elif bid == "btn_exams_back":
            self.action_dismiss_screen()

    def action_add_exam(self) -> None:
        def on_added(exam: Optional[UntisExam]) -> None:
            if exam:
                self.reload_data()
                self.app.notify(f"✓ Test for '{exam.subject}' added!", severity="information")
        self.app.push_screen(AddExamModal(), on_added)

    def action_toggle_group(self) -> None:
        new_grp = "Y" if self.current_group == "X" else "X"
        self.current_group = new_grp
        save_untis_group(new_grp)
        try:
            self.query_one("#btn_exams_group", Button).label = f"⚙️ Group: {new_grp}"
        except Exception:
            pass
        self._populate_table()
        self.app.notify(f"WebUntis group set to {new_grp}.", severity="information")

    def action_toggle_past_exams(self) -> None:
        self.show_past = not self.show_past
        self._populate_table()

    def action_sync_exams(self) -> None:
        if self._is_syncing:
            return
        self._is_syncing = True
        self.app.notify("🔄 Synchronizing WebUntis exams...", severity="information")
        try:
            self.query_one("#btn_exams_sync", Button).disabled = True
        except Exception:
            pass

        def _bg_sync():
            ok, msg, _ = sync_untis_data()
            def _done():
                self._is_syncing = False
                try:
                    self.query_one("#btn_exams_sync", Button).disabled = False
                except Exception:
                    pass
                self.reload_data()
                try:
                    self.app.notify("✓ WebUntis exams updated!", severity="information")
                except Exception:
                    pass
            try:
                self.app.call_from_thread(_done)
            except Exception:
                pass

        threading.Thread(target=_bg_sync, daemon=True, name="ExamsSyncWorker").start()

    def action_dismiss_screen(self) -> None:
        self.dismiss()


ExamsModal = ExamsScreen


class SyncSpinner(Widget):
    """Animated sync spinner in the top right corner during background sync."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    DEFAULT_CSS = """
    SyncSpinner {
        width: 4;
        height: 1;
        content-align: right middle;
        text-align: right;
        display: none;
    }
    SyncSpinner.-active {
        display: block;
    }
    """

    active: reactive[bool] = reactive(False)
    frame_idx: reactive[int] = reactive(0)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._timer = None
        self.tooltip = "Syncing assignments..."

    def watch_active(self, active: bool) -> None:
        self.set_class(active, "-active")
        if active:
            if self._timer is None:
                self._timer = self.set_interval(0.08, self._advance_frame)
            else:
                self._timer.resume()
        else:
            if self._timer is not None:
                self._timer.pause()
            self.refresh()

    def _advance_frame(self) -> None:
        if self.active:
            self.frame_idx = (self.frame_idx + 1) % len(self.FRAMES)

    def render(self) -> RenderResult:
        if not self.active:
            return ""
        frame = self.FRAMES[self.frame_idx]
        return Text.from_markup(f"[bold #a6e3a1]{frame}[/] ")

    def on_unmount(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None


class AufgabenDetectorApp(App):
    """
    Hauptanwendung des Aufgaben-Detectors mit moderner Terminal-TUI und Maus-Buttons.
    """

    TITLE = "TASKS"
    SUB_TITLE = "School Assignment Hub"

    CSS = """
    #info_bar {
        dock: top;
        height: 3;
        padding: 0 1;
        align: center middle;
    }

    #info_stats {
        width: 1fr;
        text-style: bold;
    }

    #tasks_table {
        height: 1fr;
    }

    #button_bar {
        dock: bottom;
        height: 3;
        width: 100%;
        padding: 0 1;
        overflow-x: hidden;
        overflow-y: hidden;
        align: left middle;
    }

    #main_center_buttons {
        width: 1fr;
        height: 100%;
        align: center middle;
    }

    #button_bar Button {
        margin: 0 1;
        min-width: 4;
        height: 100%;
        content-align: center middle;
    }

    /* Toast Notification Styling (Fix für Kontrast / Theme-Unabhängigkeit) */
    Toast {
        background: #1e1e2e;
        color: #cdd6f4;
        border-left: outer #89b4fa;
    }
    Toast:ansi {
        background: #1e1e2e;
        color: #cdd6f4;
    }
    Toast .toast--title {
        color: #89b4fa;
        text-style: bold;
    }
    Toast.-information {
        border-left: outer #89b4fa;
        background: #1e1e2e;
        color: #cdd6f4;
    }
    Toast.-information .toast--title {
        color: #89dceb;
    }
    Toast.-warning {
        border-left: outer #f9e2af;
        background: #1e1e2e;
        color: #cdd6f4;
    }
    Toast.-warning .toast--title {
        color: #f9e2af;
    }
    Toast.-error {
        border-left: outer #f38ba8;
        background: #1e1e2e;
        color: #cdd6f4;
    }
    Toast.-error .toast--title {
        color: #f38ba8;
    }
    """

    BINDINGS = [
        Binding("a", "add_task", "Add Task"),
        Binding("e", "show_exams", "Tests & Exams"),
        Binding("backspace", "open_courses_palette", "Open Course", show=False),
        Binding("slash", "open_courses_palette", "Open Course", show=False),
        Binding("f", "open_filter_menu", "Filter"),
        Binding("s", "filter_status", "Status Filter", show=False),
        Binding("r", "sync_tasks", "Synchronize"),
        Binding("u", "show_absences", "Absences"),
        Binding("g", "show_trash", "Trash"),
        Binding("l", "login_menu", "Login"),
        Binding("o", "open_settings", "Settings"),
        Binding("p", "filter_platform", "Platform", show=False),
        Binding("d", "filter_timeframe", "Max Duration Filter", show=False),
        Binding("t", "change_theme", "Theme", show=False),
        Binding("ctrl+p", "change_theme", "Theme / Palette", show=False),
        Binding("m", "setup_moodle", "Moodle Setup", show=False),
        Binding("q", "quit_app", "Quit"),
        # Direct selection 1-9
        Binding("1", "select_task(1)", "Task 1", show=False),
        Binding("2", "select_task(2)", "Task 2", show=False),
        Binding("3", "select_task(3)", "Task 3", show=False),
        Binding("4", "select_task(4)", "Task 4", show=False),
        Binding("5", "select_task(5)", "Task 5", show=False),
        Binding("6", "select_task(6)", "Task 6", show=False),
        Binding("7", "select_task(7)", "Task 7", show=False),
        Binding("8", "select_task(8)", "Task 8", show=False),
        Binding("9", "select_task(9)", "Task 9", show=False),
    ]

    NOTIFICATION_TIMEOUT: float = 3.0

    def notify(
        self,
        message: str,
        *,
        title: str = "",
        severity: str = "information",
        timeout: Optional[float] = None,
        markup: bool = True,
    ) -> None:
        """Alle Benachrichtigungen rechts unten generell immer 3s anzeigen."""
        super().notify(
            message,
            title=title,
            severity=severity,  # type: ignore
            timeout=3.0 if timeout is None else timeout,
            markup=markup,
        )

    def __init__(self, mgr: Optional[TaskManager] = None, sync_on_startup: Optional[bool] = None):
        super().__init__()
        self.mgr = mgr or TaskManager(autostart_prefetch=True)
        self.sync_on_startup = sync_on_startup
        self.platform_filter = "all"
        self.status_filter = "open_only"
        self.subject_filter = "all"
        self.timeframe_filter = "2_weeks"
        self.current_tasks: List[Task] = []
        self._is_syncing = False
        self._stop_mouse_listener = threading.Event()
        self._mouse_listener_thread: Optional[threading.Thread] = None
        self._terminal_hwnd: Optional[int] = None

        # Theme initialisieren & nur die 5 wichtigsten Themes behalten
        saved_theme = load_saved_theme()
        if saved_theme in ALLOWED_THEMES:
            self.theme = saved_theme
        else:
            self.theme = DEFAULT_THEME

        for t in list(self.available_themes.keys()):
            if t not in ALLOWED_THEMES:
                self.unregister_theme(t)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="info_bar"):
            yield Label("Loading statistics...", id="info_stats")
            yield SyncSpinner(id="sync_spinner")
        dt = DataTable(id="tasks_table", cursor_type="row")
        yield dt
        with Horizontal(id="button_bar"):
            yield Button("📅 Absences", id="btn_main_absences", variant="primary", tooltip="Untis absences [U]")
            yield Button("📝 Tests", id="btn_main_exams", variant="primary", tooltip="Exams & tests [E]")
            with Horizontal(id="main_center_buttons"):
                yield Button("➕ Add", id="btn_main_add", variant="success", tooltip="Add homework [A]")
                yield Button("🔄 Sync", id="btn_main_sync", variant="success", tooltip="Synchronize assignments [R]")
                yield Button("🔍 Filter", id="btn_main_filter", variant="primary", tooltip="Filter assignments [F]")
                yield Button("⚙️ Settings", id="btn_main_settings", variant="default", tooltip="Settings & theme [O]")
            yield Button("❌ Exit", id="btn_main_quit", variant="error", tooltip="Exit [Q]")


    def on_mount(self) -> None:
        dt = self.query_one(DataTable)
        dt.cell_padding = 2
        dt.add_columns("#", "Platform", "Subject", "Assignment", "Due Date", "Status", "Teacher")

        # Gecachte Aufgaben sofort anzeigen
        self.refresh_table()

        # Beim Start automatisch immer wie beim Klick auf den Sync-Button synchronisieren
        should_sync = self.sync_on_startup if self.sync_on_startup is not None else (not self.is_headless)
        if should_sync:
            self.action_sync_tasks()

        # Starte Hintergrund-Thread für Maus-Zurück-Taste (Seitentaste XBUTTON1 / "Hinten")
        self._terminal_hwnd = get_terminal_window_hwnd() or _CACHED_TERMINAL_HWND
        if sys.platform == "win32" and not self.is_headless:
            self._start_mouse_back_listener()

        # Sicherstellen, dass das Terminal-Layout beim Start sauber synchronisiert ist
        self.call_after_refresh(self._sync_initial_viewport)

    def _sync_initial_viewport(self) -> None:
        """
        Stellt sicher, dass das initiale Layout nach dem ersten Rendern stabil steht.
        Postet KEINE künstlichen Resize-Events in die Event-Queue, um ConPTY-Desynchronisationen
        und Render-Glitches (wiederholte Zeilen, Geistertext) vollständig zu verhindern.
        """
        if self.is_headless:
            return
        try:
            self.refresh(layout=True)
        except Exception:
            pass

    def on_resize(self, event: Resize) -> None:
        """Passt Spaltenbreiten bei echten Terminalgrößenänderungen dynamisch an."""
        if self.is_mounted and hasattr(self, "current_tasks") and self.current_tasks:
            self.refresh_table()

    def refresh_table(self) -> None:
        """Aktualisiert die Aufgaben-Tabelle und die Statusleiste."""
        try:
            dt = self.query_one(DataTable)
        except Exception:
            return
        if not dt.columns:
            return

        saved_row = dt.cursor_row
        dt.clear()

        # Gefilterte Aufgaben laden
        subj = None if self.subject_filter == "all" else self.subject_filter
        self.current_tasks = self.mgr.get_filtered_tasks(
            platform_filter=self.platform_filter,
            status_filter=self.status_filter,
            subject_filter=subj,
            timeframe_filter=self.timeframe_filter,
        )

        # Dynamische Breitenberechnung: Verhindert störendes horizontales Scrollen
        term_w = self.size.width if (self.size and self.size.width > 0) else 136
        max_title_len = max(23, term_w - 94)  # 12 Spalten dünner (zuvor term_w - 82, min 35)
        max_course_len = 22
        seen_row_keys = set()

        for idx, t in enumerate(self.current_tasks, 1):
            is_done = t.is_completed
            is_over = t.is_overdue

            # Platform badge
            if is_done:
                if t.platform == "moodle":
                    plat_badge = Text("🟧 Moodle", style="dim")
                elif t.platform == "teams":
                    plat_badge = Text("🟦 Teams", style="dim")
                else:
                    plat_badge = Text("✏️ Manual", style="dim")
            else:
                if t.platform == "moodle":
                    plat_badge = Text("🟧 Moodle", style="bold orange3")
                elif t.platform == "teams":
                    plat_badge = Text("🟦 Teams", style="bold dodger_blue1")
                else:
                    plat_badge = Text("✏️ Manual", style="bold green")

            # Subject styling with smart truncation
            course_text = t.course
            if len(course_text) > max_course_len:
                course_text = course_text[:max_course_len - 1] + "…"
            subj_styled = Text(course_text, style="dim cyan" if is_done else "bold cyan")

            # Status styling & normalization
            disp_txt = format_status_english(t)

            st_lower = t.status.lower()
            if is_done or disp_txt == "Completed":
                status_styled = Text(f"✓ {disp_txt}", style="dim green")
            elif is_over or disp_txt == "Overdue" or "ueberfaellig" in st_lower or "überfällig" in st_lower or "overdue" in st_lower:
                status_styled = Text(f"⚠ {disp_txt}", style="bold red")
            elif disp_txt == "Open":
                status_styled = Text("Open", style="bold yellow")
            else:
                status_styled = Text(disp_txt, style="bold yellow")

            # Title styling (Open ones stand out immediately) with smart dynamic truncation
            title_text = t.title
            if len(title_text) > max_title_len:
                title_text = title_text[:max_title_len - 1] + "…"
            if is_done:
                title_styled = Text(title_text, style="dim white")
            elif is_over:
                title_styled = Text(title_text, style="bold red")
            else:
                title_styled = Text(title_text, style="bold white")

            # Due date styling
            due_styled = Text(t.due_date_str)
            due_lower = t.due_date_str.lower()
            if is_done:
                due_styled.stylize("dim")
            elif is_over or "überfällig" in due_lower or "overdue" in due_lower or "vor " in due_lower:
                due_styled.stylize("bold red")
            elif "heute" in due_lower or "today" in due_lower:
                due_styled.stylize("bold yellow")
            elif "morgen" in due_lower or "tomorrow" in due_lower:
                due_styled.stylize("bold cyan")

            idx_styled = Text(str(idx), style="dim" if is_done else "bold")
            teacher_str = t.teacher if t.teacher and t.teacher != "-" else ""
            teacher_styled = Text(teacher_str, style="dim" if is_done else "white")

            row_key = t.id if t.id not in seen_row_keys else f"{t.id}_{idx}"
            seen_row_keys.add(row_key)

            dt.add_row(
                idx_styled,
                plat_badge,
                subj_styled,
                title_styled,
                due_styled,
                status_styled,
                teacher_styled,
                height=2,
                key=row_key,
            )

        if saved_row is not None and 0 <= saved_row < len(self.current_tasks):
            try:
                dt.move_cursor(row=saved_row)
            except Exception:
                pass

        # Update statistics: Links oben immer exakt so viele anzeigen, wie gerade sichtbar sind
        visible_tasks = getattr(self, "current_tasks", []) or []
        moodle_cnt = len([t for t in visible_tasks if t.platform == "moodle"])
        teams_cnt = len([t for t in visible_tasks if t.platform == "teams"])
        manual_cnt = len([t for t in visible_tasks if t.platform in ["manual", "custom"]])
        del_cnt = len(self.mgr.get_deleted_tasks())

        open_tasks = [t for t in visible_tasks if not t.is_completed]
        overdue_cnt = len([t for t in visible_tasks if t.is_overdue])
        open_cnt = len(open_tasks)
        total_visible = len(visible_tasks)

        if self.status_filter in ["completed", "abgegeben", "erledigt", "done"]:
            comp_cnt = len([t for t in visible_tasks if t.is_completed])
            todo_badge = f"📋 Done: [bold green]{comp_cnt} completed[/bold green]"
        elif self.status_filter in ["overdue", "ueberfaellig", "überfällig"]:
            todo_badge = f"📋 Overdue: [bold red]{total_visible} overdue![/bold red]"
        elif overdue_cnt > 0:
            todo_badge = f"📋 To Do: [bold red]{open_cnt} open[/bold red] ([bold red]{overdue_cnt} overdue![/bold red])"
        elif open_cnt > 0:
            todo_badge = f"📋 To Do: [bold yellow]{open_cnt} open[/bold yellow]"
        else:
            todo_badge = "📋 To Do: [bold green]0 open[/bold green]"

        sync_time_str = "Never"
        if self.mgr.last_sync:
            try:
                sync_time_str = time.strftime("%H:%M:%S", time.localtime(float(self.mgr.last_sync)))
            except Exception:
                sync_time_str = str(self.mgr.last_sync)

        next_exam = get_next_upcoming_exam()
        exam_badge = ""
        if next_exam:
            try:
                _ndt = datetime.datetime.strptime(next_exam.date, "%Y-%m-%d").date()
                next_date_short = f"{_ndt.day:02d}.{_ndt.month:02d}."
            except Exception:
                next_date_short = next_exam.date_display
            exam_badge = f"  |  📝 Next: [bold cyan]{next_date_short} {next_exam.subject}[/bold cyan] [bold yellow]{next_exam.countdown_display}[/bold yellow]"

        stats_text = f"{todo_badge}  |  🎓 Moodle: {moodle_cnt}  |  👥 Teams: {teams_cnt}  |  ✏️ Manual: {manual_cnt}{exam_badge}  |  🕒 Sync: {sync_time_str}"
        self.query_one("#info_stats", Label).update(stats_text)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Click with mouse or ENTER on a row opens details view."""
        row_key = event.row_key.value
        task = next((t for t in self.current_tasks if t.id == row_key), None)
        if task:
            self._open_task_details(task)

    def _open_task_details(self, task: Task) -> None:
        if not task.details_loaded:
            self.notify(f"Loading details for '{task.title}'...", severity="information")
            def worker():
                self.mgr.load_task_details(task)
                def update_ui():
                    self.push_screen(TaskDetailModal(task, self.mgr), self._on_detail_closed)
                self.call_from_thread(update_ui)

            threading.Thread(target=worker, daemon=True, name="TaskDetailsWorker").start()
        else:
            self.push_screen(TaskDetailModal(task, self.mgr), self._on_detail_closed)

    def _on_detail_closed(self, result=None) -> None:
        self.refresh_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Mouse clicks on bottom buttons."""
        bid = event.button.id
        if bid == "btn_main_add":
            self.action_add_task()
        elif bid == "btn_main_sync":
            self.action_sync_tasks()
        elif bid == "btn_main_filter":
            self.action_open_filter_menu()
        elif bid == "btn_main_absences":
            self.action_show_absences()
        elif bid == "btn_main_exams":
            self.action_show_exams()
        elif bid == "btn_main_trash":
            self.action_show_trash()
        elif bid == "btn_main_login":
            self.action_login_menu()
        elif bid == "btn_main_settings":
            self.action_open_settings()
        elif bid == "btn_main_status":
            self.action_filter_status()
        elif bid == "btn_main_subject":
            self.action_filter_subject()
        elif bid == "btn_main_platform":
            self.action_filter_platform()
        elif bid in ("btn_main_theme", "btn_main_palette"):
            self.action_change_theme()
        elif bid == "btn_main_quit":
            self.action_quit_app()

    # --- Actions (callable via mouse & keyboard) ---

    def action_open_filter_menu(self) -> None:
        def on_filter_chosen(action: Optional[str]) -> None:
            if not action:
                return
            if action == "status":
                self.action_filter_status(from_menu=True)
            elif action == "timeframe":
                self.action_filter_timeframe(from_menu=True)
            elif action == "subject":
                self.action_filter_subject(from_menu=True)
            elif action == "platform":
                self.action_filter_platform(from_menu=True)
            elif action == "reset":
                self.status_filter = "open_only"
                self.timeframe_filter = "2_weeks"
                self.subject_filter = "all"
                self.platform_filter = "all"
                self.refresh_table()
                self.notify("All filters reset to default (2 Weeks, Open only).", severity="information")

        self.push_screen(
            FilterMenuModal(self.status_filter, self.subject_filter, self.platform_filter, self.timeframe_filter),
            on_filter_chosen
        )

    def action_filter_timeframe(self, from_menu: bool = False) -> None:
        def on_selected(new_tf: Optional[str]) -> None:
            if new_tf:
                self.timeframe_filter = new_tf
                self.refresh_table()
                tf_names = {
                    "1_week": "1 Week",
                    "2_weeks": "2 Weeks",
                    "4_weeks": "4 Weeks",
                    "8_weeks": "8 Weeks",
                    "all": "All",
                }
                self.notify(f"Max Duration Filter: {tf_names.get(new_tf, new_tf)}", severity="information")
            elif from_menu:
                self.action_open_filter_menu()
        self.push_screen(TimeframeFilterModal(), on_selected)

    def action_open_settings(self) -> None:
        def on_setting_chosen(action: Optional[str]) -> None:
            if not action:
                return
            if action == "change_theme":
                self.action_change_theme()
            elif action == "show_hotkeys":
                self.action_show_hotkeys()
            elif action == "login_menu":
                self.action_login_menu(from_menu=True)
            elif action == "show_trash":
                self.action_show_trash(from_menu=True)
            elif action == "setup_teams":
                self.action_setup_teams(from_login_menu=False, from_settings=True)
            elif action == "setup_moodle":
                self.action_setup_moodle(from_login_menu=False, from_settings=True)
            elif action == "setup_untis":
                self.action_setup_untis(from_login_menu=False, from_settings=True)
            elif action in ("school_config", "excuse_profile"):
                def on_config_done(saved: bool) -> None:
                    self.refresh_table()
                    self.action_open_settings()
                self.push_screen(SchoolConfigModal(), on_config_done)
            elif action == "toggle_group":
                curr_grp = _load_untis_group() or "X"
                new_grp = "Y" if "x" in curr_grp.lower() else "X"
                save_untis_group(new_grp)
                self.notify(f"WebUntis group set to {new_grp}.", severity="information")
                self.action_open_settings()

        self.push_screen(SettingsModal(), on_setting_chosen)

    def action_add_task(self) -> None:
        def on_task_added(new_task: Optional[Task]) -> None:
            if new_task:
                self.mgr.add_task(new_task)
                self.refresh_table()
                self.notify(f"Assignment '{new_task.title}' added successfully!", severity="information")
        self.push_screen(AddTaskModal(), on_task_added)

    def action_filter_status(self, from_menu: bool = False) -> None:
        def on_selected(new_status: Optional[str]) -> None:
            if new_status:
                self.status_filter = new_status
                self.refresh_table()
            elif from_menu:
                self.action_open_filter_menu()
        self.push_screen(StatusFilterModal(), on_selected)

    def action_filter_platform(self, from_menu: bool = False) -> None:
        def on_selected(action: Optional[str]) -> None:
            if not action:
                if from_menu:
                    self.action_open_filter_menu()
                return
            if action in ("all", "moodle", "teams", "manual"):
                self.platform_filter = action
                self.refresh_table()
                plat_names = {
                    "all": "All platforms",
                    "moodle": "Moodle",
                    "teams": "Teams",
                    "manual": "Manual",
                }
                self.notify(f"Platform filter set to: {plat_names.get(action, action)}", severity="information")

        self.push_screen(PlatformFilterModal(), on_selected)

    def action_filter_subject(self, from_menu: bool = False) -> None:
        subjects = sorted(list(set(t.course for t in self.mgr.tasks)))
        def on_selected(new_subj: Optional[str]) -> None:
            if new_subj:
                self.subject_filter = new_subj
                self.refresh_table()
            elif from_menu:
                self.action_open_filter_menu()
        self.push_screen(SubjectFilterModal(subjects), on_selected)

    def action_show_trash(self, from_menu: bool = False) -> None:
        def on_trash_closed(result=None) -> None:
            self.refresh_table()
            if from_menu:
                self.action_open_settings()
        self.push_screen(TrashModal(self.mgr), on_trash_closed)

    def action_sync_tasks(self) -> None:
        if self._is_syncing:
            return
        self._is_syncing = True

        # Dreh-Ladesymbol in der oberen rechten Ecke aktivieren
        try:
            self.query_one("#sync_spinner", SyncSpinner).active = True
        except Exception:
            pass

        def sync_worker():
            # 1. Wenn Git-Cloud-Sync eingerichtet ist: Remote-Pull & Smart-Merge ausführen
            try:
                from git_sync_service import is_git_configured, GitSyncService
                if is_git_configured():
                    git_ok, git_msg, has_updates = GitSyncService.pull_and_sync()
                    if has_updates:
                        self.mgr.reload_custom_tasks()
                        try:
                            from config import load_saved_theme
                            remote_theme = load_saved_theme()
                            if hasattr(self, "theme") and self.theme != remote_theme:
                                self.theme = remote_theme
                        except Exception:
                            pass
                        self.call_from_thread(self.refresh_table)

            except Exception:
                pass

            try:
                self.mgr.sync(deep_scan=False, on_batch_complete=lambda: self.call_from_thread(self.refresh_table))
            except Exception:
                pass


            def update_ui():
                self._is_syncing = False
                try:
                    self.query_one("#sync_spinner", SyncSpinner).active = False
                except Exception:
                    pass
                self.refresh_table()

            self.call_from_thread(update_ui)

        threading.Thread(target=sync_worker, daemon=True, name="SyncWorker").start()

    def action_login_menu(self, from_menu: bool = False) -> None:
        def on_choice(choice: Optional[str]) -> None:
            if choice == "teams":
                self.action_setup_teams(from_login_menu=True, from_settings=from_menu)
            elif choice == "moodle":
                self.action_setup_moodle(from_login_menu=True, from_settings=from_menu)
            elif choice == "untis":
                self.action_setup_untis(from_login_menu=True, from_settings=from_menu)
            elif choice == "git":
                self.action_setup_git(from_login_menu=True, from_settings=from_menu)
            elif choice is None and from_menu:
                self.action_open_settings()

        self.push_screen(LoginChoiceModal(), on_choice)

    def action_setup_git(self, from_login_menu: bool = False, from_settings: bool = False) -> None:
        def on_git_done(ok: bool) -> None:
            if ok:
                self.notify("✓ Git Cloud-Sync successfully configured!", severity="information")
                self.action_sync_tasks()
            elif from_login_menu:
                self.action_login_menu(from_menu=from_settings)
            elif from_settings:
                self.action_open_settings()
        self.push_screen(GitSetupModal(), on_git_done)

    def action_setup_teams(self, from_login_menu: bool = False, from_settings: bool = False) -> None:
        def on_teams_done(ok: bool) -> None:
            if ok:
                self.notify("✓ Microsoft Teams successfully connected!", severity="information")
                self.action_sync_tasks()
            else:
                self.notify("Teams login was not completed.", severity="warning")
                if from_login_menu:
                    self.action_login_menu(from_menu=from_settings)
                elif from_settings:
                    self.action_open_settings()
        self.push_screen(TeamsSetupModal(), on_teams_done)

    def action_setup_moodle(self, from_login_menu: bool = False, from_settings: bool = False) -> None:
        def on_moodle_done(ok: bool) -> None:
            if ok:
                self.action_sync_tasks()
            elif from_login_menu:
                self.action_login_menu(from_menu=from_settings)
            elif from_settings:
                self.action_open_settings()
        self.push_screen(MoodleLoginModal(), on_moodle_done)

    def action_setup_untis(self, from_login_menu: bool = False, from_settings: bool = False) -> None:
        def on_untis_done(ok: bool) -> None:
            if ok:
                self.action_show_absences()
            elif from_login_menu:
                self.action_login_menu(from_menu=from_settings)
            elif from_settings:
                self.action_open_settings()
        self.push_screen(UntisSetupModal(), on_untis_done)

    def action_show_absences(self) -> None:
        self.push_screen(AbsencesScreen())

    def action_show_exams(self) -> None:
        """Opens WebUntis Tests & Exams screen."""
        def on_exams_closed(result=None) -> None:
            self.refresh_table()
        self.push_screen(ExamsScreen(), on_exams_closed)

    def action_show_hotkeys(self) -> None:
        """Opens the CommandPalette with all application hotkeys."""
        self.push_screen(
            CommandPalette(
                providers=[HotkeysProvider],
                placeholder="Search for hotkeys…",
            )
        )

    def action_open_courses_palette(self, initial_mode: str = "courses") -> None:
        """Opens the UnifiedCommandPalette to quickly search and launch courses or schoolbooks."""
        self.push_screen(
            UnifiedCommandPalette(
                providers=[UnifiedQuickOpenProvider],
                initial_mode=initial_mode,
            )
        )

    def open_schoolbook(self, book: dict) -> None:
        """Opens a schoolbook (PDF in viewer, web link in browser)."""
        ok, msg = SchoolbookService.open_book(book)
        if ok:
            self.notify(f"✓ {msg}", severity="information")
        else:
            self.notify(f"⚠️ {msg}", severity="error")

    def action_link_schoolbook_file(self) -> None:
        """Opens Windows file explorer in background thread to link a local PDF file."""
        self.notify("📂 Opening file explorer for PDF selection...", severity="information")

        def _worker():
            try:
                pdf_path = SchoolbookService.pick_pdf_file()
                if pdf_path:
                    book = SchoolbookService.add_pdf_book(pdf_path)
                    title = book.get("title", "Schoolbook")
                    self.call_from_thread(
                        self.notify,
                        f"✓ Schoolbook '{title}' successfully linked!",
                        severity="information",
                    )
                    self.call_from_thread(lambda: self.action_open_courses_palette(initial_mode="books"))
                else:
                    self.call_from_thread(
                        self.notify,
                        "File selection cancelled.",
                        severity="warning",
                    )
                    self.call_from_thread(lambda: self.action_open_courses_palette(initial_mode="books"))
            except Exception as e:
                self.call_from_thread(
                    self.notify,
                    f"Error during file selection: {e}",
                    severity="error",
                )

        threading.Thread(target=_worker, daemon=True).start()

    def prompt_add_schoolbook_url(self, url: str = "") -> None:
        """Opens a modal dialog to enter URL and book title."""
        def _on_result(res: Optional[dict]) -> None:
            if res and res.get("url"):
                book = SchoolbookService.add_web_book(res["url"], res.get("title", ""))
                self.notify(f"✓ Online book '{book.get('title')}' linked!", severity="information")
                self.action_open_courses_palette(initial_mode="books")
            else:
                self.action_open_courses_palette(initial_mode="books")

        self.push_screen(SchoolbookUrlModal(initial_url=url), _on_result)

    def prompt_digi4school_download(self, initial_code: str = "") -> None:
        """Opens the dialog to download a Digi4School book as OCR PDF."""
        def _on_input_result(res: Optional[dict]) -> None:
            if res and res.get("code"):
                self.push_screen(
                    Digi4SchoolProgressModal(
                        email=res["email"],
                        password=res["password"],
                        code=res["code"],
                        quality=res.get("quality", "ultra"),
                    )
                )
            else:
                self.action_open_courses_palette(initial_mode="books")

        self.push_screen(Digi4SchoolDownloadModal(initial_code=initial_code), _on_input_result)

    def action_delete_schoolbook(self, book_id: str, title: str) -> None:
        """Deletes a schoolbook and reopens the palette in schoolbook mode."""
        SchoolbookService.remove_book(book_id)
        self.notify(f"✓ Schoolbook '{title}' removed.", severity="information")
        self.action_open_courses_palette(initial_mode="books")

    def action_prompt_unlink_schoolbook(self) -> None:
        """Sets the search bar to /unlink to list all books for removal."""
        try:
            if hasattr(self, "screen") and isinstance(self.screen, UnifiedCommandPalette):
                inp = self.screen.query_one(CommandInput)
                inp.value = "/unlink"
        except Exception:
            pass

    def open_course_url(self, url: str, name: str) -> None:
        """Opens the given course URL in the default browser and shows a notification."""
        if url:
            webbrowser.open(url)
            self.notify(f"✓ Opening '{name}' in browser...", severity="information")
        else:
            self.notify(f"No link available for '{name}'.", severity="warning")

    def action_reload_courses(self, reopen_palette: bool = True) -> None:
        """Reloads the Moodle courses cache from the server in a background thread."""
        self.notify("🔄 Refreshing Moodle courses from server...", severity="information")

        def _worker():
            try:
                import moodle_service
                count = moodle_service.reload_moodle_courses_cache()
                if count > 0:
                    self.call_from_thread(
                        self.notify,
                        f"✓ {count} Moodle courses successfully refreshed!",
                        severity="information",
                    )
                    if reopen_palette:
                        self.call_from_thread(self.action_open_courses_palette)
                else:
                    self.call_from_thread(
                        self.notify,
                        "Warning: No Moodle courses found or Moodle session expired.",
                        severity="warning",
                    )
            except Exception as e:
                self.call_from_thread(
                    self.notify,
                    f"Error refreshing courses: {e}",
                    severity="error",
                )

        threading.Thread(target=_worker, daemon=True).start()

    def _update_stats_display(self) -> None:
        """Alias for refreshing table and statistics."""
        self.refresh_table()

    def action_select_task(self, num: int) -> None:
        if 1 <= num <= len(self.current_tasks):
            self._open_task_details(self.current_tasks[num - 1])

    def watch_theme(self, theme: str) -> None:
        """Textual reactive watcher: speichert das ausgewählte Theme automatisch dauerhaft."""
        if theme in ALLOWED_THEMES:
            save_saved_theme(theme)

    def action_change_theme(self) -> None:
        """Öffnet die Theme-Auswahl (Textual CommandPalette mit den 5 handverlesenen Themes)."""
        self.search_themes()

    def action_command_palette(self) -> None:
        """Palette-Taste öffnet direkt die Schnellauswahl der 5 wichtigsten Themes."""
        self.action_change_theme()

    def _start_mouse_back_listener(self) -> None:
        """Starts a lightweight daemon thread listening for Mouse Button 4 (Back / XBUTTON1)."""
        if self._mouse_listener_thread and self._mouse_listener_thread.is_alive():
            return
        self._stop_mouse_listener.clear()
        self._mouse_listener_thread = threading.Thread(
            target=self._run_mouse_back_listener,
            daemon=True,
            name="MouseBackListenerThread",
        )
        self._mouse_listener_thread.start()

    def _run_mouse_back_listener(self) -> None:
        """Monitors Windows mouse back button state and navigates back when clicked in foreground."""
        VK_XBUTTON1 = 0x05  # Mouse Back Button (Seitentaste Hinten)
        user32 = ctypes.windll.user32
        prev_pressed = False
        while not self._stop_mouse_listener.is_set():
            time.sleep(0.025)
            try:
                # Prüfe ob Taste 4 (XBUTTON1) gedrückt ist (MSB = 1)
                is_pressed = bool(user32.GetAsyncKeyState(VK_XBUTTON1) & 0x8000)
                if is_pressed and not prev_pressed:
                    # Nur auslösen, wenn Aufgaben Detector das aktive/fokussierte Fenster ist
                    if is_app_window_foreground(self, self._terminal_hwnd):
                        self.call_from_thread(self.action_navigate_back)
                prev_pressed = is_pressed
            except Exception:
                pass

    def action_navigate_back(self) -> None:
        """Navigates one level back or closes modal/submenu (invoked via Mouse Back button or ESC)."""
        if len(self.screen_stack) <= 1:
            return  # Auf der Hauptseite, nichts zu schließen

        curr_screen = self.screen
        # Bevorzuge spezifische Back-/Cancel-/Dismiss-Aktionen des Screens
        if hasattr(curr_screen, "action_dismiss_screen"):
            curr_screen.action_dismiss_screen()
        elif hasattr(curr_screen, "action_cancel"):
            curr_screen.action_cancel()
        elif hasattr(curr_screen, "action_close"):
            curr_screen.action_close()
        elif hasattr(curr_screen, "key_escape"):
            curr_screen.key_escape()
        else:
            try:
                curr_screen.dismiss(None)
            except Exception:
                try:
                    self.pop_screen()
                except Exception:
                    pass

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Handles mouse down events reported directly by terminal drivers."""
        if getattr(event, "button", 0) in (4, 8):
            self.action_navigate_back()

    def on_click(self, event: events.Click) -> None:
        """Handles click events reported directly by terminal drivers."""
        if getattr(event, "button", 0) in (4, 8):
            self.action_navigate_back()

    def on_unmount(self) -> None:
        """Wird aufgerufen, wenn die Anwendung beendet wird (egal über welchen Weg)."""
        self._stop_mouse_listener.set()
        if hasattr(self, "mgr"):
            self.mgr.shutdown()
        try:
            close_all_active_browser_contexts()
        except Exception:
            pass
        if hasattr(self, "theme") and self.theme in ALLOWED_THEMES:
            save_saved_theme(self.theme)

    def action_quit_app(self) -> None:
        self._stop_mouse_listener.set()
        if hasattr(self, "mgr"):
            self.mgr.shutdown()
        try:
            close_all_active_browser_contexts()
        except Exception:
            pass
        if hasattr(self, "theme") and self.theme in ALLOWED_THEMES:
            save_saved_theme(self.theme)
        self.exit()



def run_tui():
    """Startet die moderne Textual-TUI-Anwendung."""
    if AUTO_CLEAN_BROWSER_CACHE:
        try:
            clean_browser_profile_caches()
        except Exception:
            pass

    ensure_terminal_window_size(target_cols=136, min_height_px=750)
    app = AufgabenDetectorApp()
    try:
        app.run()
    finally:
        try:
            if hasattr(app, "mgr"):
                app.mgr.shutdown()
        except Exception:
            pass
        try:
            close_all_active_browser_contexts()
        except Exception:
            pass
        if hasattr(app, "theme") and app.theme in ALLOWED_THEMES:
            try:
                save_saved_theme(app.theme)
            except Exception:
                pass


if __name__ == "__main__":
    run_tui()
    sys.exit(0)
