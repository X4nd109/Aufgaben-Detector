"""
ui.py - Moderne, übersichtliche Terminal-Benutzeroberfläche mit Rich.
Stellt Moodle- und Teams-Aufgaben konsolidiert dar.
"""

import os
import sys
import webbrowser
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich import box

from models import Task
from auth import check_teams_session, get_saved_moodle_cookies
from config import DOWNLOADS_DIR

# Windows UTF-8 Konfiguration
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def adjust_console_window(min_cols: int = 120, min_lines: int = 32):
    """Passt das Konsolenfenster automatisch auf mindestens 120x32 an, damit die Tabelle perfekt Platz hat."""
    if os.name == "nt" and sys.stdout.isatty():
        try:
            import shutil
            cols, lines = shutil.get_terminal_size((80, 25))
            if cols < min_cols or lines < min_lines:
                os.system(f"mode con: cols={max(cols, min_cols)} lines={max(lines, min_lines)} >nul 2>&1")
        except Exception:
            pass


# adjust_console_window wird nur noch bei explizitem CLI-Start aufgerufen,
# um Desyncs in modernen Terminal-Emulatoren (Textual / Windows Terminal) zu verhindern.
_w = Console().width
console = Console(width=_w if (_w and _w >= 100) else 115)


def get_platform_badge(platform: str) -> Text:
    if platform == "moodle":
        return Text("🟧 Moodle", style="bold orange3")
    elif platform == "teams":
        return Text("🟦 Teams", style="bold dodger_blue1")
    elif platform in ["manual", "custom"]:
        return Text("✏️ Manual", style="bold medium_purple")
    return Text(platform, style="dim")


def get_subject_styled(subject: str) -> Text:
    colors = {
        "SWP PM": "bold cyan",
        "SWP": "bold cyan",
        "SESD": "bold red",
        "SPL": "bold blue",
        "NW2": "bold green",
        "NW": "bold green",
        "BET": "bold yellow",
        "AMEC": "bold magenta",
        "SMEN": "bold dark_orange",
        "D": "bold white",
        "E": "bold gold1",
        "UFW": "bold deep_pink3",
    }
    style = colors.get(subject.upper(), "bold white")
    return Text(subject, style=style)


def compact_due_date(due: str) -> str:
    if not due:
        return ""
    import re
    res = re.sub(r"\s*\((?:Überfällig|überfällig|Overdue|overdue)\)", "", due).strip()
    # Wenn "Morgen" / "Tomorrow" oder "Heute" / "Today" drin steht, Datum weglassen
    m_rel = re.search(r"(Heute|Today|Morgen|Tomorrow|Gestern|Yesterday)[^,]*,\s*\d{1,2}\.\s*[A-Za-z]+,\s*(\d{1,2}:\d{2})", res, re.IGNORECASE)
    if m_rel:
        return f"{m_rel.group(1).capitalize()}, {m_rel.group(2)}"

    # Abbreviations for weekdays and months
    replacements = [
        (r"Montag", "Mo"), (r"Dienstag", "Tu"), (r"Mittwoch", "We"),
        (r"Donnerstag", "Th"), (r"Freitag", "Fr"), (r"Samstag", "Sa"), (r"Sonntag", "Su"),
        (r"Monday", "Mo"), (r"Tuesday", "Tu"), (r"Wednesday", "We"),
        (r"Thursday", "Th"), (r"Friday", "Fr"), (r"Saturday", "Sa"), (r"Sunday", "Su"),
        (r"Januar", "Jan."), (r"January", "Jan."), (r"Februar", "Feb."), (r"February", "Feb."),
        (r"März", "Mar."), (r"March", "Mar."), (r"April", "Apr."),
        (r"Mai", "May"), (r"Juni", "Jun."), (r"Juli", "Jul."),
        (r"September", "Sep."), (r"Oktober", "Oct."), (r"October", "Oct."),
        (r"November", "Nov."), (r"Dezember", "Dec."), (r"December", "Dec.")
    ]
    for pat, rep in replacements:
        res = re.sub(pat, rep, res)
    return res.strip()


