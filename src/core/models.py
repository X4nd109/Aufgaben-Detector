"""
models.py - Datenmodelle für Aufgaben aus Moodle und Teams.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import datetime
import re


@dataclass
class TaskAttachment:
    name: str
    url: str
    size: str = ""
    local_path: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Task:
    id: str
    platform: str  # "moodle" oder "teams"
    course: str  # z.B. "SWP", "NW2", "BET"
    course_full: str  # Vollständiger Kursname
    title: str
    due_date_str: str  # z.B. "Morgen, 28. Sept., 08:00"
    status: str  # "offen", "abgegeben", "ueberfaellig", "bewertet"
    status_display: str  # z.B. "Nicht abgegeben", "Zur Bewertung abgegeben"
    url: str  # Direkter Link zur Abgabeseite
    due_timestamp: Optional[float] = None
    description: str = ""
    attachments: List[TaskAttachment] = field(default_factory=list)
    details_loaded: bool = False
    class_id: Optional[str] = None  # Relevant für Teams
    download_dir: Optional[str] = None
    teacher: str = ""  # Kürzel vom Lehrer, z.B. "KRD", "BIM/EIJ", "WAW"

    def __setattr__(self, name, value):
        if name == "status_display" and isinstance(value, str):
            val_lower = value.lower()
            if "nichts abgegeben" in val_lower or "für diese aufgabe" in val_lower or "fuer diese aufgabe" in val_lower:
                value = "noch offen"
        super().__setattr__(name, value)

    def __post_init__(self):
        if self.status_display and ("nichts abgegeben" in self.status_display.lower() or "für diese aufgabe" in self.status_display.lower() or "fuer diese aufgabe" in self.status_display.lower()):
            self.status_display = "noch offen"

    @property
    def is_overdue(self) -> bool:
        if self.id == "manual_welcome_setup_guide":
            return False
        if self.is_completed:
            return False
        if self.status.lower() in ["ueberfaellig", "überfällig", "overdue"]:
            return True
        lower_due = self.due_date_str.lower()
        if any(k in lower_due for k in ["überfällig", "ueberfaellig", "overdue", "gestern", "yesterday", "vor "]):
            return True
        if self.due_timestamp and self.due_timestamp < datetime.datetime.now().timestamp():
            return True
        return False

    @property
    def is_due_soon(self) -> bool:
        """Fällig innerhalb der nächsten 48 Stunden?"""
        if self.is_completed or self.is_overdue:
            return False
        lower = self.due_date_str.lower()
        if any(k in lower for k in ["heute", "today", "morgen", "tomorrow"]):
            return True
        if self.due_timestamp:
            diff = self.due_timestamp - datetime.datetime.now().timestamp()
            if 0 <= diff <= 48 * 3600:
                return True
        return False

    @property
    def is_completed(self) -> bool:
        if self.status.lower() in ["abgegeben", "bewertet", "completed", "done", "abgeschlossen", "zurueckgegeben", "zurückgegeben", "returned"]:
            return True
        if self.status_display and any(kw in self.status_display.lower() for kw in ["abgegeben", "bewertet", "completed", "done", "erledigt", "zurückgegeben", "zurueckgegeben", "returned"]):
            return True
        return False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["attachments"] = [a.to_dict() if isinstance(a, TaskAttachment) else a for a in self.attachments]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        attachments = []
        for att in data.get("attachments", []):
            if isinstance(att, dict):
                attachments.append(TaskAttachment(**att))
            elif isinstance(att, TaskAttachment):
                attachments.append(att)
        data_copy = dict(data)
        data_copy["attachments"] = attachments
        return cls(**data_copy)


@dataclass
class UntisLesson:
    id: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    period_num: int
    subject: str
    teacher: str = ""
    room: str = ""
    is_cancelled: bool = False
    group: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "UntisLesson":
        return cls(**d)


@dataclass
class UntisAbsenceInterval:
    id: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    reason: str = ""
    status: str = "Offen"
    text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "UntisAbsenceInterval":
        return cls(**d)


@dataclass
class MissedLesson:
    date: str  # YYYY-MM-DD
    subject: str
    period_num: int
    start_time: str
    end_time: str
    teacher: str = ""
    room: str = ""
    is_cancelled: bool = False
    reason: str = ""
    absence_status: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MissedLesson":
        return cls(**d)


@dataclass
class SubjectAbsenceSummary:
    subject: str
    total_hours: int = 0
    missed_lessons: List[MissedLesson] = field(default_factory=list)
    last_date: str = ""

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "total_hours": self.total_hours,
            "missed_lessons": [m.to_dict() for m in self.missed_lessons],
            "last_date": self.last_date,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SubjectAbsenceSummary":
        lessons = [MissedLesson.from_dict(m) for m in d.get("missed_lessons", [])]
        return cls(
            subject=d.get("subject", ""),
            total_hours=d.get("total_hours", len(lessons)),
            missed_lessons=lessons,
            last_date=d.get("last_date", ""),
        )


@dataclass
class DailyAbsenceSummary:
    date: str  # YYYY-MM-DD
    date_display: str  # DD.MM.YYYY
    school_hours: int = 0  # e.g. 4
    duration_str: str = "0:00"  # e.g. "3:20"
    subjects: List[str] = field(default_factory=list)
    status: str = "Offen"
    lessons: List[MissedLesson] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "date_display": self.date_display,
            "school_hours": self.school_hours,
            "duration_str": self.duration_str,
            "subjects": self.subjects,
            "status": self.status,
            "lessons": [m.to_dict() for m in self.lessons],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DailyAbsenceSummary":
        return cls(
            date=d.get("date", ""),
            date_display=d.get("date_display", ""),
            school_hours=d.get("school_hours", 0),
            duration_str=d.get("duration_str", "0:00"),
            subjects=d.get("subjects", []),
            status=d.get("status", "Offen"),
            lessons=[MissedLesson.from_dict(m) for m in d.get("lessons", [])],
        )


@dataclass
class UntisExam:
    id: str  # Unique exam ID or key, e.g. "20261019_1515_BET"
    exam_type: str  # "SA", "TE", "PR"
    exam_type_display: str  # "Schularbeit", "Test", "Prüfung"
    subject: str  # e.g. "BET", "SWP PM", "D", "E"
    name: str  # e.g. "Betriebstechnik"
    text: str  # e.g. "1. PLF"
    date: str  # "YYYY-MM-DD" e.g. "2026-10-19"
    date_display: str  # "DD.MM.YYYY" e.g. "19.10.2026"
    start_time: str  # "15:15"
    end_time: str  # "16:05"
    teachers: List[str] = field(default_factory=list)
    rooms: List[str] = field(default_factory=list)
    custom_topics: str = ""  # Vom Schüler selbst eingetragener Stoff
    is_past: bool = False
    days_until: int = 0
    url: str = ""  # WebUntis Lesson Details URL
    group: str = ""  # Subgroup: "X", "Y" or "" for whole class
    is_custom: bool = False  # True if manually created by the user

    @property
    def countdown_display(self) -> str:
        if self.is_past:
            if self.days_until == 0:
                return "Today"
            return f"{abs(self.days_until)}d ago"
        if self.days_until == 0:
            return "Today"
        elif self.days_until == 1:
            return "Tomorrow"
        return f"in {self.days_until}d"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "exam_type": self.exam_type,
            "exam_type_display": self.exam_type_display,
            "subject": self.subject,
            "name": self.name,
            "text": self.text,
            "date": self.date,
            "date_display": self.date_display,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "teachers": self.teachers,
            "rooms": self.rooms,
            "custom_topics": self.custom_topics,
            "is_past": self.is_past,
            "days_until": self.days_until,
            "url": self.url,
            "group": self.group,
            "is_custom": self.is_custom,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UntisExam":
        return cls(
            id=str(d.get("id", "")),
            exam_type=d.get("exam_type", "TE"),
            exam_type_display=d.get("exam_type_display", "Test"),
            subject=d.get("subject", ""),
            name=d.get("name", ""),
            text=d.get("text", ""),
            date=d.get("date", ""),
            date_display=d.get("date_display", ""),
            start_time=d.get("start_time", ""),
            end_time=d.get("end_time", ""),
            teachers=d.get("teachers", []),
            rooms=d.get("rooms", []),
            custom_topics=d.get("custom_topics", ""),
            is_past=d.get("is_past", False),
            days_until=d.get("days_until", 0),
            url=d.get("url", ""),
            group=d.get("group", ""),
            is_custom=bool(d.get("is_custom", False) or str(d.get("id", "")).startswith("custom_")),
        )
