from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()

# יצירת מנהל ההתחברויות
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # אתחול הכלים עם האפליקציה
    db.init_app(app)
    login_manager.init_app(app)
    
    # הגדרת הדף שאליו משתמשים יופנו אם הם לא מחוברים (אופציונלי אבל מומלץ)
    # login_manager.login_view = 'login' 

    with app.app_context():
        # עכשיו ה-User יכול לייבא את login_manager בבטחה
        from app.models.user import User
        from app.models.task import Task

        from app.routes.tasks import bp as task_bp
        from app.routes.dashboard import bp as dash_bp

        app.register_blueprint(task_bp)
        app.register_blueprint(dash_bp)

        db.create_all()

    return app

# פונקציה ש-Flask-Login חייב כדי לטעון את המשתמש הנוכחי מהמסד
@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))
