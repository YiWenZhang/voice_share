from sqlalchemy import text


# 定义所有表的创建语句
def init_db_with_raw_sql(db):
    # MySQL 建表语句
    # 变化点：
    # 1. AUTOINCREMENT -> AUTO_INCREMENT
    # 2. INTEGER -> INT
    # 3. 必须指定 ENGINE=InnoDB 以支持外键
    # 4. 外键约束语法调整

    sql_statements = [
        # 1. 用户表 (User)
        """
        CREATE TABLE IF NOT EXISTS user (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(256) NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            nickname VARCHAR(32) DEFAULT '新用户',
            avatar_path VARCHAR(256),
            notification_message VARCHAR(256),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        # 2. 音乐表 (Music)
        """
        CREATE TABLE IF NOT EXISTS musics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(128) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(255) NOT NULL,
            status VARCHAR(32) DEFAULT 'pending',
            rejection_reason VARCHAR(255),
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        # 3. 房间表 (Room)
        """
        CREATE TABLE IF NOT EXISTS room (
            id INT AUTO_INCREMENT PRIMARY KEY,
            owner_id INT NOT NULL,
            name VARCHAR(64) NOT NULL,
            code VARCHAR(6) NOT NULL UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            playback_status VARCHAR(16) DEFAULT 'paused',
            current_track_name VARCHAR(255),
            current_track_file VARCHAR(255),
            current_position FLOAT DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_id) REFERENCES user(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        # 4. 房间播放列表 (RoomPlaylist)
        """
        CREATE TABLE IF NOT EXISTS room_playlist (
            id INT AUTO_INCREMENT PRIMARY KEY,
            room_id INT NOT NULL,
            music_id INT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY(room_id) REFERENCES room(id) ON DELETE CASCADE,
            FOREIGN KEY(music_id) REFERENCES musics(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        # 5. 房间消息表 (RoomMessage)
        """
        CREATE TABLE IF NOT EXISTS room_message (
            id INT AUTO_INCREMENT PRIMARY KEY,
            room_id INT NOT NULL,
            user_id INT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY(room_id) REFERENCES room(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        # 6. 房间成员表 (RoomMember)
        """
        CREATE TABLE IF NOT EXISTS room_member (
            id INT AUTO_INCREMENT PRIMARY KEY,
            room_id INT NOT NULL,
            user_id INT NOT NULL,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_room_member (room_id, user_id),
            FOREIGN KEY(room_id) REFERENCES room(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        # 7. 听歌记录表 (ListenRecord)
        """
        CREATE TABLE IF NOT EXISTS listen_record (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            song_name VARCHAR(255) NOT NULL,
            played_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        # 8. 房间参与记录表 (RoomParticipationRecord)
        """
        CREATE TABLE IF NOT EXISTS room_participation_record (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            room_code VARCHAR(6) NOT NULL,
            participated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        
        
        # ==========================================
        # [新增] 实验 1.4 视图定义
        # 体现思想：
        # 1. 简化复杂查询：预先定义 Join 连接，上层应用只需查单表。
        # 2. 安全性：隐藏敏感字段（如密码、具体路径）。
        # 3. 数据聚合：预先计算统计数据（Count, Sum）。
        # ==========================================

        # 视图 1: 音乐详情全貌视图 (v_music_full_info)
        # 作用：将 musics 表与 user 表通过 user_id 连接，用于管理员快速检索。
        """
        CREATE OR REPLACE VIEW v_music_full_info AS
        SELECT 
            m.id AS music_id,
            m.title,
            m.original_filename,
            m.status,
            m.uploaded_at,
            m.rejection_reason,
            u.id AS uploader_id,
            u.username AS uploader_name,
            u.nickname AS uploader_nickname
        FROM musics m
        JOIN user u ON m.user_id = u.id;
        """,

        # 视图 2: 房间热度统计视图 (v_room_stats)
        # 作用：聚合统计每个房间的当前人数，体现 "Group By" 和聚合函数在视图中的应用。
        """
        CREATE OR REPLACE VIEW v_room_stats AS
        SELECT 
            r.id AS room_id,
            r.code,
            r.name,
            r.is_active,
            r.owner_id,
            (SELECT nickname FROM user WHERE id = r.owner_id) as owner_name,
            COUNT(rm.user_id) + 1 AS member_count  -- +1 是加上房主自己
        FROM room r
        LEFT JOIN room_member rm ON r.id = rm.room_id
        GROUP BY r.id, r.code, r.name, r.is_active, r.owner_id;
        """
    ]

    try:
        # 执行所有建表语句
        with db.engine.connect() as connection:
            for sql in sql_statements:
                connection.execute(text(sql))
            connection.commit()
        print("数据库表已通过原生 MySQL SQL 创建完成。")
    except Exception as e:
        print(f"创建表时发生错误: {e}")