import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "gik-timetable-secret-2025")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'timetable.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
