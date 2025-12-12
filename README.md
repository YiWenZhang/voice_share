## 共享听歌房系统 (Voice Share)

基于 Flask + MySQL 的一体化网页系统，覆盖注册登录、音乐上传、房间共享听歌、房间互动、行为记录、管理员审核等完整流程。普通用户 5 分钟内即可完成 “注册登录 → 创建房间 → 上传音乐 → 播放音乐 → 发送评论” 核心闭环，管理员拥有独立审核后台。

目前旧版本（SQLite）已经部署服务器，欢迎大家查看整体功能！
网址：http://115.190.207.9

### 功能概览

- **注册登录**：普通用户需通过滑块拼图验证；连续输错密码 2 次会锁定 1 分钟。管理员账号需以 `admin_` 为前缀，并输入特定密钥进行注册，拥有独立后台入口。
- **个人信息**：用户可修改昵称（≤10 字）与本地头像（≤5MB 图片），即时生效。
- **音乐上传**：仅允许 MP3（≤50MB），上传前弹出版权提示；音乐先入待审核队列，通过后方可播放，支持用户自行删除已上传条目。
- **共享听歌房**：
    - 一键创建私密房间，自动生成 6 位唯一房间号。
    - **限制**：为了资源管理，**每个用户最多只能创建 3 个房间**，需解散旧房间后方可创建新房间。
    - 房间播放逻辑固定为房主主控（切歌/暂停/播放），全员端实时同步。
- **房间互动**：支持实时文字弹幕评论，实时显示在线人数。
- **行为数据**：自动保存最近 30 天的听歌记录（歌曲名 + 播放时间）与房间参与记录（房间号 + 时间），仅本人可见，**支持手动删除单条记录**。
- **管理员审核**：后台展示“待审核”与“违规”列表；提供“通过 / 驳回”操作，驳回时可填写理由，系统自动通知用户。

### 运行方式

1. **环境准备**
   - 确保本地已安装 MySQL 8.0+。
   - 登录 MySQL 并创建数据库：
     ```sql
     CREATE DATABASE voice_share CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
     ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt


3.  **配置环境变量**

      - 项目根目录下已包含 `.env` 文件（或复制 `.env.example`），请根据本地数据库配置修改 `DATABASE_URL`：
        ```ini
        # 格式: mysql+pymysql://用户名:密码@地址:端口/数据库名
        DATABASE_URL=mysql+pymysql://root:123456@localhost:3306/voice_share
        SECRET_KEY=your_secret_key
        ```

4.  **初始化与启动**

      - 系统会在第一次启动时通过 `app/create_with_sql.py` 自动尝试创建数据表。
      - 启动应用：
        ```bash
        python run.py
        ```
      - *可选：运行 `python app/test_raw_sql.py` 可测试数据库连接及表结构状态。*

5.  **访问地址**

      - 用户前台：http://localhost:5000
      - 管理员后台：http://localhost:5000/admin/login

### 目录结构

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

### 关键设计

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

欢迎按需扩展，例如替换前端框架、接入对象存储、增加 WebSocket 实时推送等。
