from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from itsdangerous import URLSafeTimedSerializer as Serializer

# היררכיית התפקידים במערכת (מהגבוה לנמוך)
ROLE_ADMIN = 'admin'        # מנהל מערכת - רואה ומנהל הכל
ROLE_MANAGER = 'manager'    # מנהל תחום - רואה ומנהל רק את המחלקה שלו
ROLE_EMPLOYEE = 'employee'  # עובד - רואה רק את עצמו

ROLE_LABELS = {
    ROLE_ADMIN: 'מנהל מערכת',
    ROLE_MANAGER: 'מנהל תחום',
    ROLE_EMPLOYEE: 'עובד',
}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    # המייל הפך לאופציונלי - לא כולם משתמשים במייל. משמש רק כערוץ נוסף לאיפוס סיסמה/SOS.
    email = db.Column(db.String(120), unique=True, nullable=True)
    # טלפון אופציונלי - לצורך שליחת התראות SOS בוואטסאפ (wa.me)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # תפקיד: admin (מנהל מערכת) / manager (מנהל תחום) / employee (עובד)
    role = db.Column(db.String(20), default=ROLE_EMPLOYEE, nullable=False)

    # שיוך למחלקה (ה"תחום" של המשתמש). מנהל מערכת יכול להישאר ללא מחלקה.
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    department = db.relationship(
        'Department',
        back_populates='members',
        foreign_keys=[department_id]
    )

    # מנהל ישיר (לצורך עץ ארגוני / קו דיווח) - שדה עצמאי, לא חובה
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    direct_manager = db.relationship(
        'User',
        remote_side=[id],
        foreign_keys=[manager_id],
        backref='direct_reports'
    )

    tasks = db.relationship('Task', backref='author', lazy='dynamic', foreign_keys='Task.user_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id}, salt='password-reset-salt')

    @staticmethod
    def verify_reset_token(token, expires_sec=600):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, salt='password-reset-salt', max_age=expires_sec)['user_id']
        except Exception:
            return None
        return User.query.get(user_id)

    # =====================================================
    # 🔐 לוגיקת הרשאות והיררכיה
    # =====================================================

    def is_admin(self):
        return self.role == ROLE_ADMIN

    def is_manager(self):
        return self.role == ROLE_MANAGER

    def is_employee(self):
        return self.role == ROLE_EMPLOYEE

    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)

    def whatsapp_link(self, message=""):
        """
        בונה קישור wa.me תקין לפי מספר הטלפון של המשתמש (או None אם אין טלפון).
        ממיר אוטומטית פורמט ישראלי מקומי (05X-XXXXXXX / 0XXXXXXXXX) לפורמט בינלאומי (972...).
        """
        if not self.phone:
            return None
        digits = ''.join(ch for ch in self.phone if ch.isdigit())
        if not digits:
            return None
        if digits.startswith('0'):
            digits = '972' + digits[1:]
        elif not digits.startswith('972'):
            digits = '972' + digits
        from urllib.parse import quote
        return f"https://wa.me/{digits}?text={quote(message)}"

    def visible_users_query(self):
        """
        מחזיר Query של כל המשתמשים שהמשתמש הנוכחי מורשה לראות/לנהל:
        - מנהל מערכת: כולם.
        - מנהל תחום: רק חברי אותה מחלקה (כולל עצמו).
        - עובד: רק עצמו.
        """
        if self.is_admin():
            return User.query
        if self.is_manager():
            if self.department_id is None:
                return User.query.filter(User.id == self.id)
            return User.query.filter(User.department_id == self.department_id)
        return User.query.filter(User.id == self.id)

    def visible_user_ids(self):
        return [u.id for u in self.visible_users_query().all()]

    def can_manage_user(self, other_user):
        """האם למשתמש הנוכחי מותר לערוך/למחוק את other_user."""
        if self.is_admin():
            return True
        if self.is_manager():
            return (
                other_user.department_id is not None
                and other_user.department_id == self.department_id
                and other_user.role != ROLE_ADMIN
            )
        return False

    def can_assign_role(self, target_role):
        """אילו תפקידים מותר למשתמש הנוכחי להעניק בעת יצירה/עריכה."""
        if self.is_admin():
            return target_role in (ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE)
        if self.is_manager():
            return target_role == ROLE_EMPLOYEE
        return False
