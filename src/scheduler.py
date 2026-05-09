"""
scheduler.py
Enhanced CSP scheduler:
  - Labs → fixed room + 3 consecutive slots (preferred afternoon)
  - Lectures → building-affinity room selection
  - No instructor / room / program clashes
"""

from __future__ import annotations
import random
from collections import defaultdict
from src.models import (
    Course, Room, TimeSlot,
    Assignment, LabSession, ScheduleResult,
)
from src.constraints import ConflictChecker, rank_lecture_rooms

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# ─────────────────────────── Slot helpers ─────────────────────────────────────

def _sort_slots(slots: list[TimeSlot]) -> list[TimeSlot]:
    return sorted(
        slots,
        key=lambda s: (DAY_ORDER.index(s.day) if s.day in DAY_ORDER else 9,
                       s.slot_index),
    )


def _sort_lecture_slots(slots: list[TimeSlot], day_offset: int = 0) -> list[TimeSlot]:
    """
    Spread lectures across the week instead of exhausting Monday first.
    This better matches real timetable grids and keeps rooms/buildings busier
    across all days.
    """
    rotated_days = DAY_ORDER[day_offset:] + DAY_ORDER[:day_offset]
    day_rank = {day: i for i, day in enumerate(rotated_days)}
    return sorted(
        slots,
        key=lambda s: (s.slot_index,
                       day_rank.get(s.day, 9)),
    )


def _slots_by_day(slots: list[TimeSlot]) -> dict[str, list[TimeSlot]]:
    grouped: dict[str, list[TimeSlot]] = defaultdict(list)
    for s in slots:
        grouped[s.day].append(s)
    return {d: sorted(grouped[d], key=lambda x: x.slot_index) for d in grouped}


def _consecutive_triples(day_slots: list[TimeSlot]) -> list[list[TimeSlot]]:
    """
    Return all groups of 3 slots whose slot_index values are consecutive
    (i.e. index n, n+1, n+2 — no gap across the lunch break).
    Consecutive means slot_index differs by exactly 1 each step.
    """
    triples = []
    for i in range(len(day_slots) - 2):
        a, b, c = day_slots[i], day_slots[i+1], day_slots[i+2]
        if b.slot_index == a.slot_index + 1 and c.slot_index == b.slot_index + 1:
            triples.append([a, b, c])
    return triples


def _is_afternoon(triple: list[TimeSlot]) -> bool:
    """True if the triple starts at or after 12:30."""
    start = triple[0].start_time
    h = int(start.split(":")[0])
    m = int(start.split(":")[1])
    return h >= 12 or (h == 12 and m >= 30)


# ─────────────────────────── Room lookup ──────────────────────────────────────

def _build_room_index(rooms: list[Room]) -> dict[str, Room]:
    return {r.room_id: r for r in rooms}


def _rooms_by_building(rooms: list[Room]) -> dict[str, list[Room]]:
    grouped: dict[str, list[Room]] = defaultdict(list)
    for r in rooms:
        grouped[r.building].append(r)
    return dict(grouped)


# ─────────────────────────── Lab scheduler ────────────────────────────────────