def get_due_date_styled(task: Task) -> Text:
    due = compact_due_date(task.due_date_str)
    if task.is_completed:
        return Text(due, style="dim")
    elif task.is_overdue:
        return Text(f"⚠ {due}", style="bold red")
    elif task.is_due_soon:
        return Text(f"⏰ {due}", style="bold yellow")
    else:
        return Text(due, style="white")


def get_status_styled(task: Task) -> Text:
    if task.is_completed:
        return Text("✔ Completed", style="bold green")
    elif task.is_overdue:
        return Text("✖ Overdue", style="bold red")
    elif "offen" in task.status.lower() or "zugewiesen" in task.status.lower() or "open" in task.status.lower():
        return Text("⏳ Open", style="yellow")
    return Text(task.status_display, style="dim")


def render_header(total_moodle: int, total_teams: int, last_sync_time: Optional[float] = None, deleted_count: int = 0):
    """Zeigt den oberen Banner mit Systemstatus an."""
    has_moodle = bool(get_saved_moodle_cookies())
    has_teams = check_teams_session()

    moodle_status = "[bold green]Connected[/bold green]" if has_moodle else "[bold yellow]Not configured[/bold yellow]"
    teams_status = "[bold green]Connected[/bold green]" if has_teams else "[bold yellow]Not linked (Press 'T')[/bold yellow]"

    sync_str = ""
    if last_sync_time:
        import datetime
        try:
            dt = datetime.datetime.fromtimestamp(float(last_sync_time))
            sync_str = f" • Last Sync: {dt.strftime('%H:%M:%S')}"
        except Exception:
            sync_str = f" • Last Sync: {last_sync_time}"

    del_str = f"   |   [dim]🗑️ Hidden: [bold magenta]{deleted_count}[/bold magenta] (Key 'G')[/dim]" if deleted_count > 0 else ""

    markup = (
        f"Moodle ({total_moodle}): {moodle_status}   |   Teams ({total_teams}): {teams_status}{sync_str}{del_str}\n"
        f"[dim]Download location:[/dim] [underline cyan]{DOWNLOADS_DIR}[/underline cyan]"
    )

    panel = Panel(
        Text.from_markup(markup),
        title="[bold white]📚 SCHOOL ASSIGNMENT HUB[/bold white]",
        border_style="bright_blue",
        box=box.ROUNDED,
        padding=(0, 2)
    )
    console.print(panel)


def render_task_table(
    tasks: List[Task],
    current_filter_platform: str = "all",
    current_filter_status: str = "open_only",
    current_subject_filter: Optional[str] = None
):
    # Filter-Statuszeile
    filter_info = []
    if current_filter_status in ["open_only", "open", "offen", "todo", "to_do"]:
        filter_info.append("Status: [bold yellow]Open only[/bold yellow]")
    elif current_filter_status in ["overdue", "ueberfaellig", "überfällig"]:
        filter_info.append("Status: [bold red]Overdue only[/bold red]")
    elif current_filter_status in ["completed", "abgegeben", "erledigt", "done"]:
        filter_info.append("Status: [bold green]Completed only[/bold green]")
    else:
        filter_info.append("Status: [bold cyan]All[/bold cyan]")

    if current_filter_platform != "all":
        filter_info.append(f"Platform: [bold magenta]{current_filter_platform.upper()}[/bold magenta]")

    if current_subject_filter and current_subject_filter != "all":
        filter_info.append(f"Subject: [bold cyan]{current_subject_filter.upper()}[/bold cyan]")

    console.print(f" [dim]Filter: {' | '.join(filter_info)}[/dim]\n")

    if not tasks:
        console.print(
            Panel(
                "[bold green]🎉 No assignments found![/bold green]\n"
                "Either all tasks are completed, or you have active filters.\n"
                "Press [bold yellow]'R'[/bold yellow] to reload or [bold yellow]'S'[/bold yellow] to adjust the status filter.",
                box=box.ROUNDED,
                border_style="green"
            )
        )
        return

    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold bright_white on grey23",
        expand=True,
        highlight=True
    )

    table.add_column("#", style="bold dim", width=3, justify="right")
    table.add_column("Type", width=10)
    table.add_column("Subject", width=6)
    table.add_column("Teacher", width=9, justify="center")
    table.add_column("Assignment", style="bold white", ratio=3, min_width=25)
    table.add_column("Due Date", width=22, no_wrap=True)
    table.add_column("Status", width=15, no_wrap=True)
    table.add_column("Attachments", width=9, justify="center")

    for idx, t in enumerate(tasks, 1):
        if t.attachments:
            att_display = Text(f"📎 {len(t.attachments)}", style="bold yellow")
        elif t.details_loaded:
            att_display = Text("-", style="dim")
        else:
            att_display = Text("·", style="dim")

        table.add_row(
            str(idx),
            get_platform_badge(t.platform),
            get_subject_styled(t.course),
            Text(t.teacher or "-", style="bold magenta"),
            t.title,
            get_due_date_styled(t),
            get_status_styled(t),
            att_display
        )

    console.print(table)
    console.print("")


