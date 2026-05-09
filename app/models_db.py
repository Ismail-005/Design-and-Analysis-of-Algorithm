from flask_login import UserMixin
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role          = db.Column(db.String(20), default="admin")


class Room(db.Model):
    __tablename__ = "rooms"
    id        = db.Column(db.Integer, primary_key=True)
    room_id   = db.Column(db.String(50), unique=True, nullable=False)
    room_name = db.Column(db.String(100))
    building  = db.Column(db.String(50))
    capacity  = db.Column(db.Integer, default=0)
    is_lab    = db.Column(db.Boolean, default=False)
    room_type = db.Column(db.String(50))


class Course(db.Model):
    __tablename__ = "courses"
    id                    = db.Column(db.Integer, primary_key=True)
    course_id             = db.Column(db.String(50))
    code                  = db.Column(db.String(20))
    name                  = db.Column(db.String(200))
    credit_hours          = db.Column(db.Integer, default=3)
    section               = db.Column(db.String(10))
    instructor            = db.Column(db.String(100))
    program               = db.Column(db.String(50))
    course_level          = db.Column(db.String(10))
    required_lab_room_ids = db.Column(db.String(200))
    capacity              = db.Column(db.Integer, default=30)
    is_lab                = db.Column(db.Boolean, default=False)


class TimeSlot(db.Model):
    __tablename__ = "timeslots"
    id         = db.Column(db.Integer, primary_key=True)
    slot_id    = db.Column(db.String(50))
    day        = db.Column(db.String(20))
    start_time = db.Column(db.String(10))
    end_time   = db.Column(db.String(10))
    slot_index = db.Column(db.Integer, default=0)
    label      = db.Column(db.String(50))


class ScheduleRun(db.Model):
    __tablename__ = "schedule_runs"
    id           = db.Column(db.Integer, primary_key=True)
    run_at       = db.Column(db.DateTime)
    total        = db.Column(db.Integer, default=0)
    scheduled    = db.Column(db.Integer, default=0)
    unscheduled  = db.Column(db.Integer, default=0)
    success_rate = db.Column(db.Float, default=0.0)
    assignments  = db.relationship("AssignmentRow", backref="run", lazy=True,
                                   cascade="all, delete-orphan")


class AssignmentRow(db.Model):
    __tablename__ = "assignment_rows"
    id           = db.Column(db.Integer, primary_key=True)
    run_id       = db.Column(db.Integer, db.ForeignKey("schedule_runs.id"), nullable=False)
    course_code  = db.Column(db.String(30))
    section      = db.Column(db.String(10))
    course_name  = db.Column(db.String(200))
    instructor   = db.Column(db.String(100))
    room_id      = db.Column(db.String(50))
    room_name    = db.Column(db.String(100))
    building     = db.Column(db.String(50))
    day          = db.Column(db.String(20))
    start_time   = db.Column(db.String(10))
    end_time     = db.Column(db.String(10))
    slot_index   = db.Column(db.Integer)
    is_lab       = db.Column(db.Boolean, default=False)
    program      = db.Column(db.String(50))
