from app import db
from datetime import datetime

RECURRENCE_NONE = 'NONE'
RECURRENCE_DAILY = 'DAILY'
RECURRENCE_WEEKLY = 'WEEKLY'
RECURRENCE_MONTHLY = 'MONTHLY'

RECURRENCE_LABELS = {
    RECURRENCE_NONE: 'חד פעמית',
    RECURRENCE_DAILY: 'כל יום',
    RECURRENCE_WEEKLY: 'כל שבוע',
    RECURRENCE_MONTHLY: 'כל חודש',
}

# גודל מקסימלי לתמונה מצורפת (בבייטים, לפני קידוד base64) - שומר על גודל ה-DB סביר
MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB


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

    # תמונה מצורפת - נשמרת ישירות ב-DB כ-base64 (אין אחסון קבצים חיצוני מוגדר בפרויקט)
    image_data = db.Column(db.Text, nullable=True)
    image_mimetype = db.Column(db.String(50), nullable=True)

    # חזרתיות: כשמשימה עם recurrence != NONE מסומנת כ-DONE, נוצרת אוטומטית המשימה הבאה
    recurrence = db.Column(db.String(20), default=RECURRENCE_NONE)

    # קישור בין משימה חוזרת למשימה שנוצרה ממנה (לצורך מעקב/היסטוריה)
    recurrence_parent_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)
