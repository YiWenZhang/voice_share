import os
from pathlib import Path


class Config:
    """Base configuration shared across environments."""

    BASE_DIR = Path(__file__).resolve().parent
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    # SQLALCHEMY_DATABASE_URI = os.environ.get(
    #     "DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}"
    # )
    # ————————自主存取控制实现——————————————
    # 读取普通用户连接
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    # 读取管理员连接，并绑定到 'admin_db'
    SQLALCHEMY_BINDS = {
        "admin_db": os.environ.get("DATABASE_URL_ADMIN")
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024  # 60 MB upper bound for uploads
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
    AVATAR_FOLDER = UPLOAD_FOLDER / "avatars"
    MUSIC_FOLDER = UPLOAD_FOLDER / "music"
    ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
    ALLOWED_MUSIC_EXTENSIONS = {"mp3"}
    MAX_MUSIC_FILE_MB = 50
    LISTEN_RECORD_WINDOW_DAYS = 30
    ROOM_PLAYBACK_SYNC_INTERVAL = 3  # seconds


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

