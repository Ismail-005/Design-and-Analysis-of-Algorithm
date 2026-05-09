"""
tests/test_parser.py  —  unit tests for src/parser.py
"""

import sys, os, tempfile, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import load_courses, load_rooms, load_timeslots, load_all
from src.models import Course, Room, TimeSlot

COURSES_ROWS = [
    ["code","section","title","credit_hours","type","instructor","program","capacity"],
    ["CS101", "A","Computing and AI",    "2","lecture","Mr. Waheed",  "BEE1","75"],
    ["CS101L","A","Computing and AI Lab","1","lab",    "TBA",         "BEE1","75"],
    ["CE221", "B","Digital Logic Design","3","lecture","Dr. Waqar",   "BCE", "40"],
    ["ME204L","A","Engineering Graphics Lab","1","lab","Engr. Faheem","BME1","30"],
    ["PH101L","A","Applied Physics Lab", "1","lab",    "TBA",         "BME", "100"],
    ["AI321L","A","Machine Learning Lab","1","lab",    "Mr. Asim",    "BAI", "55"],
    ["MM231L","A","Materials Lab",       "1","lab",    "TBA",         "MTE", "25"],
    ["IF101L","A","Innovation Lab",      "1","lab",    "Engr. Faheem","BME", "100"],
]

ROOMS_ROWS = [
    ["room_id","room_name","building","type","capacity"],
    ["FCSE_SE_LAB", "FCSE - SE Lab", "FCSE","lab","50"],
    ["FME_LAB",     "FME Lab",       "FME", "lab","70"],
    ["FES_PH_LAB",  "FES - PH Lab",  "FES", "lab","50"],
    ["ACB_AI_LAB",  "ACB - AI Lab",  "ACB", "lab","55"],
    ["FCME_MM_LAB", "FCME - MM Lab", "FMCE","lab","30"],
    ["TBA_ROOM",    "TBA",           "TBA", "lab","999"],
    ["ACB_LH4",     "AcB LH4",       "ACB", "lecture_hall","60"],
    ["BB_EH1",      "BB EH1",        "BB",  "lecture_hall","50"],
]

SLOTS_ROWS = [
    ["slot_id","day","start_time","end_time","slot_index","day_type"],
    ["MON_S1","Monday","08:00","08:50","1","regular"],
    ["MON_S2","Monday","09:00","09:50","2","regular"],
    ["MON_S3","Monday","10:30","11:20","3","regular"],
    ["FRI_S1","Friday","08:00","08:50","1","friday"],
]

def _csv(rows):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    csv.writer(f).writerows(rows)
    f.close()
    return f.name


# ── Course count / fields ──────────────────────────────────────────────────────

def test_course_count():
    p = _csv(COURSES_ROWS)
    assert len(load_courses(p)) == 8
    os.unlink(p)

def test_course_fields():
    p = _csv(COURSES_ROWS)
    c = load_courses(p)[0]
    assert c.code == "CS101"
    assert c.section == "A"
    assert c.credit_hours == 2
    assert c.capacity == 75
    os.unlink(p)

def test_course_key_unique():
    p = _csv(COURSES_ROWS)
    keys = [c.key for c in load_courses(p)]
    assert len(keys) == len(set(keys))
    os.unlink(p)

def test_course_display():
    p = _csv(COURSES_ROWS)
    assert load_courses(p)[0].display == "CS101 A"
    os.unlink(p)


# ── Lab / lecture detection ────────────────────────────────────────────────────

def test_lab_detected_by_code_ending_L():
    p = _csv(COURSES_ROWS)
    courses = {c.code: c for c in load_courses(p)}
    assert courses["CS101L"].is_lab
    assert courses["ME204L"].is_lab
    assert courses["PH101L"].is_lab
    assert courses["AI321L"].is_lab
    os.unlink(p)

def test_lecture_detected():
    p = _csv(COURSES_ROWS)
    courses = {c.code: c for c in load_courses(p)}
    assert courses["CS101"].is_lecture
    assert courses["CE221"].is_lecture
    os.unlink(p)

def test_tba_instructor_unknown():
    p = _csv(COURSES_ROWS)
    courses = {c.code: c for c in load_courses(p)}
    assert courses["CS101L"].instructor_unknown
    assert not courses["CS101"].instructor_unknown
    os.unlink(p)


# ── Lab room ID smart detection ────────────────────────────────────────────────

def test_cs_lab_gets_fcse_se_lab():
    p = _csv(COURSES_ROWS)
    c = {x.code: x for x in load_courses(p)}["CS101L"]
    assert c.required_lab_room_ids[0] == "FCSE_SE_LAB"
    os.unlink(p)

def test_me_lab_gets_fme_lab():
    p = _csv(COURSES_ROWS)
    c = {x.code: x for x in load_courses(p)}["ME204L"]
    assert c.required_lab_room_ids[0] == "FME_LAB"
    os.unlink(p)

def test_ph_lab_gets_fes_ph_lab():
    p = _csv(COURSES_ROWS)
    c = {x.code: x for x in load_courses(p)}["PH101L"]
    assert c.required_lab_room_ids[0] == "FES_PH_LAB"
    os.unlink(p)

