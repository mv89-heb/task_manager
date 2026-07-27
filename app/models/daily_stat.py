from app import db
from datetime import date as date_type


class DailyStat(db.Model):
    """
    תמונת מצב יומית של השלמת משימות - לצורך גרף מגמות לאורך זמן.
    שורה אחת ליום עבור כל הארגון (department_id=NULL) ושורה נפרדת לכל מחלקה.
    """
    id = db.Column(db.Integer, primary_key=True)
    stat_date = db.Column(db.Date, nullable=False, default=date_type.today)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    total_tasks = db.Column(db.Integer, default=0)
    done_tasks = db.Column(db.Integer, default=0)

    department = db.relationship('Department')

    __table_args__ = (
        db.UniqueConstraint('stat_date', 'department_id', name='uq_dailystat_date_dept'),
    )

    @property
    def completion_percent(self):
        if not self.total_tasks:
            return 0
        return int((self.done_tasks / self.total_tasks) * 100)

    def __repr__(self):
        return f'<DailyStat {self.stat_date} dept={self.department_id}>'
