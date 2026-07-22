from app import db
from datetime import datetime


class Notification(db.Model):
    """התראה פנימית למשתמש - מוצגת דרך פעמון ההתראות בסרגל העליון."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    icon = db.Column(db.String(50), default='bi-bell')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<Notification {self.id} for user {self.user_id}>'


def notify(user_id, message, link=None, icon='bi-bell'):
    """יוצר התראה חדשה למשתמש נתון. לא זורק חריגה אם משהו נכשל - התראה היא best-effort."""
    if not user_id:
        return
    try:
        n = Notification(user_id=user_id, message=message, link=link, icon=icon)
        db.session.add(n)
        db.session.commit()
    except Exception:
        db.session.rollback()


def notify_with_email(user, message, link=None, icon='bi-bell', email_subject=None, email_body=None):
    """
    יוצר התראה פנימית + שולח מייל אוטומטי אם למשתמש יש כתובת מייל.
    'user' חייב להיות אובייקט User (לא רק id) כדי שנוכל לבדוק user.email.
    מחזיר True אם המייל נשלח בפועל בהצלחה, False אם נכשל או לא היה מה לשלוח -
    כדי שהקורא יוכל להציג למשתמש אם רלוונטי (למשל בהודעת flash).
    יצירת ההתראה הפנימית עצמה היא תמיד best-effort ולא תלויה בתוצאת המייל.
    """
    if not user:
        return False

    notify(user.id, message, link=link, icon=icon)

    if not user.email:
        return False

    from flask import current_app, request
    from flask_mail import Message
    from app import mail
    try:
        if link and link.startswith('http'):
            full_link = link
        elif link and request:
            full_link = request.host_url.rstrip('/') + link
        else:
            full_link = None

        msg = Message(email_subject or "התראה ממערכת המשימות", recipients=[user.email])
        msg.body = (email_body or message) + (f"\n\nלצפייה במערכת: {full_link}" if full_link else "")
        mail.send(msg)
        return True
    except Exception:
        current_app.logger.exception(f"שליחת מייל אוטומטי נכשלה עבור {user.username}")
        return False
