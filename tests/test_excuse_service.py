"""
test_excuse_service.py - Automatisierte Unit- und Integrationstests für das Entschuldigungsschreiben.
"""

import os
import sys
import unittest
from unittest.mock import patch
import tempfile
try:
    import pymupdf as fitz
except ImportError:
    import fitz

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import src

from config import load_excuse_profile, save_excuse_profile, DEFAULT_EXCUSE_PROFILE
from models import MissedLesson, SubjectAbsenceSummary, DailyAbsenceSummary
from untis_service import get_daily_absence_summaries
from excuse_service import create_excuse_pdf, get_current_school_year_strings


class TestExcuseService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def test_default_and_custom_profile(self):
        """Prüft das Laden der Standardwerte und das Speichern benutzerdefinierter Profildaten."""
        save_excuse_profile(DEFAULT_EXCUSE_PROFILE)
        prof = load_excuse_profile()
        self.assertIn("student_name", prof)
        self.assertEqual(prof["student_name"], DEFAULT_EXCUSE_PROFILE["student_name"])
        self.assertEqual(prof["student_class"], DEFAULT_EXCUSE_PROFILE["student_class"])
        self.assertEqual(prof["teacher_name"], DEFAULT_EXCUSE_PROFILE["teacher_name"])

        # Benutzerdefiniertes Profil speichern und prüfen
        test_prof = {
            "student_name": "Mustermann Max",
            "student_class": "4AHWII",
            "teacher_name": "Prof. Test",
            "school_address": "Testweg 1",
            "school_district": "A-1010 Wien",
        }
        save_excuse_profile(test_prof)
        loaded = load_excuse_profile()
        self.assertEqual(loaded["student_name"], "Mustermann Max")
        self.assertEqual(loaded["student_class"], "4AHWII")

        # Wieder zurücksetzen
        save_excuse_profile(DEFAULT_EXCUSE_PROFILE)
        reset_prof = load_excuse_profile()
        self.assertEqual(reset_prof["student_name"], DEFAULT_EXCUSE_PROFILE["student_name"])

    def test_daily_absence_aggregation(self):
        """Prüft die tagesweise Aggregation mehrerer Einzelstunden an einem Tag."""
        # 4 Einheiten am 02.10.2026
        lessons_day1 = [
            MissedLesson(
                date="2026-10-02",
                subject="SWP PM",
                period_num=1,
                start_time="08:00",
                end_time="08:50",
                absence_status="Offen",
            ),
            MissedLesson(
                date="2026-10-02",
                subject="SWP PM",
                period_num=2,
                start_time="08:50",
                end_time="09:40",
                absence_status="Offen",
            ),
            MissedLesson(
                date="2026-10-02",
                subject="D",
                period_num=3,
                start_time="09:55",
                end_time="10:45",
                absence_status="Offen",
            ),
            MissedLesson(
                date="2026-10-02",
                subject="D",
                period_num=4,
                start_time="10:45",
                end_time="11:35",
                absence_status="Offen",
            ),
        ]
        # 2 Einheiten am 05.10.2026 (entschuldigt)
        lessons_day2 = [
            MissedLesson(
                date="2026-10-05",
                subject="AMEC",
                period_num=1,
                start_time="08:00",
                end_time="08:50",
                absence_status="Entschuldigt",
            ),
            MissedLesson(
                date="2026-10-05",
                subject="AMEC",
                period_num=2,
                start_time="08:50",
                end_time="09:40",
                absence_status="Entschuldigt",
            ),
        ]

        summaries = [
            SubjectAbsenceSummary(subject="SWP PM", total_hours=2, missed_lessons=lessons_day1[:2]),
            SubjectAbsenceSummary(subject="D", total_hours=2, missed_lessons=lessons_day1[2:]),
            SubjectAbsenceSummary(subject="AMEC", total_hours=2, missed_lessons=lessons_day2),
        ]

        daily = get_daily_absence_summaries(summaries)
        self.assertEqual(len(daily), 2)

        # Neuester Tag zuerst (05.10.2026)
        d_oct5 = daily[0]
        self.assertEqual(d_oct5.date, "2026-10-05")
        self.assertEqual(d_oct5.date_display, "05.10.2026")
        self.assertEqual(d_oct5.school_hours, 2)
        # 2 * 50 = 100 Min -> 1:40
        self.assertEqual(d_oct5.duration_str, "1:40")
        self.assertEqual(d_oct5.status, "Excused")

        # Tag 2 (02.10.2026)
        d_oct2 = daily[1]
        self.assertEqual(d_oct2.date, "2026-10-02")
        self.assertEqual(d_oct2.date_display, "02.10.2026")
        self.assertEqual(d_oct2.school_hours, 4)
        # 4 * 50 = 200 Min -> 3:20 (exakt wie im WebUntis PDF)
        self.assertEqual(d_oct2.duration_str, "3:20")
        self.assertEqual(d_oct2.status, "Open")
        self.assertIn("SWP PM", d_oct2.subjects)
        self.assertIn("D", d_oct2.subjects)

    def test_daily_absence_lateness_aggregation(self):
        """Prüft, dass Verspätungen mit exakter Dauer (z.B. 11 Min) summiert werden statt 50 Min."""
        late_lesson = MissedLesson(
            date="2026-10-20",
            subject="INFI",
            period_num=7,
            start_time="14:25",
            end_time="14:36",
            duration_minutes=11,
            reason="Verspätung",
            absence_status="Offen",
        )
        summary = SubjectAbsenceSummary(subject="INFI", total_hours=1, missed_lessons=[late_lesson])
        daily = get_daily_absence_summaries([summary])
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0].school_hours, 1)
        self.assertEqual(daily[0].duration_str, "0:11")

    def test_pdf_generation_lateness_exact_sum(self):
        """Prüft, dass im PDF die exakte Minutensumme errechnet wird (z.B. 0:11 + 0:50 = 1:01)."""
        out_pdf = os.path.join(self.temp_dir, "test_lateness_sum.pdf")
        day1 = DailyAbsenceSummary(
            date="2026-10-20",
            date_display="20.10.2026",
            school_hours=1,
            duration_str="0:11",
            subjects=["INFI"],
            status="Offen",
        )
        day2 = DailyAbsenceSummary(
            date="2026-10-21",
            date_display="21.10.2026",
            school_hours=1,
            duration_str="0:50",
            subjects=["SWP"],
            status="Offen",
        )
        created_path = create_excuse_pdf([day1, day2], output_path=out_pdf)
        self.assertTrue(os.path.exists(created_path))
        doc = fitz.open(created_path)
        text = doc[0].get_text()
        self.assertIn("0:11", text)
        self.assertIn("0:50", text)
        # Summe: 11 + 50 = 61 Min -> 1:01 (und NICHT 2 * 50 = 1:40)
        self.assertIn("1:01", text)

    def test_pdf_generation_content_and_layout(self):
        """Erzeugt ein PDF und validiert alle Texte und Elemente mit PyMuPDF."""
        out_pdf = os.path.join(self.temp_dir, "test_excuse.pdf")
        day = DailyAbsenceSummary(
            date="2026-10-02",
            date_display="02.10.2026",
            school_hours=4,
            duration_str="3:20",
            subjects=["SWP PM"],
            status="Offen",
        )

        created_path = create_excuse_pdf([day], output_path=out_pdf)
        self.assertTrue(os.path.exists(created_path))

        # PDF mit fitz analysieren
        doc = fitz.open(created_path)
        self.assertEqual(len(doc), 1)
        text = doc[0].get_text()

        # Überprüfe Pflichtbestandteile
        self.assertIn("Musterstraße 1", text)
        self.assertIn("A-1010 Wien", text)
        self.assertIn("Schuljahr :", text)
        self.assertIn("Entschuldigung", text)
        self.assertIn("Fernbleiben vom Unterricht", text)
        self.assertIn("Name: Max Mustermann", text)
        self.assertIn("Klasse: 1AHIT", text)
        self.assertIn("Klassenlehrkraft: Prof. Erika Musterlehrer", text)
        self.assertIn("Datum", text)
        self.assertIn("Schulstd.", text)
        self.assertIn("Fehlstd.", text)
        self.assertIn("Abwesenheitsgrund", text)
        self.assertIn("02.10.2026", text)
        self.assertIn("4", text)
        self.assertIn("3:20", text)
        self.assertIn("Summe", text)
        self.assertIn("Unterschrift (Erzber./Eigenber.)", text)
        self.assertIn("Untis GmbH (www.untis.at)", text)
        self.assertIn("Seite 1 von 1", text)
        doc.close()


