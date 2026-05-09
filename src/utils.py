"""
utils.py
Utility helpers: bitmask slot sets, statistics, color palette.
"""

from __future__ import annotations
from collections import defaultdict
from src.models import Assignment, LabSession, TimeSlot, Room, ScheduleResult

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# ─────────────────────────── Bitmask slot set ─────────────────────────────────

class SlotBitmask:
    """O(1) overlap detection via bitwise AND."""

    def __init__(self, total_slots: int = 64):
        self._mask  = 0
        self._total = total_slots

    def set(self, idx: int)   -> None: self._mask |=  (1 << idx)
    def clear(self, idx: int) -> None: self._mask &= ~(1 << idx)
    def is_set(self, idx: int)-> bool: return bool(self._mask & (1 << idx))
    def overlaps(self, other: SlotBitmask) -> bool: return bool(self._mask & other._mask)
    def count(self) -> int: return bin(self._mask).count("1")
    def __repr__(self): return f"SlotBitmask({bin(self._mask)})"


def slot_index_map(slots: list[TimeSlot]) -> dict[str, int]:
    return {s.slot_id: i for i, s in enumerate(slots)}


def slots_by_day(slots: list[TimeSlot]) -> dict[str, list[TimeSlot]]:
    grouped: dict[str, list[TimeSlot]] = defaultdict(list)
    for s in slots:
        grouped[s.day].append(s)
    return {day: sorted(grouped[day], key=lambda x: x.slot_index)
            for day in DAY_ORDER if day in grouped}


# ─────────────────────────── Statistics ───────────────────────────────────────

def utilisation_stats(result: ScheduleResult, rooms: list[Room],
                      slots: list[TimeSlot]) -> dict:
    room_counts: dict[str, int]        = defaultdict(int)
    instructor_counts: dict[str, int]  = defaultdict(int)
    day_counts: dict[str, int]         = defaultdict(int)

    for a in result.assignments:
        room_counts[a.room.room_name]          += 1
        instructor_counts[a.course.instructor] += 1
        day_counts[a.slot.day]                 += 1

    for ls in result.lab_sessions:
        room_counts[ls.room.room_name]          += 1
        instructor_counts[ls.course.instructor] += 1
        day_counts[ls.day]                      += 1

    total    = len(result.assignments) + len(result.lab_sessions)
    n_slots  = len(slots)
    n_rooms  = len([r for r in rooms if r.room_id != "TBA_ROOM"])

    busiest_room = max(room_counts.items(),  key=lambda x: x[1]) if room_counts else ("—", 0)
    busiest_inst = max(instructor_counts.items(), key=lambda x: x[1]) if instructor_counts else ("—", 0)
    busiest_day  = max(day_counts.items(),   key=lambda x: x[1]) if day_counts else ("—", 0)

    return {
        "total_placed":         total,
        "lectures_placed":      len(result.assignments),
        "labs_placed":          len(result.lab_sessions),
        "unscheduled":          len(result.unscheduled),
        "success_rate":         round(result.success_rate, 1),
        "rooms_used":           len(room_counts),
        "busiest_room":         busiest_room,
        "busiest_instructor":   busiest_inst,
        "busiest_day":          busiest_day,
        "avg_classes_per_slot": round(total / n_slots, 2) if n_slots else 0,
    }


def lab_room_usage(result: ScheduleResult) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for ls in result.lab_sessions:
        counts[ls.room.room_name] += 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def lecture_building_usage(result: ScheduleResult) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for a in result.assignments:
        counts[a.room.building] += 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ─────────────────────────── Program color palette ────────────────────────────

PROGRAM_COLORS: dict[str, str] = {
    "BAI": "#D6EAF8", "BCS": "#D5F5E3", "BDS": "#FEF9E7",
    "CYS": "#FDEBD0", "SE":  "#F0E6FF", "BCE": "#E8F8F5",
    "BEE": "#FDF2E9", "EEE": "#FDFEFE", "EEP": "#EBF5FB",
    "BME": "#E8F6F3", "MTE": "#FEF5E7", "CME": "#F4ECF7",
    "MGS": "#EAFAF1", "BES": "#EBF5FB", "ES":  "#F2F3F4",
    "DS":  "#FEF9E7",
}
DEFAULT_COLOR = "#FFFFFF"

LAB_CELL_COLOR    = "#FFF3CD"   # warm amber for lab cells in PDF/HTML
LECTURE_CELL_COLOR = "#FFFFFF"


def program_color(program: str) -> str:
    return PROGRAM_COLORS.get(program[:3] if len(program) >= 3 else program,
                              DEFAULT_COLOR)
