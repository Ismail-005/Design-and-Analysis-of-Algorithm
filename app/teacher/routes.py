from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models_db import AssignmentRow, ScheduleRun

teacher_bp = Blueprint("teacher", __name__, template_folder="../templates")

DAYS_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday"]


@teacher_bp.route("/")
@login_required
def index():
    last_run    = ScheduleRun.query.order_by(ScheduleRun.id.desc()).first()
    instructors = []
    schedule    = {}
    selected    = request.args.get("instructor", "").strip()
    days        = []
    slot_labels = {}
    all_slot_indices = []

    if last_run:
        instructors = sorted({
            r.instructor
            for r in AssignmentRow.query.filter_by(run_id=last_run.id).all()
            if r.instructor
        })

        if selected:
            rows = AssignmentRow.query.filter_by(
                run_id=last_run.id, instructor=selected).all()

            days = [d for d in DAYS_ORDER if any(r.day == d for r in rows)]
            for r in rows:
                slot_labels[r.slot_index] = f"{r.start_time}–{r.end_time}"
            all_slot_indices = sorted(slot_labels.keys())

            for r in rows:
                schedule.setdefault(r.day, {}).setdefault(r.slot_index, []).append(r)

    return render_template(
        "teacher/index.html",
        instructors=instructors,
        selected=selected,
        schedule=schedule,
        days=days,
        slot_labels=slot_labels,
        all_slot_indices=all_slot_indices,
    )
