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
        
        

        # 视图定义
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
        """,

        # 索引
        # 1.性能优化索引
        # 为高频查询字段添加索引，加速 WHERE 子句过滤
        """
        CREATE INDEX idx_music_title ON musics(title);
        """,
        """
        CREATE INDEX idx_music_status ON musics(status);
        """,
        """
        CREATE INDEX idx_music_uploaded_at ON musics(uploaded_at);
        """,
        """
        CREATE INDEX idx_user_nickname ON user(nickname);
        """,

        #  2.房间查询优化索引
        """
        CREATE INDEX idx_room_name ON room(name);
        """,
        """
        CREATE INDEX idx_room_code ON room(code);
        """,
        """
        CREATE INDEX idx_room_active ON room(is_active);
        """,
        # 3.听歌记录查询优化索引
        """
        CREATE INDEX idx_listen_song ON listen_record(song_name);
        """,
        """
        CREATE INDEX idx_listen_time ON listen_record(played_at);
        """,
        """
        CREATE INDEX idx_user_username ON user(username);
        """,

        # 存储过程与触发器 (自动化与审计)
        # 1. 创建审计日志表
        """
        CREATE TABLE IF NOT EXISTS system_audit_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            action_type VARCHAR(32) NOT NULL,
            table_name VARCHAR(64) NOT NULL,
            record_id INT,
            details TEXT,
            action_time DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        # 2. 定义存储过程: 每日维护 (sp_daily_maintenance)
        # [修改点] 将 30 DAY 改为了 1 DAY
        """
        DROP PROCEDURE IF EXISTS sp_daily_maintenance;
        """,

        """
        CREATE PROCEDURE sp_daily_maintenance()
        BEGIN
            -- 1. 清理过期听歌记录 (保留最近 1 天)
            DELETE FROM listen_record 
            WHERE played_at < DATE_SUB(NOW(), INTERVAL 1 DAY);

            -- 2. 自动关闭“僵尸”房间 (超过 7 天没有更新的活跃房间)
            UPDATE room 
            SET is_active = 0, playback_status = 'paused'
            WHERE is_active = 1 
              AND updated_at < DATE_SUB(NOW(), INTERVAL 7 DAY);
        END;
        """,

        # 3. 定义触发器: 房间成员审计 (trg_room_join_audit)
        # 功能：每当有人加入房间，自动在审计表中记录
        """
        CREATE TRIGGER trg_room_join_audit 
        AFTER INSERT ON room_member
        FOR EACH ROW
        BEGIN
            INSERT INTO system_audit_log (action_type, table_name, record_id, details, action_time)
            VALUES (
                'JOIN', 
                'room', 
                NEW.room_id, 
                CONCAT('User (ID: ', NEW.user_id, ') joined the room.'),
                NOW()
            );
        END;
        """,
    ]


    from sqlalchemy import text
    # [新增] 导入 SQL 执行时的运行错误异常
    from sqlalchemy.exc import OperationalError

    # ... (上面的 sql_statements 列表定义保持不变) ...

    # ... (前面的 sql_statements 列表定义保持不变)

    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    try:
        # [核心修改] 显式获取 'admin_db' (即 vs_admin) 的引擎来执行建表
        # 注意：这里 bind='admin_db' 必须与 config.py 中 SQLALCHEMY_BINDS 的键名一致
        admin_engine = db.get_engine(bind='admin_db')

        # 使用管理员引擎建立连接
        with admin_engine.connect() as connection:
            for sql in sql_statements:
                try:
                    connection.execute(text(sql))
                except OperationalError as e:
                    # 错误码 1061: Duplicate key name (索引已存在)
                    # 错误码 1050: Table already exists (表已存在)
                    # 错误码 1304: PROCEDURE already exists (存储过程已存在)
                    # 错误码 1359: TRIGGER already exists (触发器已存在)
                    if e.orig.args[0] in (1061, 1050, 1304, 1359):
                        print(f"提示: 对象已存在，跳过 -> {str(e.orig.args)}")
                    else:
                        print(f"执行 SQL 出错: {sql[:50]}...")
                        raise e

            connection.commit()
        print("数据库表、索引及自动化脚本校验完成 (Success)。")
    except Exception as e:
        print(f"初始化过程发生未处理错误: {e}")
        print("建议检查: 1. config.py 是否配置了 SQLALCHEMY_BINDS; 2. .env 中 DATABASE_URL_ADMIN 是否正确。")