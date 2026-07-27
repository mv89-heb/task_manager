import pytest
from app import db
from app.models.task import Task
from app.models.user import User
from app.models.audit_log import AuditLog
from datetime import date

def get_or_create_admin(app):
    """פונקציית עזר ליצירת משתמש מנהל לבדיקות"""
    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin = User(username="admin_test", email="admin@test.com", role="admin")
            admin.set_password("pass123")
            db.session.add(admin)
            db.session.commit()
        return admin

def test_health_check(client):
    """בדיקת נקודת ניטור בריאות המערכת"""
    resp = client.get('/api/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert data['db_online'] is True

def test_dashboard_workload_analytics(client, app):
    """בדיקת עליית הדשבורד עם הנתונים החדשים של עומס עבודה (Estimated Minutes)"""
    admin = get_or_create_admin(app)
    with app.app_context():
        # ניצור משימה עם זמן מוערך כדי לוודא שאין קריסות חישוב ב-Jinja
        task = Task(title="Workload Task", assigned_to_id=admin.id, estimated_minutes=120)
        db.session.add(task)
        db.session.commit()
        
    client.post('/login', data={"username": admin.username, "password": "pass123"})
    resp = client.get('/dashboard')
    assert resp.status_code == 200
    # מוודא שהעמוד נטען בהצלחה ללא שגיאות 500

def test_audit_log_filtering(client, app):
    """בדיקת סינון יומן ביקורת (Audit Log) לפי פעולה"""
    admin = get_or_create_admin(app)
    with app.app_context():
        log1 = AuditLog(action="test_action_1", user_id=admin.id, details="First log")
        log2 = AuditLog(action="test_action_2", user_id=admin.id, details="Second log")
        db.session.add_all([log1, log2])
        db.session.commit()
        
    client.post('/login', data={"username": admin.username, "password": "pass123"})
    
    # סינון לפי פעולה ספציפית
    resp = client.get('/admin/audit_log?action=test_action_1')
    assert resp.status_code == 200
    assert b"First log" in resp.data
    assert b"Second log" not in resp.data

def test_exports_with_phase4_fields(client, app):
    """בדיקת הייצוא ל-Excel ו-PDF כדי לוודא שהשדות החדשים (תלויות, זמן) לא גורמים לקריסה"""
    admin = get_or_create_admin(app)
    with app.app_context():
        task = Task(title="Export Task", assigned_to_id=admin.id, estimated_minutes=45)
        db.session.add(task)
        db.session.commit()
        
    client.post('/login', data={"username": admin.username, "password": "pass123"})
    
    # Excel
    resp_excel = client.get('/export/excel')
    assert resp_excel.status_code == 200
    assert resp_excel.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    # PDF
    resp_pdf = client.get('/export/pdf')
    assert resp_pdf.status_code == 200
    assert resp_pdf.mimetype == 'application/pdf'
