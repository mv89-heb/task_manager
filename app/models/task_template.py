from app import db


class TaskTemplate(db.Model):
    """תבנית משימה מוכנה מראש - להאצת יצירת משימות חוזרות/נפוצות."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default='LOW')
    recurrence = db.Column(db.String(20), default='NONE')

    # מחלקה רלוונטית (אופציונלי) - לצורך ארגון בלבד, לא חוסם שימוש
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    department = db.relationship('Department')

    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def __repr__(self):
        return f'<TaskTemplate {self.name}>'
