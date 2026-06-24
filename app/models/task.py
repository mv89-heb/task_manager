from app import db
from datetime import datetime

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)  # שדה טקסט ארוך לתיאור
    due_date = db.Column(db.Date, nullable=True)     # תאריך יעד
    status = db.Column(db.String(20), default="TODO") # 👈 שים לב שהשורה הזו קיימת!
    priority = db.Column(db.String(20), default="LOW") # 👈 שים לב שהשורה הזו קיימת!
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
