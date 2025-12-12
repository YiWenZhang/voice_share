from sqlalchemy import text


# 定义所有表的创建语句
def init_db_with_raw_sql(db):
    sql_statements = [
        # 1. 用户表 (User)
        """
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(256) NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            nickname VARCHAR(32) DEFAULT '新用户',
            avatar_path VARCHAR(256),
            notification_message VARCHAR(256),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """,

        # 2. 音乐表 (Music)
        """
        CREATE TABLE IF NOT EXISTS musics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title VARCHAR(128) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(255) NOT NULL,
            status VARCHAR(32) DEFAULT 'pending',
            rejection_reason VARCHAR(255),
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(id)
        );
        """,

        # 3. 房间表 (Room)
        """
        CREATE TABLE IF NOT EXISTS room (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            name VARCHAR(64) NOT NULL,
            code VARCHAR(6) NOT NULL UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            playback_status VARCHAR(16) DEFAULT 'paused',
            current_track_name VARCHAR(255),
            current_track_file VARCHAR(255),
            current_position FLOAT DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_id) REFERENCES user(id)
        );
        """,

        # 4. 房间播放列表 (RoomPlaylist)
        """
        CREATE TABLE IF NOT EXISTS room_playlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            music_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(room_id) REFERENCES room(id),
            FOREIGN KEY(music_id) REFERENCES musics(id)
        );
        """,

        # 5. 房间消息表 (RoomMessage)
        """
        CREATE TABLE IF NOT EXISTS room_message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(room_id) REFERENCES room(id),
            FOREIGN KEY(user_id) REFERENCES user(id)
        );
        """,

        # 6. 房间成员表 (RoomMember)
        """
        CREATE TABLE IF NOT EXISTS room_member (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(room_id, user_id),
            FOREIGN KEY(room_id) REFERENCES room(id),
            FOREIGN KEY(user_id) REFERENCES user(id)
        );
        """,

        # 7. 听歌记录表 (ListenRecord)
        """
        CREATE TABLE IF NOT EXISTS listen_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            song_name VARCHAR(255) NOT NULL,
            played_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(id)
        );
        """,

        # 8. 房间参与记录表 (RoomParticipationRecord)
        """
        CREATE TABLE IF NOT EXISTS room_participation_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            room_code VARCHAR(6) NOT NULL,
            participated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(id)
        );
        """
    ]

    # 执行所有建表语句
    for sql in sql_statements:
        db.session.execute(text(sql))
    db.session.commit()
    print("数据库表已通过原生 SQL 创建完成。")