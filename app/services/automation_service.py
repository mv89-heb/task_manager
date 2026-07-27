"""
AutomationService - כל הלוגיקה העסקית של מנוע האוטומציה יושבת כאן, ולא ב-routes.
ה-routes (Controllers) נשארים "thin" - קוראים לפונקציות כאן ומחזירים את התוצאה.

MVP מכוון: בלי Celery/RQ, בלי scheduler עצמאי - "task_overdue" מופעל ע"י cron
חיצוני (בדיוק כמו send_due_reminders/snapshot_daily_stats הקיימים). Actions הן
best-effort (לא retry-with-backoff אמיתי) - תואם את שאר הארכיטקטורה של המערכת.
"""
from app import db
from app.models.automation import AutomationRule, AutomationLog
from app.models.audit_log import log_audit
from app.models.notification import notify_recipients_multi_channel
from app.models.user import User
from datetime import date


# =========================================================
# קבועי ולידציה - allowlists בלבד, שום קלט חופשי לא מתקבל
# =========================================================

VALID_TRIGGERS = {'task_created', 'status_changed', 'task_overdue', 'report_submitted'}
VALID_FIELDS = {'status', 'priority', 'source', 'department_id', 'is_overdue'}
VALID_OPERATORS = {'equals', 'not_equals'}
VALID_ACTION_TYPES = {
    'notify_assignee', 'notify_department_managers', 'notify_all_admins',
    'change_priority', 'reassign_to',
}
VALID_STATUS_VALUES = {'TODO', 'IN_PROGRESS', 'DONE'}
VALID_PRIORITY_VALUES = {'HIGH', 'MEDIUM', 'LOW'}
VALID_SOURCE_VALUES = {'internal', 'public'}

TRIGGER_LABELS = {
    'task_created': 'משימה נוצרה',
    'status_changed': 'סטטוס השתנה',
    'task_overdue': 'משימה באיחור',
    'report_submitted': 'דיווח התקבל',
}
ACTION_LABELS = {
    'notify_assignee': 'התרע לאחראי על המשימה',
    'notify_department_managers': 'התרע למנהלי המחלקה',
    'notify_all_admins': 'התרע לכל מנהלי המערכת',
    'change_priority': 'שנה עדיפות',
    'reassign_to': 'הקצה מחדש למשתמש',
}


class AutomationValidationError(ValueError):
    """שגיאת ולידציה ספציפית ל-conditions/actions - מאפשרת ל-route להציג הודעה ברורה."""
    pass


# =========================================================
# ולידציה
# =========================================================

def validate_conditions(conditions):
    """
    conditions: רשימת dict בפורמט {"field": ..., "operator": ..., "value": ...}
    רשימה ריקה = תקינה (משמעה "הכלל תמיד רץ", בלי סינון).
    """
    if not isinstance(conditions, list):
        raise AutomationValidationError("conditions חייב להיות רשימה.")

    for i, cond in enumerate(conditions):
        if not isinstance(cond, dict):
            raise AutomationValidationError(f"תנאי מספר {i + 1} אינו אובייקט תקין.")

        field = cond.get('field')
        operator = cond.get('operator')
        value = cond.get('value')

        if field not in VALID_FIELDS:
            raise AutomationValidationError(f"שדה לא נתמך: {field!r}. שדות מותרים: {sorted(VALID_FIELDS)}")
        if operator not in VALID_OPERATORS:
            raise AutomationValidationError(f"אופרטור לא נתמך: {operator!r}. מותר רק: {sorted(VALID_OPERATORS)}")

        if field == 'status' and value not in VALID_STATUS_VALUES:
            raise AutomationValidationError(f"ערך סטטוס לא תקין: {value!r}")
        if field == 'priority' and value not in VALID_PRIORITY_VALUES:
            raise AutomationValidationError(f"ערך עדיפות לא תקין: {value!r}")
        if field == 'source' and value not in VALID_SOURCE_VALUES:
            raise AutomationValidationError(f"ערך מקור לא תקין: {value!r}")
        if field == 'is_overdue' and not isinstance(value, bool):
            raise AutomationValidationError("ערך is_overdue חייב להיות true/false.")
        if field == 'department_id' and value is not None and not isinstance(value, int):
            raise AutomationValidationError("department_id חייב להיות מספר שלם או null.")

    return True


