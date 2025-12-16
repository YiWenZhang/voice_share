from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from pathlib import Path
from app.create_with_sql import init_db_with_raw_sql
from sqlalchemy import text
from flask_apscheduler import APScheduler # [新增]
import os
import json

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.config.from_object("config.Config")

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["AVATAR_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["MUSIC_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"

    from . import models  # noqa: F401
    from .routes import main_bp
    from .auth import auth_bp
    from .admin import admin_bp
    from .database_views import db_views_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(db_views_bp)

    with app.app_context():
        # 创建数据库
        init_db_with_raw_sql(db)

#________________________________________________________________
        # [新增] 初始化调度器
        scheduler.init_app(app)

        from app.backup_service import execute_save_backup

        def run_scheduled_backup():
            with app.app_context():
                execute_save_backup()

        scheduler.start()

        # [新增] 启动时读取 JSON 配置
        with app.app_context():
            import logging
            logging.getLogger('apscheduler').setLevel(logging.WARNING)
            try:
                interval = 24
                config_path = os.path.join(app.root_path, '..', 'backup_config.json')
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        conf = json.load(f)
                        interval = int(conf.get('backup_interval_hours', 24))

                if not scheduler.get_job('auto_backup_job'):
                    scheduler.add_job(
                        id='auto_backup_job',
                        func=run_scheduled_backup,
                        trigger='interval',
                        hours=interval
                    )
            except Exception:
                pass
#______________________________________________________________
    return app

