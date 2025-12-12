import os
import sys
from datetime import datetime, timezone  # [修改] 引入 timezone
from dotenv import load_dotenv
from sqlalchemy import text

# 1. 加载环境变量 (确保能连上 MySQL)
load_dotenv()

from app import create_app, db

# 初始化应用上下文
app = create_app()


def get_test_user_id():
    """辅助函数：获取或创建一个专用的测试用户"""
    # 尝试查找名为 test_runner 的用户
    sql = text("SELECT id FROM user WHERE username = 'test_runner' LIMIT 1")
    result = db.session.execute(sql).fetchone()

    if result:
        return result[0]

    # 如果不存在，创建一个
    print(">>> 正在初始化测试用户 'test_runner'...")
    insert_sql = text("""
        INSERT INTO user (username, password_hash, is_admin, nickname, created_at, updated_at)
        VALUES ('test_runner', 'dummy_hash', 0, 'TestUser', :now, :now)
    """)
    # [修改] 使用 datetime.now(timezone.utc)
    db.session.execute(insert_sql, {"now": datetime.now(timezone.utc)})
    db.session.commit()

    # 获取新创建的 ID
    return db.session.execute(sql).fetchone()[0]


# ==========================================
# 测试功能函数
# ==========================================

def test_profile_update():
    print("\n[测试 1] 修改个人资料 (UPDATE)")
    user_id = get_test_user_id()
    new_nickname = f"User_{datetime.now().strftime('%H%M%S')}"  # 生成随机昵称

    # 1. 执行原生 UPDATE
    sql = text("""
        UPDATE user 
        SET nickname = :nickname, updated_at = :now
        WHERE id = :uid
    """)

    try:
        db.session.execute(sql, {
            "nickname": new_nickname,
            # [修改] 使用 datetime.now(timezone.utc)
            "now": datetime.now(timezone.utc),
            "uid": user_id
        })
        db.session.commit()
        print(f"   执行 SQL: UPDATE user SET nickname='{new_nickname}'...")

        # 2. 验证结果
        check_sql = text("SELECT nickname FROM user WHERE id = :uid")
        res = db.session.execute(check_sql, {"uid": user_id}).fetchone()

        print(f"   数据库当前值: {res[0]}")
        if res[0] == new_nickname:
            print("   测试通过")
        else:
            print("   测试失败：数据未更新")

    except Exception as e:
        print(f"   发生异常: {e}")
        db.session.rollback()


def test_music_upload():
    print("\n[测试 2] 上传音乐 (INSERT)")
    user_id = get_test_user_id()
    title = f"TestSong_{datetime.now().strftime('%H%M%S')}"

    # 1. 执行原生 INSERT
    sql = text("""
        INSERT INTO musics (user_id, title, original_filename, stored_filename, status, uploaded_at, created_at)
        VALUES (:uid, :title, 'test.mp3', 'test_stored.mp3', 'pending', :now, :now)
    """)

    try:
        db.session.execute(sql, {
            "uid": user_id,
            "title": title,
            # [修改] 使用 datetime.now(timezone.utc)
            "now": datetime.now(timezone.utc)
        })
        db.session.commit()
        print(f"   执行 SQL: INSERT INTO musics ... title='{title}'")

        # 2. 验证结果
        check_sql = text("SELECT id, title, status FROM musics WHERE title = :title")
        res = db.session.execute(check_sql, {"title": title}).fetchone()

        if res:
            print(f"   查询结果: ID={res[0]}, Title={res[1]}, Status={res[2]}")
            print("   测试通过")
            return res[0]  # 返回 ID 供其他测试使用
        else:
            print("   测试失败：未查到插入的记录")

    except Exception as e:
        print(f"   发生异常: {e}")
        db.session.rollback()
    return None


def test_music_delete():
    print("\n[测试 3] 删除音乐 (DELETE)")
    # 准备工作：先插入一条，确保有东西可删
    print("   ...准备数据中...")
    music_id = test_music_upload()
    if not music_id: return

    user_id = get_test_user_id()

    # 1. 执行原生 DELETE
    sql_del = text("DELETE FROM musics WHERE id = :mid AND user_id = :uid")

    try:
        result = db.session.execute(sql_del, {"mid": music_id, "uid": user_id})
        db.session.commit()
        print(f"   执行 SQL: DELETE FROM musics WHERE id={music_id}...")

        # 2. 验证结果
        if result.rowcount > 0:
            print(f"   影响行数: {result.rowcount}")
            # 二次确认
            check = db.session.execute(text("SELECT count(*) FROM musics WHERE id=:mid"), {"mid": music_id}).scalar()
            if check == 0:
                print("   测试通过 (记录已消失)")
            else:
                print("   测试失败 (记录仍然存在)")
        else:
            print("   删除失败：影响行数为 0")

    except Exception as e:
        print(f"   发生异常: {e}")
        db.session.rollback()


