from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from app.routes.tasks import bp as task_bp
    from app.routes.dashboard import bp as dash_bp

    app.register_blueprint(task_bp)
    app.register_blueprint(dash_bp)

    with app.app_context():
        db.create_all()

    return app
