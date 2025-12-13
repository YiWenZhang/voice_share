from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, Response, send_file
from flask_login import current_user, login_required
from sqlalchemy import text
from . import db
from .models import Music, User, Room
import json
import io
from datetime import datetime
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, Response, send_file, jsonify

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _admin_required():
    """辅助函数：确保当前用户是管理员"""
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


# ==============================================================================
# 1. 页面导航路由 (Sidebar Navigation)
# ==============================================================================

@admin_bp.route("/")
@login_required
def dashboard():
    """审核工作台 (首页)"""
    _admin_required()
    pending = Music.query.filter_by(status="pending").order_by(Music.uploaded_at.asc()).all()
    rejected = Music.query.filter_by(status="rejected").order_by(Music.uploaded_at.desc()).all()
    return render_template("admin/dashboard.html",
                           pending=pending,
                           rejected=rejected,
                           active_page='review')


@admin_bp.route("/db-health")
@login_required
def db_health():
    """索引与健康页面 (升级版：概览 + 详情)"""
    _admin_required()

    target_table = request.args.get('table')

    # --- 模式 A: 单表详情模式 (当 URL 包含 ?table=xxx 时触发) ---
    if target_table:
        # 简单防注入验证
        if not target_table.isidentifier():
            flash("非法表名", "error")
            return redirect(url_for('admin.db_health'))

        try:
            # 1. 获取索引详情
            indexes = db.session.execute(text(f"SHOW INDEX FROM {target_table}")).mappings().all()

            # 2. 获取外键详情 (额外查询 KEY_COLUMN_USAGE 表)
            fk_sql = text("""
                SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = :t 
                  AND REFERENCED_TABLE_NAME IS NOT NULL
            """)
            fks = db.session.execute(fk_sql, {"t": target_table}).mappings().all()

            return render_template("admin/dba_module.html",
                                   active_page='health',
                                   detail_mode=True,
                                   table_name=target_table,
                                   indexes=indexes,
                                   fks=fks,
                                   title=f"表详情: {target_table}",
                                   subtitle="索引结构与完整性约束明细",
                                   icon="ri-table-line")
        except Exception as e:
            flash(f"获取表详情失败: {str(e)}", "error")
            return redirect(url_for('admin.db_health'))

    # --- 模式 B: 全库概览模式 (默认显示) ---
    else:
        try:
            # [新增] 表功能描述字典 (含视图)
            table_desc = {
                'user': '存储用户账号、密码、昵称及头像路径',
                'room': '存储房间信息、在线状态及播放进度',
                'musics': '存储音乐元数据、文件路径及审核状态',
                'room_member': '记录当前房间内的在线成员关联',
                'room_message': '存储所有房间的历史聊天弹幕',
                'listen_record': '记录用户的听歌历史流水',
                'room_participation_record': '记录用户的房间访问足迹',
                'room_playlist': '存储各房间当前的排队播放列表',
                'system_audit_log':'存储流水的审计日志表',
                # 视图描述
                'v_music_full_info': '聚合查询：音乐+用户信息的完整视图',
                'v_room_stats': '统计视图：计算房间实时热度和在线人数'
            }

            # [修复] 修正后的 SQL 查询 (增加了 TABLE_TYPE)
            sql = """
            SELECT 
                T.TABLE_NAME,
                T.TABLE_TYPE,  -- [新增] 关键字段：区分 BASE TABLE 或 VIEW
                T.TABLE_ROWS,
                T.DATA_LENGTH,
                -- 统计索引个数 (去重索引名)
                (SELECT COUNT(DISTINCT INDEX_NAME) 
                 FROM information_schema.STATISTICS S 
                 WHERE S.TABLE_NAME = T.TABLE_NAME 
                   AND S.TABLE_SCHEMA = DATABASE()) as index_count,
                -- 统计主键个数 (实体完整性)
                (SELECT COUNT(*) 
                 FROM information_schema.TABLE_CONSTRAINTS C 
                 WHERE C.TABLE_NAME = T.TABLE_NAME 
                   AND C.TABLE_SCHEMA = DATABASE() 
                   AND C.CONSTRAINT_TYPE = 'PRIMARY KEY') as pk_count,
                -- 统计外键个数 (参照完整性)
                (SELECT COUNT(*) 
                 FROM information_schema.TABLE_CONSTRAINTS C 
                 WHERE C.TABLE_NAME = T.TABLE_NAME 
                   AND C.TABLE_SCHEMA = DATABASE() 
                   AND C.CONSTRAINT_TYPE = 'FOREIGN KEY') as fk_count
            FROM information_schema.TABLES T
            WHERE T.TABLE_SCHEMA = DATABASE();
            """

            tables_stats = db.session.execute(text(sql)).mappings().all()

            return render_template("admin/dba_module.html",
                                   active_page='health',
                                   detail_mode=False,
                                   tables=tables_stats,
                                   table_desc=table_desc,  # 传递描述字典
                                   title="数据库健康全景",
                                   subtitle="核心表索引、实体完整性与参照完整性概览",
                                   icon="ri-heart-pulse-line")
        except Exception as e:
            flash(f"获取概览失败: {str(e)}", "error")
            # 出错时返回空列表，避免页面崩溃
            return render_template("admin/dba_module.html",
                                   active_page='health',
                                   tables=[],
                                   title="Error",
                                   subtitle="Connection Failed",
                                   icon="ri-error-warning-line")