def validate_actions(actions):
    """actions: רשימת dict בפורמט {"type": ..., "params": {...}} - חייבת להכיל לפחות פעולה אחת."""
    if not isinstance(actions, list) or not actions:
        raise AutomationValidationError("actions חייב להיות רשימה עם לפחות פעולה אחת.")

    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            raise AutomationValidationError(f"פעולה מספר {i + 1} אינה אובייקט תקין.")

        action_type = action.get('type')
        if action_type not in VALID_ACTION_TYPES:
            raise AutomationValidationError(f"סוג פעולה לא נתמך: {action_type!r}. מותר רק: {sorted(VALID_ACTION_TYPES)}")

        params = action.get('params') or {}
        if not isinstance(params, dict):
            raise AutomationValidationError(f"params של פעולה מספר {i + 1} חייב להיות אובייקט.")

        if action_type == 'change_priority':
            if params.get('priority') not in VALID_PRIORITY_VALUES:
                raise AutomationValidationError("פעולת change_priority דורשת priority תקין (HIGH/MEDIUM/LOW).")

        if action_type == 'reassign_to':
            user_id = params.get('user_id')
            if not isinstance(user_id, int):
                raise AutomationValidationError("פעולת reassign_to דורשת user_id מספרי.")
            if not User.query.get(user_id):
                raise AutomationValidationError(f"פעולת reassign_to: משתמש {user_id} לא נמצא.")

    return True


def validate_trigger_event(trigger_event):
    if trigger_event not in VALID_TRIGGERS:
        raise AutomationValidationError(f"trigger_event לא נתמך: {trigger_event!r}. מותר רק: {sorted(VALID_TRIGGERS)}")
    return True


# =========================================================
# CRUD על כללים - כולל Audit מלא לכל שינוי (חובה לפי דרישה מפורשת)
# =========================================================

def create_rule(actor, name, trigger_event, conditions, actions, department_id=None, is_active=True):
    validate_trigger_event(trigger_event)
    validate_conditions(conditions)
    validate_actions(actions)

    rule = AutomationRule(
        name=name,
        trigger_event=trigger_event,
        department_id=department_id,
        is_active=is_active,
        created_by_id=actor.id if actor else None,
    )
    rule.conditions = conditions
    rule.actions = actions
    db.session.add(rule)
    db.session.commit()

    log_audit(actor, "create_automation_rule", target_type="automation_rule", target_id=rule.id,
              target_label=name, details=f"trigger={trigger_event}, active={is_active}")
    return rule


def update_rule(actor, rule, name=None, trigger_event=None, conditions=None, actions=None,
                 department_id=None, is_active=None):
    """כל פרמטר שהוא None נשאר ללא שינוי - מאפשר עדכון חלקי."""
    changes = []

    if name is not None and name != rule.name:
        changes.append(f"name: {rule.name!r} -> {name!r}")
        rule.name = name

    if trigger_event is not None and trigger_event != rule.trigger_event:
        validate_trigger_event(trigger_event)
        changes.append(f"trigger_event: {rule.trigger_event!r} -> {trigger_event!r}")
        rule.trigger_event = trigger_event

    if conditions is not None:
        validate_conditions(conditions)
        changes.append("conditions updated")
        rule.conditions = conditions

    if actions is not None:
        validate_actions(actions)
        changes.append("actions updated")
        rule.actions = actions

    if department_id is not None and department_id != rule.department_id:
        changes.append(f"department_id: {rule.department_id!r} -> {department_id!r}")
        rule.department_id = department_id

    if is_active is not None and is_active != rule.is_active:
        changes.append(f"is_active: {rule.is_active} -> {is_active}")
        rule.is_active = is_active

    db.session.commit()

    if changes:
        log_audit(actor, "update_automation_rule", target_type="automation_rule", target_id=rule.id,
                  target_label=rule.name, details="; ".join(changes))
    return rule


def delete_rule(actor, rule):
    rule_id, rule_name = rule.id, rule.name
    db.session.delete(rule)
    db.session.commit()
    log_audit(actor, "delete_automation_rule", target_type="automation_rule", target_id=rule_id, target_label=rule_name)


def list_rules_for(user):
    """Admin רואה את כל הכללים; מנהל תחום רואה רק כללים כלליים (בלי מחלקה) + כללים של המחלקה שלו."""
    if user.role == "admin":
        return AutomationRule.query.order_by(AutomationRule.created_at.desc()).all()
    if user.role == "manager":
        return AutomationRule.query.filter(
            (AutomationRule.department_id.is_(None)) | (AutomationRule.department_id == user.department_id)
        ).order_by(AutomationRule.created_at.desc()).all()
    return []