def render_task_detail(task: Task, is_deleted: bool = False):
    """Zeigt die Detailansicht einer ausgewählten Aufgabe mit Angabe und Anhängen."""
    console.clear()

    from config import extract_teacher
    teacher_code = task.teacher or extract_teacher(task.course_full, task.course, task.title, task.description)
    if not teacher_code or teacher_code in ["-", "AIC", "GRO"] or task.course.upper() == "UFW":
        teacher_code = extract_teacher(task.course_full, task.course, task.title, task.description)
        task.teacher = teacher_code

    # Meta-Header
    meta_table = Table.grid(padding=(0, 2))
    meta_table.add_column(style="bold cyan", justify="right")
    meta_table.add_column()

    meta_table.add_row("Title:", f"[bold white]{task.title}[/bold white]")
    meta_table.add_row("Subject:", f"{task.course} ({task.course_full})")
    meta_table.add_row("Teacher:", f"[bold magenta]{teacher_code or '-'}[/bold magenta]")
    meta_table.add_row("Platform:", get_platform_badge(task.platform))
    meta_table.add_row("Due Date:", get_due_date_styled(task))
    meta_table.add_row("Status:", get_status_styled(task))
    if is_deleted:
        meta_table.add_row("Visibility:", "[bold magenta]🗑️ Hidden (Deleted)[/bold magenta]")
    meta_table.add_row("Direct Link:", f"[underline bright_cyan]{task.url}[/underline bright_cyan]" if task.url else "[dim]None[/dim]")

    if task.download_dir:
        meta_table.add_row("Saved in:", f"[green]{task.download_dir}[/green]")

    teacher_tag = f" • [bold magenta]{teacher_code}[/bold magenta]" if teacher_code and teacher_code != "-" else ""
    header_title = f"[bold red]Assignment Details (DELETED) • {task.course}{teacher_tag}[/bold red]" if is_deleted else f"[bold]Assignment Details • {task.course}{teacher_tag}[/bold]"
    border_col = "magenta" if is_deleted else "cyan"

    header_panel = Panel(
        meta_table,
        title=header_title,
        box=box.ROUNDED,
        border_style=border_col
    )
    console.print(header_panel)

    # Aufgabenstellung / Angabe
    console.print("\n[bold bright_white]── Assignment Description ──[/bold bright_white]")
    if task.description:
        import re
        clean_desc = task.description
        clean_desc = re.sub(r'!\[.*?\]\(.*?\)', '[Image]', clean_desc)
        clean_desc = re.sub(r'<img[^>]*>', '[Image]', clean_desc, flags=re.IGNORECASE)
        clean_desc = re.sub(r'\[\s*\[(?:Bild|Image)\]\s*\]\(.*?\)', '[Image]', clean_desc)
        clean_desc = re.sub(r'\[(?:Bild|Image)\]\(.*?\)', '[Image]', clean_desc)
        if "<" in clean_desc and ">" in clean_desc:
            clean_desc = re.sub(r"<style[^>]*>.*?</style>", "", clean_desc, flags=re.DOTALL | re.IGNORECASE)
            clean_desc = re.sub(r"<script[^>]*>.*?</script>", "", clean_desc, flags=re.DOTALL | re.IGNORECASE)
            clean_desc = re.sub(r"<br\s*/?>", "\n", clean_desc, flags=re.IGNORECASE)
            clean_desc = re.sub(r"</p>", "\n\n", clean_desc, flags=re.IGNORECASE)
            clean_desc = re.sub(r"</div>", "\n", clean_desc, flags=re.IGNORECASE)
            clean_desc = re.sub(r"<[^>]+>", "", clean_desc)
            clean_desc = re.sub(r"\n{3,}", "\n\n", clean_desc).strip()
        md = Markdown(clean_desc)
        console.print(Panel(md, box=box.SIMPLE, border_style="grey37"))
    else:
        console.print("[dim]No assignment description available.[/dim]\n")

    # Anhänge
    console.print("[bold bright_white]── Attachments / Files ──[/bold bright_white]")
    if task.attachments:
        for idx, att in enumerate(task.attachments, 1):
            local = f" [green](Local: {att.local_path})[/green]" if att.local_path else ""
            console.print(f" [bold yellow]📎 {idx}.[/bold yellow] {att.name}{local}")
    else:
        console.print(" [dim]No attachments included.[/dim]")

    console.print("\n" + "─" * 70)
    if is_deleted:
        console.print(
            "[bold white]Actions:[/bold white] "
            "[bold cyan][O][/bold cyan] Open in browser  |  "
            "[bold green][W][/bold green] Restore  |  "
            "[bold green][D][/bold green] Download to Downloads  |  "
            "[bold yellow][Z][/bold yellow] Back"
        )
    else:
        console.print(
            "[bold white]Actions:[/bold white] "
            "[bold cyan][O][/bold cyan] Open in browser  |  "
            "[bold green][D][/bold green] Download to Downloads  |  "
            "[bold red][L][/bold red] Hide assignment  |  "
            "[bold yellow][Z][/bold yellow] Back to list"
        )


