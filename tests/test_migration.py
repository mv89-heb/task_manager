"""בדיקות שדרוג סכימה אוטומטי - מוודאות שהתרחיש שקרה בפועל בפרודקשן לא יחזור."""
from sqlalchemy import text


def test_legacy_user_table_gets_new_columns_and_admin_promoted(app):
    from app import db
    from app.models.user import User
    from werkzeug.security import generate_password_hash

    with app.app_context():
        # מדמים סכימה ישנה: טבלת user בלי department_id/manager_id, עם mv כ-'manager'
        db.session.execute(text('DROP TABLE "user"'))
        db.session.execute(text("""
            CREATE TABLE "user" (
                id INTEGER PRIMARY KEY,
                username VARCHAR(64) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(256) NOT NULL,
                role VARCHAR(20) DEFAULT 'employee' NOT NULL
            )
        """))
        db.session.commit()
        db.session.execute(
            text("INSERT INTO \"user\" (username, email, password_hash, role) VALUES ('mv', 'mv@test.com', :ph, 'manager')"),
            {"ph": generate_password_hash("123456")}
        )
        db.session.commit()

    # מדמים redeploy - יצירת app מחדש מריצה את ה-migration האוטומטי
    from app import create_app
    app2 = create_app()
    with app2.app_context():
        cols = {c[1] for c in db.session.execute(text('PRAGMA table_info("user")')).fetchall()}
        assert "department_id" in cols
        assert "manager_id" in cols

        mv = User.query.filter_by(username="mv").first()
        assert mv.role == "admin"
        assert mv.check_password("123456")  # הסיסמה הישנה לא נפגעה


def test_legacy_task_table_gets_new_columns(app):
    from app import db

    with app.app_context():
        cols = {c[1] for c in db.session.execute(text('PRAGMA table_info(task)')).fetchall()}
        assert "image_data" in cols
        assert "recurrence" in cols
        assert "recurrence_parent_id" in cols