# =========================================================
# הרצה בפועל - הליבה של המנוע
# =========================================================

def _get_task_field_value(task, field):
    if field == 'status':
        return task.status
    if field == 'priority':
        return task.priority
    if field == 'source':
        return task.source
    if field == 'department_id':
        return task.department_id
    if field == 'is_overdue':
        return bool(task.due_date and task.due_date < date.today() and task.status != 'DONE')
    return None


def evaluate_conditions(task, conditions):
    """AND בלבד ב-v1 - כל התנאים חייבים להתקיים. רשימה ריקה = תמיד אמת."""
    for cond in conditions:
        actual = _get_task_field_value(task, cond.get('field'))
        expected = cond.get('value')
        operator = cond.get('operator')

        if operator == 'equals' and actual != expected:
            return False
        if operator == 'not_equals' and actual == expected:
            return False

    return True


def _resolve_department_managers(task):
    dept_id = task.department_id or (task.assignee.department_id if task.assignee else None)
    if not dept_id:
        return []
    return User.query.filter_by(department_id=dept_id, role="manager").all()


def execute_action(task, action, rule):
    """מבצע פעולה בודדת. best-effort - חריגה כאן נתפסת ע"י הקורא (trigger())."""
    action_type = action.get('type')
    params = action.get('params') or {}

    if action_type == 'notify_assignee':
        if task.assignee:
            notify_recipients_multi_channel(
                [task.assignee], f"אוטומציה '{rule.name}' הופעלה על המשימה \"{task.title}\"",
                link=f"/edit/{task.id}", icon="bi-gear-fill",
                email_subject=f"אוטומציה: {rule.name}",
            )

    elif action_type == 'notify_department_managers':
        managers = _resolve_department_managers(task)
        if managers:
            notify_recipients_multi_channel(
                managers, f"אוטומציה '{rule.name}' הופעלה על המשימה \"{task.title}\"",
                link=f"/edit/{task.id}", icon="bi-gear-fill",
                email_subject=f"אוטומציה: {rule.name}",
            )

    elif action_type == 'notify_all_admins':
        admins = User.query.filter_by(role="admin").all()
        if admins:
            notify_recipients_multi_channel(
                admins, f"אוטומציה '{rule.name}' הופעלה על המשימה \"{task.title}\"",
                link=f"/edit/{task.id}", icon="bi-gear-fill",
                email_subject=f"אוטומציה: {rule.name}",
            )

    elif action_type == 'change_priority':
        task.priority = params.get('priority')
        db.session.commit()

    elif action_type == 'reassign_to':
        task.assigned_to_id = params.get('user_id')
        db.session.commit()

    else:
        raise ValueError(f"סוג פעולה לא ידוע בזמן הרצה: {action_type!r}")


def trigger(event_name, task):
    """
    נקודת הכניסה הראשית - נקראת מה-routes בכל אירוע רלוונטי (task_created,
    status_changed, task_overdue, report_submitted). Thin call: route רק קורא
    ל-trigger(...), כל הלוגיקה כאן.
    """
    if event_name not in VALID_TRIGGERS:
        return  # מגן על עצמנו משגיאת מפתח פנימית - לא אמור לקרות עם קוד תקין

    rules = AutomationRule.query.filter_by(trigger_event=event_name, is_active=True).all()

    for rule in rules:
        # אם לכלל יש מחלקה מוגדרת, הוא רץ רק על משימות של אותה מחלקה
        rule_dept = rule.department_id
        if rule_dept is not None:
            task_dept = task.department_id or (task.assignee.department_id if task.assignee else None)
            if task_dept != rule_dept:
                continue

        try:
            if not evaluate_conditions(task, rule.conditions):
                continue

            for action in rule.actions:
                execute_action(task, action, rule)

            log = AutomationLog(rule_id=rule.id, task_id=task.id, success=True,
                                 details=f"{len(rule.actions)} פעולות בוצעו בהצלחה")
            db.session.add(log)
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            log = AutomationLog(rule_id=rule.id, task_id=task.id, success=False, details=str(e))
            db.session.add(log)
            db.session.commit()
