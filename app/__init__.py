from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from app.auth.routes    import auth_bp
    from app.main.routes    import main_bp
    from app.rooms.routes   import rooms_bp
    from app.courses.routes import courses_bp
    from app.timeslots.routes import timeslots_bp
    from app.schedule.routes  import schedule_bp
    from app.teacher.routes   import teacher_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(rooms_bp,     url_prefix="/rooms")
    app.register_blueprint(courses_bp,   url_prefix="/courses")
    app.register_blueprint(timeslots_bp, url_prefix="/timeslots")
    app.register_blueprint(schedule_bp,  url_prefix="/schedule")
    app.register_blueprint(teacher_bp,   url_prefix="/teacher")

    with app.app_context():
        db.create_all()
        _seed_admin()

    return app


def _seed_admin():
    from app.models_db import User
    from werkzeug.security import generate_password_hash
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()