@admin_bp.route("/db-automation")
@login_required
def db_automation():
    """自动化运维页面"""
    _admin_required()
    return render_template("admin/dba_module.html",
                           active_page='automation',
                           title="自动化与审计中心",
                           subtitle="存储过程任务调度与触发器日志审计",
                           icon="ri-robot-2-line")


@admin_bp.route("/db-security")
@login_required
def db_security():
    """安全与事务页面"""
    _admin_required()
    return render_template("admin/dba_module.html",
                           active_page='security',
                           title="安全与事务管理",
                           subtitle="ACID 事务级用户封禁与权限控制",
                           icon="ri-shield-keyhole-line")


@admin_bp.route("/db-backup")
@login_required
def db_backup():
    """灾备管理页面"""
    _admin_required()
    return render_template("admin/dba_module.html",
                           active_page='backup',
                           title="灾备管理中心",
                           subtitle="数据库全量快照备份与时间点恢复",
                           icon="ri-save-3-line")


# ==============================================================================
# 2. 功能操作路由 (Action Buttons) - 解决 BuildError 的关键
# ==============================================================================


# --- [模块：自动化] 1. 执行存储过程 (AJAX版) ---
@admin_bp.route("/maintenance/exec", methods=["POST"])
@login_required
def exec_maintenance():
    _admin_required()
    try:
        # 调用存储过程 sp_daily_maintenance
        db.session.execute(text("CALL sp_daily_maintenance()"))
        db.session.commit()
        # [修改] 不再用 flash+redirect，而是返回 JSON
        return jsonify({
            "status": "success",
            "message": "每日维护存储过程执行成功！\n已清理 1 天前的过期记录与僵尸房间。"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"执行失败: {str(e)}"
        }), 500


# --- [模块：自动化] 2. 查看审计日志 ---
@admin_bp.route("/audit-logs")
@login_required
def audit_logs():
    _admin_required()
    # 查询审计表
    try:
        logs = db.session.execute(
            text("SELECT * FROM system_audit_log ORDER BY action_time DESC LIMIT 50")).mappings().all()
    except Exception as e:
        logs = []
        flash("审计表查询失败，请检查表是否存在", "warning")

    # 复用 dba_module 模板，但激活 'audit_logs_view' 状态来显示表格
    return render_template("admin/dba_module.html",
                           active_page='audit_logs_view',
                           title="审计日志明细",
                           subtitle="最近 50 条敏感操作记录 (Trigger Generated)",
                           icon="ri-file-list-3-line",
                           logs=logs)


# --- [模块：安全] 3. 事务级用户封禁 (Transaction) ---
@admin_bp.route("/user/transaction-ban", methods=["POST"])
@login_required
def manage_user_transaction():
    _admin_required()
    username = request.form.get("target_username")
    user = User.query.filter_by(username=username).first()

    if not user:
        flash(f"用户 {username} 不存在", "error")
        return redirect(url_for("admin.db_security"))

    if user.is_admin:
        flash("无法封禁管理员账号", "error")
        return redirect(url_for("admin.db_security"))

    try:
        # --- 开启事务 (ACID) ---
        # 1. 锁定用户 (修改昵称以示惩罚，实际项目应有 status 字段)
        old_nickname = user.nickname
        user.nickname = f"[封禁] {old_nickname}"

        # 2. 强制关闭其所有房间
        # 使用原生 SQL 或 ORM 批量更新
        Room.query.filter_by(owner_id=user.id).update({"is_active": False, "playback_status": "paused"})

        # 3. 下架其所有音乐
        Music.query.filter_by(user_id=user.id).update(
            {"status": "rejected", "rejection_reason": "账号严重违规，系统级封禁"})

        # 提交事务：以上三步要么全成功，要么因报错全回滚
        db.session.commit()

        flash(f"事务执行成功：用户[{username}]已封禁，关联房间与音乐已下架。", "success")

    except Exception as e:
        db.session.rollback()  # 回滚
        flash(f"事务执行失败，已回滚所有操作：{str(e)}", "error")

    return redirect(url_for("admin.db_security"))



