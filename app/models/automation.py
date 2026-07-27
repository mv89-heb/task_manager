from app import db
from datetime import datetime
import json


class AutomationRule(db.Model):
    """
    כלל אוטומציה: Trigger + Conditions + Actions.
    conditions/actions נשמרים כ-JSON (טקסט) - ולידציה מלאה מתבצעת אך ורק
    ב-AutomationService, לא כאן ולא ב-route. המודל עצמו "טיפש" בכוונה.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # 'task_created' | 'status_changed' | 'task_overdue' | 'report_submitted'
    trigger_event = db.Column(db.String(50), nullable=False, index=True)

    conditions_json = db.Column(db.Text, nullable=False, default='[]')
    actions_json = db.Column(db.Text, nullable=False, default='[]')

    is_active = db.Column(db.Boolean, default=True, index=True)

    # אופציונלי - אם מוגדר, הכלל רץ רק על משימות של מחלקה זו
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    department = db.relationship('Department')

    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def conditions(self):
        try:
            return json.loads(self.conditions_json or '[]')
        except (ValueError, TypeError):
            return []

    @conditions.setter
    def conditions(self, value):
        self.conditions_json = json.dumps(value)

    @property
    def actions(self):
        try:
            return json.loads(self.actions_json or '[]')
        except (ValueError, TypeError):
            return []

    @actions.setter
    def actions(self, value):
        self.actions_json = json.dumps(value)

    def __repr__(self):
        return f'<AutomationRule {self.name} ({self.trigger_event})>'


class AutomationLog(db.Model):
    """יומן הרצה - כל ניסיון הפעלה של כלל (הצליח/נכשל) לצורך שקיפות וניפוי תקלות."""
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('automation_rule.id'), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    success = db.Column(db.Boolean, default=True)
    details = db.Column(db.Text, nullable=True)

    rule = db.relationship('AutomationRule')
    task = db.relationship('Task')

    def __repr__(self):
        return f'<AutomationLog rule={self.rule_id} task={self.task_id} success={self.success}>'
