"""
constraints.py
Conflict detection for lectures and 3-hour lab sessions.

Hash-set approach — all checks O(1):
  slot_instructors[slot_id]  → set of instructors
  slot_rooms[slot_id]        → set of room_ids
  slot_programs[slot_id]     → set of programs

For labs: all three slot_ids in the block are checked / committed together.
"""

from __future__ import annotations
from collections import defaultdict
from src.models import Course, Room, TimeSlot, Assignment, LabSession


# ─────────────────────────── Building → rooms map (used for lecture ranking) ──

BUILDING_ROOMS: dict[str, list[str]] = {}  # populated by scheduler at runtime


# ─────────────────────────── Lecture room ranking ─────────────────────────────

def rank_lecture_rooms(course: Course, rooms: list[Room]) -> list[Room]:
    """
    Return rooms sorted by suitability for a LECTURE.
    Priority:
      +4  allowed building for this program prefix
      +3  capacity >= course capacity
      +1  lecture_hall preferred over main_hall
      -99 lab rooms → never used for lectures
    """
    allowed = set(course.allowed_lecture_buildings)
    lecture_rooms = [r for r in rooms if not r.is_lab]
    preferred_rooms = [
        r for r in lecture_rooms
        if r.building in allowed and r.capacity >= course.capacity
    ]
    pool = preferred_rooms or lecture_rooms

    def score(r: Room) -> int:
        if r.is_lab:
            return -99
        s = 0
        if r.building in allowed:
            s += 4
        if r.capacity >= course.capacity:
            s += 3
        if r.type == "lecture_hall":
            s += 1
        return s

    return sorted(pool, key=score, reverse=True)


# ─────────────────────────── ConflictChecker ──────────────────────────────────

class ConflictChecker:
    """
    Stateful checker updated as assignments are committed.
    Handles both single-slot lectures and 3-slot lab sessions.
    """

    def __init__(self):
        self._instructors: dict[str, set[str]] = defaultdict(set)
        self._rooms:       dict[str, set[str]] = defaultdict(set)
        self._programs:    dict[str, set[str]] = defaultdict(set)

    # ── Lecture checks ────────────────────────────────────────────────────────

    def can_assign_lecture(
        self, course: Course, room: Room, slot: TimeSlot,
        ignore_cohort: bool = False,
    ) -> tuple[bool, str]:
        sid = slot.slot_id

        if not course.instructor_unknown:
            if course.instructor in self._instructors[sid]:
                return False, f"instructor '{course.instructor}' busy at {sid}"

        if room.room_id in self._rooms[sid]:
            return False, f"room '{room.room_name}' busy at {sid}"

        if not ignore_cohort:
            cohort = course.cohort_key
            if cohort and cohort in self._programs[sid]:
                return False, f"cohort '{cohort}' has class at {sid}"

        if room.is_lab:
            return False, "lecture cannot go in a lab room"

        if room.capacity < course.capacity:
            return False, (f"room capacity {room.capacity} < "
                           f"course capacity {course.capacity}")

        return True, ""

    def assign_lecture(self, course: Course, room: Room, slot: TimeSlot) -> None:
        sid = slot.slot_id
        if not course.instructor_unknown:
            self._instructors[sid].add(course.instructor)
        self._rooms[sid].add(room.room_id)
        if course.cohort_key:
            self._programs[sid].add(course.cohort_key)

    # ── Lab session checks (3 consecutive slots) ──────────────────────────────

    def can_assign_lab(
        self, course: Course, room: Room, slots: list[TimeSlot],
        ignore_cohort: bool = False,
    ) -> tuple[bool, str]:
        for slot in slots:
            sid = slot.slot_id

            if not course.instructor_unknown:
                if course.instructor in self._instructors[sid]:
                    return False, (f"instructor '{course.instructor}' "
                                   f"busy at {sid}")

            if room.room_id in self._rooms[sid]:
                return False, f"lab room '{room.room_name}' busy at {sid}"

            if not ignore_cohort:
                cohort = course.cohort_key
                if cohort and cohort in self._programs[sid]:
                    return False, f"cohort '{cohort}' has class at {sid}"

        if not room.is_lab:
            return False, f"'{room.room_name}' is not a lab room"

        # TBA_ROOM has infinite capacity — always accepts
        if room.room_id != "TBA_ROOM" and room.capacity < course.capacity:
            return False, (f"lab room '{room.room_name}' capacity {room.capacity} "
                           f"< course capacity {course.capacity}")

        return True, ""

    def assign_lab(self, course: Course, room: Room, slots: list[TimeSlot]) -> None:
        for slot in slots:
            sid = slot.slot_id
            if not course.instructor_unknown:
                self._instructors[sid].add(course.instructor)
            self._rooms[sid].add(room.room_id)
            if course.cohort_key:
                self._programs[sid].add(course.cohort_key)

    # ── Snapshot / restore (multi-solution) ───────────────────────────────────

    def snapshot(self) -> dict:
        return {
            "i": {k: set(v) for k, v in self._instructors.items()},
            "r": {k: set(v) for k, v in self._rooms.items()},
            "p": {k: set(v) for k, v in self._programs.items()},
        }

    def restore(self, snap: dict) -> None:
        self._instructors = defaultdict(set, snap["i"])
        self._rooms       = defaultdict(set, snap["r"])
        self._programs    = defaultdict(set, snap["p"])


