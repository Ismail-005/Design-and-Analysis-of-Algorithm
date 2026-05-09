import io
import sys
import csv
import tempfile
import os
from datetime import datetime
from collections import defaultdict

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, Response, after_this_request, send_file)
from flask_login import login_required
from app import db
from app.models_db import Room, Course, TimeSlot, ScheduleRun, AssignmentRow

schedule_bp = Blueprint("schedule", __name__, template_folder="../templates")


def _clean(val, default=""):
    """Return a clean string, converting None/NaN/'nan' to default."""
    import math
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
    s = str(val).strip()
    return default if s.lower() == "nan" else s


def _build_dataclasses():
    from pathlib import Path
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.models import Room as DRoom, Course as DCourse, TimeSlot as DSlot

    db_rooms   = Room.query.all()
    db_courses = Course.query.all()
    db_slots   = TimeSlot.query.order_by(TimeSlot.slot_index).all()

    rooms = [
        DRoom(
            room_id   = _clean(r.room_id, f"r{r.id}"),
            room_name = _clean(r.room_name) or _clean(r.room_id, f"r{r.id}"),
            building  = _clean(r.building),
            capacity  = r.capacity or 0,
            type      = "lab" if r.is_lab else (_clean(r.room_type) or "lecture_hall"),
        )
        for r in db_rooms
    ]

    slots = [
        DSlot(
            slot_id    = _clean(s.slot_id) or f"s{s.id}",
            day        = _clean(s.day),
            start_time = _clean(s.start_time),
            end_time   = _clean(s.end_time),
            slot_index = s.slot_index,
            day_type   = "friday" if s.day == "Friday" else "regular",
        )
        for s in db_slots
    ]

    courses = []
    for c in db_courses:
        courses.append(
            DCourse(
                source_id    = _clean(c.course_id) or f"c{c.id}",
                code         = _clean(c.code),
                title        = _clean(c.name),
                credit_hours = c.credit_hours or 3,
                section      = _clean(c.section),
                instructor   = _clean(c.instructor),
                program      = _clean(c.program),
                capacity     = c.capacity or 30,
                type         = "lab" if c.is_lab else "lecture",
            )
        )

    return rooms, courses, slots