def render_deleted_tasks_table(deleted_tasks: List[Task]):
    """Zeigt die Tabelle aller gelöschten/ausgeblendeten Aufgaben an."""
    console.clear()

    title_text = "[bold magenta]🗑️  HIDDEN / DELETED ASSIGNMENTS[/bold magenta]"
    console.print(Panel(
        "[dim]These assignments were manually hidden (e.g. group work submitted by classmates).\n"
        "They no longer appear in your active task list, but can be restored here anytime.[/dim]",
        title=title_text,
        border_style="magenta",
        box=box.ROUNDED,
        padding=(0, 2)
    ))

    if not deleted_tasks:
        console.print(
            Panel(
                "[bold green]No hidden assignments found.[/bold green]\n"
                "All your assignments are visible in the active task list.",
                box=box.ROUNDED,
                border_style="green"
            )
        )
        return

    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold bright_white on grey23",
        expand=True,
        highlight=True
    )

    table.add_column("#", style="bold dim", width=3, justify="right")
    table.add_column("Type", width=10)
    table.add_column("Subject", width=6)
    table.add_column("Teacher", width=9, justify="center")
    table.add_column("Assignment", style="bold dim", ratio=3, min_width=25)
    table.add_column("Due Date", width=22, no_wrap=True)
    table.add_column("Status", width=15, no_wrap=True)
    table.add_column("Attachments", width=9, justify="center")

    for idx, t in enumerate(deleted_tasks, 1):
        if t.attachments:
            att_display = Text(f"📎 {len(t.attachments)}", style="bold yellow")
        elif t.details_loaded:
            att_display = Text("-", style="dim")
        else:
            att_display = Text("·", style="dim")

        table.add_row(
            str(idx),
            get_platform_badge(t.platform),
            get_subject_styled(t.course),
            Text(t.teacher or "-", style="bold magenta"),
            t.title,
            get_due_date_styled(t),
            Text("🗑️ Hidden", style="bold magenta"),
            att_display
        )

    console.print(table)
    console.print("")


def open_task_in_browser(task: Task):
    """Öffnet die Abgabeseite im Standard-Webbrowser des Benutzers."""
    if task.url:
        console.print(f"\n[cyan]Opening in browser: {task.url}[/cyan]")
        webbrowser.open(task.url)
    else:
        console.print("\n[red]No submission URL available for this assignment.[/red]")
