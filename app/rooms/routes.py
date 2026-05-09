import io
import csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
import pandas as pd
from app import db
from app.models_db import Room

rooms_bp = Blueprint("rooms", __name__, template_folder="../templates")


@rooms_bp.route("/")
@login_required
def index():
    rooms = Room.query.order_by(Room.room_id).all()
    return render_template("rooms/index.html", rooms=rooms)


@rooms_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "warning")
        return redirect(url_for("rooms.index"))

    filename = file.filename.lower()
    try:
        if filename.endswith((".xlsx", ".xls", ".xlsm")):
            df = pd.read_excel(file)
        else:
            df = pd.read_csv(file)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        Room.query.delete(synchronize_session=False)
        db.session.commit()

        for _, row in df.iterrows():
            r = Room(
                room_id   = str(row.get("room_id", "")).strip(),
                room_name = str(row.get("room_name", "")).strip(),
                building  = str(row.get("building", "")).strip(),
                capacity  = int(row.get("capacity", 0) or 0),
                is_lab    = str(row.get("is_lab", "false")).strip().lower() in ("true", "1", "yes"),
                room_type = str(row.get("type", row.get("room_type", ""))).strip(),
            )
            db.session.add(r)
        db.session.commit()
        flash(f"Rooms uploaded successfully ({len(df)} records).", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Upload failed: {e}", "danger")

    return redirect(url_for("rooms.index"))


@rooms_bp.route("/template")
@login_required
def template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["room_id", "room_name", "building", "capacity", "is_lab", "type"])
    writer.writerow(["CR-101", "Classroom 101", "Academic Block", "60", "false", "classroom"])
    writer.writerow(["Lab-01", "CS Lab 1", "CS Building", "30", "true", "lab"])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=rooms_template.csv"},
    )