def test_room_create():
    print("\n[测试 4] 创建房间 (INSERT 多表)")
    user_id = get_test_user_id()
    room_code = datetime.now().strftime('%H%M%S')  # 简单生成6位码

    # [修改] 使用 datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)

    # 1. 插入房间表
    sql_room = text("""
        INSERT INTO room (owner_id, name, code, is_active, playback_status, current_position, created_at)
        VALUES (:uid, 'SQL Test Room', :code, 1, 'paused', 0.0, :now)
    """)

    # 2. 插入参与记录表
    sql_record = text("""
        INSERT INTO room_participation_record (user_id, room_code, participated_at)
        VALUES (:uid, :code, :now)
    """)

    try:
        db.session.execute(sql_room, {"uid": user_id, "code": room_code, "now": now})
        db.session.execute(sql_record, {"uid": user_id, "code": room_code, "now": now})
        db.session.commit()
        print(f"   执行 SQL: 插入 room 和 participation 记录, Code={room_code}")

        # 3. 验证
        res_room = db.session.execute(text("SELECT id FROM room WHERE code=:code"), {"code": room_code}).fetchone()
        res_rec = db.session.execute(text("SELECT id FROM room_participation_record WHERE room_code=:code"),
                                     {"code": room_code}).fetchone()

        if res_room and res_rec:
            print(f"   测试通过 (RoomID={res_room[0]}, RecID={res_rec[0]})")
            return res_room[0], room_code
        else:
            print("   测试失败：数据不完整")

    except Exception as e:
        print(f"   发生异常: {e}")
        db.session.rollback()
    return None, None


def test_add_playlist():
    print("\n[测试 5] 添加到播放列表 (INSERT)")
    # 准备环境
    print("   ...准备房间和音乐...")
    room_id, _ = test_room_create()
    music_id = test_music_upload()

    if not room_id or not music_id:
        print("   前置条件不足，跳过")
        return

    # 1. 执行原生 INSERT
    sql = text("""
        INSERT INTO room_playlist (room_id, music_id, created_at)
        VALUES (:rid, :mid, :now)
    """)

    try:
        db.session.execute(sql, {
            "rid": room_id,
            "mid": music_id,
            # [修改] 使用 datetime.now(timezone.utc)
            "now": datetime.now(timezone.utc)
        })
        db.session.commit()
        print("   执行 SQL: INSERT INTO room_playlist ...")

        # 2. 验证
        count = db.session.execute(
            text("SELECT count(*) FROM room_playlist WHERE room_id=:rid AND music_id=:mid"),
            {"rid": room_id, "mid": music_id}
        ).scalar()

        if count > 0:
            print("   测试通过")
        else:
            print("   测试失败")
    except Exception as e:
        print(f"   发生异常: {e}")


def test_room_availability():
    print("\n[测试 6] 房间开关状态 (UPDATE)")
    # 准备环境
    print("   ...准备房间...")
    room_id, _ = test_room_create()
    if not room_id: return

    # 1. 执行原生 UPDATE (关闭房间)
    sql = text("""
        UPDATE room 
        SET is_active = 0, playback_status = 'paused', updated_at = :now 
        WHERE id = :rid
    """)

    try:
        # [修改] 使用 datetime.now(timezone.utc)
        db.session.execute(sql, {"now": datetime.now(timezone.utc), "rid": room_id})
        db.session.commit()
        print("   执行 SQL: UPDATE room SET is_active=0 ...")

        # 2. 验证
        status = db.session.execute(
            text("SELECT is_active FROM room WHERE id=:rid"),
            {"rid": room_id}
        ).scalar()

        # MySQL boolean 返回 0 或 1
        if status == 0 or status is False:
            print("   测试通过 (房间已关闭)")
        else:
            print(f"   测试失败 (状态仍为 {status})")
    except Exception as e:
        print(f"   发生异常: {e}")


# ==========================================
# 主程序入口
# ==========================================
def main():
    # 必须在 app_context 下运行才能访问 db
    with app.app_context():
        print("=" * 40)
        print(f"当前数据库: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("=" * 40)

        while True:
            print("\n请选择要测试的原生 SQL 功能:")
            print("1. 修改个人资料 (UPDATE)")
            print("2. 上传音乐 (INSERT)")
            print("3. 删除音乐 (DELETE)")
            print("4. 创建房间 (INSERT)")
            print("5. 添加到播放列表 (INSERT)")
            print("6. 房间开关状态 (UPDATE)")
            print("q. 退出")

            choice = input("\n请输入选项 (1-6): ").strip()

            if choice == '1':
                test_profile_update()
            elif choice == '2':
                test_music_upload()
            elif choice == '3':
                test_music_delete()
            elif choice == '4':
                test_room_create()
            elif choice == '5':
                test_add_playlist()
            elif choice == '6':
                test_room_availability()
            elif choice.lower() == 'q':
                print("退出测试。")
                break
            else:
                print("无效输入，请重试。")


if __name__ == "__main__":
    main()