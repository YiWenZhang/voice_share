import os
from dotenv import load_dotenv  # [新增] 1. 导入加载工具

# [新增] 2. 必须在导入 app 之前加载环境变量，否则连的还是 SQLite
load_dotenv()

from sqlalchemy import text
from app import create_app, db

# 初始化 Flask 应用
app = create_app()


def test_backend():
    # 使用 app_context() 才能访问数据库配置和 session
    with app.app_context():
        print("=" * 40)
        print("开始后端原生 SQL 测试 (MySQL 版)")
        print("=" * 40)

        # 打印一下当前的数据库连接，确认是不是 MySQL
        # 如果打印出来是 sqlite:///... 说明 .env 没加载成功
        print(f"当前连接目标: {app.config['SQLALCHEMY_DATABASE_URI']}")

        # ---------------------------------------------------------
        # 1.1 数据库定义测试点
        # ---------------------------------------------------------
        print("\n>>> 验证数据库定义 (DDL)...")

        try:
            # [修改] SQLite 使用 sqlite_master，MySQL 使用 SHOW TABLES
            inspector_sql = text("SHOW TABLES;")
            result = db.session.execute(inspector_sql)

            # MySQL 返回的结果是元组列表 [('user',), ('room',)]，需要取第一个元素
            tables = [row[0] for row in result.fetchall()]

            print(f"当前数据库中存在的表: {tables}")

            # 检查核心表是否存在
            expected_tables = {'user', 'musics', 'room'}
            if expected_tables.issubset(set(tables)):
                print("成功：核心表 (user, musics, room) 已检测到。")
            else:
                print(f"失败：缺少表 {expected_tables - set(tables)}")

        except Exception as e:
            print(f"测试执行出错: {e}")
            print("请检查数据库连接是否正常，或表是否已创建。")


if __name__ == "__main__":
    test_backend()