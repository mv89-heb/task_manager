from app import db
from datetime import datetime

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    status = db.Column(db.String(20), default="TODO")
    priority = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)