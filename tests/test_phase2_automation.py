import json
import pytest
from app import db
from app.models.automation import AutomationRule
from app.services import automation_service


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(username='automation_admin', role='admin')
        admin.set_password('automation-test-123')
        db.session.add(admin)
        db.session.commit()
    else:
        admin.set_password('automation-test-123')
        db.session.commit()
    client.post('/login', data={'username': admin.username, 'password': 'automation-test-123'})
    return admin


def test_create_rule_via_route_with_invalid_data_shows_error(client, db_session):
    _login_admin(client)
    r = client.post(
        "/admin/automations",
        data=json.dumps({
            "name": "כלל שגוי",
            "trigger_event": "not_a_trigger",
            "conditions": [],
            "actions": [{"type": "notify_all_admins", "params": {}}],
        }),
        content_type="application/json",
    )
    body = r.get_json()
    assert r.status_code == 400
    assert "לא נתמך" in body["message"]


def test_automation_log_page_renders(client, db_session):
    from app.models.user import User
    from app.models.task import Task
    admin = _login_admin(client)
    task = Task(title="Automation log test", assigned_to_id=admin.id)
    db.session.add(task)
    db.session.commit()
    rule = AutomationRule(name="Log Rule", trigger_event="task_created", conditions=[], actions=[{"type": "notify_all_admins", "params": {}}], created_by_id=admin.id)
    db.session.add(rule)
    db.session.commit()
    response = client.get('/admin/automations/log')
    assert response.status_code == 200
