"""
excuse_service.py - PDF-Generator für WebUntis Entschuldigungsschreiben.
Erstellt eine 1:1 druckfertige Nachbildung des offiziellen WebUntis-Entschuldigungsschreibens.
"""

import os
import sys
import datetime
import logging
from typing import List, Optional, Dict
from fpdf import FPDF

# Suppress harmless fontTools warnings when subsetting Graphite/SIL font tables
logging.getLogger("fontTools.subset").setLevel(logging.ERROR)

from config import load_excuse_profile, save_excuse_profile, DOWNLOADS_DIR, FONTS_DIR, WORKSPACE_DIR
from models import DailyAbsenceSummary


def get_current_school_year_strings() -> tuple:
    """
    Ermittelt das Schuljahr (z.B. '2026/2027') und den Datumsbereich (z.B. '07.09.2026 - 04.07.2027').
    """
    today = datetime.date.today()
    curr_y = today.year
    start_y = curr_y if today.month >= 8 else curr_y - 1
    end_y = start_y + 1
    year_str = f"{start_y}/{end_y}"
    range_str = f"07.09.{start_y} - 04.07.{end_y}"
    return year_str, range_str


def create_excuse_pdf(
    selected_days: List[DailyAbsenceSummary],
    profile: Optional[Dict[str, str]] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Erstellt das offizielle WebUntis Entschuldigungs-PDF für die ausgewählten Fehltage.
    Gibt den absoluten Dateipfad der erzeugten PDF zurück.
    """
    if profile is None:
        profile = load_excuse_profile()

    student_name = profile.get("student_name", "Max Mustermann")
    student_class = profile.get("student_class", "1AHIT")
    teacher_name = profile.get("teacher_name", "Prof. Erika Musterlehrer")
    school_address = profile.get("school_address", "Musterstraße 1")
    school_district = profile.get("school_district", "A-1010 Wien")

    school_year, school_year_range = get_current_school_year_strings()

    # Bestimme Dateinamen & Pfad im Downloads-Ordner
    if not output_path:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Excuse_{ts}.pdf"
        output_path = os.path.join(DOWNLOADS_DIR, filename)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Initialisiere FPDF mit DIN-A4 in Punkt (595 x 842 pt)
    pdf = FPDF(unit="pt", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()

    # Schriften konfigurieren (Bevorzugt Gentium, Fallback auf Times New Roman / Times)
    gentium_reg = os.path.join(FONTS_DIR, "GentiumPlus-Regular.ttf")
    gentium_bold = os.path.join(FONTS_DIR, "GentiumPlus-Bold.ttf")
    if not os.path.exists(gentium_reg):
        legacy_dir = os.path.join(WORKSPACE_DIR, "fonts")
        gentium_reg = os.path.join(legacy_dir, "GentiumPlus-Regular.ttf")
        gentium_bold = os.path.join(legacy_dir, "GentiumPlus-Bold.ttf")
    times_reg = r"C:\Windows\Fonts\times.ttf"
    times_bold = r"C:\Windows\Fonts\timesbd.ttf"

    font_name = "Times"
    if os.path.exists(gentium_reg):
        try:
            pdf.add_font("Gentium", "", gentium_reg)
            if os.path.exists(gentium_bold):
                pdf.add_font("Gentium", "B", gentium_bold)
            else:
                pdf.add_font("Gentium", "B", gentium_reg)
            font_name = "Gentium"
        except Exception:
            font_name = "Times"

    if font_name == "Times" and os.path.exists(times_reg):
        try:
            pdf.add_font("TimesNewRoman", "", times_reg)
            if os.path.exists(times_bold):
                pdf.add_font("TimesNewRoman", "B", times_bold)
            else:
                pdf.add_font("TimesNewRoman", "B", times_reg)
            font_name = "TimesNewRoman"
        except Exception:
            font_name = "Times"

    # 1. Kopfzeile rechts (Schuladresse, Bezirk/Ort, Schuljahr)
    pdf.set_font(font_name, "", 10)
    pdf.set_xy(350, 42)
    # Rechtsbündige Ausgabe im Bereich x=350..570
    pdf.cell(220, 11, school_address, align="R")
    pdf.set_xy(350, 54)
    pdf.cell(220, 11, school_district, align="R")
    pdf.set_xy(350, 68)
    pdf.cell(220, 11, f"Schuljahr :  {school_year}", align="R")

    # 2. Titel (Zentriert)
    pdf.set_font(font_name, "", 14)
    pdf.set_xy(25, 94)
    pdf.cell(545, 18, "Entschuldigung über das Fernbleiben vom Unterricht", align="C")

    # 3. Drei graue Informationsbalken (#cccccc / 204, 204, 204)
    pdf.set_fill_color(204, 204, 204)
    pdf.set_draw_color(204, 204, 204)

    # Balken 1: Name und Klasse
    pdf.rect(25, 129, 270, 15, style="F")
    pdf.rect(295, 129, 275, 15, style="F")
    pdf.set_font(font_name, "", 11)
    pdf.set_xy(30, 131)
    pdf.cell(260, 12, f"Name: {student_name}")
    pdf.set_xy(300, 131)
    pdf.cell(265, 12, f"Klasse: {student_class}")

    # Balken 2: Klassenlehrkraft
    pdf.rect(25, 150, 545, 15, style="F")
    pdf.set_xy(30, 152)
    pdf.cell(535, 12, f"Klassenlehrkraft: {teacher_name}")

    # Balken 3: Schuljahr-Datumsbereich
    pdf.rect(25, 171, 545, 15, style="F")
    pdf.set_xy(30, 173)
    pdf.cell(535, 12, school_year_range)

    # 4. Tabellen-Überschriften
    pdf.set_font(font_name, "B", 11)
    pdf.set_xy(30, 191)
    pdf.cell(80, 12, "Datum")
    pdf.set_xy(110, 191)
    pdf.cell(120, 12, "Schulstd.")
    pdf.set_xy(230, 191)
    pdf.cell(120, 12, "Fehlstd.")
    pdf.set_xy(350, 191)
    pdf.cell(215, 12, "Abwesenheitsgrund")

    # 5. Zeilen der ausgewählten Fehltage
    pdf.set_font(font_name, "", 11)
    current_y = 214
    total_hours = 0
    total_minutes = 0

    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(1.0)

    for day in selected_days:
        pdf.set_xy(30, current_y)
        pdf.cell(80, 12, day.date_display)
        pdf.set_xy(110, current_y)
        pdf.cell(120, 12, str(day.school_hours))
        pdf.set_xy(230, current_y)
        pdf.cell(120, 12, day.duration_str)

        # Gestrichelte Linie für handschriftlichen Abwesenheitsgrund
        line_y = current_y + 16
        pdf.set_dash_pattern(dash=5, gap=3)
        pdf.line(345, line_y, 565, line_y)
        pdf.set_dash_pattern()

        total_hours += day.school_hours
        day_mins = 0
        if day.duration_str and ":" in day.duration_str:
            try:
                parts = day.duration_str.split(":")
                day_mins = int(parts[0]) * 60 + int(parts[1])
            except Exception:
                day_mins = day.school_hours * 50
        else:
            day_mins = day.school_hours * 50
        total_minutes += day_mins
        current_y += 18

    # Falls keine Fehltage ausgewählt wurden (Leerzeile)
    if not selected_days:
        line_y = current_y + 16
        pdf.set_dash_pattern(dash=5, gap=3)
        pdf.line(345, line_y, 565, line_y)
        pdf.set_dash_pattern()
        current_y += 18

    # 6. Summenzeile (Label bold, Zahlen normal)
    dur_h = total_minutes // 60
    dur_m = total_minutes % 60
    sum_duration_str = f"{dur_h}:{dur_m:02d}"

    pdf.set_xy(30, current_y)
    pdf.set_font(font_name, "B", 11)
    pdf.cell(80, 12, "Summe")
    pdf.set_font(font_name, "", 11)
    pdf.set_xy(110, current_y)
    pdf.cell(120, 12, str(total_hours))
    pdf.set_xy(230, current_y)
    pdf.cell(120, 12, sum_duration_str)

    # 7. Unterschriftsbereich (Gestrichelte Linien für Datum & Unterschrift)
    sig_y = max(current_y + 92, 325)

    pdf.set_dash_pattern(dash=5, gap=3)
    # Linke Linie für Datum (x=25 bis 175)
    pdf.line(25, sig_y, 175, sig_y)
    # Rechte Linie für Unterschrift (x=285 bis 570)
    pdf.line(285, sig_y, 570, sig_y)
    pdf.set_dash_pattern()

    # Beschriftung unter den Linien (Bold)
    pdf.set_font(font_name, "B", 11)
    pdf.set_xy(25, sig_y + 4)
    pdf.cell(150, 12, "Datum", align="C")

    pdf.set_xy(285, sig_y + 4)
    pdf.cell(285, 12, "Unterschrift (Erzber./Eigenber.)", align="C")

    # 8. Fußzeile
    footer_line_y = 766.5
    pdf.line(25, footer_line_y, 570, footer_line_y)

    footer_y = 787
    curr_webuntis_year = datetime.date.today().year + (1 if datetime.date.today().month >= 8 else 0)
    pdf.set_font(font_name, "", 11)
    pdf.set_xy(28, footer_y)
    pdf.cell(150, 12, f"WebUntis {curr_webuntis_year}")

    pdf.set_xy(234, footer_y)
    pdf.cell(200, 12, "Untis GmbH (www.untis.at)")

    pdf.set_xy(468, footer_y)
    pdf.cell(100, 12, "Seite 1 von 1")

    # PDF speichern
    pdf.output(output_path)
    return output_path


def open_pdf_in_system_viewer(file_path: str) -> bool:
    """Öffnet die generierte PDF-Datei im Standard-PDF-Viewer des Betriebssystems."""
    if not os.path.exists(file_path):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(file_path)
            return True
        elif sys.platform == "darwin":
            os.system(f'open "{file_path}"')
            return True
        else:
            os.system(f'xdg-open "{file_path}"')
            return True
    except Exception as e:
        print(f"Fehler beim Öffnen der PDF: {e}", file=sys.stderr)
        return False
