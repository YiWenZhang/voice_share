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
# 2. 全局音乐视图查询 (升级版 Pro Max：多维度搜索 + 动态排序)
# ------------------------------------------------------------------------------
@db_views_bp.route("/music-list")
@login_required
def admin_music_view_query():
    _admin_required()

    # 1. 定义列映射 (增加 'sql_field' 用于排序)
    column_map = {
        'id': {'field': 'music_id', 'name': 'ID', 'sql_field': 'music_id'},
        'title': {'field': 'title', 'name': '歌曲信息', 'sql_field': 'title'},
        'uploader': {'field': 'uploader_nickname', 'name': '上传者', 'sql_field': 'uploader_nickname'},
        'status': {'field': 'status', 'name': '当前状态', 'sql_field': 'status'},
        'time': {'field': 'uploaded_at', 'name': '上传时间', 'sql_field': 'uploaded_at'},
        'reason': {'field': 'rejection_reason', 'name': '驳回原因', 'sql_field': 'rejection_reason'}
    }

    # 2. 获取筛选参数
    default_cols = ['id', 'title', 'uploader', 'status', 'time']
    selected_keys = request.args.getlist('cols') or default_cols
    final_cols = [k for k in selected_keys if k in column_map]
    if not final_cols: final_cols = default_cols

    # 获取搜索四剑客
    q_title = request.args.get('q_title', '').strip()
    q_uploader = request.args.get('q_uploader', '').strip()
    q_uid = request.args.get('q_uid', '').strip()
    filter_status = request.args.get('status', '').strip()

    # [新增] 获取排序参数
    sort_by = request.args.get('sort', 'time')  # 默认按时间排
    sort_order = request.args.get('order', 'desc').lower()  # 默认降序

    # 3. 构建动态 SQL
    base_sql = "SELECT * FROM v_music_full_info WHERE 1=1"
    params = {}

    # WHERE 子句
    if q_title:
        base_sql += " AND title LIKE :q_title"
        params['q_title'] = f"%{q_title}%"
    if q_uploader:
        base_sql += " AND uploader_nickname LIKE :q_uploader"
        params['q_uploader'] = f"%{q_uploader}%"
    if q_uid and q_uid.isdigit():
        base_sql += " AND uploader_id = :q_uid"
        params['q_uid'] = q_uid
    if filter_status:
        base_sql += " AND status = :status"
        params['status'] = filter_status

    # [新增] ORDER BY 子句构建
    if sort_by in column_map:
        target_field = column_map[sort_by]['sql_field']
    else:
        target_field = 'uploaded_at'  # 默认字段

    direction = 'ASC' if sort_order == 'asc' else 'DESC'

    base_sql += f" ORDER BY {target_field} {direction}"

    # 二级排序：ID倒序 (保证分页/排序稳定性)
    if target_field != 'music_id':
        base_sql += ", music_id DESC"

    # 执行查询
    results = db.session.execute(text(base_sql), params).mappings().all()

    return render_template(
        "database_views/music_view_list.html",
        musics=results,
        all_columns=column_map,
        selected_cols=final_cols,
        # 回显搜索参数
        q_title=q_title,
        q_uploader=q_uploader,
        q_uid=q_uid,
        filter_status=filter_status,
        # [新增] 回显排序参数
        current_sort=sort_by,
        current_order=sort_order
    )





