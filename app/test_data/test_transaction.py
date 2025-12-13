import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import text

# 1. 加载环境变量
load_dotenv()

from app import create_app, db
from app.models import User, Room, Music

# 初始化应用上下文
app = create_app()


def get_admin_conn():
    """获取管理员权限连接"""
    return db.get_engine(bind='admin_db').connect()


def setup_test_data():
    """准备测试数据"""
    print("\n>>> [准备阶段] 初始化测试数据...")

    username = "trans_tester"

    # [Admin操作] 清理旧数据
    with get_admin_conn() as conn:
        trans = conn.begin()
        conn.execute(text("DELETE FROM user WHERE username = :name"), {"name": username})
        trans.commit()
        print(f"    [Admin操作] 已清理旧用户: {username}")

    # 2. 创建新用户
    user = User(username=username, nickname="OriginalName", password_hash="dummy", is_admin=False)
    db.session.add(user)
    db.session.commit()

    # 3. 创建房间
    room = Room(owner_id=user.id, name="TestRoom", code="888888", is_active=True, playback_status="playing")
    db.session.add(room)

    # 4. 创建音乐
    music = Music(user_id=user.id, title="TestMusic", original_filename="t.mp3", stored_filename="t.mp3",
                  status="approved")
    db.session.add(music)

    db.session.commit()
    print(f"    用户 ID: {user.id}, 昵称: {user.nickname}")
    return user.id


def test_transaction_success(user_id):
    """测试 1: 正常流程 (Commit)"""
    print("\n" + "=" * 50)
    print("【测试 1】 事务正常提交测试 (Commit)")
    print("=" * 50)

    try:
        # --- [修改点] 使用 db.session.get 替代 .query.get ---
        user = db.session.get(User, user_id)

        user.nickname = f"[封禁] {user.nickname}"
        print("    [步骤1] 修改用户昵称... (未提交)")

        Room.query.filter_by(owner_id=user.id).update({"is_active": False, "playback_status": "paused"})
        print("    [步骤2] 关闭用户房间... (未提交)")

        Music.query.filter_by(user_id=user.id).update({"status": "rejected", "rejection_reason": "封禁"})
        print("    [步骤3] 下架用户音乐... (未提交)")

        db.session.commit()
        print("    >>> 执行 db.session.commit()")

        # --- 验证结果 ---
        print("\n    [验证结果]")
        db.session.expire_all()

        # --- [修改点] ---
        u = db.session.get(User, user_id)
        r = Room.query.filter_by(owner_id=user_id).first()
        m = Music.query.filter_by(user_id=user_id).first()

        if u.nickname.startswith("[封禁]") and r.is_active is False and m.status == "rejected":
            print("通过：所有数据均已更新。")
        else:
            print(f"失败：数据状态不符合预期")

    except Exception as e:
        db.session.rollback()
        print(f" 测试异常: {e}")


def test_transaction_rollback(user_id):
    """测试 2: 异常回滚测试 (Rollback)"""
    print("\n" + "=" * 50)
    print("【测试 2】 事务异常回滚测试 (Rollback)")
    print("=" * 50)

    # 重置数据
    # --- [修改点] ---
    user = db.session.get(User, user_id)
    user.nickname = "OriginalName"
    Room.query.filter_by(owner_id=user_id).update({"is_active": True})
    db.session.commit()
    print("    >>> 数据已重置为正常状态，准备开始...")

    try:
        # --- [修改点] ---
        user = db.session.get(User, user_id)
        user.nickname = "[封禁] Should_Be_Rollbacked"
        print("    [步骤1] 修改用户昵称... (内存中已修改)")

        Room.query.filter_by(owner_id=user.id).update({"is_active": False})
        print("    [步骤2] 关闭用户房间... (内存中已修改)")

        print("    [步骤3] !!! 模拟发生严重错误 (Raise Exception) !!!")
        raise Exception("人为制造的数据库崩溃")

        Music.query.filter_by(user_id=user.id).update({"status": "rejected"})
        db.session.commit()

    except Exception as e:
        print(f"    >>> 捕获到异常: {e}")
        print("    >>> 执行 db.session.rollback() 回滚事务...")
        db.session.rollback()

        # --- 验证结果 ---
        print("\n    [验证结果]")
        db.session.expire_all()

        # --- [修改点] ---
        u = db.session.get(User, user_id)
        r = Room.query.filter_by(owner_id=user_id).first()

        if u.nickname == "OriginalName" and r.is_active is True:
            print("通过：回滚成功！步骤 1 和 步骤 2 的修改已被撤销。")
        else:
            print(f"失败：回滚无效，数据被部分修改了！")


if __name__ == "__main__":
    with app.app_context():
        uid = setup_test_data()
        test_transaction_success(uid)
        test_transaction_rollback(uid)

        print("\n[清理] 删除测试数据...")
        with get_admin_conn() as conn:
            trans = conn.begin()
            conn.execute(text("DELETE FROM user WHERE id = :uid"), {"uid": uid})
            trans.commit()
            print("    [Admin操作] 测试数据清理完毕。")