from app import db


class Department(db.Model):
    """מחלקה/תחום בארגון (למשל: אחזקה, כספים, שירות לקוחות)."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))

    # שורת הנוחות: כל חברי המחלקה (עובדים + מנהל התחום) נגישים דרך department.members
    members = db.relationship(
        'User',
        back_populates='department',
        foreign_keys='User.department_id'
    )

    def __repr__(self):
        return f'<Department {self.name}>'