def _schedule_labs(
    labs:       list[Course],
    slots:      list[TimeSlot],
    rooms:      list[Room],
    checker:    ConflictChecker,
    room_index: dict[str, Room],
    verbose:    bool,
) -> tuple[list[LabSession], list[Course]]:
    """
    Schedule each lab as a 3-hour continuous block.
    Room is fixed by course.required_lab_room_ids.
    Preference: afternoon slots, Mon–Thu before Fri.
    """
    sessions:    list[LabSession] = []
    unscheduled: list[Course]     = []

    by_day = _slots_by_day(slots)

    # Build candidate (day, triple) list: afternoon Mon-Thu first,
    # then morning Mon-Thu, then Friday
    candidate_blocks: list[tuple[str, list[TimeSlot]]] = []
    for day in DAY_ORDER:
        day_slots = by_day.get(day, [])
        triples   = _consecutive_triples(day_slots)
        afternoon = [t for t in triples if     _is_afternoon(t)]
        morning   = [t for t in triples if not _is_afternoon(t)]
        candidate_blocks += [(day, t) for t in afternoon]
        candidate_blocks += [(day, t) for t in morning]

    # All lab rooms available as a fallback pool (largest first)
    all_lab_rooms = sorted([r for r in rooms if r.is_lab], key=lambda r: -r.capacity)

    # Sort labs: larger capacity first
    sorted_labs = sorted(labs, key=lambda c: -c.capacity)

    # ── First pass ────────────────────────────────────────────────────────────
    for course in sorted_labs:
        placed = False
        preferred_room_ids = course.required_lab_room_ids
        preferred_rooms = [room_index[rid] for rid in preferred_room_ids if rid in room_index]
        fallback_rooms  = [r for r in all_lab_rooms if r.room_id not in set(preferred_room_ids)]
        candidate_rooms = preferred_rooms + fallback_rooms

        for room in candidate_rooms:
            for day, triple in candidate_blocks:
                ok, reason = checker.can_assign_lab(course, room, triple)
                if ok:
                    checker.assign_lab(course, room, triple)
                    sessions.append(LabSession(
                        course=course, room=room, day=day, slots=triple,
                    ))
                    placed = True
                    break
            if placed:
                break

        if not placed:
            unscheduled.append(course)
            if verbose:
                print(f"  [lab] UNSCHEDULED: {course.display} "
                      f"(wanted {course.required_lab_room_ids})")

    # ── Second pass: retry ignoring cohort saturation ─────────────────────────
    still_unscheduled: list[Course] = []
    for course in unscheduled:
        placed = False
        preferred_room_ids = course.required_lab_room_ids
        preferred_rooms = [room_index[rid] for rid in preferred_room_ids if rid in room_index]
        fallback_rooms  = [r for r in all_lab_rooms if r.room_id not in set(preferred_room_ids)]
        candidate_rooms = preferred_rooms + fallback_rooms

        for room in candidate_rooms:
            for day, triple in candidate_blocks:
                ok, _ = checker.can_assign_lab(course, room, triple, ignore_cohort=True)
                if ok:
                    checker.assign_lab(course, room, triple)
                    sessions.append(LabSession(
                        course=course, room=room, day=day, slots=triple,
                    ))
                    placed = True
                    break
            if placed:
                break

        if not placed:
            still_unscheduled.append(course)

    # ── Third pass: merge with an already-placed session (same code + instructor)
    final_unscheduled: list[Course] = []
    for course in still_unscheduled:
        if not course.instructor_unknown:
            match = next(
                (s for s in sessions
                 if s.course.code == course.code
                 and s.course.instructor == course.instructor),
                None,
            )
            if match:
                sessions.append(LabSession(
                    course=course,
                    room=match.room,
                    day=match.day,
                    slots=match.slots,
                ))
                if verbose:
                    print(f"  [lab] MERGED: {course.display} "
                          f"combined with {match.course.display} "
                          f"({match.day} {match.slots[0].start_time})")
                continue
        final_unscheduled.append(course)

    return sessions, final_unscheduled


# ─────────────────────────── Lecture scheduler ────────────────────────────────

def _schedule_lectures(
    lectures:    list[Course],
    slots:       list[TimeSlot],
    rooms:       list[Room],
    checker:     ConflictChecker,
    rng:         random.Random,
    verbose:     bool,
) -> tuple[list[Assignment], list[Course]]:
    """
    Schedule each lecture into one weekly meeting per credit hour.
    Room chosen from allowed buildings, ranked by capacity fit.
    """
    assignments: list[Assignment] = []
    unscheduled: list[Course]     = []

    sorted_lects  = sorted(lectures, key=lambda c: (-c.capacity, c.credit_hours))

    for course_idx, course in enumerate(sorted_lects):
        ordered_slots = _sort_lecture_slots(slots, course_idx % len(DAY_ORDER))
        meetings_needed = max(1, int(course.credit_hours or 1))
        course_days: set[str] = set()
        course_room: Room | None = None

        # Rank rooms, then shuffle within each score tier for variety
        all_ranked = rank_lecture_rooms(course, rooms)
        # Group by score to shuffle within tier, preserving overall priority
        from itertools import groupby
        from src.constraints import rank_lecture_rooms as _rank

        def score_fn(r):
            allowed = set(course.allowed_lecture_buildings)
            if r.is_lab: return -99
            s = 0
            if r.building in allowed:        s += 4
            if r.capacity >= course.capacity: s += 3
            if r.type == "lecture_hall":      s += 1
            return s

        scored = [(score_fn(r), r) for r in all_ranked]
        tiers: dict[int, list] = {}
        for sc, r in scored:
            tiers.setdefault(sc, []).append(r)
        for sc in tiers:
            rng.shuffle(tiers[sc])
        candidate_rooms = []
        for sc in sorted(tiers.keys(), reverse=True):
            candidate_rooms.extend(tiers[sc])

        for meeting_idx in range(meetings_needed):
            placed = False

            unused_day_slots = [s for s in ordered_slots if s.day not in course_days]
            slot_candidates = unused_day_slots + [
                s for s in ordered_slots if s.day in course_days
            ]

            if course_room:
                room_candidates = [course_room] + [
                    r for r in candidate_rooms if r.room_id != course_room.room_id
                ]
            else:
                room_candidates = candidate_rooms

            for slot in slot_candidates:
                for room in room_candidates:
                    ok, _ = checker.can_assign_lecture(course, room, slot)
                    if ok:
                        checker.assign_lecture(course, room, slot)
                        assignments.append(Assignment(course=course, room=room, slot=slot))
                        course_days.add(slot.day)
                        course_room = room
                        placed = True
                        break
                if placed:
                    break

            if not placed:
                unscheduled.append(course)
                if verbose:
                    print(f"  [lecture] UNSCHEDULED: {course.display} "
                          f"meeting {meeting_idx + 1}/{meetings_needed}")

    # ── Second pass: retry failed lectures ignoring cohort saturation ─────────
    still_unscheduled: list[Course] = []
    seen_ids: set[str] = set()
    retry_courses: list[Course] = []
    for c in unscheduled:
        if c.source_id not in seen_ids:
            seen_ids.add(c.source_id)
            retry_courses.append(c)

    for course in retry_courses:
        meetings_needed = max(1, int(course.credit_hours or 1))
        already_placed  = sum(1 for a in assignments if a.course.source_id == course.source_id)
        remaining       = meetings_needed - already_placed
        if remaining <= 0:
            continue

        ordered_slots = _sort_lecture_slots(slots)
        course_days2: set[str] = set(
            a.slot.day for a in assignments if a.course.source_id == course.source_id
        )
        course_room2: Room | None = next(
            (a.room for a in assignments if a.course.source_id == course.source_id), None
        )

        def _score(r: Room, c: Course = course) -> int:
            if r.is_lab:
                return -99
            s = 0
            allowed = set(c.allowed_lecture_buildings)
            if r.building in allowed:         s += 4
            if r.capacity >= c.capacity:      s += 3
            if r.type == "lecture_hall":      s += 1
            return s

        tiers2: dict[int, list[Room]] = {}
        for r in rooms:
            sc = _score(r)
            tiers2.setdefault(sc, []).append(r)
        candidate_rooms2: list[Room] = []
        for sc in sorted(tiers2.keys(), reverse=True):
            candidate_rooms2.extend(tiers2[sc])

        for _ in range(remaining):
            placed = False
            unused_day_slots = [s for s in ordered_slots if s.day not in course_days2]
            slot_candidates  = unused_day_slots + [s for s in ordered_slots if s.day in course_days2]
            room_candidates  = (
                [course_room2] + [r for r in candidate_rooms2 if r.room_id != course_room2.room_id]
                if course_room2 else candidate_rooms2
            )

            for slot in slot_candidates:
                for room in room_candidates:
                    ok, _ = checker.can_assign_lecture(course, room, slot, ignore_cohort=True)
                    if ok:
                        checker.assign_lecture(course, room, slot)
                        assignments.append(Assignment(course=course, room=room, slot=slot))
                        course_days2.add(slot.day)
                        course_room2 = room
                        placed = True
                        break
                if placed:
                    break

            if not placed:
                still_unscheduled.append(course)

    return assignments, still_unscheduled


