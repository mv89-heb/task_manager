"""
בדיקות Phase 2 - Workflow Automation:
- ולידציה מלאה (conditions/actions)
- CRUD + Audit לכל שינוי כלל
- כל Trigger בנפרד (task_created, status_changed, task_overdue, report_submitted)
- כל Action בנפרד (notify_assignee, notify_department_managers, notify_all_admins,
  change_priority, reassign_to)
- הרשאות: admin בלבד לניהול כללים
"""
from datetime import date, timedelta


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


# ---------- ולידציה ----------

def test_validate_conditions_rejects_invalid_field(app):
    from app.services import automation_service as svc
    with app.app_context():
        import pytest
        with pytest.raises(svc.AutomationValidationError):
            svc.validate_conditions([{"field": "not_a_real_field", "operator": "equals", "value": "x"}])


def test_validate_conditions_rejects_invalid_operator(app):
    from app.services import automation_service as svc
    with app.app_context():
        import pytest
        with pytest.raises(svc.AutomationValidationError):
            svc.validate_conditions([{"field": "status", "operator": "greater_than", "value": "DONE"}])


def test_validate_conditions_rejects_invalid_status_value(app):
    from app.services import automation_service as svc
    with app.app_context():
        import pytest
        with pytest.raises(svc.AutomationValidationError):
            svc.validate_conditions([{"field": "status", "operator": "equals", "value": "NOT_A_STATUS"}])


def test_validate_conditions_accepts_empty_list(app):
    from app.services import automation_service as svc
    with app.app_context():
        assert svc.validate_conditions([]) is True


def test_validate_conditions_rejects_non_list(app):
    from app.services import automation_service as svc
    with app.app_context():
        import pytest
        with pytest.raises(svc.AutomationValidationError):
            svc.validate_conditions("not a list")


def test_validate_actions_rejects_empty_list(app):
    from app.services import automation_service as svc
    with app.app_context():
        import pytest
        with pytest.raises(svc.AutomationValidationError):
            svc.validate_actions([])


def test_validate_actions_rejects_unknown_type(app):
    from app.services import automation_service as svc
    with app.app_context():
        import pytest
        with pytest.raises(svc.AutomationValidationError):
            svc.validate_actions([{"type": "send_sms", "params": {}}])


def test_validate_actions_change_priority_requires_valid_priority(app, db_session):
    from app.services import automation_service as svc
    import pytest
    with pytest.raises(svc.AutomationValidationError):
        svc.validate_actions([{"type": "change_priority", "params": {"priority": "URGENT"}}])


def test_validate_actions_reassign_to_requires_existing_user(app, db_session):
    from app.services import automation_service as svc
    import pytest
    with pytest.raises(svc.AutomationValidationError):
        svc.validate_actions([{"type": "reassign_to", "params": {"user_id": 999999}}])


def test_validate_trigger_event_rejects_unknown(app):
    from app.services import automation_service as svc
    with app.app_context():
        import pytest
        with pytest.raises(svc.AutomationValidationError):
            svc.validate_trigger_event("task_deleted_forever")


# ---------- CRUD + Audit ----------

def test_create_rule_via_service(db_session):
    from app.services import automation_service as svc
    from app.models.user import User

    admin = User.query.filter_by(role="admin").first()
    rule = svc.create_rule(
        admin, "כלל בדיקה", "task_created",
        [{"field": "priority", "operator": "equals", "value": "HIGH"}],
        [{"type": "notify_all_admins", "params": {}}],
    )
    assert rule.id is not None
    assert rule.conditions == [{"field": "priority", "operator": "equals", "value": "HIGH"}]


