import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Cấu hình upload
# UPLOAD_FOLDER = str(BASE_DIR / 'app' / 'static' / 'uploads')
UPLOAD_FOLDER = r"D:\project2\app\static\uploads"

# UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'epub'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

# Lấy cấu hình database từ biến môi trường
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'book'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4'),
}

# Lấy secret key từ biến môi trường
SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')
