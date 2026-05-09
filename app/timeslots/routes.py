import io
import csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
import pandas as pd
from app import db
from app.models_db import TimeSlot

timeslots_bp = Blueprint("timeslots", __name__, template_folder="../templates")


@timeslots_bp.route("/")
@login_required
def index():
    slots = TimeSlot.query.order_by(TimeSlot.day, TimeSlot.slot_index).all()
    return render_template("timeslots/index.html", slots=slots)


@timeslots_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "warning")
        return redirect(url_for("timeslots.index"))

    filename = file.filename.lower()
    try:
        if filename.endswith((".xlsx", ".xls", ".xlsm")):
            df = pd.read_excel(file)
        else:
            df = pd.read_csv(file)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        TimeSlot.query.delete(synchronize_session=False)
        db.session.commit()

        for _, row in df.iterrows():
            s = TimeSlot(
                slot_id    = str(row.get("slot_id", "")).strip(),
                day        = str(row.get("day", "")).strip(),
                start_time = str(row.get("start_time", "")).strip(),
                end_time   = str(row.get("end_time", "")).strip(),
                slot_index = int(row.get("slot_index", 0) or 0),
                label      = str(row.get("label", "")).strip(),
            )
            db.session.add(s)
        db.session.commit()
        flash(f"Time slots uploaded successfully ({len(df)} records).", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Upload failed: {e}", "danger")

    return redirect(url_for("timeslots.index"))


@timeslots_bp.route("/template")
@login_required
def template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["slot_id", "day", "start_time", "end_time", "slot_index", "label"])
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    times = [("08:00","09:00"),("09:00","10:00"),("10:00","11:00"),
             ("11:00","12:00"),("12:00","13:00"),("13:00","14:00"),
             ("14:00","15:00"),("15:00","16:00"),("16:00","17:00")]
    idx = 0
    for day in days:
        for i,(st,en) in enumerate(times):
            writer.writerow([f"{day[:3].upper()}{i+1}", day, st, en, idx, f"{day[:3]} {st}"])
            idx += 1
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=timeslots_template.csv"},
    )