@schedule_bp.route("/run", methods=["POST"])
@login_required
def run():
    try:
        rooms, courses, slots = _build_dataclasses()
        if not rooms or not courses or not slots:
            flash("Please upload Rooms, Courses, and Time Slots before generating.", "warning")
            return redirect(url_for("schedule.view"))

        from src.scheduler import schedule as run_scheduler
        result = run_scheduler(rooms=rooms, courses=courses, slots=slots,
                               seed=42, verbose=False)

        AssignmentRow.query.delete(synchronize_session=False)
        ScheduleRun.query.delete(synchronize_session=False)
        db.session.commit()

        total       = len(courses)
        unscheduled = len(result.unscheduled)
        scheduled   = total - unscheduled
        rate        = round(scheduled / total * 100, 1) if total else 0.0

        run_obj = ScheduleRun(
            run_at       = datetime.utcnow(),
            total        = total,
            scheduled    = scheduled,
            unscheduled  = unscheduled,
            success_rate = rate,
        )
        db.session.add(run_obj)
        db.session.flush()

        for a in result.assignments:
            db.session.add(AssignmentRow(
                run_id      = run_obj.id,
                course_code = a.course.code,
                section     = a.course.section,
                course_name = a.course.title,
                instructor  = a.course.instructor,
                room_id     = a.room.room_id,
                room_name   = a.room.room_name,
                building    = a.room.building,
                day         = a.slot.day,
                start_time  = a.slot.start_time,
                end_time    = a.slot.end_time,
                slot_index  = a.slot.slot_index,
                is_lab      = False,
                program     = a.course.program,
            ))

        for ls in result.lab_sessions:
            for slot in ls.slots:
                db.session.add(AssignmentRow(
                    run_id      = run_obj.id,
                    course_code = ls.course.code,
                    section     = ls.course.section,
                    course_name = ls.course.title,
                    instructor  = ls.course.instructor,
                    room_id     = ls.room.room_id,
                    room_name   = ls.room.room_name,
                    building    = ls.room.building,
                    day         = ls.day,
                    start_time  = slot.start_time,
                    end_time    = slot.end_time,
                    slot_index  = slot.slot_index,
                    is_lab      = True,
                    program     = ls.course.program,
                ))

        db.session.commit()
        flash(f"Schedule generated! {scheduled}/{total} sections placed ({rate}%).", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Scheduler error: {e}", "danger")

    return redirect(url_for("schedule.view"))


@schedule_bp.route("/")
@schedule_bp.route("/view")
@login_required
def view():
    last_run = ScheduleRun.query.order_by(ScheduleRun.id.desc()).first()
    if not last_run:
        return render_template("schedule/view.html", last_run=None,
                               days=[], grid={}, room_ids=[], room_map={},
                               slot_labels={}, all_slot_indices=[])

    rows = AssignmentRow.query.filter_by(run_id=last_run.id).all()

    days_order = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    days = [d for d in days_order if any(r.day == d for r in rows)]

    grid = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        grid[r.day][r.room_id][r.slot_index].append(r)

    room_ids = sorted({r.room_id for r in rows})
    room_map = {r.room_id: r.room_name for r in rows}

    slot_labels = {}
    for r in rows:
        slot_labels[r.slot_index] = f"{r.start_time}–{r.end_time}"

    all_slot_indices = sorted(slot_labels.keys())

    return render_template(
        "schedule/view.html",
        last_run=last_run,
        days=days,
        grid=grid,
        room_ids=room_ids,
        room_map=room_map,
        slot_labels=slot_labels,
        all_slot_indices=all_slot_indices,
    )


@schedule_bp.route("/search")
@login_required
def search():
    query    = request.args.get("q", "").strip()
    results  = []
    last_run = ScheduleRun.query.order_by(ScheduleRun.id.desc()).first()
    if query and last_run:
        results = AssignmentRow.query.filter(
            AssignmentRow.run_id == last_run.id,
            db.or_(
                AssignmentRow.course_code.ilike(f"%{query}%"),
                AssignmentRow.course_name.ilike(f"%{query}%"),
                AssignmentRow.instructor.ilike(f"%{query}%"),
            )
        ).order_by(AssignmentRow.day, AssignmentRow.slot_index).all()
    return render_template("schedule/search.html", results=results, query=query)


@schedule_bp.route("/download/csv")
@login_required
def download_csv():
    last_run = ScheduleRun.query.order_by(ScheduleRun.id.desc()).first()
    if not last_run:
        flash("No schedule found. Please run the scheduler first.", "warning")
        return redirect(url_for("schedule.view"))

    rows = AssignmentRow.query.filter_by(run_id=last_run.id).order_by(
        AssignmentRow.day, AssignmentRow.slot_index, AssignmentRow.room_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Course Code","Section","Course Name","Instructor",
                     "Room","Building","Day","Start","End","Type"])
    for r in rows:
        writer.writerow([
            r.course_code, r.section, r.course_name, r.instructor,
            r.room_name, r.building, r.day, r.start_time, r.end_time,
            "Lab" if r.is_lab else "Lecture",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=timetable.csv"},
    )


@schedule_bp.route("/download/pdf")
@login_required
def download_pdf():
    last_run = ScheduleRun.query.order_by(ScheduleRun.id.desc()).first()
    if not last_run:
        flash("No schedule found. Please run the scheduler first.", "warning")
        return redirect(url_for("schedule.view"))

    try:
        rooms, courses, slots = _build_dataclasses()
        from src.scheduler import schedule as run_scheduler
        from src.exporter  import export_pdf

        result   = run_scheduler(rooms=rooms, courses=courses, slots=slots,
                                 seed=42, verbose=False)
        tmp      = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_path = tmp.name
        tmp.close()

        export_pdf(result, slots, rooms, tmp_path)

        @after_this_request
        def _cleanup(response):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return response

        return send_file(tmp_path, mimetype="application/pdf",
                         as_attachment=True, download_name="timetable.pdf")

    except Exception as e:
        flash(f"PDF generation failed: {e}", "danger")
        return redirect(url_for("schedule.view"))