def test_create_rule_creates_audit_entry(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.audit_log import AuditLog

    admin = User.query.filter_by(role="admin").first()
    svc.create_rule(admin, "כלל לביקורת", "task_created", [], [{"type": "notify_all_admins", "params": {}}])

    entry = AuditLog.query.filter_by(action="create_automation_rule").first()
    assert entry is not None
    assert entry.target_label == "כלל לביקורת"


def test_update_rule_creates_audit_entry_with_diff(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.audit_log import AuditLog

    admin = User.query.filter_by(role="admin").first()
    rule = svc.create_rule(admin, "כלל לעדכון", "task_created", [], [{"type": "notify_all_admins", "params": {}}])

    svc.update_rule(admin, rule, name="שם חדש")

    entry = AuditLog.query.filter_by(action="update_automation_rule", target_id=rule.id).first()
    assert entry is not None
    assert "שם חדש" in entry.details


def test_delete_rule_creates_audit_entry(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.audit_log import AuditLog
    from app.models.automation import AutomationRule

    admin = User.query.filter_by(role="admin").first()
    rule = svc.create_rule(admin, "כלל למחיקה", "task_created", [], [{"type": "notify_all_admins", "params": {}}])
    rule_id = rule.id

    svc.delete_rule(admin, rule)

    assert AutomationRule.query.get(rule_id) is None
    entry = AuditLog.query.filter_by(action="delete_automation_rule", target_id=rule_id).first()
    assert entry is not None


def test_manager_sees_only_own_department_and_global_rules(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.department import Department

    admin = User.query.filter_by(role="admin").first()
    dept_a = Department(name="מחלקת אוטומציה א")
    dept_b = Department(name="מחלקת אוטומציה ב")
    db_session.add_all([dept_a, dept_b])
    db_session.commit()

    mgr = User(username="automgr", role="manager", department_id=dept_a.id)
    mgr.set_password("x")
    db_session.add(mgr)
    db_session.commit()

    svc.create_rule(admin, "כלל גלובלי", "task_created", [], [{"type": "notify_all_admins", "params": {}}])
    svc.create_rule(admin, "כלל מחלקה א", "task_created", [], [{"type": "notify_all_admins", "params": {}}], department_id=dept_a.id)
    svc.create_rule(admin, "כלל מחלקה ב", "task_created", [], [{"type": "notify_all_admins", "params": {}}], department_id=dept_b.id)

    visible = svc.list_rules_for(mgr)
    names = {r.name for r in visible}
    assert "כלל גלובלי" in names
    assert "כלל מחלקה א" in names
    assert "כלל מחלקה ב" not in names


def test_employee_sees_no_rules(db_session):
    from app.services import automation_service as svc
    from app.models.user import User

    emp = User(username="autoemp", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    assert svc.list_rules_for(emp) == []


def test_admin_automations_page_requires_admin(client, db_session):
    from app.models.user import User

    mgr = User(username="noautomgr", role="manager")
    mgr.set_password("x")
    db_session.add(mgr)
    db_session.commit()

    client.post("/login", data={"username": "noautomgr", "password": "x"})
    r = client.get("/admin/automations", follow_redirects=True)
    assert "אין לך הרשאה" in r.get_data(as_text=True) or "רק מנהל מערכת" in r.get_data(as_text=True)


# ---------- כל Trigger בנפרד ----------

def test_trigger_task_created(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task
    from app.models.automation import AutomationLog

    admin = User.query.filter_by(role="admin").first()
    rule = svc.create_rule(admin, "בעת יצירה", "task_created", [], [{"type": "change_priority", "params": {"priority": "HIGH"}}])

    task = Task(title="נוצרה", user_id=admin.id, assigned_to_id=admin.id, priority="LOW")
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_created", task)

    refreshed = Task.query.get(task.id)
    assert refreshed.priority == "HIGH"
    log = AutomationLog.query.filter_by(rule_id=rule.id, task_id=task.id).first()
    assert log is not None
    assert log.success is True


def test_trigger_status_changed(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    svc.create_rule(
        admin, "בעת שינוי סטטוס", "status_changed",
        [{"field": "status", "operator": "equals", "value": "DONE"}],
        [{"type": "change_priority", "params": {"priority": "LOW"}}]
    )

    task = Task(title="השתנה", user_id=admin.id, assigned_to_id=admin.id, priority="HIGH", status="DONE")
    db_session.add(task)
    db_session.commit()

    svc.trigger("status_changed", task)

    assert Task.query.get(task.id).priority == "LOW"


def test_trigger_via_http_update_status_route(client, db_session):
    """בדיקת אינטגרציה: ה-route בפועל (לא רק הפונקציה) מפעיל את הכלל."""
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    admin = _login_admin(client)
    svc.create_rule(
        admin, "אינטגרציה שינוי סטטוס", "status_changed",
        [{"field": "status", "operator": "equals", "value": "DONE"}],
        [{"type": "change_priority", "params": {"priority": "LOW"}}]
    )

    task = Task(title="אינטגרציה", user_id=admin.id, assigned_to_id=admin.id, priority="HIGH", status="TODO")
    db_session.add(task)
    db_session.commit()

    client.post(f"/update_status/{task.id}", json={"status": "DONE"})

    assert Task.query.get(task.id).priority == "LOW"


def test_trigger_task_overdue(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    svc.create_rule(admin, "באיחור", "task_overdue",
                     [{"field": "is_overdue", "operator": "equals", "value": True}],
                     [{"type": "change_priority", "params": {"priority": "HIGH"}}])

    task = Task(title="משימה ישנה", user_id=admin.id, assigned_to_id=admin.id, priority="LOW",
                due_date=date.today() - timedelta(days=3), status="TODO")
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_overdue", task)

    assert Task.query.get(task.id).priority == "HIGH"


def test_trigger_task_overdue_via_cron_endpoint(client, db_session, monkeypatch):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    monkeypatch.setenv("REMINDER_SECRET", "phase2key")

    admin = User.query.filter_by(role="admin").first()
    svc.create_rule(admin, "באיחור cron", "task_overdue", [], [{"type": "change_priority", "params": {"priority": "HIGH"}}])

    task = Task(title="ישנה לקרון", user_id=admin.id, assigned_to_id=admin.id, priority="LOW",
                due_date=date.today() - timedelta(days=1), status="TODO")
    db_session.add(task)
    db_session.commit()

    r = client.get("/api/run_overdue_automations?key=phase2key")
    assert r.status_code == 200
    assert r.get_json()["checked"] == 1
    assert Task.query.get(task.id).priority == "HIGH"


def test_trigger_report_submitted(client, db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    svc.create_rule(admin, "דיווח חדש", "report_submitted", [], [{"type": "change_priority", "params": {"priority": "HIGH"}}])

    client.post("/report", data={"title": "תקלה לאוטומציה", "description": ""})

    task = Task.query.filter_by(title="תקלה לאוטומציה").first()
    assert task.priority == "HIGH"


# ---------- כל Action בנפרד ----------

def test_action_notify_assignee(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task
    from app.models.notification import Notification

    admin = User.query.filter_by(role="admin").first()
    emp = User(username="notifyassigneeuser", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    rule = svc.create_rule(admin, "התרע לאחראי", "task_created", [], [{"type": "notify_assignee", "params": {}}])
    task = Task(title="עם אחראי", user_id=admin.id, assigned_to_id=emp.id)
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_created", task)

    notif = Notification.query.filter_by(user_id=emp.id).first()
    assert notif is not None
    assert rule.name in notif.message


def test_action_notify_department_managers(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.department import Department
    from app.models.task import Task
    from app.models.notification import Notification

    admin = User.query.filter_by(role="admin").first()
    dept = Department(name="מחלקת פעולה")
    db_session.add(dept)
    db_session.commit()

    mgr = User(username="actionmgr", role="manager", department_id=dept.id)
    mgr.set_password("x")
    emp = User(username="actionemp", role="employee", department_id=dept.id)
    emp.set_password("x")
    db_session.add_all([mgr, emp])
    db_session.commit()

    svc.create_rule(admin, "התרע למנהלים", "task_created", [], [{"type": "notify_department_managers", "params": {}}])
    task = Task(title="למחלקה", user_id=admin.id, assigned_to_id=emp.id)
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_created", task)

    assert Notification.query.filter_by(user_id=mgr.id).first() is not None


def test_action_notify_all_admins(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task
    from app.models.notification import Notification

    admin = User.query.filter_by(role="admin").first()
    svc.create_rule(admin, "התרע לכל המנהלים", "task_created", [], [{"type": "notify_all_admins", "params": {}}])
    task = Task(title="לכולם", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_created", task)

    assert Notification.query.filter_by(user_id=admin.id).first() is not None


def test_action_change_priority(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    svc.create_rule(admin, "שנה עדיפות", "task_created", [], [{"type": "change_priority", "params": {"priority": "MEDIUM"}}])
    task = Task(title="לשינוי עדיפות", user_id=admin.id, assigned_to_id=admin.id, priority="LOW")
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_created", task)

    assert Task.query.get(task.id).priority == "MEDIUM"


def test_action_reassign_to(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    emp = User(username="reassigntargetuser", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    svc.create_rule(admin, "הקצה מחדש", "task_created", [], [{"type": "reassign_to", "params": {"user_id": emp.id}}])
    task = Task(title="להקצאה מחדש", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_created", task)

    assert Task.query.get(task.id).assigned_to_id == emp.id


# ---------- כללי המרה נוספים ----------

def test_condition_prevents_action_when_not_met(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    svc.create_rule(
        admin, "רק לעדיפות גבוהה", "task_created",
        [{"field": "priority", "operator": "equals", "value": "HIGH"}],
        [{"type": "change_priority", "params": {"priority": "LOW"}}]
    )

    task = Task(title="לא גבוהה", user_id=admin.id, assigned_to_id=admin.id, priority="MEDIUM")
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_created", task)

    assert Task.query.get(task.id).priority == "MEDIUM"  # לא השתנה כי התנאי לא התקיים


def test_inactive_rule_does_not_fire(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    svc.create_rule(admin, "כבוי", "task_created", [], [{"type": "change_priority", "params": {"priority": "HIGH"}}], is_active=False)

    task = Task(title="לא אמור להשתנות", user_id=admin.id, assigned_to_id=admin.id, priority="LOW")
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_created", task)

    assert Task.query.get(task.id).priority == "LOW"


def test_rule_scoped_to_department_does_not_fire_for_other_department(db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.department import Department
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    dept_a = Department(name="מחלקת סקופ א")
    dept_b = Department(name="מחלקת סקופ ב")
    db_session.add_all([dept_a, dept_b])
    db_session.commit()

    emp_b = User(username="scopeemp", role="employee", department_id=dept_b.id)
    emp_b.set_password("x")
    db_session.add(emp_b)
    db_session.commit()

    svc.create_rule(admin, "רק מחלקה א", "task_created", [], [{"type": "change_priority", "params": {"priority": "HIGH"}}], department_id=dept_a.id)

    task = Task(title="במחלקה ב", user_id=admin.id, assigned_to_id=emp_b.id, priority="LOW")
    db_session.add(task)
    db_session.commit()

    svc.trigger("task_created", task)

    assert Task.query.get(task.id).priority == "LOW"  # לא הופעל כי זה מחלקה אחרת


def test_toggle_rule_via_route(client, db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.automation import AutomationRule

    admin = _login_admin(client)
    rule = svc.create_rule(admin, "להפעלה/כיבוי", "task_created", [], [{"type": "notify_all_admins", "params": {}}])
    assert rule.is_active is True

    client.post(f"/admin/automations/{rule.id}/toggle")
    assert AutomationRule.query.get(rule.id).is_active is False


def test_delete_rule_via_route(client, db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.automation import AutomationRule

    admin = _login_admin(client)
    rule = svc.create_rule(admin, "למחיקה דרך route", "task_created", [], [{"type": "notify_all_admins", "params": {}}])
    rule_id = rule.id

    client.post(f"/admin/automations/{rule_id}/delete")
    assert AutomationRule.query.get(rule_id) is None


def test_create_rule_via_route_with_invalid_data_shows_error(client, db_session):
    _login_admin(client)
    r = client.post("/admin/automations", data={
        "name": "כלל שגוי", "trigger_event": "not_a_trigger",
        "action_type": "notify_all_admins",
    }, follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "לא נתמך" in body


def test_automation_log_page_renders(client, db_session):
    from app.services import automation_service as svc
    from app.models.user import User
    from app.models.task import Task

    admin = _login_admin(client)
    rule = svc.create_rule(admin, "ליומן", "task_created", [], [{"type": "notify_all_admins", "params": {}}])
    task = Task(title="ליומן משימה", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()
    svc.trigger("task_created", task)

    r = client.get("/admin/automations/log")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "ליומן" in body
