#!/usr/bin/env python3
"""
main.py  —  GIK Institute Timetable Scheduling System (Enhanced)

Usage examples:
  python main.py                        # full run, all outputs
  python main.py --format pdf           # PDF only
  python main.py --validate             # run constraint validator
  python main.py --seed 99              # different variant
  python main.py --data my_data/        # custom input directory
  python main.py --out  my_output/      # custom output directory
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.parser      import load_all
from src.scheduler   import schedule
from src.constraints import ScheduleValidator
from src.exporter    import export_csv, export_html, export_pdf, export_all
from src.utils       import utilisation_stats, lab_room_usage, lecture_building_usage


BANNER = """
╔══════════════════════════════════════════════════════════════╗
║   GIK Institute – Timetable Scheduling System  (Enhanced)   ║
║   Fall 2025  |  Intelligent Room & Lab Allocation            ║
╚══════════════════════════════════════════════════════════════╝
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GIK Timetable Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--data",     default="data",   help="Input data directory")
    p.add_argument("--out",      default="output", help="Output directory")
    p.add_argument("--seed",     type=int, default=42)
    p.add_argument("--multi",    type=int, default=0,
                   help="Generate N variants and keep the best one")
    p.add_argument("--validate", action="store_true",
                   help="Run post-hoc constraint validator")
    p.add_argument("--format",   nargs="+",
                   choices=["csv", "html", "pdf", "all"], default=["all"])
    p.add_argument("--verbose",  action="store_true")
    return p.parse_args()


def print_validation(violations: list[str]) -> None:
    print("\n── Constraint Validation ─────────────────────────────────────")
    if not violations:
        print("  ✓  Zero violations — schedule is fully constraint-satisfying.")
    else:
        print(f"  ✗  {len(violations)} violation(s):\n")
        for v in violations:
            print(f"     • {v}")
    print("──────────────────────────────────────────────────────────────\n")


def print_stats(result, rooms, slots) -> None:
    s = utilisation_stats(result, rooms, slots)
    print("── Schedule Statistics ───────────────────────────────────────")
    print(f"  Lectures placed     : {s['lectures_placed']}")
    print(f"  Lab sessions placed : {s['labs_placed']}")
    print(f"  Unscheduled         : {s['unscheduled']}")
    print(f"  Success rate        : {s['success_rate']}%")
    print(f"  Rooms used          : {s['rooms_used']}")
    print(f"  Busiest room        : {s['busiest_room'][0]}  ({s['busiest_room'][1]} classes)")
    print(f"  Busiest instructor  : {s['busiest_instructor'][0]}  ({s['busiest_instructor'][1]} classes)")
    print(f"  Busiest day         : {s['busiest_day'][0]}  ({s['busiest_day'][1]} classes)")
    print(f"  Avg classes/slot    : {s['avg_classes_per_slot']}")

    lab_usage = lab_room_usage(result)
    if lab_usage:
        print("\n  Lab room usage:")
        for rm, cnt in lab_usage.items():
            print(f"    {rm:<30} {cnt} sessions")

    bld_usage = lecture_building_usage(result)
    if bld_usage:
        print("\n  Lecture building usage:")
        for bld, cnt in bld_usage.items():
            print(f"    {bld:<20} {cnt} lectures")

    print("──────────────────────────────────────────────────────────────\n")


def generate_schedule(courses, slots, rooms, seed: int, multi: int, verbose: bool):
    if multi <= 1:
        return schedule(courses, slots, rooms, seed=seed, verbose=verbose)

    print(f"Generating {multi} timetable variants …")
    best = None
    best_seed = seed

    for i in range(multi):
        variant_seed = seed + i
        result = schedule(courses, slots, rooms, seed=variant_seed, verbose=verbose)
        if best is None or result.success_rate > best.success_rate:
            best = result
            best_seed = variant_seed

    print(f"  Best variant seed: {best_seed}  ({best.success_rate:.1f}% success)\n")
    return best


def main() -> None:
    print(BANNER)
    args  = parse_args()
    t0    = time.time()
    out_d = Path(args.out)
    out_d.mkdir(parents=True, exist_ok=True)

    # ── Load ──────────────────────────────────────────────────────────────────
    print("Loading input files …")
    courses, slots, rooms = load_all(Path(args.data))
    labs     = sum(1 for c in courses if c.is_lab)
    lectures = len(courses) - labs
    print(f"  {len(courses)} courses  ({lectures} lectures + {labs} labs)")
    print(f"  {len(slots)} time slots  |  {len(rooms)} rooms\n")

    # ── Schedule ──────────────────────────────────────────────────────────────
    print("Scheduling …")
    result = generate_schedule(
        courses, slots, rooms,
        seed=args.seed,
        multi=args.multi,
        verbose=args.verbose,
    )

    # ── Validate ──────────────────────────────────────────────────────────────
    if args.validate:
        validator  = ScheduleValidator()
        violations = validator.validate(result.assignments, result.lab_sessions)
        print_validation(violations)

    # ── Stats ─────────────────────────────────────────────────────────────────
    print_stats(result, rooms, slots)

    # ── Export ────────────────────────────────────────────────────────────────
    fmts = set(args.format)
    if "all" in fmts:
        print("Exporting …")
        paths = export_all(result, slots, rooms, out_d)
        for fmt, p in paths.items():
            print(f"  {fmt.upper():<5} → {p}")
    else:
        if "csv"  in fmts: export_csv (result,              out_d / "timetable_fall_2025.csv")
        if "html" in fmts: export_html(result, slots, rooms, out_d / "timetable_fall_2025.html")
        if "pdf"  in fmts: export_pdf (result, slots, rooms, out_d / "timetable_fall_2025.pdf")

    # ── Unscheduled log ───────────────────────────────────────────────────────
    if result.unscheduled:
        log = out_d / "unscheduled.txt"
        with open(log, "w") as f:
            f.write("Unscheduled Courses – GIK Fall 2025\n")
            f.write("=" * 55 + "\n\n")
            for c in result.unscheduled:
                tag = "LAB" if c.is_lab else "LEC"
                f.write(f"[{tag}] {c.display:<25} {c.instructor:<35} "
                        f"[{c.program}] cap={c.capacity}\n")
        print(f"\n⚠  {len(result.unscheduled)} unscheduled course(s) → {log}")

    print(f"\n✓  Done in {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