class TestExcuseTUIModals(unittest.IsolatedAsyncioTestCase):

    async def test_excuse_profile_modal_flow(self):
        from tui_app import AufgabenDetectorApp, SchoolConfigModal, SettingsModal
        from textual.widgets import Input, Button

        app = AufgabenDetectorApp()
        async with app.run_test() as pilot:
            # Teste SettingsModal
            settings_modal = SettingsModal()
            app.push_screen(settings_modal)
            await pilot.pause()

            btn_cfg = settings_modal.query_one("#btn_set_school_config", Button)
            btn_cfg.press()
            await pilot.pause()

            # Teste SchoolConfigModal
            config_modal = SchoolConfigModal()
            app.push_screen(config_modal)
            await pilot.pause()

            inp_name = config_modal.query_one("#inp_cfg_name", Input)
            inp_class = config_modal.query_one("#inp_cfg_class", Input)
            btn_grp = config_modal.query_one("#btn_cfg_group", Button)
            inp_school = config_modal.query_one("#inp_cfg_school", Input)

            self.assertIsNotNone(inp_class)
            self.assertIsNotNone(btn_grp)
            self.assertIsNotNone(inp_school)

            inp_name.value = "Testschüler Anton"
            btn_save = config_modal.query_one("#btn_cfg_save", Button)
            btn_save.press()
            await pilot.pause()

            prof = load_excuse_profile()
            self.assertEqual(prof["student_name"], "Testschüler Anton")

            # Wieder zurücksetzen
            save_excuse_profile(DEFAULT_EXCUSE_PROFILE)

    async def test_excuse_letter_modal_selection_and_actions(self):
        from tui_app import AufgabenDetectorApp, ExcuseLetterModal, AbsencesScreen
        from textual.widgets import Button, DataTable, Label

        test_lessons = [
            MissedLesson(
                date="2026-10-02",
                subject="SWP PM",
                period_num=1,
                start_time="08:00",
                end_time="08:50",
                absence_status="Offen",
            ),
            MissedLesson(
                date="2026-10-02",
                subject="SWP PM",
                period_num=2,
                start_time="08:50",
                end_time="09:40",
                absence_status="Offen",
            ),
            MissedLesson(
                date="2026-10-05",
                subject="D",
                period_num=1,
                start_time="08:00",
                end_time="08:50",
                absence_status="Entschuldigt",
            ),
        ]
        summaries = [
            SubjectAbsenceSummary(subject="SWP PM", total_hours=2, missed_lessons=test_lessons[:2]),
            SubjectAbsenceSummary(subject="D", total_hours=1, missed_lessons=test_lessons[2:]),
        ]

        app = AufgabenDetectorApp()
        async with app.run_test() as pilot:
            # 1. AbsencesScreen prüfen
            abs_screen = AbsencesScreen()
            app.push_screen(abs_screen)
            await pilot.pause()
            btn_excuse = abs_screen.query_one("#btn_abs_excuse", Button)
            self.assertIsNotNone(btn_excuse)

            # 2. ExcuseLetterModal prüfen
            excuse_modal = ExcuseLetterModal(summaries)
            app.push_screen(excuse_modal)
            await pilot.pause()

            table = excuse_modal.query_one("#excuse_table", DataTable)
            self.assertEqual(table.row_count, 2)

            # Initial: nur offene ausgewählt (2026-10-02)
            self.assertIn("2026-10-02", excuse_modal.selected_dates)
            self.assertNotIn("2026-10-05", excuse_modal.selected_dates)

            # Teste [Select All]
            btn_all = excuse_modal.query_one("#btn_el_all", Button)
            btn_all.press()
            await pilot.pause()
            self.assertEqual(len(excuse_modal.selected_dates), 2)

            # Teste [Clear]
            btn_clear = excuse_modal.query_one("#btn_el_clear", Button)
            btn_clear.press()
            await pilot.pause()
            self.assertEqual(len(excuse_modal.selected_dates), 0)

            # Teste [Only Open]
            btn_open = excuse_modal.query_one("#btn_el_open", Button)
            btn_open.press()
            await pilot.pause()
            self.assertEqual(len(excuse_modal.selected_dates), 1)
            self.assertIn("2026-10-02", excuse_modal.selected_dates)

            # Teste Toggle über Row-Selection
            excuse_modal._toggle_date("2026-10-05")
            await pilot.pause()
            self.assertEqual(len(excuse_modal.selected_dates), 2)

            # Teste PDF Generierungs-Action
            with patch("excuse_service.open_pdf_in_system_viewer", return_value=True):
                btn_gen = excuse_modal.query_one("#btn_el_generate", Button)
                btn_gen.press()
                await pilot.pause()

            # Teste Back Button: Soll zu AbsencesScreen zurückkehren und NICHT SchoolConfigModal öffnen!
            btn_back = excuse_modal.query_one("#btn_el_back", Button)
            btn_back.press()
            await pilot.pause()
            self.assertIsInstance(app.screen, AbsencesScreen)

    async def test_excuse_letter_modal_hide_lateness_toggle(self):
        from tui_app import AufgabenDetectorApp, ExcuseLetterModal
        from textual.widgets import Button, DataTable

        lessons = [
            MissedLesson(date="2026-10-02", subject="SWP", period_num=1, start_time="08:00", end_time="08:50", duration_minutes=50),
            MissedLesson(date="2026-10-20", subject="INFI", period_num=7, start_time="14:25", end_time="14:36", duration_minutes=11, reason="Verspätung"),
        ]
        summaries = [
            SubjectAbsenceSummary(subject="SWP", total_hours=1, missed_lessons=[lessons[0]]),
            SubjectAbsenceSummary(subject="INFI", total_hours=1, missed_lessons=[lessons[1]]),
        ]

        app = AufgabenDetectorApp()
        async with app.run_test() as pilot:
            excuse_modal = ExcuseLetterModal(summaries)
            app.push_screen(excuse_modal)
            await pilot.pause()

            # 1. Standardmäßig aktiv: Verspätung (11 Min < 50 Min) ist ausgeblendet
            self.assertTrue(excuse_modal.hide_lateness)
            btn_toggle = excuse_modal.query_one("#btn_el_filter_lateness", Button)
            self.assertIn("ON", str(btn_toggle.label))
            table = excuse_modal.query_one("#excuse_table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertEqual(len(excuse_modal.visible_absences), 1)
            self.assertEqual(excuse_modal.visible_absences[0].date, "2026-10-02")

            # 2. Button drücken -> deaktivieren (Verspätungen einblenden)
            btn_toggle.press()
            await pilot.pause()
            self.assertFalse(excuse_modal.hide_lateness)
            self.assertIn("OFF", str(btn_toggle.label))
            self.assertEqual(table.row_count, 2)
            self.assertEqual(len(excuse_modal.visible_absences), 2)

            # 3. Nochmal drücken -> wieder aktivieren (ausblenden)
            btn_toggle.press()
            await pilot.pause()
            self.assertTrue(excuse_modal.hide_lateness)
            self.assertIn("ON", str(btn_toggle.label))
            self.assertEqual(table.row_count, 1)


if __name__ == "__main__":
    unittest.main()

