from app import db
from datetime import datetime
import threading


class Notification(db.Model):
    """התראה פנימית למשתמש - מוצגת דרך פעמון ההתראות בסרגל העליון."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
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


def _send_email_in_background(app, msg):
    """
    רץ בתוך thread נפרד. אם ה-SMTP לא מוגדר/לא זמין/איטי, זה עלול לקחת הרבה זמן
    להיכשל (smtplib לא חוסם timeout קצר כברירת מחדל) - בגלל זה זה קריטי שזה
    לעולם לא ירוץ בתוך thread הבקשה עצמו, אחרת המשתמש רואה עמוד "חושב" ארוך.
    """
    with app.app_context():
        from app import mail
        try:
            mail.send(msg)
        except Exception:
            app.logger.exception("שליחת מייל ברקע נכשלה")


def queue_email(msg):
    """
    שולח הודעת מייל ברקע (thread נפרד) במקום לחסום את הבקשה הנוכחית.
    יש לקרוא לזה מתוך קונטקסט של בקשה פעילה (current_app זמין).
    """
    from flask import current_app
    app_obj = current_app._get_current_object()
    thread = threading.Thread(target=_send_email_in_background, args=(app_obj, msg), daemon=True)
    thread.start()


def notify_with_email(user, message, link=None, icon='bi-bell', email_subject=None, email_body=None):
    """
    יוצר התראה פנימית + שולח מייל אוטומטי ברקע אם למשתמש יש כתובת מייל.
    'user' חייב להיות אובייקט User (לא רק id) כדי שנוכל לבדוק user.email.
    מחזיר True אם הייתה כתובת מייל ותור השליחה ברקע הופעל בהצלחה (לא בהכרח
    שהמייל כבר הגיע בפועל - זה קורה אסינכרונית!). מחזיר False אם אין כתובת מייל בכלל.
    יצירת ההתראה הפנימית עצמה היא תמיד best-effort ולא תלויה בתוצאת המייל.
    """
    if not user:
        return False

    notify(user.id, message, link=link, icon=icon)

    if not user.email:
        return False

    from flask import current_app, request
    from flask_mail import Message
    try:
        if link and link.startswith('http'):
            full_link = link
        elif link and request:
            full_link = request.host_url.rstrip('/') + link
        else:
            full_link = None

        msg = Message(email_subject or "התראה ממערכת המשימות", recipients=[user.email])
        msg.body = (email_body or message) + (f"\n\nלצפייה במערכת: {full_link}" if full_link else "")
        queue_email(msg)
        return True
    except Exception:
        current_app.logger.exception(f"הכנת מייל אוטומטי נכשלה עבור {user.username}")
        return False


def notify_recipients_multi_channel(recipients, message, link=None, icon='bi-bell',
                                     email_subject=None, send_email=True, send_whatsapp=True):
    """
    שולח התראה פנימית + מייל ברקע + קישור וואטסאפ לרשימת נמענים - הלוגיקה המשותפת
    בין SOS והודעות קבוצתיות (שהיו כמעט זהות, רק עם toggles/הודעות שונות).

    מחזיר (email_sent_to, email_failed_to, whatsapp_targets):
    - email_sent_to/failed_to: רשימות שמות משתמשים
    - whatsapp_targets: רשימת dict בפורמט {"name": ..., "link": ...} מוכן לתצוגה בממשק
    """
    from flask import current_app
    from flask_mail import Message

    email_sent_to, email_failed_to, whatsapp_targets = [], [], []

    for recipient in recipients:
        notify(recipient.id, message, link=link, icon=icon)

        if send_email and recipient.email:
            try:
                msg = Message(email_subject or "התראה ממערכת המשימות", recipients=[recipient.email])
                msg.body = message
                queue_email(msg)
                email_sent_to.append(recipient.username)
            except Exception:
                current_app.logger.exception(f"הכנת מייל נכשלה עבור {recipient.username}")
                email_failed_to.append(recipient.username)

        if send_whatsapp:
            wa_link = recipient.whatsapp_link(message)
            if wa_link:
                whatsapp_targets.append({"name": recipient.username, "link": wa_link})

    return email_sent_to, email_failed_to, whatsapp_targets
