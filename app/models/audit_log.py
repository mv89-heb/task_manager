from app import db
from datetime import datetime


class AuditLog(db.Model):
    """
    יומן ביקורת - מתעד פעולות רגישות (מחיקות, שינויי הרשאות, כלי ניהול מסוכנים).
    לא מתעד כל פעולה במערכת (זה היה מציף) - רק דברים שחשוב לדעת "מי עשה מה" אם משהו משתבש.
    """
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    actor_username = db.Column(db.String(64), nullable=True)  # נשמר גם כטקסט - שרד גם אם המשתמש נמחק אחר כך
    action = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    target_label = db.Column(db.String(200), nullable=True)  # למשל שם המשתמש/מחלקה שנמחקו
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    actor = db.relationship('User', foreign_keys=[actor_id])

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.actor_username} at {self.created_at}>'


def log_audit(actor, action, target_type=None, target_id=None, target_label=None, details=None):
    """
    רושם פעולה ליומן הביקורת. Best-effort - אם הרישום עצמו נכשל, לא מפיל את הפעולה המקורית.
    'actor' יכול להיות אובייקט User או None (למשל פעולה שבוצעה ע"י cron/מפתח מיגרציה).
    """
    try:
        entry = AuditLog(
            actor_id=actor.id if actor else None,
            actor_username=actor.username if actor else "system",
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            details=details,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
