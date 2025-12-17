# app/backup_service.py
import os
import json
from datetime import datetime
from sqlalchemy import text
from flask import current_app
from . import db


def execute_save_backup():
    """后台自动备份逻辑"""
    # 1. 定义要备份的表
    tables = [
        'user', 'musics', 'room',
        'room_member', 'room_playlist', 'room_message',
        'listen_record', 'room_participation_record',
        'system_audit_log'
    ]
    data = {
        'meta': {
            'backup_time': str(datetime.now()),
            'version': '1.0',
            'description': 'Voice Share Auto Backup'
        }
    }

    # 2. 获取管理员连接读取数据
    # 注意：这里需要在应用上下文或请求上下文中调用
    try:
        admin_engine = db.get_engine(bind='admin_db')
        with admin_engine.connect() as conn:
            for t in tables:
                try:
                    rows = conn.execute(text(f"SELECT * FROM {t}")).mappings().all()
                    data[t] = [dict(row) for row in rows]
                except Exception as e:
                    print(f"[AutoBackup] Error reading {t}: {e}")
                    data[t] = []

        # 3. 写入文件
        backup_dir = os.path.join(current_app.root_path, '..', 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        filename = f"备份-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        filepath = os.path.join(backup_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str, indent=2, ensure_ascii=False)

        print(f"[AutoBackup] Success: {filepath}")

    except Exception as e:
        print(f"[AutoBackup] Failed: {e}")