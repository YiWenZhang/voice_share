# 共享听歌房系统 (Voice Share)

基于 Flask + MySQL 的一体化网页系统，覆盖注册登录、音乐上传、房间共享听歌、房间互动、行为记录、管理员审核等完整流程。普通用户 5 分钟内即可完成 “注册登录 → 创建房间 → 上传音乐 → 播放音乐 → 发送评论” 核心闭环，管理员拥有独立审核后台和超高级数据库处理权限。 

项目严格遵循 DAC（自主存取控制） 原则，通过最小权限账户 vs_normal 运行核心业务，而将高危运维功能交给特权账户 vs_admin 处理。

目前最新版本已经部署服务器，欢迎大家查看整体功能！
网址：http://115.190.207.9

## 功能概览
### 1.客户端
- 登录与注册：提供普通用户与管理员的登录/注册入口。
    - 注册安全：需完成滑块拼图验证。
    - 登录安全：连续登录失败 2 次，账号将锁定 60 秒（限流）。
- 仪表盘：用户主页，聚合核心功能入口。
    - 热门推荐：基于数据库视图 v_room_stats 实时展示最活跃的房间，点击可加入哦。
    - 房间创建：提供创建和加入房间的表单，并限制每个用户最多创建 3 个房间。
    - 加入房间：输入房间号码加入房间。
- 我的音乐：音乐资源管理与上传。
    - 上传限制：仅支持 MP3 格式，单文件限制 50MB。
    - 审核机制：上传后默认进入 待审核状态，通过后才可播放。
    - 操作：支持对已上传音乐进行删除。
    - 记录查看：可以显示所有上传的音乐以及审核状态
- 我的房间：管理用户创建和加入的房间列表。
    - 房间管理：可对自建房间进行进入管理或解散房间操作。
    - 当前加入房间：可以查看当前加入的所有房间以及状态
- 听歌房详情：房间的核心互动与播放界面。
    - 播放主控：房主拥有对播放、暂停、切歌的主控权，播放进度实时同步给所有成员。
    - 房间互动：支持实时文字弹幕聊天及在线人数显示，进入离开都会有提示哦。
    - 房主操作：可对房间进行暂时关闭或重新开放（影响访客加入，房间关闭会踢出用户。
- 历史记录：追踪用户行为足迹。
    - 数据范围：展示最近的听歌记录和房间参与记录。
    - 隐私管理：用户可以对单条听歌记录或访客记录进行手动删除。
- 个人资料：修改个人信息。
    - 数据更新：支持修改昵称（≤10 字）和头像（≤5MB，JPG/PNG），数据更新通过 原生 SQL UPDATE 实现。

### 2.管理员
后台提供隔离的 DAC 特权通道（vs_admin 连接），用于执行高权限操作。
- 管理员注册：需要密钥认证，账号admin_开头
- 审核工作台：音乐审核，处理用户上传的待审核列表，驳回时系统自动通知上传用户。
    - 待处理队列
        - 展示申请用户、音乐信息、提交时间
        - 实时刷新：点击刷新按钮重新加载待审核列表
        - 待办统计：右上角显示当前待处理任务数量
    - 最近驳回记录：按时间倒序展示最近被驳回的音乐，方便管理员查看历史审核决策
-  数据洞察中心：基于视图+索引提供高级查询功能
    - 全平台音乐库：多维度搜索，动态排序，自定义列
    - 房间活跃度监控：实时显示在线人数（房主 + 成员）热度进度条可视化展示
    - 听歌行为流水：记录所有用户的播放行为（歌名 + 播放时间）
- 索引与健康：提供数据库表结构、索引、完整性约束的可视化监控，支持全库概览和单表详情两种模式。
    - 全库概览模式：所有数据表和视图以卡片形式展示，展示索引、完整性、行数等
    - 单表详情模式：索引明细+外键明细
- 自动化运维：基于存储过程和触发器技术实现
    - 每日维护任务：调用存储过程清理 1 天前的过期记录，自动关闭 7 天未更新的僵尸房间
    - 审计日志查看：基于触发器自动记录所有用户加入房间的行为
- 安全与事务：可以执行账号封禁和权限查看
    - 事务级用户封禁：基于 ACID 事务原子性执行，锁定用户 → 关闭房间 → 下架音乐
    - 权限视图对比：查看当前数据库连接用户的权限分配（DAC 自主存取控制）
- 灾备管理：数据备份和恢复功能
    - 全量备份：生成当前数据库核心表状态的 JSON 快照文件
    - 数据恢复：上传备份 JSON 文件，将数据库回滚到指定时间点的状态

## 运行方式

### 1.**数据库环境准备 (DAC 权限配置)**

为了实现**自主存取控制 (Discretionary Access Control)**，本系统严禁使用 `root` 账号直接运行。请登录 MySQL 执行以下 SQL 脚本，创建权限分离的专用账户：

#### 1.1 **创建数据库**
```sql
    DROP DATABASE IF EXISTS voice_share;
    CREATE DATABASE voice_share CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    -- 可选项：解决 MySQL 8.0+ 触发器报错 (Error 1419)
    -- 允许非 SUPER 用户创建触发器，这对后续 Python 脚本自动创建触发器至关重要
    SET GLOBAL log_bin_trust_function_creators = 1;
```

#### 1.2 **创建角色**
以root权限进入你的数据库，并运行以下SQL语句，创建两个角色 (如果已存在则重建，确保环境纯净)
```sql
    DROP USER IF EXISTS 'vs_admin'@'localhost';
    DROP USER IF EXISTS 'vs_normal'@'localhost';
    
    CREATE USER 'vs_admin'@'localhost' IDENTIFIED BY 'AdminPass123!';
    CREATE USER 'vs_normal'@'localhost' IDENTIFIED BY 'UserPass123!';
    
    -- 授予管理员“施工”权限
    -- vs_admin 需要有权在 voice_share 库里建表、建存储过程、清空数据
    GRANT ALL PRIVILEGES ON voice_share.* TO 'vs_admin'@'localhost';
    SET GLOBAL log_bin_trust_function_creators = 1;
    GRANT SUPER ON *.* TO 'vs_admin'@'localhost';
    -- 刷新权限
    FLUSH PRIVILEGES;
```


