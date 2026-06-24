from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from app.models.user import User
        from app.models.task import Task

        from app.routes.tasks import bp as task_bp
        from app.routes.dashboard import bp as dash_bp

        app.register_blueprint(task_bp)
        app.register_blueprint(dash_bp)

        # ⚠️ מרעננים את מסד הנתונים כדי לוודא ששדה ה-status קיים בטבלה האמיתית ב-PostgreSQL
        
        db.create_all()

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))
