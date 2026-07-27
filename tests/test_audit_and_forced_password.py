"""בדיקות: יומן ביקורת (Audit log), ואכיפת חובת החלפת סיסמה."""


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


# ---------- Audit log ----------

def test_delete_user_creates_audit_entry(client, db_session):
    from app.models.user import User
    from app.models.audit_log import AuditLog

    admin = _login_admin(client)
    victim = User(username="auditvictim", role="employee")
    victim.set_password("x")
    db_session.add(victim)
    db_session.commit()
    victim_id = victim.id

    client.post(f"/admin/delete_user/{victim_id}")

    entry = AuditLog.query.filter_by(action="delete_user", target_id=victim_id).first()
    assert entry is not None
    assert entry.actor_username == admin.username
    assert entry.target_label == "auditvictim"


def test_role_change_creates_audit_entry(client, db_session):
    from app.models.user import User
    from app.models.audit_log import AuditLog

    admin = _login_admin(client)
    emp = User(username="rolechangeaudit", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post(f"/admin/user/{emp.id}/edit", data={
        "username": "rolechangeaudit", "email": "", "phone": "", "role": "manager",
        "department_id": "", "manager_id": "", "password": "",
    })

    entry = AuditLog.query.filter_by(action="change_role", target_id=emp.id).first()
    assert entry is not None
    assert "employee" in entry.details and "manager" in entry.details


def test_no_role_change_entry_when_role_unchanged(client, db_session):
    from app.models.user import User
    from app.models.audit_log import AuditLog

    admin = _login_admin(client)
    emp = User(username="samerole", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post(f"/admin/user/{emp.id}/edit", data={
        "username": "samerole", "email": "", "phone": "", "role": "employee",
        "department_id": "", "manager_id": "", "password": "",
    })

    entry = AuditLog.query.filter_by(action="change_role", target_id=emp.id).first()
    assert entry is None


def test_password_reset_by_admin_creates_audit_entry(client, db_session):
    from app.models.user import User
    from app.models.audit_log import AuditLog

    admin = _login_admin(client)
    emp = User(username="pwresetaudit", role="employee")
    emp.set_password("OldPassw0rd")
    db_session.add(emp)
    db_session.commit()

    client.post(f"/admin/user/{emp.id}/edit", data={
        "username": "pwresetaudit", "email": "", "phone": "", "role": "employee",
        "department_id": "", "manager_id": "", "password": "NewPassw0rd",
    })

    entry = AuditLog.query.filter_by(action="reset_user_password", target_id=emp.id).first()
    assert entry is not None


def test_delete_department_creates_audit_entry(client, db_session):
    from app.models.department import Department
    from app.models.audit_log import AuditLog

    _login_admin(client)
    dept = Department(name="מחלקת ביקורת")
    db_session.add(dept)
    db_session.commit()
    dept_id = dept.id

    client.post(f"/admin/departments/{dept_id}/delete")

    entry = AuditLog.query.filter_by(action="delete_department", target_id=dept_id).first()
    assert entry is not None
    assert entry.target_label == "מחלקת ביקורת"


def test_delete_task_creates_audit_entry(client, db_session):
    from app.models.task import Task
    from app.models.audit_log import AuditLog

    admin = _login_admin(client)
    task = Task(title="משימה לביקורת", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    client.post(f"/delete/{task_id}")

    entry = AuditLog.query.filter_by(action="delete_task", target_id=task_id).first()
    assert entry is not None
    assert entry.target_label == "משימה לביקורת"


def test_bulk_reassign_creates_audit_entry(client, db_session):
    from app.models.user import User
    from app.models.task import Task
    from app.models.audit_log import AuditLog

    admin = _login_admin(client)
    emp = User(username="bulkauditemp", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    task = Task(title="למעקב ביקורת", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()

    client.post("/bulk_reassign_tasks", data={"task_ids": [str(task.id)], "assignee_id": str(emp.id)})

    entry = AuditLog.query.filter_by(action="bulk_reassign_tasks", target_id=emp.id).first()
    assert entry is not None


def test_rescue_tool_creates_system_audit_entry(app, client, monkeypatch):
    from app.models.audit_log import AuditLog

    monkeypatch.setenv("ENABLE_ADMIN_TOOLS", "true")
    monkeypatch.setenv("MIGRATION_SECRET", "audittest")

    client.get("/rescue?key=audittest")

    with app.app_context():
        entry = AuditLog.query.filter_by(action="use_rescue_tool").first()
        assert entry is not None
        assert entry.actor_username == "system"
        assert entry.actor_id is None


def test_audit_log_page_requires_admin(client, db_session):
    from app.models.user import User

    mgr = User(username="auditpageperm", role="manager")
    mgr.set_password("x")
    db_session.add(mgr)
    db_session.commit()

    client.post("/login", data={"username": "auditpageperm", "password": "x"})
    r = client.get("/admin/audit_log")
    assert r.status_code == 302  # redirected away, not shown


def test_audit_log_page_renders_for_admin(client, db_session):
    from app.models.user import User
    from app.models.audit_log import log_audit

    admin = _login_admin(client)
    log_audit(admin, "delete_user", target_label="someone")

    r = client.get("/admin/audit_log")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "מחיקת משתמש" in body


# ---------- אכיפת חובת החלפת סיסמה ----------

def test_rescue_sets_must_change_password_flag(client, db_session, monkeypatch):
    from app.models.user import User

    monkeypatch.setenv("ENABLE_ADMIN_TOOLS", "true")
    monkeypatch.setenv("MIGRATION_SECRET", "rescuetest")

    client.get("/rescue?key=rescuetest")

    mv = User.query.filter_by(username="mv").first()
    assert mv is not None
    assert mv.must_change_password is True


def test_flagged_user_redirected_to_change_password(client, db_session):
    from app.models.user import User

    emp = User(username="flaggeduser", role="employee", must_change_password=True)
    emp.set_password("OldPass1")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "flaggeduser", "password": "OldPass1"})
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/change_password" in r.headers["Location"]


def test_unflagged_user_not_redirected(client, db_session):
    from app.models.user import User

    emp = User(username="unflaggeduser", role="employee", must_change_password=False)
    emp.set_password("OldPass1")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "unflaggeduser", "password": "OldPass1"})
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200


def test_logout_accessible_while_flagged(client, db_session):
    from app.models.user import User

    emp = User(username="flaggedlogout", role="employee", must_change_password=True)
    emp.set_password("OldPass1")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "flaggedlogout", "password": "OldPass1"})
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code == 302
    assert "/change_password" not in r.headers["Location"]