def test_ai_lab_gets_acb_ai_lab():
    p = _csv(COURSES_ROWS)
    c = {x.code: x for x in load_courses(p)}["AI321L"]
    assert c.required_lab_room_ids[0] == "ACB_AI_LAB"
    os.unlink(p)

def test_mm_lab_gets_fcme_mm_lab():
    p = _csv(COURSES_ROWS)
    c = {x.code: x for x in load_courses(p)}["MM231L"]
    assert c.required_lab_room_ids[0] == "FCME_MM_LAB"
    os.unlink(p)

def test_if_lab_gets_tba():
    p = _csv(COURSES_ROWS)
    c = {x.code: x for x in load_courses(p)}["IF101L"]
    assert c.required_lab_room_ids[0] == "TBA_ROOM"
    os.unlink(p)

def test_lecture_has_no_lab_room_ids():
    p = _csv(COURSES_ROWS)
    c = {x.code: x for x in load_courses(p)}["CS101"]
    assert c.required_lab_room_ids == []
    os.unlink(p)


# ── FME keyword detection ─────────────────────────────────────────────────────

def test_fme_keyword_in_title_overrides_prefix():
    """A CS-prefixed lab with 'Workshop' in title should go to FME Lab."""
    rows = [
        ["code","section","title","credit_hours","type","instructor","program","capacity"],
        ["CS999L","A","Workshop Practice Lab","1","lab","TBA","BCS","30"],
    ]
    p = _csv(rows)
    c = load_courses(p)[0]
    assert c.required_lab_room_ids[0] == "FME_LAB", (
        f"Expected FME_LAB, got {c.required_lab_room_ids}"
    )
    os.unlink(p)

def test_fluid_keyword_gives_fme():
    rows = [
        ["code","section","title","credit_hours","type","instructor","program","capacity"],
        ["CE999L","A","Fluid Mechanics Lab","1","lab","TBA","BCE","40"],
    ]
    p = _csv(rows)
    c = load_courses(p)[0]
    assert c.required_lab_room_ids[0] == "FME_LAB"
    os.unlink(p)


# ── Lecture building affinity ─────────────────────────────────────────────────

def test_cs_lecture_allows_acb_fcse():
    p = _csv(COURSES_ROWS)
    c = {x.code: x for x in load_courses(p)}["CS101"]
    assert set(c.allowed_lecture_buildings) == {"ACB", "FCSE"}
    os.unlink(p)

def test_hm_lecture_only_bb():
    rows = [
        ["code","section","title","credit_hours","type","instructor","program","capacity"],
        ["HM101","A","Communication Skills","2","lecture","Mr. Abrar","BME","100"],
    ]
    p = _csv(rows)
    c = load_courses(p)[0]
    assert c.allowed_lecture_buildings == ["BB"]
    os.unlink(p)

def test_ee_lecture_only_fee():
    rows = [
        ["code","section","title","credit_hours","type","instructor","program","capacity"],
        ["EE211","A","Linear Circuit Analysis","3","lecture","Dr. Hadeed","BEE1","35"],
    ]
    p = _csv(rows)
    c = load_courses(p)[0]
    assert c.allowed_lecture_buildings == ["FEE"]
    os.unlink(p)

def test_me_lecture_only_fme():
    rows = [
        ["code","section","title","credit_hours","type","instructor","program","capacity"],
        ["ME313","A","Theory of Machines","3","lecture","Dr. Taimoor","BME1","30"],
    ]
    p = _csv(rows)
    c = load_courses(p)[0]
    assert c.allowed_lecture_buildings == ["FME"]
    os.unlink(p)


# ── Room / slot loading ───────────────────────────────────────────────────────

def test_room_count():
    p = _csv(ROOMS_ROWS)
    assert len(load_rooms(p)) == 8
    os.unlink(p)

def test_room_lab_flag():
    p = _csv(ROOMS_ROWS)
    rooms = {r.room_id: r for r in load_rooms(p)}
    assert rooms["FME_LAB"].is_lab
    assert rooms["ACB_LH4"].is_lecture
    os.unlink(p)

def test_slot_count():
    p = _csv(SLOTS_ROWS)
    assert len(load_timeslots(p)) == 4
    os.unlink(p)

def test_slot_friday_flag():
    p = _csv(SLOTS_ROWS)
    slots = {s.slot_id: s for s in load_timeslots(p)}
    assert slots["FRI_S1"].is_friday
    assert not slots["MON_S1"].is_friday
    os.unlink(p)

def test_slot_label():
    p = _csv(SLOTS_ROWS)
    s = load_timeslots(p)[0]
    assert "08:00" in s.label
    os.unlink(p)


# ── Integration against real data ─────────────────────────────────────────────

def test_load_all_real_data():
    d = Path(__file__).parent.parent / "data"
    if not d.exists():
        print("  [skip] data/ not found")
        return
    courses, slots, rooms = load_all(d)
    assert len(courses) > 0
    assert len(slots)   > 0
    assert len(rooms)   > 0
    labs = [c for c in courses if c.is_lab]
    lecs = [c for c in courses if c.is_lecture]
    print(f"\n  [real] {len(courses)} courses: {len(lecs)} lectures + {len(labs)} labs")


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
