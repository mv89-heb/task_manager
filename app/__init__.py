import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import text, inspect
from config import Config

# הגדרת אובייקטי הבסיס של המערכת (כולל מנוע המייל)
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'tasks.login'
login_manager.login_message = 'אנא התחבר כדי לגשת לעמוד זה.'
login_manager.login_message_category = 'danger'

mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def _add_columns_if_missing(app, table_name, columns):
    """
    מוסיף עמודות חסרות לטבלה קיימת, בצורה אידמפוטנטית ובטוחה לפי dialect.
    columns: רשימת tuples (column_name, sql_type) למשל [('department_id', 'INTEGER')]
    """
    dialect = db.engine.dialect.name  # 'postgresql' או 'sqlite'
    quoted_table = f'"{table_name}"' if table_name == 'user' else table_name

    if dialect == 'postgresql':
        for column_name, sql_type in columns:
            try:
                db.session.execute(text(f'ALTER TABLE {quoted_table} ADD COLUMN IF NOT EXISTS {column_name} {sql_type}'))
                db.session.commit()
                app.logger.info(f"✅ עמודת '{column_name}' קיימת/נוספה בטבלת {table_name}.")
            except Exception:
                db.session.rollback()
                app.logger.exception(f"❌ נכשלה הוספת העמודה '{column_name}' לטבלת {table_name}.")
    else:
        try:
            inspector = inspect(db.engine)
            existing_columns = {c['name'] for c in inspector.get_columns(table_name)}
        except Exception:
            app.logger.exception(f"לא ניתן לבדוק עמודות טבלת {table_name}.")
            existing_columns = set()

        for column_name, sql_type in columns:
            if column_name not in existing_columns:
                try:
                    db.session.execute(text(f'ALTER TABLE {quoted_table} ADD COLUMN {column_name} {sql_type}'))
                    db.session.commit()
                    app.logger.info(f"✅ עמודת '{column_name}' נוספה אוטומטית לטבלת {table_name}.")
                except Exception:
                    db.session.rollback()
                    app.logger.exception(f"❌ נכשלה הוספת העמודה '{column_name}' לטבלת {table_name}.")


def _auto_migrate_and_seed_admin(app):
    """
    רץ אוטומטית בכל עליית שרת (idempotent - בטוח להריץ שוב ושוב):
    1. מוודא שהעמודות החדשות בטבלאות user ו-task קיימות.
    2. מוודא שקיים לפחות משתמש admin אחד. אם לא - יוצר אחד (או משדרג את 'mv' הישן).
    בכך אין תלות בביקור ידני בכתובת מיגרציה - זה קורה לבד עם כל deploy.
    """
    from app.models.user import User, ROLE_ADMIN

    _add_columns_if_missing(app, 'user', [
        ('department_id', 'INTEGER'),
        ('manager_id', 'INTEGER'),
        ('phone', 'VARCHAR(20)'),
    ])
    _add_columns_if_missing(app, 'task', [
        ('image_data', 'TEXT'),
        ('image_mimetype', 'VARCHAR(50)'),
        ('recurrence', "VARCHAR(20) DEFAULT 'NONE'"),
        ('recurrence_parent_id', 'INTEGER'),
    ])

    # ⚠️ שינוי התחברות: המייל כבר לא חובה (לא לכולם יש מייל, ההתחברות עכשיו לפי שם משתמש).
    # במסד קיים שנוצר לפני השינוי, לעמודת email עדיין יש אילוץ NOT NULL - משחררים אותו כאן.
    if db.engine.dialect.name == 'postgresql':
        try:
            db.session.execute(text('ALTER TABLE "user" ALTER COLUMN email DROP NOT NULL'))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # אם כבר קיים מנהל מערכת - אין מה לעשות
    if User.query.filter_by(role=ROLE_ADMIN).first():
        return

    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@taskmanager.local')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'Admin@2026!')

    # אם קיים המשתמש הישן 'mv' - פשוט נהפוך אותו לאדמין במקום ליצור כפול
    legacy_admin = User.query.filter_by(username='mv').first()
    if legacy_admin:
        legacy_admin.role = ROLE_ADMIN
        db.session.commit()
        app.logger.info("👑 המשתמש 'mv' שודרג אוטומטית ל-admin.")
        return

    # אם קיים כבר משתמש עם שם/מייל זהה (אך לא admin) - נשדרג אותו במקום ליצור כפילות
    existing = User.query.filter(
        (User.username == admin_username) | (User.email == admin_email)
    ).first()
    if existing:
        existing.role = ROLE_ADMIN
        db.session.commit()
        app.logger.info(f"👑 המשתמש '{existing.username}' שודרג אוטומטית ל-admin.")
        return

    new_admin = User(username=admin_username, email=admin_email, role=ROLE_ADMIN)
    new_admin.set_password(admin_password)
    db.session.add(new_admin)
    db.session.commit()
    app.logger.info(f"👑 נוצר משתמש admin חדש אוטומטית: {admin_username}")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ⚠️ אבטחת עוגיות: מונע גישה ל-cookie דרך JS, ומגביל שליחה חוצת-אתרים.
    # SECURE=True דורש HTTPS - ב-Render זה תמיד המצב, אבל בפיתוח מקומי (http)
    # נשאיר את זה כבוי כדי לא לשבור התחברות מקומית.
    is_production = bool(os.environ.get('RENDER'))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = is_production

    if is_production and app.config['SECRET_KEY'] == 'default-dev-key-123':
        app.logger.warning(
            "⚠️ אזהרת אבטחה: רץ בפרודקשן עם SECRET_KEY ברירת מחדל! "
            "יש להגדיר משתנה סביבה SECRET_KEY ייחודי ב-Render בהקדם."
        )

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)  # הפעלת המייל בתוך האפליקציה
    csrf.init_app(app)  # הגנת CSRF על כל טופס POST באתר
    limiter.init_app(app)

    with app.app_context():
        from app.models.department import Department
        from app.models.user import User
        from app.models.task import Task
        from app.models.comment import TaskComment
        from app.models.notification import Notification
        from app.models.task_template import TaskTemplate

        from app.routes.tasks import bp as task_bp
        from app.routes.dashboard import bp as dash_bp

        app.register_blueprint(task_bp)
        app.register_blueprint(dash_bp)

        db.create_all()
        _auto_migrate_and_seed_admin(app)

    return app


@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))
