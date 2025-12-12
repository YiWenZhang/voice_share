import os
from sqlalchemy import text
from app import create_app, db

# 初始化 Flask 应用
app = create_app()


def test_backend():
    # 使用 app_context() 才能访问数据库配置和 session
    with app.app_context():
        print("=" * 40)
        print("开始后端原生 SQL 测试")
        print("=" * 40)

        # ---------------------------------------------------------
        # 1.1数据库定义测试点
        # ---------------------------------------------------------
        print("\n>>> 验证数据库定义 (DDL)...")

        # 查询 SQLite 系统表，看看有哪些表被创建了
        inspector_sql = text("SELECT name FROM sqlite_master WHERE type='table';")
        result = db.session.execute(inspector_sql)
        tables = [row[0] for row in result.fetchall()]

        print(f"当前数据库中存在的表: {tables}")

        expected_tables = {'user', 'musics', 'room'}
        if expected_tables.issubset(set(tables)):
            print("成功：核心表 (user, musics, room) 已通过原生 SQL 创建。")
        else:
            print(f"失败：缺少表 {expected_tables - set(tables)}")


if __name__ == "__main__":
    test_backend()