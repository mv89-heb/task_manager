from app import db
from datetime import datetime


class TaskComment(db.Model):
    """תגובה/עדכון על משימה - יומן תקשורת בתוך המערכת."""
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    task = db.relationship('Task', backref=db.backref('comments', order_by='TaskComment.created_at', lazy='dynamic', cascade='all, delete-orphan'))
    author = db.relationship('User')

    def __repr__(self):
        return f'<TaskComment {self.id} on task {self.task_id}>'
