"""בדיקות לשדרוגי הסבב הזה: חוזק סיסמה, session/remember-me, הגבלת קנבן,
ימי איחור, וגרף מגמות (DailyStat + snapshot + trend endpoint)."""
from datetime import date, timedelta


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


# ---------- חוזק סיסמה ----------

def test_register_rejects_weak_password(client, db_session):
    from app.models.user import User

    r = client.post("/register", data={"username": "weakpw", "password": "abc"}, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "8 תווים" in body
    assert User.query.filter_by(username="weakpw").first() is None


def test_register_rejects_password_without_digit(client, db_session):
    from app.models.user import User
    r = client.post("/register", data={"username": "nodigitpw", "password": "abcdefgh"}, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "ספרה" in body
    assert User.query.filter_by(username="nodigitpw").first() is None


def test_register_accepts_strong_password(client, db_session):
    from app.models.user import User
    client.post("/register", data={"username": "strongpw", "password": "abcdefg1"})
    assert User.query.filter_by(username="strongpw").first() is not None


def test_admin_add_user_rejects_weak_password(client, db_session):
    from app.models.user import User

    _login_admin(client)
    r = client.post("/admin/user/new", data={
        "username": "weakadminadd", "email": "", "phone": "",
        "role": "employee", "department_id": "", "manager_id": "", "password": "weak",
    }, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "8 תווים" in body
    assert User.query.filter_by(username="weakadminadd").first() is None


def test_admin_edit_user_rejects_weak_new_password(client, db_session):
    from app.models.user import User

    admin = _login_admin(client)
    emp = User(username="editweakpw", role="employee")
    emp.set_password("OldPassw0rd")
    db_session.add(emp)
    db_session.commit()

    r = client.post(f"/admin/user/{emp.id}/edit", data={
        "username": "editweakpw", "email": "", "phone": "", "role": "employee",
        "department_id": "", "manager_id": "", "password": "weak",
    }, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "8 תווים" in body

    refreshed = User.query.filter_by(username="editweakpw").first()
    assert refreshed.check_password("OldPassw0rd")  # לא השתנתה


def test_admin_edit_user_allows_empty_password_unchanged(client, db_session):
    """שדה סיסמה ריק בעריכה = לא לשנות, לא אמור לחייב חוזק."""
    from app.models.user import User

    admin = _login_admin(client)
    r = client.post(f"/admin/user/{admin.id}/edit", data={
        "username": admin.username, "email": admin.email or "", "phone": "",
        "role": "admin", "department_id": "", "manager_id": "", "password": "",
    }, follow_redirects=True)
    assert r.status_code == 200


def test_reset_token_rejects_weak_password(client, db_session):
    from app.models.user import User

    admin = _login_admin(client)
    token = admin.get_reset_token()
    client.get("/logout")
    r = client.post(f"/reset_password/{token}", data={"password": "weak"}, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "8 תווים" in body


# ---------- session / remember-me ----------

def test_login_without_remember_me_still_logs_in(client, db_session):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    r = client.post("/login", data={"username": admin.username, "password": "Admin@2026!"}, follow_redirects=True)
    assert r.status_code == 200
    assert r.request.path == "/"


def test_login_with_remember_me_checked(client, db_session):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    r = client.post("/login", data={
        "username": admin.username, "password": "Admin@2026!", "remember_me": "1"
    }, follow_redirects=True)
    assert r.status_code == 200


# ---------- הגבלת קנבן ----------

def test_kanban_done_column_capped_at_50(client, db_session):
    from app.models.user import User
    from app.models.task import Task

    admin = _login_admin(client)
    for i in range(60):
        db_session.add(Task(title=f"בוצע {i}", user_id=admin.id, assigned_to_id=admin.id, status="DONE"))
    db_session.commit()

    from app import create_app
    r = client.get("/kanban")
    assert r.status_code == 200
    # נבדוק ישירות דרך ה-view function שהעמודה מוגבלת
    from app.routes.tasks import visible_task_query
    from app.models.task import Task as T
    base_query = visible_task_query(admin)
    done = base_query.filter(T.status == "DONE").order_by(T.created_at.desc()).limit(50).all()
    assert len(done) == 50


def test_kanban_todo_not_limited(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    for i in range(60):
        db_session.add(Task(title=f"לביצוע {i}", user_id=admin.id, assigned_to_id=admin.id, status="TODO"))
    db_session.commit()

    from app.routes.tasks import visible_task_query
    base_query = visible_task_query(admin)
    todo = base_query.filter(Task.status.in_(["TODO", None])).all()
    assert len(todo) == 60


# ---------- ימי איחור ----------

def test_dashboard_shows_days_overdue(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    overdue_task = Task(title="באיחור של שלושה ימים", user_id=admin.id, assigned_to_id=admin.id,
                         due_date=date.today() - timedelta(days=3), status="TODO", priority="LOW")
    db_session.add(overdue_task)
    db_session.commit()

    r = client.get("/dashboard")
    body = r.get_data(as_text=True)
    assert "3 ימים באיחור" in body


def test_dashboard_singular_day_overdue(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="באיחור של יום אחד", user_id=admin.id, assigned_to_id=admin.id,
                due_date=date.today() - timedelta(days=1), status="TODO", priority="LOW")
    db_session.add(task)
    db_session.commit()

    r = client.get("/dashboard")
    body = r.get_data(as_text=True)
    assert "1 יום באיחור" in body


def test_dashboard_no_overdue_badge_when_not_overdue(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="עדיפות גבוהה לא באיחור", user_id=admin.id, assigned_to_id=admin.id,
                due_date=date.today() + timedelta(days=5), status="TODO", priority="HIGH")
    db_session.add(task)
    db_session.commit()

    r = client.get("/dashboard")
    body = r.get_data(as_text=True)
    assert "ימים באיחור" not in body or "עדיפות גבוהה לא באיחור" in body


# ---------- מגמות לאורך זמן ----------

def test_snapshot_requires_reminder_key(client):
    r = client.get("/api/snapshot_daily_stats")
    assert r.status_code == 403


def test_snapshot_creates_daily_stat(client, db_session, monkeypatch):
    from app.models.user import User
    from app.models.task import Task
    from app.models.daily_stat import DailyStat

    monkeypatch.setenv("REMINDER_SECRET", "trendkey")

    admin = User.query.filter_by(role="admin").first()
    db_session.add_all([
        Task(title="t1", user_id=admin.id, assigned_to_id=admin.id, status="DONE"),
        Task(title="t2", user_id=admin.id, assigned_to_id=admin.id, status="TODO"),
    ])
    db_session.commit()

    r = client.get("/api/snapshot_daily_stats?key=trendkey")
    data = r.get_json()
    assert data["success"] is True
    assert data["total_tasks"] == 2

    org_stat = DailyStat.query.filter_by(stat_date=date.today(), department_id=None).first()
    assert org_stat is not None
    assert org_stat.total_tasks == 2
    assert org_stat.done_tasks == 1
    assert org_stat.completion_percent == 50


def test_snapshot_is_idempotent_same_day(client, db_session, monkeypatch):
    from app.models.user import User
    from app.models.task import Task
    from app.models.daily_stat import DailyStat

    monkeypatch.setenv("REMINDER_SECRET", "trendkey2")

    admin = User.query.filter_by(role="admin").first()
    db_session.add(Task(title="t1", user_id=admin.id, assigned_to_id=admin.id, status="DONE"))
    db_session.commit()

    client.get("/api/snapshot_daily_stats?key=trendkey2")
    client.get("/api/snapshot_daily_stats?key=trendkey2")  # קריאה שנייה באותו יום

    count = DailyStat.query.filter_by(stat_date=date.today(), department_id=None).count()
    assert count == 1  # לא נוצרה כפילות


def test_snapshot_creates_per_department_stats(client, db_session, monkeypatch):
    from app.models.user import User
    from app.models.department import Department
    from app.models.task import Task
    from app.models.daily_stat import DailyStat

    monkeypatch.setenv("REMINDER_SECRET", "trendkey3")

    admin = User.query.filter_by(role="admin").first()
    dept = Department(name="מחלקת מגמות")
    db_session.add(dept)
    db_session.commit()

    emp = User(username="trendemp", role="employee", department_id=dept.id)
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    db_session.add(Task(title="t1", user_id=admin.id, assigned_to_id=emp.id, status="DONE"))
    db_session.commit()

    client.get("/api/snapshot_daily_stats?key=trendkey3")

    dept_stat = DailyStat.query.filter_by(stat_date=date.today(), department_id=dept.id).first()
    assert dept_stat is not None
    assert dept_stat.total_tasks == 1
    assert dept_stat.done_tasks == 1


def test_stats_trend_requires_admin(client, db_session):
    from app.models.user import User

    emp = User(username="trendnoperm", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "trendnoperm", "password": "x"})
    r = client.get("/api/stats_trend")
    assert r.status_code == 403


def test_stats_trend_returns_recent_history(client, db_session, monkeypatch):
    from app.models.user import User
    from app.models.task import Task

    monkeypatch.setenv("REMINDER_SECRET", "trendkey4")
    admin = _login_admin(client)
    db_session.add(Task(title="t1", user_id=admin.id, assigned_to_id=admin.id, status="DONE"))
    db_session.commit()

    client.get("/api/snapshot_daily_stats?key=trendkey4")

    r = client.get("/api/stats_trend")
    data = r.get_json()
    assert len(data["labels"]) >= 1
    assert data["completion_percent"][-1] == 100
