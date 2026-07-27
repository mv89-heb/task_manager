from app import db

class SlaPolicy(db.Model):
    """
    מודל להגדרת מדיניות זמני שירות (Service Level Agreement).
    מאפשר קביעת זמן גג (max_hours) לביצוע משימה על בסיס צירוף של:
    עדיפות, מחלקה וסוג משימה. ככל שהכלל ספציפי יותר, כך הוא גובר.
    """
    __tablename__ = 'sla_policy'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    # תנאי המדיניות (כולם אופציונליים - מדיניות ללא תנאים תחול על הכל כברירת מחדל)
    priority = db.Column(db.String(20), nullable=True) # LOW, MEDIUM, HIGH, CRITICAL
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    task_type = db.Column(db.String(50), nullable=True)
    
    # זמן יעד בשעות
    max_hours = db.Column(db.Float, nullable=False, default=24.0)

    department = db.relationship('Department')
