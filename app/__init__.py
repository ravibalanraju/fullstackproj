from flask import Flask
def create_app():
    """Flask application factory."""
    app = Flask(__name__)
    from .database import seed_data
    seed_data()
    from .routes import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")
    return app
