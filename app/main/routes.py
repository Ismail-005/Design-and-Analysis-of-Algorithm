from flask import Blueprint, render_template
from flask_login import login_required
from app.models_db import Room, Course, TimeSlot, ScheduleRun

main_bp = Blueprint("main", __name__, template_folder="../templates")


@main_bp.route("/")
@login_required
def dashboard():
    room_count     = Room.query.count()
    course_count   = Course.query.count()
    timeslot_count = TimeSlot.query.count()
    last_run       = ScheduleRun.query.order_by(ScheduleRun.id.desc()).first()
    return render_template(
        "main/dashboard.html",
        room_count=room_count,
        course_count=course_count,
        timeslot_count=timeslot_count,
        last_run=last_run,
    )