# ------------------------------------------------------------------------------
# 3. 房间热度视图查询 (升级版 Pro Max：多维度搜索 + 动态排序)
# ------------------------------------------------------------------------------
@db_views_bp.route("/room-stats")
@login_required
def admin_room_view_query():
    _admin_required()

    # 1. 定义列映射 (前端 key -> 数据库字段 & 显示名称)
    # [新增] 'sql_field' 用于排序时的 SQL 字段名
    column_map = {
        'id': {'field': 'room_id', 'name': '系统ID', 'sql_field': 'room_id'},
        'code': {'field': 'code', 'name': '房间号', 'sql_field': 'code'},
        'name': {'field': 'name', 'name': '房间名称', 'sql_field': 'name'},
        'owner': {'field': 'owner_name', 'name': '房主', 'sql_field': 'owner_name'},
        'status': {'field': 'is_active', 'name': '营业状态', 'sql_field': 'is_active'},
        'heat': {'field': 'member_count', 'name': '实时热度', 'sql_field': 'member_count'}
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

    # [新增] 获取排序参数
    # sort_by: 前端传来的列 key (例如 'heat', 'id')
    # sort_order: 'asc' 或 'desc'
    sort_by = request.args.get('sort', 'heat')  # 默认按热度排
    sort_order = request.args.get('order', 'desc').lower()  # 默认降序

    # 3. 构建动态 SQL
    base_sql = "SELECT * FROM v_room_stats WHERE 1=1"
    params = {}

    # WHERE 子句 (保持不变)
    if q_name:
        base_sql += " AND name LIKE :q_name"
        params['q_name'] = f"%{q_name}%"
    if q_owner:
        base_sql += " AND owner_name LIKE :q_owner"
        params['q_owner'] = f"%{q_owner}%"
    if q_code:
        base_sql += " AND code = :q_code"
        params['q_code'] = q_code
    if filter_status:
        base_sql += " AND is_active = :status"
        params['status'] = int(filter_status)

    # [新增] ORDER BY 子句构建
    # 安全校验：防止 SQL 注入，只允许 column_map 中的字段
    if sort_by in column_map:
        target_field = column_map[sort_by]['sql_field']
    else:
        target_field = 'member_count'  # 默认字段

    # 校验排序方向
    direction = 'ASC' if sort_order == 'asc' else 'DESC'

    # 拼接 SQL
    base_sql += f" ORDER BY {target_field} {direction}"

    # 为了稳定性，当主排序字段相同时，追加二级排序
    if target_field != 'room_id':
        base_sql += ", room_id DESC"

    # 执行查询
    results = db.session.execute(text(base_sql), params).mappings().all()

    return render_template(
        "database_views/room_view_list.html",
        rooms=results,
        all_columns=column_map,
        selected_cols=final_cols,
        # 回显搜索参数
        q_name=q_name,
        q_owner=q_owner,
        q_code=q_code,
        filter_status=filter_status,
        # [新增] 回显排序参数
        current_sort=sort_by,
        current_order=sort_order
    )


# ------------------------------------------------------------------------------
# 4. 用户听歌流水查询 (升级版 Pro Max：多维度搜索 + 动态排序)
# ------------------------------------------------------------------------------
@db_views_bp.route("/listen-records")
@login_required
def admin_record_view_query():
    _admin_required()

    # 1. 定义列映射 (注意：sql_field 需要带表别名 lr. 或 u.)
    column_map = {
        'id': {'field': 'id', 'name': '记录ID', 'sql_field': 'lr.id'},
        'song': {'field': 'song_name', 'name': '歌曲名称', 'sql_field': 'lr.song_name'},
        'nickname': {'field': 'nickname', 'name': '用户昵称', 'sql_field': 'u.nickname'},
        'username': {'field': 'username', 'name': '用户账号', 'sql_field': 'u.username'},
        'uid': {'field': 'user_id', 'name': '用户ID', 'sql_field': 'u.id'},
        'time': {'field': 'played_at', 'name': '播放时间', 'sql_field': 'lr.played_at'}
    }

    # 2. 获取筛选参数
    default_cols = ['id', 'time', 'nickname', 'song']
    selected_keys = request.args.getlist('cols') or default_cols
    final_cols = [k for k in selected_keys if k in column_map]
    if not final_cols: final_cols = default_cols

    # 获取搜索参数
    q_song = request.args.get('q_song', '').strip()
    q_nickname = request.args.get('q_nickname', '').strip()
    q_username = request.args.get('q_username', '').strip()
    q_uid = request.args.get('q_uid', '').strip()

    # 获取排序参数
    sort_by = request.args.get('sort', 'time')  # 默认按时间排
    sort_order = request.args.get('order', 'desc').lower()

    # 3. 构建动态 SQL (基于 JOIN 查询)
    base_sql = """
        SELECT 
            lr.id,
            lr.song_name,
            lr.played_at,
            u.id AS user_id,
            u.username,
            u.nickname
        FROM listen_record lr
        JOIN user u ON lr.user_id = u.id
        WHERE 1=1
    """
    params = {}

    # 动态拼接 WHERE
    if q_song:
        base_sql += " AND lr.song_name LIKE :q_song"
        params['q_song'] = f"%{q_song}%"

    if q_nickname:
        base_sql += " AND u.nickname LIKE :q_nickname"
        params['q_nickname'] = f"%{q_nickname}%"

    if q_username:
        base_sql += " AND u.username LIKE :q_username"
        params['q_username'] = f"%{q_username}%"

    if q_uid and q_uid.isdigit():
        base_sql += " AND u.id = :q_uid"
        params['q_uid'] = q_uid

    # 动态拼接 ORDER BY
    if sort_by in column_map:
        target_field = column_map[sort_by]['sql_field']
    else:
        target_field = 'lr.played_at'

    direction = 'ASC' if sort_order == 'asc' else 'DESC'
    base_sql += f" ORDER BY {target_field} {direction}"

    # 限制返回数量，防止爆表 (实际生产环境应使用分页)
    base_sql += " LIMIT 200"

    results = db.session.execute(text(base_sql), params).mappings().all()

    return render_template(
        "database_views/record_view_list.html",
        records=results,
        all_columns=column_map,
        selected_cols=final_cols,
        # 回显参数
        q_song=q_song,
        q_nickname=q_nickname,
        q_username=q_username,
        q_uid=q_uid,
        current_sort=sort_by,
        current_order=sort_order
    )



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