# ─────────────────────────── Post-hoc validator ───────────────────────────────

class ScheduleValidator:
    """Validates a completed schedule and returns human-readable violation strings."""

    def validate(
        self,
        assignments:  list[Assignment],
        lab_sessions: list[LabSession],
    ) -> list[str]:
        violations: list[str] = []
        violations += self._instructor_clash(assignments, lab_sessions)
        violations += self._room_clash(assignments, lab_sessions)
        violations += self._program_clash(assignments, lab_sessions)
        violations += self._lecture_in_lab_room(assignments)
        violations += self._lab_in_non_lab_room(lab_sessions)
        violations += self._capacity_violations(assignments, lab_sessions)
        return violations

    def _all_pairs(self, assignments, lab_sessions):
        """Yield (instructor, room_id, cohort_key, slot_id) for every entry."""
        for a in assignments:
            yield a.course.instructor, a.room.room_id, a.course.cohort_key, a.slot.slot_id

        for ls in lab_sessions:
            for slot in ls.slots:
                yield ls.course.instructor, ls.room.room_id, ls.course.cohort_key, slot.slot_id

    def _instructor_clash(self, assignments, lab_sessions):
        seen: dict[tuple, list] = defaultdict(list)
        for a in assignments:
            if not a.course.instructor_unknown:
                seen[(a.course.instructor, a.slot.slot_id)].append(a.course.display)
        for ls in lab_sessions:
            if not ls.course.instructor_unknown:
                for s in ls.slots:
                    seen[(ls.course.instructor, s.slot_id)].append(ls.course.display)
        return [f"INSTRUCTOR CLASH: '{k[0]}' at {k[1]}: {v}"
                for k, v in seen.items() if len(v) > 1]

    def _room_clash(self, assignments, lab_sessions):
        seen: dict[tuple, list] = defaultdict(list)
        for a in assignments:
            seen[(a.room.room_id, a.slot.slot_id)].append(a.course.display)
        for ls in lab_sessions:
            for s in ls.slots:
                seen[(ls.room.room_id, s.slot_id)].append(ls.course.display)
        return [f"ROOM CLASH: '{k[0]}' at {k[1]}: {v}"
                for k, v in seen.items() if len(v) > 1]

    def _program_clash(self, assignments, lab_sessions):
        seen: dict[tuple, list] = defaultdict(list)
        for a in assignments:
            if a.course.cohort_key:
                seen[(a.course.cohort_key, a.slot.slot_id)].append(a.course.display)
        for ls in lab_sessions:
            if ls.course.cohort_key:
                for s in ls.slots:
                    seen[(ls.course.cohort_key, s.slot_id)].append(ls.course.display)
        return [f"COHORT CLASH: '{k[0]}' at {k[1]}: {v}"
                for k, v in seen.items() if len(v) > 1]

    def _lecture_in_lab_room(self, assignments):
        return [f"ROOM TYPE: lecture {a.course.display} in lab room '{a.room.room_name}'"
                for a in assignments if a.room.is_lab]

    def _lab_in_non_lab_room(self, lab_sessions):
        return [f"ROOM TYPE: lab {ls.course.display} in non-lab '{ls.room.room_name}'"
                for ls in lab_sessions if not ls.room.is_lab]

    def _capacity_violations(self, assignments, lab_sessions):
        v = []
        for a in assignments:
            if a.room.capacity < a.course.capacity:
                v.append(f"CAPACITY: {a.course.display} needs {a.course.capacity} "
                         f"but '{a.room.room_name}' holds {a.room.capacity}")
        for ls in lab_sessions:
            if ls.room.room_id == "TBA_ROOM":
                continue   # TBA is a placeholder — skip capacity check
            if ls.room.capacity < ls.course.capacity:
                v.append(f"CAPACITY: lab {ls.course.display} needs {ls.course.capacity} "
                         f"but '{ls.room.room_name}' holds {ls.room.capacity}")
        return v
