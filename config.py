import os

database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

class Config:
    # כאן אנחנו מושכים את המפתח הסודי מ-Render
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-key-123') 
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///db.sqlite3'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
