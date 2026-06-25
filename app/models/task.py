from app import db
from datetime import datetime

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='TODO') # TODO, IN_PROGRESS, DONE
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(20), default='LOW') # LOW, MEDIUM, HIGH
    
    # מי יצר את המשימה (המנהל)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # 🔥 למי המשימה מוקצת לביצוע (העובד)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    assignee = db.relationship('User', foreign_keys=[assigned_to_id])
