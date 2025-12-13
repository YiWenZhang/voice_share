# ==============================================================================
# 模块名称：高级数据查询模块
# 文件名：database_views.py
# 描述：基于数据库视图 (View) 和原生 SQL 的高级数据检索接口
# ==============================================================================

from flask import Blueprint, render_template, request  # [新增] 导入 request
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
# 2. 全局音乐视图查询 (升级版 Pro：多维度精准搜索)
# ------------------------------------------------------------------------------
@db_views_bp.route("/music-list")
@login_required
def admin_music_view_query():
    _admin_required()

    # 1. 定义列映射 (前端 checkbox value -> 视图字段名)
    column_map = {
        'id': {'field': 'music_id', 'name': 'ID'},
        'title': {'field': 'title', 'name': '歌曲信息'},
        'uploader': {'field': 'uploader_nickname', 'name': '上传者'},
        'status': {'field': 'status', 'name': '当前状态'},
        'time': {'field': 'uploaded_at', 'name': '上传时间'},
        'reason': {'field': 'rejection_reason', 'name': '驳回原因'}
    }

    # 2. 获取前端筛选参数
    default_cols = ['id', 'title', 'uploader', 'status', 'time']
    selected_keys = request.args.getlist('cols') or default_cols
    final_cols = [k for k in selected_keys if k in column_map]
    if not final_cols: final_cols = default_cols

    # [修改] 获取拆分后的搜索参数
    q_title = request.args.get('q_title', '').strip()  # 栏1: 歌名
    q_uploader = request.args.get('q_uploader', '').strip()  # 栏2: 上传者昵称
    q_uid = request.args.get('q_uid', '').strip()  # 栏3: 上传者ID
    filter_status = request.args.get('status', '').strip()  # 栏4: 状态

    # 3. 构建动态 SQL
    # 为了演示性能优化，我们基于 v_music_full_info 视图查询
    base_sql = "SELECT * FROM v_music_full_info WHERE 1=1"
    params = {}

    # [修改] 动态拼接 WHERE 子句
    if q_title:
        base_sql += " AND title LIKE :q_title"
        params['q_title'] = f"%{q_title}%"

    if q_uploader:
        # 对应视图字段 uploader_nickname
        base_sql += " AND uploader_nickname LIKE :q_uploader"
        params['q_uploader'] = f"%{q_uploader}%"

    if q_uid:
        # 对应视图字段 uploader_id (精确匹配)
        if q_uid.isdigit():
            base_sql += " AND uploader_id = :q_uid"
            params['q_uid'] = q_uid

    if filter_status:
        base_sql += " AND status = :status"
        params['status'] = filter_status

    base_sql += " ORDER BY uploaded_at DESC"

    # 执行查询
    results = db.session.execute(text(base_sql), params).mappings().all()

    return render_template(
        "database_views/music_view_list.html",
        musics=results,
        all_columns=column_map,
        selected_cols=final_cols,
        # [修改] 将所有参数回传给前端用于回显
        q_title=q_title,
        q_uploader=q_uploader,
        q_uid=q_uid,
        filter_status=filter_status
    )


# ------------------------------------------------------------------------------
# 3. 房间热度视图查询 (升级版 Pro：多维度精准搜索)
# ------------------------------------------------------------------------------
@db_views_bp.route("/room-stats")
@login_required
def admin_room_view_query():
    _admin_required()

    # 1. 定义列映射 (前端 checkbox value -> 视图字段名)
    column_map = {
        'id': {'field': 'room_id', 'name': '系统ID'},
        'code': {'field': 'code', 'name': '房间号'},
        'name': {'field': 'name', 'name': '房间名称'},
        'owner': {'field': 'owner_name', 'name': '房主'},
        'status': {'field': 'is_active', 'name': '营业状态'},
        'heat': {'field': 'member_count', 'name': '实时热度'}
    }

    # 2. 获取筛选参数
    default_cols = ['code', 'name', 'owner', 'status', 'heat']
    selected_keys = request.args.getlist('cols') or default_cols
    final_cols = [k for k in selected_keys if k in column_map]
    if not final_cols: final_cols = default_cols

    # 获取搜索三剑客 + 状态
    q_name = request.args.get('q_name', '').strip()
    q_owner = request.args.get('q_owner', '').strip()
    q_code = request.args.get('q_code', '').strip()
    filter_status = request.args.get('status', '').strip()

    # 3. 构建动态 SQL
    # 基于视图 v_room_stats
    base_sql = "SELECT * FROM v_room_stats WHERE 1=1"
    params = {}

    # 动态拼接 WHERE
    if q_name:
        base_sql += " AND name LIKE :q_name"
        params['q_name'] = f"%{q_name}%"

    if q_owner:
        base_sql += " AND owner_name LIKE :q_owner"
        params['q_owner'] = f"%{q_owner}%"

    if q_code:
        # 房间号通常是精确查找
        base_sql += " AND code = :q_code"
        params['q_code'] = q_code

    if filter_status:
        # 这里的 status 是 '1' 或 '0'
        base_sql += " AND is_active = :status"
        params['status'] = int(filter_status)

    # 排序：优先按热度降序，其次是状态(营业中在前)
    base_sql += " ORDER BY member_count DESC, is_active DESC"

    results = db.session.execute(text(base_sql), params).mappings().all()

    return render_template(
        "database_views/room_view_list.html",
        rooms=results,
        all_columns=column_map,
        selected_cols=final_cols,
        # 回显参数
        q_name=q_name,
        q_owner=q_owner,
        q_code=q_code,
        filter_status=filter_status
    )



# ------------------------------------------------------------------------------
# 4. 用户听歌流水查询 (原生连接查询)
# ------------------------------------------------------------------------------
@db_views_bp.route("/listen-records")
@login_required
def admin_record_view_query():
    _admin_required()
    # 连接查询
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