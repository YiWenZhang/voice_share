from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import text
from .database_views import get_hot_rooms_data
from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from . import db
from .forms import MusicUploadForm, ProfileForm, RoomCreateForm, RoomJoinForm
from .models import (
    ListenRecord,
    Music,
    Room,
    RoomMember,
    RoomMessage,
    RoomParticipationRecord,
    RoomPlaylist,
    User,
)
from .utils import generate_room_code, generate_room_name, save_avatar, save_music

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("main.dashboard"))
    return render_template("public/landing.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    room_form = RoomCreateForm()
    if not room_form.name.data:
        room_form.name.data = generate_room_name()
    join_form = RoomJoinForm()
    pending_notice = current_user.notification_message
    if pending_notice:
        current_user.notification_message = None
        db.session.commit()
        flash(pending_notice, "warning")
    # [新增] 获取热门房间数据 (体现视图聚合作用)
    hot_rooms = get_hot_rooms_data(limit=4)
    return render_template(
        "dashboard.html",
        room_form=room_form,
        join_form=join_form,
        hot_rooms=hot_rooms,  # [新增] 传递数据到前端
    )


@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if current_user.is_admin:
        abort(403)
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        # --- 原生 SQL UPDATE ---
        avatar_path = current_user.avatar_path
        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename:
            stored_name = save_avatar(avatar_file)
            if not stored_name:
                flash("仅支持常见图片格式，大小请控制在 5MB 内", "error")
                return render_template("profile.html", form=form)
            avatar_path = stored_name  # 更新路径变量

        sql = text("""
            UPDATE user 
            SET nickname = :nickname, avatar_path = :avatar, updated_at = :now
            WHERE id = :uid
        """)
        db.session.execute(sql, {
            "nickname": form.nickname.data,
            "avatar": avatar_path,
            "now": datetime.utcnow(),
            "uid": current_user.id
        })
        # --- [结束修改] ---

        db.session.commit()
        flash("个人信息已更新", "success")
        return redirect(url_for("main.profile"))
    return render_template("profile.html", form=form)

@main_bp.route("/music", methods=["GET", "POST"])
@login_required
def music():
    if current_user.is_admin:
        abort(403)
    upload_form = MusicUploadForm()
    if upload_form.validate_on_submit():
        file = request.files.get("file")
        if not file or not file.filename:
            flash("请选择 MP3 文件", "error")
        else:
            stored_name, error = save_music(file)
            if error:
                flash(error, "error")
            else:
                title = (upload_form.title.data or "").strip()
                if not title:
                    title = Path(file.filename).stem or "未命名歌曲"

                # --- [开始修改] 改为原生 SQL INSERT ---
                # 注意表名是 musics
                sql = text("""
                                    INSERT INTO musics (user_id, title, original_filename, stored_filename, status, uploaded_at, created_at)
                                    VALUES (:uid, :title, :orig_name, :stored_name, 'pending', :now, :now)
                                """)

                db.session.execute(sql, {
                    "uid": current_user.id,
                    "title": title,
                    "orig_name": file.filename,
                    "stored_name": stored_name,
                    "now": datetime.utcnow()
                })
                # --- [结束修改] ---

                db.session.commit()
                flash("请确保上传音乐拥有合法使用权限", "info")
                flash("音乐已进入待审核队列", "success")
                return redirect(url_for("main.music"))
    my_music = Music.query.filter_by(user_id=current_user.id).order_by(Music.uploaded_at.desc()).all()
    return render_template("music.html", upload_form=upload_form, musics=my_music)


@main_bp.route("/music/<int:music_id>/delete", methods=["POST"])
@login_required
def delete_music(music_id):
    if current_user.is_admin:
        abort(403)

    # --- [开始修改] 改为原生 SQL DELETE ---
    # 为了数据一致性，先删除关联的播放列表记录（如果数据库未设置级联删除）
    sql_del_playlist = text("DELETE FROM room_playlist WHERE music_id = :mid")
    db.session.execute(sql_del_playlist, {"mid": music_id})

    # 再删除音乐本身，且必须确保是当前用户的音乐
    sql_del_music = text("DELETE FROM musics WHERE id = :mid AND user_id = :uid")
    result = db.session.execute(sql_del_music, {"mid": music_id, "uid": current_user.id})

    if result.rowcount == 0:
        abort(404)  # 如果没删掉任何行，说明音乐不存在或不属于该用户
    # --- [结束修改] ---

    db.session.commit()
    flash("音乐已删除", "info")
    return redirect(url_for("main.music"))


@main_bp.route("/my-rooms")
@login_required
def my_rooms():
    if current_user.is_admin:
        abort(403)
    owned_rooms = (
        Room.query.filter_by(owner_id=current_user.id).order_by(Room.created_at.desc()).all()
    )
    memberships = (
        RoomMember.query.filter_by(user_id=current_user.id)
        .order_by(RoomMember.joined_at.desc())
        .all()
    )
    return render_template(
        "my_rooms.html",
        owned_rooms=owned_rooms,
        memberships=memberships,
    )


def _generate_unique_room_code():
    while True:
        code = generate_room_code()
        if not Room.query.filter_by(code=code).first():
            return code


@main_bp.route("/rooms/create", methods=["POST"])
@login_required
def create_room():
    if current_user.is_admin:
        abort(403)
    form = RoomCreateForm()
    if not form.validate_on_submit():
        flash("房间名称校验失败", "error")
        return redirect(url_for("main.dashboard"))
    # ========================== [开始插入修改代码] ==========================
    # 检查用户是否已经创建了 3 个或更多房间
    current_count = Room.query.filter_by(owner_id=current_user.id).count()
    if current_count >= 3:
        # 使用 flash 提示错误，而不是报错
        flash("创建失败：你已拥有 3 个房间，请先解散旧房间再创建", "error")
        # 重定向回仪表盘页面
        return redirect(url_for("main.dashboard"))
    # ========================== [结束插入修改代码] ==========================



    # --- [开始修改] 改为原生 SQL INSERT ---
    code = _generate_unique_room_code()
    room_name = form.name.data or generate_room_name()
    now = datetime.utcnow()

    # 1. 插入房间表
    sql_room = text("""
        INSERT INTO room (owner_id, name, code, is_active, playback_status, current_position, created_at)
        VALUES (:uid, :name, :code, 1, 'paused', 0.0, :now)
    """)
    db.session.execute(sql_room, {
        "uid": current_user.id,
        "name": room_name,
        "code": code,
        "now": now
    })

    # 2. 插入参与记录表
    sql_record = text("""
        INSERT INTO room_participation_record (user_id, room_code, participated_at)
        VALUES (:uid, :code, :now)
    """)
    db.session.execute(sql_record, {
        "uid": current_user.id,
        "code": code,
        "now": now
    })
    # --- [结束修改] ---

    db.session.commit()
    flash(f"房间创建成功，房间号 {code}", "success")
    return redirect(url_for("main.room_detail", code=code))


@main_bp.route("/rooms/join", methods=["POST"])
@login_required
def join_room():
    if current_user.is_admin:
        abort(403)
    form = RoomJoinForm()
    if not form.validate_on_submit():
        flash("请输入正确的 6 位房间号", "error")
        return redirect(url_for("main.dashboard"))
    room = Room.query.filter_by(code=form.code.data).first()
    if not room:
        flash("房间不存在或已关闭", "error")
        return redirect(url_for("main.dashboard"))
    if not room.is_active:
        flash("房间已关闭，暂不可加入", "error")
        return redirect(url_for("main.dashboard"))
    _attach_member(room, current_user)
    flash("加入成功，祝你听歌愉快", "success")
    return redirect(url_for("main.room_detail", code=room.code))


def _attach_member(room: Room, user: User, *, record_participation: bool = True):
    if not room.is_active:
        return
    if room.owner_id == user.id:
        return
    existing = RoomMember.query.filter_by(room_id=room.id, user_id=user.id).first()
    created_now = False
    if not existing:
        membership = RoomMember(room_id=room.id, user_id=user.id)
        db.session.add(membership)
        created_now = True

        # [新增] 插入进入房间的消息
        join_msg = RoomMessage(room_id=room.id, user_id=user.id, content="进入了房间")
        db.session.add(join_msg)

    if record_participation or created_now:
        record = RoomParticipationRecord(user_id=user.id, room_code=room.code)
        db.session.add(record)
    db.session.commit()


@main_bp.route("/rooms/<code>")
@login_required
def room_detail(code):
    if current_user.is_admin:
        abort(403)
    room = Room.query.filter_by(code=code).first_or_404()
    if not room.is_active and room.owner_id != current_user.id:
        flash("房间已关闭，无法进入", "error")
        return redirect(url_for("main.dashboard"))
    if room.owner_id != current_user.id:
        _attach_member(room, current_user, record_participation=False)
    member_count = RoomMember.query.filter_by(room_id=room.id).count() + 1
    # 获取房间播放列表
    room_playlist = RoomPlaylist.query.filter_by(room_id=room.id).order_by(RoomPlaylist.created_at.asc()).all()

    # 获取用户自己的已审核音乐（用于添加到房间）
    my_approved_music = (
        Music.query.filter_by(user_id=current_user.id, status="approved")
        .order_by(Music.uploaded_at.desc())
        .all()
    )

    messages = RoomMessage.query.filter_by(room_id=room.id).order_by(RoomMessage.created_at.asc()).all()

    return render_template(
        "room.html",
        room=room,
        is_owner=room.owner_id == current_user.id,
        room_playlist=room_playlist,
        my_library=my_approved_music,
        messages=messages,
        member_count=member_count,
        timedelta=timedelta,  # [新增] 把 timedelta 工具传给前端
    )



@main_bp.route("/rooms/<code>/playlist/add", methods=["POST"])
@login_required
def add_to_playlist(code):
    room = Room.query.filter_by(code=code).first_or_404()
    music_id = request.form.get("music_id")

    if not music_id:
        flash("请选择音乐", "error")
        return redirect(url_for("main.room_detail", code=code))

    music = Music.query.filter_by(id=music_id, user_id=current_user.id, status="approved").first()
    if not music:
        flash("音乐不存在或未审核通过", "error")
        return redirect(url_for("main.room_detail", code=code))

    # 检查是否已在列表中（可选，这里允许重复添加）
    # existing = RoomPlaylist.query.filter_by(room_id=room.id, music_id=music.id).first()

    # --- [开始修改] 改为原生 SQL INSERT ---
    # 先验证音乐是否存在且属于当前用户且已过审（用 Select 验证）
    check_sql = text("SELECT id, title FROM musics WHERE id=:mid AND user_id=:uid AND status='approved'")
    res = db.session.execute(check_sql, {"mid": music_id, "uid": current_user.id}).fetchone()

    if not res:
        flash("音乐不存在或未审核通过", "error")
        return redirect(url_for("main.room_detail", code=code))

    music_title = res[1]  # 获取歌名用于提示

    # 插入播放列表
    insert_sql = text("""
        INSERT INTO room_playlist (room_id, music_id, created_at)
        VALUES (:rid, :mid, :now)
    """)
    db.session.execute(insert_sql, {
        "rid": room.id,  # 这里 room.id 还是可以从上面查询出来的 room 对象获取，或者也改成 SQL 查询
        "mid": music_id,
        "now": datetime.utcnow()
    })
    # --- [结束修改] ---

    db.session.commit()
    flash(f"已将《{music_title}》添加到房间播放列表", "success")
    return redirect(url_for("main.room_detail", code=code))


@main_bp.route("/rooms/<code>/leave", methods=["POST"])
@login_required
def leave_room(code):
    room = Room.query.filter_by(code=code).first_or_404()
    if room.owner_id == current_user.id:
        flash("房主无法直接退出，如需解散请关闭房间", "warning")
        return redirect(url_for("main.room_detail", code=code))
    membership = RoomMember.query.filter_by(room_id=room.id, user_id=current_user.id).first()
    if membership:
        # ========================== [开始插入修改代码] ==========================
        # 1. 在删除成员关系之前，先发送一条离开的消息
        # 注意：content 内容可以自定义，前端会自动显示发送者名字
        leave_msg = RoomMessage(room_id=room.id, user_id=current_user.id, content="离开了房间")
        db.session.add(leave_msg)
        # ========================== [结束插入修改代码] ==========================

        db.session.delete(membership)
        db.session.commit()
        flash("你已退出房间，可随时再次通过房间号加入", "info")
    else:
        flash("当前未在该房间中", "warning")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/rooms/<code>/availability", methods=["POST"])
@login_required
def room_availability(code):
    # --- [开始修改] 改为原生 SQL UPDATE ---
    # 1. 确认房间存在且属于当前用户
    room_query = text("SELECT id, is_active FROM room WHERE code=:code AND owner_id=:uid")
    result = db.session.execute(room_query, {"code": code, "uid": current_user.id}).fetchone()

    if not result:
        abort(403)

    room_id = result[0]

    action = request.form.get("action")
    message = ""

    if action == "close":
        # 关闭房间：设置 is_active=0, playback_status='paused'
        update_sql = text("""
            UPDATE room 
            SET is_active = 0, playback_status = 'paused', updated_at = :now 
            WHERE id = :rid
        """)
        message = "房间已关闭，成员将无法继续进入"
    elif action == "open":
        # 开启房间：设置 is_active=1
        update_sql = text("""
            UPDATE room 
            SET is_active = 1, updated_at = :now 
            WHERE id = :rid
        """)
        message = "房间已重新开放，房间号可继续使用"
    else:
        flash("未知操作", "error")
        return redirect(url_for("main.room_detail", code=code))

    db.session.execute(update_sql, {"now": datetime.utcnow(), "rid": room_id})
    # --- [结束修改] ---

    db.session.commit()
    flash(message, "success")
    return redirect(url_for("main.room_detail", code=code))

@main_bp.route("/rooms/<code>/delete", methods=["POST"])
@login_required
def delete_room(code):
    room = Room.query.filter_by(code=code).first_or_404()
    if room.owner_id != current_user.id:
        abort(403)
    RoomMessage.query.filter_by(room_id=room.id).delete(synchronize_session=False)
    RoomMember.query.filter_by(room_id=room.id).delete(synchronize_session=False)
    RoomPlaylist.query.filter_by(room_id=room.id).delete(synchronize_session=False)
    db.session.delete(room)
    db.session.commit()
    flash("房间已删除，房间号不再可用", "info")
    return redirect(url_for("main.my_rooms"))




@main_bp.route("/records")
@login_required
def records():
    if current_user.is_admin:
        abort(403)
    cutoff = datetime.utcnow() - timedelta(days=30)
    listen_records = (
        ListenRecord.query.filter(ListenRecord.user_id == current_user.id, ListenRecord.played_at >= cutoff)
        .order_by(ListenRecord.played_at.desc())
        .all()
    )
    room_records = (
        RoomParticipationRecord.query.filter(
            RoomParticipationRecord.user_id == current_user.id,
            RoomParticipationRecord.participated_at >= cutoff,
        )
        .order_by(RoomParticipationRecord.participated_at.desc())
        .all()
    )
    return render_template("records.html", listen_records=listen_records, room_records=room_records)



@main_bp.route("/rooms/<code>/state")
@login_required
def room_state(code):
    room = Room.query.filter_by(code=code).first_or_404()
    if not room.is_active and room.owner_id != current_user.id:
        abort(403)

    # 1. 智能进度计算
    current_pos = room.current_position
    if room.playback_status == 'playing' and room.updated_at:
        elapsed = (datetime.utcnow() - room.updated_at).total_seconds()
        current_pos += elapsed
    current_member_count = RoomMember.query.filter_by(room_id=room.id).count() + 1
    # 2. 聊天记录 (修复：必须返回 messages 字段)
    recent_msgs = RoomMessage.query.filter_by(room_id=room.id) \
        .order_by(RoomMessage.created_at.desc()) \
        .limit(50).all()
    recent_msgs.reverse()
    messages_data = [{
        "id": m.id,
        "author_id": m.author.id,
        "author_name": m.author.nickname or m.author.username,
        "author_avatar": m.author.avatar_url,
        "created_at": (m.created_at + timedelta(hours=8)).strftime('%H:%M'),
        "content": m.content
    } for m in recent_msgs]

    # 3. 播放列表 (修复：必须返回 playlist 字段)
    playlist_items = RoomPlaylist.query.filter_by(room_id=room.id) \
        .order_by(RoomPlaylist.created_at.asc()).all()
    playlist_data = [{
        "id": item.id,
        "music_id": item.music.id,
        "title": item.music.title
    } for item in playlist_items]

    return jsonify({
        "playback_status": room.playback_status,
        "current_track_name": room.current_track_name,
        "current_track_file": room.current_track_file,
        "current_position": current_pos,
        "is_active": room.is_active,
        "updated_at": room.updated_at.isoformat() if room.updated_at else None,
        "messages": messages_data,  # 确保前端能收到消息
        "playlist": playlist_data,  # 确保前端能收到歌单
        "member_count": current_member_count
    })


@main_bp.route("/rooms/<code>/toggle", methods=["POST"])
@login_required
def toggle_playback(code):
    room = Room.query.filter_by(code=code).first_or_404()
    if room.owner_id != current_user.id:
        abort(403)

    music_id = request.form.get("music_id")
    action = request.form.get("action")

    try:
        position = request.form.get("position", type=float)
    except (ValueError, TypeError):
        position = None

    # 1. 切歌逻辑
    if music_id:
        music = Music.query.get(music_id)
        if music and music.status == "approved":
            room.current_track_name = music.title
            room.current_track_file = music.stored_filename
            room.playback_status = "playing"
            room.current_position = 0.0
            room.updated_at = datetime.utcnow()
            db.session.add(ListenRecord(user_id=current_user.id, song_name=music.title))
        else:
            flash("无法播放该歌曲", "error")

    # 2. 播放/暂停/停止逻辑
    elif action in {"play", "pause", "stop"}:
        if action == "stop":
            # 【新增】播放结束或清空状态
            room.playback_status = "paused"
            room.current_track_name = None  # 清空歌名
            room.current_track_file = None  # 清空文件
            room.current_position = 0.0
        else:
            room.playback_status = "playing" if action == "play" else "paused"
            if position is not None and position >= 0:
                room.current_position = position

        room.updated_at = datetime.utcnow()

    db.session.commit()
    return jsonify({"status": "success"})


@main_bp.route("/rooms/<code>/messages", methods=["POST"])
@login_required
def send_message(code):
    room = Room.query.filter_by(code=code).first_or_404()
    content = request.form.get("content", "").strip()
    if not content:
        return jsonify({"error": "内容不能为空"}), 400
    message = RoomMessage(room_id=room.id, user_id=current_user.id, content=content)
    db.session.add(message)
    db.session.commit()
    return jsonify({"status": "success"})


@main_bp.route("/rooms/<code>/playlist/delete", methods=["POST"])
@login_required
def delete_from_playlist(code):
    room = Room.query.filter_by(code=code).first_or_404()
    if room.owner_id != current_user.id:
        abort(403)
    item_id = request.form.get("item_id")
    if item_id:
        entry = RoomPlaylist.query.get(item_id)
        if entry and entry.room_id == room.id:
            db.session.delete(entry)
            db.session.commit()
    return jsonify({"status": "success"})


# [新增] 删除听歌记录路由
@main_bp.route("/records/listen/<int:record_id>/delete", methods=["POST"])
@login_required
def delete_listen_record(record_id):
    if current_user.is_admin:
        abort(403)
    record = ListenRecord.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    db.session.delete(record)
    db.session.commit()
    flash("听歌记录已删除", "success")
    return redirect(url_for("main.records"))


# [新增] 删除房间参与记录路由
@main_bp.route("/records/room/<int:record_id>/delete", methods=["POST"])
@login_required
def delete_room_record(record_id):
    if current_user.is_admin:
        abort(403)
    record = RoomParticipationRecord.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    db.session.delete(record)
    db.session.commit()
    flash("访客记录已删除", "success")
    return redirect(url_for("main.records"))


