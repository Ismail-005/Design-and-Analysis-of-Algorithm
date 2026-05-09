"""
parser.py
Reads and validates all input files (CSV / Excel) into model objects.
Supported formats:
  courses   → courses.csv  or  courses_offered.xlsx
  rooms     → rooms.xlsx   or  rooms.csv
  timeslots → timeslots.csv
"""

import os
import pandas as pd
from pathlib import Path
from src.models import Course, Room, TimeSlot


# ─────────────────────────── helpers ──────────────────────────────────────────

def _read_file(path: str | Path) -> pd.DataFrame:
    """Read CSV or Excel based on file extension."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    if p.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(p, dtype=str).fillna("")
    return pd.read_csv(p, dtype=str).fillna("")


def _required(row: pd.Series, col: str, path: str) -> str:
    val = str(row.get(col, "")).strip()
    if val == "":
        raise ValueError(f"Missing required column '{col}' in {path}")
    return val


# ─────────────────────────── public loaders ───────────────────────────────────

def load_courses(path: str | Path) -> list[Course]:
    """
    Expected columns (case-insensitive):
      code, section, title, credit_hours, type, instructor, program, capacity
    """
    df = _read_file(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    courses: list[Course] = []
    for i, row in df.iterrows():
        try:
            code         = _required(row, "code", str(path))
            section      = str(row.get("section", "")).strip()
            title        = str(row.get("title", "")).strip() or code
            credit_hours = int(str(row.get("credit_hours", "1")).strip() or 1)
            ctype        = str(row.get("type", "lecture")).strip().lower()
            instructor   = str(row.get("instructor", "TBA")).strip()
            program      = str(row.get("program", "")).strip()
            capacity     = int(str(row.get("capacity", "30")).strip() or 30)

            courses.append(Course(
                code=code, section=section, title=title,
                credit_hours=credit_hours, type=ctype,
                instructor=instructor, program=program, capacity=capacity,
                source_id=f"{code}_{section}_{i + 2}",
            ))
        except Exception as e:
            print(f"  [parser] Skipping row {i+2} in courses file: {e}")

    print(f"[parser] Loaded {len(courses)} courses from {Path(path).name}")
    return courses


def load_rooms(path: str | Path) -> list[Room]:
    """
    Expected columns:
      room_id, room_name, building, type, capacity
    """
    df = _read_file(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    rooms: list[Room] = []
    for i, row in df.iterrows():
        try:
            room_id   = _required(row, "room_id",   str(path))
            room_name = str(row.get("room_name", room_id)).strip()
            building  = str(row.get("building",  "")).strip()
            rtype     = str(row.get("type",       "lecture_hall")).strip().lower()
            capacity  = int(str(row.get("capacity", "60")).strip() or 60)

            rooms.append(Room(
                room_id=room_id, room_name=room_name,
                building=building, type=rtype, capacity=capacity,
            ))
        except Exception as e:
            print(f"  [parser] Skipping row {i+2} in rooms file: {e}")

    print(f"[parser] Loaded {len(rooms)} rooms from {Path(path).name}")
    return rooms


def load_timeslots(path: str | Path) -> list[TimeSlot]:
    """
    Expected columns:
      slot_id, day, start_time, end_time, slot_index, day_type
    """
    df = _read_file(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    slots: list[TimeSlot] = []
    for i, row in df.iterrows():
        try:
            slot_id    = _required(row, "slot_id",    str(path))
            day        = _required(row, "day",         str(path))
            start_time = str(row.get("start_time", "")).strip()
            end_time   = str(row.get("end_time",   "")).strip()
            slot_index = int(str(row.get("slot_index", "1")).strip() or 1)
            day_type   = str(row.get("day_type", "regular")).strip().lower()

            slots.append(TimeSlot(
                slot_id=slot_id, day=day,
                start_time=start_time, end_time=end_time,
                slot_index=slot_index, day_type=day_type,
            ))
        except Exception as e:
            print(f"  [parser] Skipping row {i+2} in timeslots file: {e}")

    print(f"[parser] Loaded {len(slots)} time slots from {Path(path).name}")
    return slots


def load_all(data_dir: str | Path) -> tuple[list[Course], list[TimeSlot], list[Room]]:
    """
    Convenience loader: auto-discovers files in data_dir.
    Looks for: courses.csv / courses.xlsx, rooms.xlsx / rooms.csv, timeslots.csv
    """
    d = Path(data_dir)
    candidates = {
        "courses":   ["courses.csv", "courses.xlsx", "courses_offered.csv", "courses_offered.xlsx"],
        "rooms":     ["rooms.xlsx", "rooms.csv"],
        "timeslots": ["timeslots.csv", "timeslots.xlsx", "time_slots.csv"],
    }

    def find(key):
        for name in candidates[key]:
            p = d / name
            if p.exists():
                return p
        raise FileNotFoundError(
            f"Could not find {key} file in {d}. Expected one of: {candidates[key]}"
        )

    courses   = load_courses(find("courses"))
    rooms     = load_rooms(find("rooms"))
    timeslots = load_timeslots(find("timeslots"))
    return courses, timeslots, rooms
