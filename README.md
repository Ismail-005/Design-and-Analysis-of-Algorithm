# GIK Institute – Automated Timetable Scheduling System

Automatically generates a clash-free weekly timetable from Excel/CSV input files and exports it as a **GIK-style PDF**, interactive **HTML**, and flat **CSV**.

---

## Project Structure

```
timetable_scheduler/
├── data/
│   ├── courses.csv           ← offered courses (or .xlsx)
│   ├── timeslots.csv         ← available time slots
│   ├── rooms.xlsx            ← rooms / lecture halls
│   └── constraints.json      ← hard/soft constraint config
├── src/
│   ├── models.py             ← Course, Room, TimeSlot, Assignment dataclasses
│   ├── parser.py             ← reads & validates all input files
│   ├── scheduler.py          ← CSP backtracking engine
│   ├── constraints.py        ← clash detection + room ranking
│   ├── exporter.py           ← PDF, HTML, CSV outputs
│   └── utils.py              ← bitmask helpers, statistics, colors
├── tests/
│   ├── test_parser.py
│   ├── test_scheduler.py
│   └── test_constraints.py
├── output/                   ← generated timetables land here
├── main.py                   ← CLI entry point
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1 – Install dependencies

```bash
pip install -r requirements.txt
```

### 2 – Prepare input files

Place these three files in `data/`:

| File | Required columns |
|------|-----------------|
| `courses.csv` | `code, section, title, credit_hours, type, instructor, program, capacity` |
| `timeslots.csv` | `slot_id, day, start_time, end_time, slot_index, day_type` |
| `rooms.xlsx` | `room_id, room_name, building, type, capacity` |

> **type** for courses: `lecture` or `lab`  
> **type** for rooms: `lecture_hall`, `main_hall`, or `lab`  
> **day_type** for slots: `regular` (Mon–Thu) or `friday`

### 3 – Run

```bash
# Generate all output formats (PDF + HTML + CSV)
python main.py

# PDF only
python main.py --format pdf

# Custom data and output directories
python main.py --data my_data/ --out my_output/

# Validate the generated schedule for constraint violations
python main.py --validate

# Generate 3 timetable variants, pick the best
python main.py --multi 3

# Reproducible run with a specific seed
python main.py --seed 99
```

---

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--data DIR` | `data/` | Directory containing input files |
| `--out DIR` | `output/` | Directory for generated output |
| `--seed INT` | `42` | Random seed for reproducibility |
| `--multi N` | `0` | Generate N variants, use the best |
| `--validate` | off | Run post-hoc constraint validator |
| `--format F [F...]` | `all` | Output formats: `pdf`, `html`, `csv`, `all` |
| `--verbose` | off | Extra debug output |

---

## Algorithm

### Scheduling (CSP with backtracking)

1. **Sort courses** — descending by enrollment capacity, lectures before labs, higher credit-hours first. Largest/hardest courses are placed first.
2. **Sort slots** — Mon → Fri, earlier slots first. Friday slots are used as a last resort.
3. **For each course**, iterate candidate `(slot, room)` pairs in priority order:
   - Rooms are pre-ranked per course via `rank_rooms()` (capacity fit, type match, building affinity).
   - The first pair that passes all hard constraints is committed immediately.
4. **Unscheduled courses** (no valid slot found) are written to `output/unscheduled.txt`.

### Conflict Detection (O(1) hash-set lookups)

Each committed assignment updates three hash sets keyed by `slot_id`:

| Set | Blocks |
|-----|--------|
| `slot_instructors[slot_id]` | Same instructor in same slot |
| `slot_rooms[slot_id]` | Same room in same slot |
| `slot_programs[slot_id]` | Same student program in same slot |

`TBA` / `TBD` instructors are excluded from instructor clash checks.

### Room Ranking Score

| Criterion | Points |
|-----------|--------|
| Room capacity ≥ course capacity | +4 |
| Room type matches course type | +2 |
| Room is in preferred building for program | +2 |
| TBA_ROOM fallback | −1 |

---

## Hard Constraints

| Constraint | Description |
|-----------|-------------|
| No instructor clash | An instructor cannot be in two places at once |
| No room double-booking | A room can hold only one class per slot |
| No program clash | A student cohort has at most one class per slot |
| Room type match | Lab courses → lab rooms; lectures → lecture/main halls |
| Capacity check | Room capacity must cover course enrollment |

---

## Output Files

| File | Description |
|------|-------------|
| `output/timetable_fall_2025.pdf` | GIK-style landscape A3 PDF, one page per day |
| `output/timetable_fall_2025.html` | Interactive HTML with day tabs and color-coded cells |
| `output/timetable_fall_2025.csv` | Flat CSV — one row per assignment |
| `output/unscheduled.txt` | List of courses that could not be placed (if any) |

---

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Individual test files
python tests/test_parser.py
python tests/test_constraints.py
python tests/test_scheduler.py
```

---

## Extending the System

### Add a new hard constraint

In `src/constraints.py`, extend `ConflictChecker.can_assign()`:

```python
def can_assign(self, course, room, slot):
    ...
    # Example: block 8am slots for final-year courses
    if course.code.endswith("48") and slot.slot_index == 1:
        return False, "final-year courses avoid 8am slots"
    ...
```

### Add a new output format (e.g. Excel)

In `src/exporter.py`, add an `export_excel()` function following the same pattern as `export_csv()`, then call it from `export_all()` and wire it up in `main.py`.

### Use OR-Tools instead of backtracking

Install `ortools` and replace `src/scheduler.py` with a CP-SAT model. The `ConflictChecker` constraints translate directly to `model.AddAllDifferent()` and `model.AddNoOverlap()` calls. All other modules (`parser`, `exporter`, `utils`) remain unchanged.

---

## Input File Examples

### courses.csv

```csv
code,section,title,credit_hours,type,instructor,program,capacity
CS221,A,Data Structures & Algorithms,3,lecture,Mr. Qasim Riaz,BAI,50
CS221L,A,Data Structures Lab,1,lab,Muhammad Naeem,BAI,50
CE221,B,Digital Logic Design,3,lecture,Dr. Waqar Ahmad,BCE,40
```

### timeslots.csv

```csv
slot_id,day,start_time,end_time,slot_index,day_type
MON_S1,Monday,08:00,08:50,1,regular
MON_S2,Monday,09:00,09:50,2,regular
MON_S3,Monday,10:30,11:20,3,regular
FRI_S1,Friday,08:00,08:50,1,friday
```

### rooms.xlsx

| room_id | room_name | building | type | capacity |
|---------|-----------|----------|------|----------|
| CS_LH1 | CS LH1 | FCSE | lecture_hall | 80 |
| ACB_LH4 | AcB LH4 | ACB | lecture_hall | 60 |
| ACB_AI_LAB | ACB AI Lab | ACB | lab | 50 |

---

## License

For academic use at GIK Institute of Engineering Sciences and Technology.
