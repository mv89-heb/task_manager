import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")

    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://")
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///db.sqlite3"

    SQLALCHEMY_TRACK_MODIFICATIONS = False