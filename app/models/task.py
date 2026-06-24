from app import db
from datetime import datetime

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="TODO")
    priority = db.Column(db.String(20), default="LOW")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # שינינו כאן ל-True כדי לאפשר למשימות הישנות שלך להישאר במערכת
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
