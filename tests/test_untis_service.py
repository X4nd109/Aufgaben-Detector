"""
test_untis_service.py - Unit tests for WebUntis matching and absence calculations.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import src

from models import UntisLesson, UntisAbsenceInterval, MissedLesson, SubjectAbsenceSummary
from untis_service import (
    time_to_minutes,
    intervals_overlap,
    normalize_subject_name,
    match_absences_with_timetable,
    format_untis_time,
)


class TestUntisService(unittest.TestCase):

    def test_time_conversions(self):
        self.assertEqual(time_to_minutes("08:00"), 480)
        self.assertEqual(time_to_minutes("08:50"), 530)
        self.assertEqual(time_to_minutes("10:45"), 645)
        self.assertEqual(time_to_minutes("14:15"), 855)

    def test_intervals_overlap(self):
        # Lesson 08:50 - 09:40 vs Absence 08:50 - 10:45 -> overlaps
        self.assertTrue(intervals_overlap("08:50", "09:40", "08:50", "10:45"))
        # Lesson 09:55 - 10:45 vs Absence 08:50 - 10:45 -> overlaps
        self.assertTrue(intervals_overlap("09:55", "10:45", "08:50", "10:45"))
        # Lesson 08:00 - 08:50 vs Absence 08:50 - 10:45 -> no overlap (touching boundary)
        self.assertFalse(intervals_overlap("08:00", "08:50", "08:50", "10:45"))
        # Lesson 10:45 - 11:35 vs Absence 08:50 - 10:45 -> no overlap (touching boundary)
        self.assertFalse(intervals_overlap("10:45", "11:35", "08:50", "10:45"))

    def test_normalize_subject_name(self):
        self.assertEqual(normalize_subject_name("SWP"), "SWP")
        self.assertEqual(normalize_subject_name("SWP1x"), "SWP")
        self.assertEqual(normalize_subject_name("SWP_1y"), "SWP")
        self.assertEqual(normalize_subject_name("SWP PM"), "SWP PM")
        self.assertEqual(normalize_subject_name("SWP_PM"), "SWP PM")
        self.assertEqual(normalize_subject_name("NW2"), "NW2")
        self.assertEqual(normalize_subject_name("D"), "D")

    def test_format_untis_time(self):
        self.assertEqual(format_untis_time(850), "08:50")
        self.assertEqual(format_untis_time(1045), "10:45")
        self.assertEqual(format_untis_time("8:50"), "08:50")
        self.assertEqual(format_untis_time("14:15"), "14:15")

    def test_user_scenario_matching(self):
        """
        User scenario:
        - Absence on 2026-09-30 from 08:50 to 10:45.
        - Lessons on 2026-09-30:
          * 08:00 - 08:50: NW2 (Period 1) -> NOT missed
          * 08:50 - 09:40: SWP1x (Period 2) -> MISSED
          * 09:55 - 10:45: D (Period 3) -> MISSED
          * 10:45 - 11:35: BET (Period 4) -> NOT missed
        - Lessons on another Wednesday (2026-10-07):
          * 08:50 - 09:40: AMEC -> NOT MISSED (since absence was specifically on 2026-09-30)
        """
        absences = [
            UntisAbsenceInterval(
                id="abs_1",
                date="2026-09-30",
                start_time="08:50",
                end_time="10:45",
                reason="Arztbesuch",
                status="Entschuldigt",
            )
        ]

        lessons = [
            # 2026-09-30 lessons
            UntisLesson(id="l1", date="2026-09-30", start_time="08:00", end_time="08:50", period_num=1, subject="NW2"),
            UntisLesson(id="l2", date="2026-09-30", start_time="08:50", end_time="09:40", period_num=2, subject="SWP1x", group="1x"),
            UntisLesson(id="l3", date="2026-09-30", start_time="09:55", end_time="10:45", period_num=3, subject="D"),
            UntisLesson(id="l4", date="2026-09-30", start_time="10:45", end_time="11:35", period_num=4, subject="BET"),
            # Another date's lessons (should not be matched!)
            UntisLesson(id="l5", date="2026-10-07", start_time="08:50", end_time="09:40", period_num=2, subject="AMEC"),
        ]

        summaries = match_absences_with_timetable(absences, lessons, student_group="1x")

        # Must have exactly 2 missed subjects: SWP (1 hour) and D (1 hour)
        subj_map = {s.subject: s.total_hours for s in summaries}
        self.assertEqual(len(summaries), 2)
        self.assertEqual(subj_map.get("SWP"), 1)
        self.assertEqual(subj_map.get("D"), 1)
        self.assertNotIn("AMEC", subj_map)
        self.assertNotIn("NW2", subj_map)
        self.assertNotIn("BET", subj_map)

    def test_group_split_filtering(self):
        """
        Parallel lessons:
        SWP_1x (group 1x) vs SWP_1y (group 1y) at 13:25 - 14:15.
        With student_group='1x', only the 1x lesson must be counted (1 hour total, NOT 2).
        """
        absences = [
            UntisAbsenceInterval(
                id="abs_split",
                date="2026-10-05",
                start_time="13:00",
                end_time="15:00",
                reason="Krank",
                status="Entschuldigt",
            )
        ]

        lessons = [
            UntisLesson(id="l_1x", date="2026-10-05", start_time="13:25", end_time="14:15", period_num=7, subject="SWP_1x", group="1x", teacher="RAM"),
            UntisLesson(id="l_1y", date="2026-10-05", start_time="13:25", end_time="14:15", period_num=7, subject="SWP_1y", group="1y", teacher="MJA"),
        ]

        summaries = match_absences_with_timetable(absences, lessons, student_group="X")
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].subject, "SWP")
        self.assertEqual(summaries[0].total_hours, 1)
        self.assertEqual(summaries[0].missed_lessons[0].teacher, "RAM")

        summaries_y = match_absences_with_timetable(absences, lessons, student_group="Y")
        self.assertEqual(len(summaries_y), 1)
        self.assertEqual(summaries_y[0].subject, "SWP")
        self.assertEqual(summaries_y[0].total_hours, 1)
        self.assertEqual(summaries_y[0].missed_lessons[0].teacher, "MJA")

    def test_cancelled_lessons_counted(self):
        """
        Cancelled lessons (is_cancelled=True) must still be counted as agreed with the user.
        """
        absences = [
            UntisAbsenceInterval(
                id="abs_canc",
                date="2026-10-06",
                start_time="08:00",
                end_time="09:40",
                reason="Arzt",
                status="Offen",
            )
        ]

        lessons = [
            UntisLesson(id="l_c1", date="2026-10-06", start_time="08:00", end_time="08:50", period_num=1, subject="E1x", is_cancelled=True),
            UntisLesson(id="l_c2", date="2026-10-06", start_time="08:50", end_time="09:40", period_num=2, subject="SWP1x", is_cancelled=False),
        ]

        summaries = match_absences_with_timetable(absences, lessons, student_group="1x")
        subj_map = {s.subject: s.total_hours for s in summaries}
        self.assertEqual(subj_map.get("E"), 1)
        self.assertEqual(subj_map.get("SWP"), 1)

    def test_lateness_partial_period_matching(self):
        """
        Tests that an absence with a short duration (e.g. 11 mins late) calculates
        the exact overlap window, retains the original period times, and sets duration_minutes.
        """
        absences = [
            UntisAbsenceInterval(
                id="abs_late",
                date="2026-10-20",
                start_time="14:25",
                end_time="14:36",
                reason="Verspätung",
                status="Offen",
            )
        ]
        lessons = [
            UntisLesson(
                id="l_infi",
                date="2026-10-20",
                start_time="14:25",
                end_time="15:15",
                period_num=7,
                subject="INFI",
            )
        ]
        summaries = match_absences_with_timetable(absences, lessons, student_group="X")
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].subject, "INFI")
        self.assertEqual(summaries[0].total_hours, 1)

        missed = summaries[0].missed_lessons[0]
        self.assertEqual(missed.start_time, "14:25")
        self.assertEqual(missed.end_time, "14:36")
        self.assertEqual(missed.lesson_start_time, "14:25")
        self.assertEqual(missed.lesson_end_time, "15:15")
        self.assertEqual(missed.duration_minutes, 11)
        self.assertEqual(missed.reason, "Verspätung")

    def test_resolve_webuntis_server(self):
        from untis_service import resolve_webuntis_server
        # 1. School as simple name
        base, school = resolve_webuntis_server(school="spengergasse")
        self.assertEqual(school, "spengergasse")
        self.assertIn("spengergasse", base)

        # 2. School as full URL
        base, school = resolve_webuntis_server(school="https://spengergasse.webuntis.com/WebUntis/?school=spengergasse")
        self.assertEqual(school, "spengergasse")
        self.assertIn("spengergasse", base)

    def test_school_config_persistence(self):
        from config import save_untis_school, _load_untis_school
        original = _load_untis_school()
        try:
            save_untis_school("htl_wien")
            self.assertEqual(_load_untis_school(), "htl_wien")
        finally:
            save_untis_school(original)


if __name__ == "__main__":
    unittest.main()