### 2.**安装依赖**
```bash
pip install -r requirements.txt
```


### 3.**配置环境变量**

项目根目录下已包含 .env 文件，请填入上述创建的两个账号：
```Ini, TOML

# 普通业务连接 (vs_normal)
DATABASE_URL=mysql+pymysql://vs_normal:UserPass123!@localhost:3306/voice_share

# 管理员连接 (vs_admin) - 用于审计与灾备
DATABASE_URL_ADMIN=mysql+pymysql://vs_admin:AdminPass123
```

### 4.**初始化与启动**

- 系统会在第一次启动时通过 `app/create_with_sql.py` 自动尝试创建数据表。
- 启动应用：
```bash
        python run.py
```

### 5.**最终授权（MySQL 端）**
登录你的数据库，用root权限完成建表后的最终授权：
```sql
    USE voice_share;
    
    -- 1. 授予业务表的增删改查权限
    GRANT SELECT, INSERT, UPDATE, DELETE ON voice_share.musics TO 'vs_normal'@'localhost';
    GRANT SELECT, INSERT, UPDATE, DELETE ON voice_share.room TO 'vs_normal'@'localhost';
    GRANT SELECT, INSERT, UPDATE, DELETE ON voice_share.room_playlist TO 'vs_normal'@'localhost';
    GRANT SELECT, INSERT, UPDATE, DELETE ON voice_share.room_member TO 'vs_normal'@'localhost';
    GRANT SELECT, INSERT, UPDATE, DELETE ON voice_share.room_message TO 'vs_normal'@'localhost';
    GRANT SELECT, INSERT, UPDATE, DELETE ON voice_share.listen_record TO 'vs_normal'@'localhost';
    GRANT SELECT, INSERT, UPDATE, DELETE ON voice_share.room_participation_record TO 'vs_normal'@'localhost';
    
    -- 2. [安全控制] 用户表只给 增/改/查，严禁 DELETE
    GRANT SELECT, INSERT, UPDATE ON voice_share.user TO 'vs_normal'@'localhost';
    
    -- 3. 视图权限
    GRANT SELECT ON voice_share.v_music_full_info TO 'vs_normal'@'localhost';
    GRANT SELECT ON voice_share.v_room_stats TO 'vs_normal'@'localhost';
    
    -- 4. 再次刷新
    FLUSH PRIVILEGES;
```


### 6.**运行访问**
此时全部授权已经完成，再次执行
```bash
        python run.py
```
访问端口如下
- 用户前台：http://localhost:5000
- 管理员后台：http://localhost:5000/admin/login

## 目录结构

```text
voice_share/
├── app/                        # Flask 应用核心代码
│   ├── __init__.py             # 应用工厂、扩展初始化、蓝图注册
│   ├── admin.py                # 管理员后台路由逻辑
│   ├── auth.py                 # 认证模块（注册、登录、注销）
│   ├── create_with_sql.py      # MySQL 原生建表脚本 (自动执行)
│   ├── forms.py                # WTForms 表单定义（含滑块验证逻辑）
│   ├── models.py               # SQLAlchemy 数据模型
│   ├── routes.py               # 用户端主业务路由（房间、音乐、记录）
│   ├── test_raw_sql.py         # 数据库连接测试脚本
│   └── utils.py                # 工具函数（文件存储、ID生成、限流等）
├── static/                     # 静态资源
│   ├── css/                    # 样式文件 (main.css)
│   ├── js/                     # 前端脚本 (main.js)
│   └── uploads/                # 用户上传文件目录 (自动生成)
│       ├── avatars/            # 用户头像
│       └── music/              # MP3 文件
├── templates/                  # Jinja2 模板文件
│   ├── admin/                  # 后台模板 (dashboard.html)
│   ├── auth/                   # 认证模板 (login.html, register.html)
│   ├── public/                 # 公共页模板 (landing.html)
│   ├── dashboard.html          # 用户控制台
│   ├── layout.html             # 全局基础布局
│   ├── music.html              # 音乐管理页
│   ├── my_rooms.html           # 房间管理页
│   ├── profile.html            # 个人资料页
│   ├── records.html            # 历史记录页
│   └── room.html               # 听歌房详情与互动页
├── .env                        # 环境变量配置文件
├── config.py                   # 全局配置类
├── requirements.txt            # 项目依赖清单
└── run.py                      # 项目启动入口
```

## 关键设计

  - **安全性**
      - 使用 Flask-WTF CSRF 防护。
      - 密码使用 Hash 加密存储。
      - 滑块验证阻断基础脚本批量注册；登录失败计数在 1 分钟内封锁高频尝试。
      - 严格的文件类型与大小校验（头像\<5MB, 音乐\<50MB）。
  - **易用性**
      - 首页仪表盘聚合核心入口。
      - 房间播放同步采用轮询机制（间隔 3秒），兼顾实现简单与实时性。
      - 界面采用极光流体风格设计，适配移动端。
  - **数据持久化**
      - 采用 MySQL 存储核心业务数据，通过原生 SQL 脚本确保建表兼容性，支持外键约束与级联删除。
      - 管理员实时管理用户数据，基于MySQL数据库实现对数据的增删改查+并发+事务+备份恢复+存储过程等

欢迎按需扩展，例如替换前端框架、增加 WebSocket 实时推送等。