def test_change_password_rejects_weak_password(client, db_session):
    from app.models.user import User

    emp = User(username="weakchangepw", role="employee", must_change_password=True)
    emp.set_password("OldPass1")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "weakchangepw", "password": "OldPass1"})
    r = client.post("/change_password", data={"password": "weak"})
    body = r.get_data(as_text=True)
    assert "8 תווים" in body

    refreshed = User.query.filter_by(username="weakchangepw").first()
    assert refreshed.must_change_password is True  # עדיין נעול


def test_change_password_clears_flag_and_unlocks(client, db_session):
    from app.models.user import User

    emp = User(username="unlockme", role="employee", must_change_password=True)
    emp.set_password("OldPass1")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "unlockme", "password": "OldPass1"})
    client.post("/change_password", data={"password": "BrandNewPass1"})

    refreshed = User.query.filter_by(username="unlockme").first()
    assert refreshed.must_change_password is False
    assert refreshed.check_password("BrandNewPass1")

    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200


def test_admin_can_force_password_change_on_other_user(client, db_session):
    from app.models.user import User
    from app.models.audit_log import AuditLog

    admin = _login_admin(client)
    emp = User(username="forcedbyadmin", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post(f"/admin/user/{emp.id}/edit", data={
        "username": "forcedbyadmin", "email": "", "phone": "", "role": "employee",
        "department_id": "", "manager_id": "", "password": "",
        "force_password_change": "1",
    })

    refreshed = User.query.filter_by(username="forcedbyadmin").first()
    assert refreshed.must_change_password is True

    entry = AuditLog.query.filter_by(action="force_password_change", target_id=emp.id).first()
    assert entry is not None


def test_admin_can_unset_forced_password_change(client, db_session):
    from app.models.user import User

    admin = _login_admin(client)
    emp = User(username="unforceme", role="employee", must_change_password=True)
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post(f"/admin/user/{emp.id}/edit", data={
        "username": "unforceme", "email": "", "phone": "", "role": "employee",
        "department_id": "", "manager_id": "", "password": "",
        # force_password_change checkbox not sent = unchecked
    })

    refreshed = User.query.filter_by(username="unforceme").first()
    assert refreshed.must_change_password is False
