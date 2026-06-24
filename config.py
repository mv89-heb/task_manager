import os

# מחפש את הכתובת של מסד הנתונים בענן
database_url = os.environ.get('DATABASE_URL')

# תיקון קטן שחובה לעשות ב-Render עבור SQLAlchemy
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# אם יש כתובת ענן - השתמש בה. אם לא - השתמש ב-SQLite המקומי
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///db.sqlite3'
