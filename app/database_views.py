# ==============================================================================
# 模块名称：高级数据查询模块
# 文件名：database_views.py
# 描述：基于数据库视图 (View) 和原生 SQL 的高级数据检索接口
# ==============================================================================

from flask import Blueprint, render_template
from sqlalchemy import text
from flask_login import login_required, current_user
from app import db

db_views_bp = Blueprint("db_views", __name__, url_prefix="/data-center")

def _admin_required():
    from flask import abort
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)

# ------------------------------------------------------------------------------
# 1. 数据中心主页 (Dashboard)
# ------------------------------------------------------------------------------
@db_views_bp.route("/")
@login_required
def admin_query_center():
    """数据查询中心入口"""
    _admin_required()
    return render_template("database_views/admin_query_center.html")


# ------------------------------------------------------------------------------
# 2. 全局音乐视图查询
# ------------------------------------------------------------------------------
@db_views_bp.route("/music-list")
@login_required
def admin_music_view_query():
    _admin_required()
    # 查询视图 v_music_full_info
    sql = text("SELECT * FROM v_music_full_info ORDER BY uploaded_at DESC")
    results = db.session.execute(sql).mappings().all()
    return render_template("database_views/music_view_list.html", musics=results)


# ------------------------------------------------------------------------------
# 3. 房间热度视图查询
# ------------------------------------------------------------------------------
@db_views_bp.route("/room-stats")
@login_required
def admin_room_view_query():
    _admin_required()
    # 查询视图 v_room_stats
    sql = text("SELECT * FROM v_room_stats ORDER BY member_count DESC, is_active DESC")
    results = db.session.execute(sql).mappings().all()
    return render_template("database_views/room_view_list.html", rooms=results)


# ------------------------------------------------------------------------------
# 4. 用户听歌流水查询 (原生连接查询)
# ------------------------------------------------------------------------------
@db_views_bp.route("/listen-records")
@login_required
def admin_record_view_query():
    _admin_required()
    # 这里演示一个较复杂的原生连接查询，模拟视图的效果
    sql = text("""
        SELECT 
            lr.id,
            lr.song_name,
            lr.played_at,
            u.username,
            u.nickname
        FROM listen_record lr
        JOIN user u ON lr.user_id = u.id
        ORDER BY lr.played_at DESC
        LIMIT 100
    """)
    results = db.session.execute(sql).mappings().all()
    return render_template("database_views/record_view_list.html", records=results)


# ------------------------------------------------------------------------------
# 辅助函数：供首页 Dashboard 使用
# ------------------------------------------------------------------------------
def get_hot_rooms_data(limit=5):
    sql = text("""
        SELECT * FROM v_room_stats 
        WHERE is_active = 1 
        ORDER BY member_count DESC 
        LIMIT :limit
    """)
    return db.session.execute(sql, {"limit": limit}).mappings().all()