# --- [模块：灾备] 4. 数据库全量备份 ---
@admin_bp.route("/backup/download")
@login_required
def backup_db():
    _admin_required()
    try:
        # 定义需要备份的所有表名 (顺序建议：先父表后子表，虽然恢复时会关外键)
        tables = [
            'user', 'musics', 'room',
            'room_member', 'room_playlist', 'room_message',
            'listen_record', 'room_participation_record',
            'system_audit_log'  # 连同审计日志一起备份
        ]

        # 构造备份数据结构
        data = {
            'meta': {
                'backup_time': str(datetime.now()),
                'version': '1.0',
                'description': 'Voice Share Full Database Backup'
            }
        }

        # 遍历查询所有表数据
        for t in tables:
            try:
                # 使用 mappings() 获取字典格式结果
                rows = db.session.execute(text(f"SELECT * FROM {t}")).mappings().all()
                # 将 RowMapping 转为普通 dict，并利用 default=str 处理 datetime 对象
                data[t] = [dict(row) for row in rows]
            except Exception as table_err:
                # 如果某个表不存在（比如审计表还没建），跳过不报错
                print(f"Backup warning: table {t} not found or error. {table_err}")
                data[t] = []

        json_str = json.dumps(data, default=str, indent=2, ensure_ascii=False)

        # 生成文件名
        filename = f"voice_share_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # 返回文件下载流
        return Response(
            json_str,
            mimetype="application/json",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        flash(f"备份生成失败: {str(e)}", "error")
        return redirect(url_for("admin.db_backup"))


# --- [模块：灾备] 5. 数据库恢复 (危险操作) ---
@admin_bp.route("/backup/restore", methods=["POST"])
@login_required
def restore_db():
    _admin_required()

    # 获取上传的文件
    file = request.files.get('file')
    if not file:
        return jsonify({'status': 'error', 'message': '未检测到上传文件'}), 400

    try:
        # 1. 解析 JSON
        data = json.load(file)

        # 简单格式校验
        if 'meta' not in data or 'user' not in data:
            return jsonify({'status': 'error', 'message': '无效的备份文件格式，缺少关键元数据'}), 400

        # 2. 准备恢复列表 (注意顺序：删除时先子后父，插入时先父后子)
        # 这里我们依靠关闭外键检查来简化顺序问题
        tables = [
            'room_participation_record', 'listen_record', 'room_message',
            'room_playlist', 'room_member', 'system_audit_log',
            'room', 'musics', 'user'
        ]

        # --- 开始事务 ---
        # 3. 关闭外键约束检查 (关键步骤，否则无法清空有外键关联的表)
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        # 4. 清空旧数据 (TRUNCATE 会重置自增 ID，DELETE 不会。为了完全恢复，推荐 TRUNCATE)
        for t in tables:
            try:
                db.session.execute(text(f"TRUNCATE TABLE {t}"))
            except Exception:
                # 如果 TRUNCATE 失败 (某些 MySQL 版本限制)，尝试 DELETE
                db.session.execute(text(f"DELETE FROM {t}"))

        # 5. 插入新数据
        for t in tables:
            # 倒序之后的 tables 列表其实是删除顺序，我们恢复时可以直接用 data 里的键
            # 或者重新定义一个插入顺序。这里直接遍历 json 中的 keys 也可以，因为外键已关。
            if t not in data: continue

            rows = data[t]
            if not rows: continue

            # 构建 INSERT 语句: INSERT INTO table (col1, col2) VALUES (:col1, :col2)
            # 假设每一行的 keys 都是一样的，取第一行做模板
            keys = rows[0].keys()
            columns_str = ', '.join(keys)
            values_str = ', '.join([f':{k}' for k in keys])

            sql = text(f"INSERT INTO {t} ({columns_str}) VALUES ({values_str})")

            # 批量执行插入
            db.session.execute(sql, rows)

        # 6. 恢复外键约束检查
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

        db.session.commit()

        user_count = len(data.get('user', []))
        return jsonify({
            'status': 'success',
            'message': f'数据恢复成功！\n快照时间: {data["meta"]["backup_time"]}\n恢复用户数: {user_count}'
        })

    except Exception as e:
        db.session.rollback()
        # 发生异常也要尝试把外键检查开回来，防止影响后续操作
        try:
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            db.session.commit()
        except:
            pass

        return jsonify({'status': 'error', 'message': f'恢复失败: {str(e)}'}), 500


# ==============================================================================
# 3. 原有审核路由
# ==============================================================================

@admin_bp.post("/music/<int:music_id>/approve")
@login_required
def approve_music(music_id):
    _admin_required()
    music = Music.query.filter_by(id=music_id).first_or_404()
    music.status = "approved"
    music.rejection_reason = None
    db.session.commit()
    flash("音乐审核已通过", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.post("/music/<int:music_id>/reject")
@login_required
def reject_music(music_id):
    _admin_required()
    reason = request.form.get("reason", "上传音乐涉及违规内容，已驳回删除")
    music = Music.query.filter_by(id=music_id).first_or_404()
    music.status = "rejected"
    music.rejection_reason = reason
    if music.owner:
        music.owner.notification_message = reason
    db.session.commit()
    flash("音乐已驳回", "info")
    return redirect(url_for("admin.dashboard"))