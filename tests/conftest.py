import os
import pytest

os.environ.setdefault("ADMIN_PASSWORD", "Admin@2026!")


@pytest.fixture
def app(tmp_path, monkeypatch):
    """אפליקציה טרייה עם DB זמני לכל בדיקה - לא נוגעת בפרודקשן בשום צורה."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    from app import create_app, db
    flask_app = create_app()
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    # Flask-Mail קובע את דגל suppress בזמן mail.init_app() בתוך create_app(),
    # כלומר לפני שהשורה למעלה מגדירה TESTING=True - צריך לכפות את זה ידנית
    # כדי שבדיקות עם mail.record_messages() לא ינסו להתחבר ל-SMTP אמיתי.
    flask_app.extensions["mail"].suppress = True

    yield flask_app

    with flask_app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    from app import db
    with app.app_context():
        yield db.session
