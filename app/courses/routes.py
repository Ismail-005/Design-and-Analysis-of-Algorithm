import io
import csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
import pandas as pd
from app import db
from app.models_db import Course

courses_bp = Blueprint("courses", __name__, template_folder="../templates")


@courses_bp.route("/")
@login_required
def index():
    program_filter = request.args.get("program", "")
    query = Course.query
    if program_filter:
        query = query.filter(Course.program == program_filter)
    courses  = query.order_by(Course.code, Course.section).all()
    programs = [r[0] for r in db.session.query(Course.program).distinct().all() if r[0]]
    return render_template("courses/index.html", courses=courses,
                           programs=programs, program_filter=program_filter)


@courses_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "warning")
        return redirect(url_for("courses.index"))

    filename = file.filename.lower()
    try:
        if filename.endswith((".xlsx", ".xls", ".xlsm")):
            df = pd.read_excel(file)
        else:
            df = pd.read_csv(file)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        Course.query.delete(synchronize_session=False)
        db.session.commit()

        def clean(val, default=""):
            import math
            if val is None:
                return default
            if isinstance(val, float) and math.isnan(val):
                return default
            s = str(val).strip()
            return default if s.lower() == "nan" else s

        for _, row in df.iterrows():
            c = Course(
                course_id             = clean(row.get("course_id")),
                code                  = clean(row.get("code")),
                name                  = clean(row.get("name")),
                credit_hours          = int(row.get("credit_hours") or 3),
                section               = clean(row.get("section")),
                instructor            = clean(row.get("instructor")),
                program               = clean(row.get("program")),
                course_level          = clean(row.get("course_level")),
                required_lab_room_ids = clean(row.get("required_lab_room_ids")),
                capacity              = int(row.get("capacity") or 30),
                is_lab                = clean(row.get("is_lab"), "false").lower() in ("true", "1", "yes"),
            )
            db.session.add(c)
        db.session.commit()
        flash(f"Courses uploaded successfully ({len(df)} records).", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Upload failed: {e}", "danger")

    return redirect(url_for("courses.index"))


@courses_bp.route("/template")
@login_required
def template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["course_id","code","name","credit_hours","section",
                     "instructor","program","course_level","required_lab_room_ids","capacity","is_lab"])
    writer.writerow(["CS101-A","CS101","Intro to Programming","3","A",
                     "Dr. Smith","CS","100","","40","false"])
    writer.writerow(["CS101L-A","CS101L","Intro to Programming Lab","1","A",
                     "Dr. Smith","CS","100","Lab-01","20","true"])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=courses_template.csv"},
    )
