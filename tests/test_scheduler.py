"""
tests/test_scheduler.py  —  unit & integration tests for src/scheduler.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models      import Course, Room, TimeSlot, LabSession, Assignment
from src.scheduler   import schedule, _consecutive_triples, _is_afternoon, _slots_by_day
from src.constraints import ScheduleValidator


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_lecture(code, section="A", instructor=None, program="BCS", cap=40) -> Course:
    return Course(code=code, section=section, title=code, credit_hours=3,
                  type="lecture", instructor=instructor or f"Dr.{code}",
                  program=program, capacity=cap)

def make_lab(code, section="A", instructor=None, program="BCS", cap=25) -> Course:
    lab_code = code if code.endswith("L") else code + "L"
    return Course(code=lab_code, section=section, title=f"{code} Lab",
                  credit_hours=1, type="lab",
                  instructor=instructor or f"Dr.{code}Lab",
                  program=program, capacity=cap)

def make_rooms() -> list[Room]:
    return [
        Room("FCSE_SE_LAB","FCSE - SE Lab","FCSE","lab",50),
        Room("FME_LAB",    "FME Lab",      "FME", "lab",70),
        Room("FES_PH_LAB", "FES - PH Lab", "FES", "lab",50),
        Room("ACB_AI_LAB", "ACB - AI Lab", "ACB", "lab",55),
        Room("FCME_MM_LAB","FCME - MM Lab","FMCE","lab",30),
        Room("TBA_ROOM",   "TBA",          "TBA", "lab",999),
        Room("ACB_LH4",    "AcB LH4",      "ACB", "lecture_hall",60),
        Room("ACB_LH5",    "AcB LH5",      "ACB", "lecture_hall",60),
        Room("FCSE_LH1",   "FCSE LH1",     "FCSE","lecture_hall",80),
        Room("FEE_LH4",    "FEE LH4",      "FEE", "lecture_hall",80),
        Room("FME_LH1",    "FME LH1",      "FME", "lecture_hall",60),
        Room("BB_EH1",     "BB EH1",       "BB",  "lecture_hall",50),
        Room("BB_LH2",     "BB LH2",       "BB",  "lecture_hall",50),
    ]

def make_slots(n_per_day=8) -> list[TimeSlot]:
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    slots = []
    hours = ["08:00","09:00","10:30","11:30","12:30","14:30","15:30","16:30"]
    ends  = ["08:50","09:50","11:20","12:20","13:20","15:20","16:20","17:20"]
    for day in days:
        for i in range(min(n_per_day, len(hours))):
            slots.append(TimeSlot(
                slot_id    = f"{day[:3].upper()}_S{i+1}",
                day        = day,
                start_time = hours[i],
                end_time   = ends[i],
                slot_index = i + 1,
                day_type   = "friday" if day == "Friday" else "regular",
            ))
    return slots


# ── Slot helper tests ─────────────────────────────────────────────────────────

def test_consecutive_triples_correct():
    slots = make_slots(8)
    by_day = _slots_by_day(slots)
    mon    = by_day["Monday"]
    triples = _consecutive_triples(mon)
    assert len(triples) > 0
    for t in triples:
        assert t[1].slot_index == t[0].slot_index + 1
        assert t[2].slot_index == t[1].slot_index + 1

def test_consecutive_triples_not_across_gaps():
    """slot_index 3→5 should NOT form a triple (gap at 4)."""
    slots = [
        TimeSlot("S1","Monday","08:00","08:50",1,"regular"),
        TimeSlot("S2","Monday","09:00","09:50",2,"regular"),
        # slot 3 missing (lunch break)
        TimeSlot("S4","Monday","14:30","15:20",4,"regular"),
        TimeSlot("S5","Monday","15:30","16:20",5,"regular"),
        TimeSlot("S6","Monday","16:30","17:20",6,"regular"),
    ]
    triples = _consecutive_triples(slots)
    for t in triples:
        indices = [x.slot_index for x in t]
        assert indices[1] == indices[0]+1 and indices[2] == indices[1]+1, \
            f"Non-consecutive triple found: {indices}"

def test_is_afternoon_true():
    s = [TimeSlot("X","Monday","14:30","15:20",6,"regular")] * 3
    assert _is_afternoon(s)

def test_is_afternoon_false():
    s = [TimeSlot("X","Monday","08:00","08:50",1,"regular")] * 3
    assert not _is_afternoon(s)


# ── Lab scheduling ────────────────────────────────────────────────────────────

def test_labs_get_continuous_3h_block():
    courses = [make_lab("CS221")]
    result  = schedule(courses, make_slots(), make_rooms(), verbose=False)
    assert len(result.lab_sessions) == 1
    ls = result.lab_sessions[0]
    assert len(ls.slots) == 3
    for i in range(2):
        assert ls.slots[i+1].slot_index == ls.slots[i].slot_index + 1

def test_lab_placed_in_correct_room():
    """CS lab → FCSE_SE_LAB."""
    result = schedule([make_lab("CS221")], make_slots(), make_rooms(), verbose=False)
    assert result.lab_sessions[0].room.room_id == "FCSE_SE_LAB"

def test_me_lab_placed_in_fme_lab():
    result = schedule([make_lab("ME313")], make_slots(), make_rooms(), verbose=False)
    assert result.lab_sessions[0].room.room_id == "FME_LAB"

def test_ai_lab_placed_in_acb_ai_lab():
    result = schedule([make_lab("AI321")], make_slots(), make_rooms(), verbose=False)
    assert result.lab_sessions[0].room.room_id == "ACB_AI_LAB"

def test_ph_lab_placed_in_fes_ph_lab():
    result = schedule(
        [make_lab("PH101", program="BME")],
        make_slots(), make_rooms(), verbose=False,
    )
    assert result.lab_sessions[0].room.room_id == "FES_PH_LAB"

def test_lab_prefers_afternoon():
    result = schedule([make_lab("CS221")], make_slots(), make_rooms(), verbose=False)
    ls = result.lab_sessions[0]
    start_h = int(ls.start_time.split(":")[0])
    assert start_h >= 12, f"Lab should prefer afternoon, got {ls.start_time}"


# ── Lecture scheduling ────────────────────────────────────────────────────────

def test_lectures_placed():
    courses = [make_lecture(f"CS{100+i}", section="A", program="BCS") for i in range(5)]
    result  = schedule(courses, make_slots(), make_rooms(), verbose=False)
    assert len(result.assignments) == 15

def test_lecture_in_allowed_building():
    """CS lecture must land in ACB or FCSE — both are in the fixture."""
    result = schedule(
        [make_lecture("CS221", program="BCS")],
        make_slots(), make_rooms(), verbose=False,
    )
    assert len(result.assignments) == 3
    for a in result.assignments:
        assert a.room.building in ("ACB", "FCSE"), (
            f"CS lecture should be in ACB or FCSE, got {a.room.building}"
        )

def test_ee_lecture_in_fee():
    """EE lecture must land in FEE building if FEE rooms exist in fixture."""
    result = schedule(
        [make_lecture("EE211", program="BEE")],
        make_slots(), make_rooms(), verbose=False,
    )
    # FEE_LH4 is in make_rooms fixture — EE course must use it
    if result.assignments:
        assert result.assignments[0].room.building == "FEE", (
            f"EE lecture should be in FEE, got {result.assignments[0].room.building}"
        )

def test_me_lecture_in_fme():
    """ME lecture must land in FME building if FME rooms exist in fixture."""
    result = schedule(
        [make_lecture("ME313", program="BME")],
        make_slots(), make_rooms(), verbose=False,
    )
    if result.assignments:
        assert result.assignments[0].room.building == "FME", (
            f"ME lecture should be in FME, got {result.assignments[0].room.building}"
        )

def test_lecture_not_in_lab_room():
    result = schedule(
        [make_lecture("CS221", program="BCS")],
        make_slots(), make_rooms(), verbose=False,
    )
    for a in result.assignments:
        assert not a.room.is_lab, f"Lecture in lab room: {a.room.room_name}"


# ── Clash-free guarantee ──────────────────────────────────────────────────────

def test_zero_violations_mixed_courses():
    courses = (
        [make_lecture(f"CS{100+i}", section="A",
                      instructor=f"Dr.Lect{i}", program="BCS") for i in range(6)] +
        [make_lab(f"CS{200+i}",    section="A",
                  instructor=f"Dr.Lab{i}",  program="BCS") for i in range(3)]
    )
    result    = schedule(courses, make_slots(), make_rooms(), verbose=False)
    validator = ScheduleValidator()
    viol      = validator.validate(result.assignments, result.lab_sessions)
    assert viol == [], f"Violations:\n" + "\n".join(viol)

def test_no_instructor_double_booked():
    """Same instructor teaching two lectures must not be double-booked."""
    courses = [
        make_lecture("CS101","A","Dr.Shared","BCS",40),
        make_lecture("CS202","B","Dr.Shared","BCE",40),
    ]
    result = schedule(courses, make_slots(), make_rooms(), verbose=False)
    v = ScheduleValidator()
    assert v.validate(result.assignments, result.lab_sessions) == []

def test_no_program_clash():
    """Same program should never have two classes at the same time."""
    courses = [make_lecture(f"CS{100+i}","A",f"Dr.{i}","BCS",40) for i in range(8)]
    result  = schedule(courses, make_slots(), make_rooms(), verbose=False)
    v = ScheduleValidator()
    viol = [x for x in v.validate(result.assignments, result.lab_sessions)
            if "COHORT" in x]
    assert viol == [], f"Cohort clashes:\n" + "\n".join(viol)

def test_lab_slots_block_lectures_for_same_program():
    """While a program is in a 3h lab, no lecture can be added for them."""
    courses = [
        make_lab("CS221",     "A", "Dr.LabA", "BCS", 25),
        make_lecture("CS201", "A", "Dr.LecA", "BCS", 40),
        make_lecture("CS202", "A", "Dr.LecB", "BCS", 40),
    ]
    result = schedule(courses, make_slots(), make_rooms(), verbose=False)
    v      = ScheduleValidator()
    viol   = v.validate(result.assignments, result.lab_sessions)
    cohort_viol = [x for x in viol if "COHORT" in x]
    assert cohort_viol == [], f"Cohort clashes:\n" + "\n".join(cohort_viol)


# ── Reproducibility ───────────────────────────────────────────────────────────

def test_reproducible_with_seed():
    courses = [make_lecture(f"CS{100+i}","A",f"Dr.{i}","BCS") for i in range(5)]
    r1 = schedule(courses, make_slots(), make_rooms(), seed=7,  verbose=False)
    r2 = schedule(courses, make_slots(), make_rooms(), seed=7,  verbose=False)
    keys1 = sorted(a.course.key + a.slot.slot_id for a in r1.assignments)
    keys2 = sorted(a.course.key + a.slot.slot_id for a in r2.assignments)
    assert keys1 == keys2


# ── ScheduleResult helpers ────────────────────────────────────────────────────

def test_success_rate_100():
    courses = [make_lecture("CS101")]
    result  = schedule(courses, make_slots(), make_rooms(), verbose=False)
    assert result.success_rate == 100.0

def test_all_rows_includes_labs_and_lectures():
    courses = [make_lecture("CS101"), make_lab("CS101")]
    result  = schedule(courses, make_slots(), make_rooms(), verbose=False)
    rows    = result.all_rows
    types   = {r["session_type"] for r in rows}
    assert "Lecture" in types
    assert "LAB (3h continuous)" in types

def test_to_dict_has_required_keys():
    courses = [make_lecture("CS101"), make_lab("CS101")]
    result  = schedule(courses, make_slots(), make_rooms(), verbose=False)
    required = {"code","section","title","instructor","program",
                "day","start_time","end_time","room_name","building"}
    for row in result.all_rows:
        missing = required - set(row.keys())
        assert not missing, f"Missing keys in row: {missing}"


# ── Full real-data integration ────────────────────────────────────────────────

def test_real_data_zero_violations():
    d = Path(__file__).parent.parent / "data"
    if not d.exists():
        print("  [skip] data/ not found")
        return
    from src.parser import load_all
    courses, slots, rooms = load_all(d)
    result = schedule(courses, slots, rooms, verbose=True)

    v    = ScheduleValidator()
    viol = v.validate(result.assignments, result.lab_sessions)
    assert viol == [], f"{len(viol)} violations:\n" + "\n".join(viol[:10])
    assert result.success_rate > 85, f"Success rate too low: {result.success_rate:.1f}%"

    # All lab sessions should be in lab rooms (TBA_ROOM is a lab type)
    for ls in result.lab_sessions:
        assert ls.room.is_lab, (
            f"Lab {ls.course.display} placed in non-lab room '{ls.room.room_name}'"
        )

    # No lectures in lab rooms
    for a in result.assignments:
        assert not a.room.is_lab, (
            f"Lecture {a.course.display} placed in lab room '{a.room.room_name}'"
        )


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"  ✓ {t.__name__}"); passed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ {t.__name__}: {e}")
            if "--verbose" in sys.argv:
                traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
