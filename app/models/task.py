from app import db
from datetime import datetime

RECURRENCE_NONE = 'NONE'
RECURRENCE_DAILY = 'DAILY'
RECURRENCE_WEEKLY = 'WEEKLY'
RECURRENCE_MONTHLY = 'MONTHLY'

RECURRENCE_LABELS = {
    RECURRENCE_NONE: 'חד פעמית',
    RECURRENCE_DAILY: 'כל יום',
    RECURRENCE_WEEKLY: 'כל שבוע',
    RECURRENCE_MONTHLY: 'כל חודש',
}

MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB

task_dependencies = db.Table('task_dependencies',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id', ondelete="CASCADE"), primary_key=True),
    db.Column('depends_on_task_id', db.Integer, db.ForeignKey('task.id', ondelete="CASCADE"), primary_key=True)
)

class TaskChecklistItem(db.Model):
    __tablename__ = 'task_checklist_item'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id', ondelete="CASCADE"), nullable=False)
    text = db.Column(db.String(255), nullable=False)
    is_done = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='TODO', index=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Phase 4.4: מעקב שינויים ברמת הרשומה לאיתור משימות "תקועות"
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(20), default='LOW') # LOW, MEDIUM, HIGH, CRITICAL

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    assignee = db.relationship('User', foreign_keys=[assigned_to_id])

    image_data = db.Column(db.Text, nullable=True)
    image_mimetype = db.Column(db.String(50), nullable=True)

    recurrence = db.Column(db.String(20), default=RECURRENCE_NONE)
    recurrence_parent_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)

    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True, index=True)
    department = db.relationship('Department')

    source = db.Column(db.String(20), default='internal', index=True)
    reporter_name = db.Column(db.String(100), nullable=True)
    reporter_phone = db.Column(db.String(20), nullable=True)

    parent_task_id = db.Column(db.Integer, db.ForeignKey('task.id', ondelete="CASCADE"), nullable=True)
    sub_tasks = db.relationship('Task', 
                                backref=db.backref('parent_task', remote_side=[id]), 
                                lazy='dynamic', 
                                foreign_keys=[parent_task_id],
                                cascade="all, delete-orphan")

    estimated_minutes = db.Column(db.Integer, nullable=True, default=0)

    # ===============================
    # Phase 4.2: SLA Management
    # ===============================
    task_type = db.Column(db.String(50), nullable=True)
    sla_breach_at = db.Column(db.DateTime, nullable=True, index=True)

    checklist_items = db.relationship('TaskChecklistItem', backref='task', lazy='dynamic', cascade="all, delete-orphan", order_by="TaskChecklistItem.order")

    dependencies = db.relationship(
        'Task',
        secondary=task_dependencies,
        primaryjoin=(id == task_dependencies.c.task_id),
        secondaryjoin=(id == task_dependencies.c.depends_on_task_id),
        backref=db.backref('dependent_tasks', lazy='dynamic'),
        lazy='dynamic'
    )