# ─────────────────────────── Main entry point ─────────────────────────────────

def schedule(
    courses: list[Course],
    slots:   list[TimeSlot],
    rooms:   list[Room],
    seed:    int  = 42,
    verbose: bool = True,
) -> ScheduleResult:
    """
    Full schedule:
      1. Split courses → labs | lectures
      2. Schedule labs first (fixed rooms, 3-hour blocks)
      3. Schedule lectures (building-affinity rooms, single slots)
    """
    rng        = random.Random(seed)
    checker    = ConflictChecker()
    room_index = _build_room_index(rooms)

    labs     = [c for c in courses if c.is_lab]
    lectures = [c for c in courses if c.is_lecture]

    if verbose:
        print(f"  Labs:     {len(labs)}")
        print(f"  Lectures: {len(lectures)}")

    # ── 1. Labs ───────────────────────────────────────────────────────────────
    lab_sessions, unscheduled_labs = _schedule_labs(
        labs, slots, rooms, checker, room_index, verbose,
    )

    # ── 2. Lectures ───────────────────────────────────────────────────────────
    assignments, unscheduled_lects = _schedule_lectures(
        lectures, slots, rooms, checker, rng, verbose,
    )

    unscheduled = unscheduled_labs + unscheduled_lects
    result = ScheduleResult(
        assignments=assignments,
        lab_sessions=lab_sessions,
        unscheduled=unscheduled,
    )

    if verbose:
        _print_summary(result)

    return result


def _print_summary(result: ScheduleResult) -> None:
    placed = len(result.assignments) + len(result.lab_sessions)
    print(f"\n{'='*58}")
    print(f"  Scheduling complete")
    print(f"  Lectures placed  : {len(result.assignments)}")
    print(f"  Lab sessions     : {len(result.lab_sessions)}")
    print(f"  Total placed     : {placed} / {result.total_courses}")
    print(f"  Unscheduled      : {len(result.unscheduled)}")
    print(f"  Success rate     : {result.success_rate:.1f}%")
    if result.unscheduled:
        print(f"\n  Unscheduled:")
        for c in result.unscheduled[:20]:
            tag = "LAB" if c.is_lab else "LEC"
            print(f"    [{tag}] {c.display:<22} {c.instructor:<30} [{c.program}]")
        if len(result.unscheduled) > 20:
            print(f"    ... and {len(result.unscheduled)-20} more")
    print(f"{'='*58}\n")
