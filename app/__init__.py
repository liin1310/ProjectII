from flask import Flask
from config import DB_CONFIG

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your_secret_key'  # Dùng cho flash messages

    # Đăng ký Blueprint
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.user import user_bp
    # from app.routes.books import books_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    # app.register_blueprint(books_bp)

    return app