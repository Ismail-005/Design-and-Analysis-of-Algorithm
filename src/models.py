"""
models.py
Core dataclasses for the GIK timetable scheduling system.
Enhanced with:
  - Smart lab room detection from course code / title
  - 3-hour continuous LabSession model
  - Allowed lecture buildings per course prefix
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re


# ── Keywords that force FME Lab regardless of prefix ──────────────────────────
FME_KEYWORDS = [
    "fluid", "heat", "vibration", "workshop", "mos",
    "mechanics of solid", "vehicle", "thermo-fluid",
    "mechatronics", "manufacturing",
]

# ── Lab room ID → fallback if primary full ────────────────────────────────────
LAB_FALLBACKS: dict[str, list[str]] = {
    "FCSE_SE_LAB": ["FES_SE_LAB"],
    "FES_PH_LAB":  ["FES_PH_LAB2"],
    "ACB_AI_LAB":  ["ACB_DA_LAB"],
    "ACB_CYS_LAB": ["ACB_AI_LAB"],
    "FCME_MM_LAB": ["FCME_CH_LAB"],
    "FCME_CH_LAB": ["FCME_MM_LAB"],
    "FME_LAB":     ["TBA_ROOM"],
    "BB_PC_LAB":   ["TBA_ROOM"],
    "FBS_LAB":     ["TBA_ROOM"],
}


@dataclass
class Course:
    code: str
    section: str
    title: str
    credit_hours: int
    type: str           # "lecture" | "lab"
    instructor: str
    program: str
    capacity: int
    source_id: str = ""

    # ── Identity ──────────────────────────────────────────────────────────────
    @property
    def key(self) -> str:
        if self.source_id:
            return self.source_id
        return f"{self.code}_{self.section}"

    @property
    def display(self) -> str:
        sec = f" {self.section}" if self.section else ""
        return f"{self.code}{sec}"

    # ── Type detection ────────────────────────────────────────────────────────
    @property
    def is_lab(self) -> bool:
        """True if code ends with 'L' OR type explicitly set to 'lab'."""
        return self.code.upper().endswith("L") or self.type.lower() == "lab"

    @property
    def is_lecture(self) -> bool:
        return not self.is_lab

    @property
    def instructor_unknown(self) -> bool:
        return self.instructor.upper().strip() in ("TBA", "TBD", "")

    @property
    def course_level(self) -> str:
        """
        First numeric digit in the course code, used as an approximate cohort year.
        Examples: CS101 -> 1, CE221L -> 2, AI4xx -> 4.
        """
        m = re.search(r"\d", self.code)
        return m.group(0) if m else "X"

    @property
    def cohort_key(self) -> str:
        """
        Clash key for student cohorts. A whole program spans multiple years, so
        using only program is too restrictive for real timetable data.
        SC-prefix courses (Social Sciences) are open electives not tied to a
        fixed cohort, so they skip cohort conflict checking entirely.
        """
        if self.prefix == "SC":
            return ""
        return f"{self.program}:{self.course_level}" if self.program else ""

    # ── Code prefix (alpha chars before digits) ───────────────────────────────
    @property
    def prefix(self) -> str:
        """'CS221L' → 'CS',  'CE211' → 'CE',  'CYS331' → 'CYS'"""
        p = ""
        for ch in self.code.upper():
            if ch.isalpha():
                p += ch
            else:
                break
        # Strip trailing L from lab prefix so CS221L → CS, not CSL
        if self.is_lab and p.endswith("L") and len(p) > 1:
            p = p[:-1]
        return p

    # ── Smart lab room assignment ─────────────────────────────────────────────
    @property
    def required_lab_room_ids(self) -> list[str]:
        """
        Return ordered list of preferred room_ids for this lab.
        First element = primary, rest = fallbacks.
        """
        if not self.is_lab:
            return []

        code  = self.code.upper()
        title = self.title.lower()
        pfx   = self.prefix

        # IF Lab → always TBA
        if pfx == "IF":
            return ["TBA_ROOM"]

        # Physics lab
        if pfx == "PH":
            return ["FES_PH_LAB", "FES_PH_LAB2"]

        # FME keyword in title takes priority over prefix
        if any(kw in title for kw in FME_KEYWORDS):
            return ["FME_LAB", "TBA_ROOM"]

        # Mechanical / Manufacturing
        if pfx in ("ME", "MTE"):
            return ["FME_LAB", "TBA_ROOM"]

        # Materials / Chemical
        if pfx in ("MM", "CH"):
            return ["FCME_MM_LAB", "FCME_CH_LAB"]

        # AI labs
        if pfx == "AI":
            return ["ACB_AI_LAB", "ACB_DA_LAB"]

        # CYS labs
        if pfx in ("CY", "CYS"):
            return ["ACB_CYS_LAB", "ACB_AI_LAB"]

        # Data Science
        if pfx == "DS" or "data" in title:
            return ["ACB_DA_LAB", "ACB_AI_LAB"]

        # CS / CE / SE → FCSE SE Lab primary, FES SE Lab backup
        if pfx in ("CS", "CE", "SE"):
            return ["FCSE_SE_LAB", "FES_SE_LAB"]

        # EE labs → FBS Lab
        if pfx == "EE":
            return ["FBS_LAB", "TBA_ROOM"]

        # ES / BES → FES SE Lab
        if pfx == "ES":
            return ["FES_SE_LAB", "ACB_AI_LAB"]

        # HM labs → BB PC Lab
        if pfx == "HM":
            return ["BB_PC_LAB", "TBA_ROOM"]

        # CV labs → FES
        if pfx == "CV":
            return ["FES_SE_LAB", "TBA_ROOM"]

        return ["TBA_ROOM"]

    # ── Allowed lecture buildings ─────────────────────────────────────────────
    @property
    def allowed_lecture_buildings(self) -> list[str]:
        pfx = self.prefix
        if pfx in ("HM", "MS", "SC", "AF", "EM"):
            return ["BB"]
        if pfx in ("MT", "ES", "PH"):
            return ["ACB", "FES"]
        if pfx in ("CS", "CE", "DS", "AI"):
            return ["ACB", "FCSE"]
        if pfx in ("CY", "CYS", "SE"):
            return ["ACB", "FCSE"]
        if pfx == "EE":
            return ["FEE"]
        if pfx == "ME":
            return ["FME"]
        if pfx in ("MM", "CH"):
            return ["FMCE"]
        if pfx == "CV":
            return ["ACB", "FES"]
        if pfx == "IF":
            return ["FME"]
        return ["ACB"]


@dataclass
class Room:
    room_id: str
    room_name: str
    building: str
    type: str       # "lecture_hall" | "main_hall" | "lab"
    capacity: int

    @property
    def is_lab(self) -> bool:
        return self.type == "lab"

    @property
    def is_lecture(self) -> bool:
        return self.type in ("lecture_hall", "main_hall")


@dataclass
class TimeSlot:
    slot_id: str
    day: str
    start_time: str
    end_time: str
    slot_index: int
    day_type: str   # "regular" | "friday"

    @property
    def label(self) -> str:
        return f"{self.start_time}–{self.end_time}"

    @property
    def is_friday(self) -> bool:
        return self.day_type == "friday"


@dataclass
class LabSession:
    """
    A 3-hour continuous lab block occupying exactly 3 consecutive slots.
    """
    course: Course
    room: Room
    day: str
    slots: list[TimeSlot]   # exactly 3

    @property
    def start_time(self) -> str:
        return self.slots[0].start_time

    @property
    def end_time(self) -> str:
        return self.slots[-1].end_time

    @property
    def label(self) -> str:
        return f"{self.start_time}–{self.end_time}"

    @property
    def slot_ids(self) -> list[str]:
        return [s.slot_id for s in self.slots]

    def to_dict(self) -> dict:
        return {
            "course_key":   self.course.key,
            "code":         self.course.code,
            "section":      self.course.section,
            "title":        self.course.title,
            "session_type": "LAB (3h continuous)",
            "instructor":   self.course.instructor,
            "program":      self.course.program,
            "capacity":     self.course.capacity,
            "credit_hours": self.course.credit_hours,
            "room_id":      self.room.room_id,
            "room_name":    self.room.room_name,
            "building":     self.room.building,
            "day":          self.day,
            "start_time":   self.start_time,
            "end_time":     self.end_time,
            "slot_ids":     " | ".join(self.slot_ids),
        }


@dataclass
class Assignment:
    """Single-slot assignment for a lecture."""
    course: Course
    room: Room
    slot: TimeSlot

    def to_dict(self) -> dict:
        return {
            "course_key":   self.course.key,
            "code":         self.course.code,
            "section":      self.course.section,
            "title":        self.course.title,
            "session_type": "Lecture",
            "instructor":   self.course.instructor,
            "program":      self.course.program,
            "capacity":     self.course.capacity,
            "credit_hours": self.course.credit_hours,
            "room_id":      self.room.room_id,
            "room_name":    self.room.room_name,
            "building":     self.room.building,
            "day":          self.slot.day,
            "start_time":   self.slot.start_time,
            "end_time":     self.slot.end_time,
            "slot_ids":     self.slot.slot_id,
        }


@dataclass
class ScheduleResult:
    assignments:  list[Assignment] = field(default_factory=list)
    lab_sessions: list[LabSession] = field(default_factory=list)
    unscheduled:  list[Course]     = field(default_factory=list)

    @property
    def total_courses(self) -> int:
        return len(self.assignments) + len(self.lab_sessions) + len(self.unscheduled)

    @property
    def success_rate(self) -> float:
        placed = len(self.assignments) + len(self.lab_sessions)
        if self.total_courses == 0:
            return 0.0
        return placed / self.total_courses * 100

    @property
    def all_rows(self) -> list[dict]:
        rows = [a.to_dict()  for a in self.assignments]
        rows += [ls.to_dict() for ls in self.lab_sessions]
        return rows
