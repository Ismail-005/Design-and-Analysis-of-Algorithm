"""
tests/test_constraints.py  —  unit tests for src/constraints.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models      import Course, Room, TimeSlot, Assignment, LabSession
from src.constraints import ConflictChecker, ScheduleValidator, rank_lecture_rooms


# ── Fixtures ──────────────────────────────────────────────────────────────────

def C(code="CS101", section="A", instructor="Dr.X",
      program="BCS", capacity=40, ctype="lecture", title="X") -> Course:
    return Course(code=code, section=section, title=title,
                  credit_hours=3, type=ctype,
                  instructor=instructor, program=program, capacity=capacity)

def R(rid="LH1", building="ACB", rtype="lecture_hall", cap=80) -> Room:
    return Room(room_id=rid, room_name=rid, building=building,
                type=rtype, capacity=cap)

def S(sid="MON_S1", day="Monday", idx=1) -> TimeSlot:
    return TimeSlot(slot_id=sid, day=day, start_time="08:00", end_time="08:50",
                    slot_index=idx, day_type="regular")

def triple(day="Monday") -> list[TimeSlot]:
    return [
        S(f"{day[:3].upper()}_S1", day, 1),
        S(f"{day[:3].upper()}_S2", day, 2),
        S(f"{day[:3].upper()}_S3", day, 3),
    ]


# ── Lecture checks ────────────────────────────────────────────────────────────

def test_fresh_checker_allows_lecture():
    checker = ConflictChecker()
    ok, reason = checker.can_assign_lecture(C(), R(), S())
    assert ok, reason

def test_instructor_clash_lecture():
    checker = ConflictChecker()
    c1 = C("CS101","A","Dr.X","BCS"); r1 = R("LH1")
    c2 = C("CS202","A","Dr.X","BCE"); r2 = R("LH2")
    s  = S()
    checker.assign_lecture(c1, r1, s)
    ok, reason = checker.can_assign_lecture(c2, r2, s)
    assert not ok
    assert "instructor" in reason.lower()

def test_room_clash_lecture():
    checker = ConflictChecker()
    c1 = C("CS101","A","Dr.A","BCS"); c2 = C("CS202","A","Dr.B","BCE")
    r  = R("LH1"); s = S()
    checker.assign_lecture(c1, r, s)
    ok, reason = checker.can_assign_lecture(c2, r, s)
    assert not ok
    assert "room" in reason.lower()

def test_program_clash_lecture():
    checker = ConflictChecker()
    c1 = C("CS101","A","Dr.A","BCS"); c2 = C("CS102","B","Dr.B","BCS")
    r1 = R("LH1"); r2 = R("LH2"); s = S()
    checker.assign_lecture(c1, r1, s)
    ok, reason = checker.can_assign_lecture(c2, r2, s)
    assert not ok
    assert "cohort" in reason.lower()

def test_different_slot_no_clash():
    checker = ConflictChecker()
    c = C(instructor="Dr.X"); r = R()
    s1 = S("MON_S1", idx=1); s2 = S("MON_S2", idx=2)
    checker.assign_lecture(c, r, s1)
    ok, _ = checker.can_assign_lecture(c, r, s2)
    assert ok

def test_tba_instructor_no_clash_different_programs():
    checker = ConflictChecker()
    c1 = C("CS101","A","TBA","BCS"); c2 = C("CS202","A","TBA","BCE")
    r1 = R("LH1"); r2 = R("LH2"); s = S()
    checker.assign_lecture(c1, r1, s)
    ok, reason = checker.can_assign_lecture(c2, r2, s)
    assert ok, f"TBA instructors should not clash: {reason}"

def test_lecture_in_lab_room_blocked():
    checker = ConflictChecker()
    c = C(ctype="lecture"); r = R(rtype="lab"); s = S()
    ok, reason = checker.can_assign_lecture(c, r, s)
    assert not ok
    assert "lab" in reason.lower()

def test_capacity_violation_lecture():
    checker = ConflictChecker()
    c = C(capacity=100); r = R(cap=60); s = S()
    ok, reason = checker.can_assign_lecture(c, r, s)
    assert not ok
    assert "capacity" in reason.lower()


# ── Lab session checks ────────────────────────────────────────────────────────

def test_lab_triple_ok():
    checker = ConflictChecker()
    c = C("CS101L","A","Dr.X","BCS",25,"lab")
    r = R("LAB1", rtype="lab", cap=50)
    t = triple()
    ok, reason = checker.can_assign_lab(c, r, t)
    assert ok, reason

def test_lab_instructor_clash_in_triple():
    checker = ConflictChecker()
    c1 = C("CS101L","A","Dr.X","BCS",25,"lab")
    c2 = C("CS202L","A","Dr.X","BCE",25,"lab")
    r1 = R("LAB1",rtype="lab",cap=50); r2 = R("LAB2",rtype="lab",cap=50)
    t  = triple()
    checker.assign_lab(c1, r1, t)
    ok, reason = checker.can_assign_lab(c2, r2, t)
    assert not ok
    assert "instructor" in reason.lower()

def test_lab_room_clash_in_triple():
    checker = ConflictChecker()
    c1 = C("CS101L","A","Dr.A","BCS",25,"lab")
    c2 = C("CS202L","A","Dr.B","BCE",25,"lab")
    r  = R("LAB1",rtype="lab",cap=50)
    t  = triple()
    checker.assign_lab(c1, r, t)
    ok, reason = checker.can_assign_lab(c2, r, t)
    assert not ok
    assert "room" in reason.lower()

def test_lab_program_clash_in_triple():
    checker = ConflictChecker()
    c1 = C("CS101L","A","Dr.A","BCS",25,"lab")
    c2 = C("CS102L","A","Dr.B","BCS",25,"lab")
    r1 = R("LAB1",rtype="lab",cap=50); r2 = R("LAB2",rtype="lab",cap=50)
    t  = triple()
    checker.assign_lab(c1, r1, t)
    ok, reason = checker.can_assign_lab(c2, r2, t)
    assert not ok
    assert "cohort" in reason.lower()

def test_lab_in_lecture_room_blocked():
    checker = ConflictChecker()
    c = C("CS101L","A","Dr.X","BCS",25,"lab")
    r = R("LH1", rtype="lecture_hall")
    t = triple()
    ok, reason = checker.can_assign_lab(c, r, t)
    assert not ok

def test_lab_different_days_no_clash():
    checker = ConflictChecker()
    c  = C("CS101L","A","Dr.X","BCS",25,"lab")
    r  = R("LAB1",rtype="lab",cap=50)
    t1 = triple("Monday"); t2 = triple("Tuesday")
    checker.assign_lab(c, r, t1)
    ok, _ = checker.can_assign_lab(c, r, t2)
    assert ok

def test_lecture_and_lab_same_program_clash():
    """Program in a 3h lab block must block lectures in those same slots."""
    checker = ConflictChecker()
    c_lab  = C("CS101L","A","Dr.A","BCS",25,"lab")
    c_lect = C("CS102", "A","Dr.B","BCS",40,"lecture")
    r_lab  = R("LAB1",rtype="lab",cap=50)
    r_lect = R("LH1", rtype="lecture_hall",cap=80)
    t      = triple()
    checker.assign_lab(c_lab, r_lab, t)
    ok, reason = checker.can_assign_lecture(c_lect, r_lect, t[0])
    assert not ok
    assert "cohort" in reason.lower()

def test_snapshot_restore():
    checker = ConflictChecker()
    c = C("CS101","A","Dr.Y","BCS"); r = R(); s = S()
    snap = checker.snapshot()
    checker.assign_lecture(c, r, s)
    checker.restore(snap)
    ok, _ = checker.can_assign_lecture(c, r, s)
    assert ok


# ── rank_lecture_rooms ────────────────────────────────────────────────────────

def test_rank_no_lab_rooms_for_lecture():
    c = C("CS101", capacity=40)
    rooms = [R("LAB1",rtype="lab",cap=80), R("LH1",rtype="lecture_hall",cap=80)]
    ranked = rank_lecture_rooms(c, rooms)
    assert all(not r.is_lab for r in ranked)

def test_rank_allowed_building_first():
    c = C("CS101", program="BCS")   # BCS → ACB/FCSE
    rooms = [
        R("BB_LH",   building="BB",   rtype="lecture_hall", cap=80),
        R("ACB_LH",  building="ACB",  rtype="lecture_hall", cap=80),
        R("FCSE_LH", building="FCSE", rtype="lecture_hall", cap=80),
    ]
    ranked = rank_lecture_rooms(c, rooms)
    assert ranked[0].building in ("ACB", "FCSE")

def test_rank_capacity_fit_preferred():
    c = C(capacity=60)
    rooms = [
        R("SMALL", cap=40, rtype="lecture_hall", building="ACB"),
        R("BIG",   cap=100,rtype="lecture_hall", building="ACB"),
    ]
    ranked = rank_lecture_rooms(c, rooms)
    assert ranked[0].room_id == "BIG"


# ── ScheduleValidator ─────────────────────────────────────────────────────────

def _asgn(code, section, instructor, program, room_id, slot_id,
          day="Monday", cap=40, rtype="lecture_hall"):
    c = C(code, section, instructor, program, cap)
    r = R(room_id, rtype=rtype, cap=max(cap,80))
    s = S(slot_id, day)
    return Assignment(course=c, room=r, slot=s)

def _lab_sess(code, section, instructor, program, room_id, day="Monday", cap=25):
    c = C(code, section, instructor, program, cap, "lab")
    r = R(room_id, rtype="lab", cap=max(cap,50))
    t = triple(day)
    return LabSession(course=c, room=r, day=day, slots=t)

def test_validator_clean_schedule():
    v = ScheduleValidator()
    a1 = _asgn("CS101","A","Dr.A","BCS","LH1","MON_S1")
    a2 = _asgn("CS202","A","Dr.B","BCE","LH2","MON_S2")
    assert v.validate([a1, a2], []) == []

def test_validator_detects_instructor_clash():
    v  = ScheduleValidator()
    a1 = _asgn("CS101","A","Dr.X","BCS","LH1","MON_S1")
    a2 = _asgn("CS202","B","Dr.X","BCE","LH2","MON_S1")
    viol = v.validate([a1, a2], [])
    assert any("INSTRUCTOR" in x for x in viol)

def test_validator_detects_room_clash():
    v  = ScheduleValidator()
    a1 = _asgn("CS101","A","Dr.A","BCS","LH1","MON_S1")
    a2 = _asgn("CS202","A","Dr.B","BCE","LH1","MON_S1")
    viol = v.validate([a1, a2], [])
    assert any("ROOM" in x for x in viol)

def test_validator_detects_lab_in_lecture_room():
    v  = ScheduleValidator()
    ls = _lab_sess("CS101L","A","Dr.A","BCS","LH1")
    ls.room.type = "lecture_hall"   # force violation
    viol = v.validate([], [ls])
    assert any("ROOM TYPE" in x for x in viol)

def test_validator_detects_capacity():
    v  = ScheduleValidator()
    a  = _asgn("CS101","A","Dr.A","BCS","LH1","MON_S1",cap=200,rtype="lecture_hall")
    a.room.capacity = 50   # force violation
    viol = v.validate([a], [])
    assert any("CAPACITY" in x for x in viol)

def test_validator_clean_with_labs():
    v  = ScheduleValidator()
    a  = _asgn("CS101","A","Dr.A","BCS","LH1","MON_S1")
    ls = _lab_sess("CS101L","A","Dr.B","BCE","LAB1","Tuesday")
    assert v.validate([a], [ls]) == []


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t(); print(f"  ✓ {t.__name__}"); passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}"); failed += 1
    print(f"\n{passed} passed, {failed} failed")
