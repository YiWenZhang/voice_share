import os
from dotenv import load_dotenv  # 1. 导入加载工具

# 2. 在所有其他导入之前，先加载环境变量
# 这样后续代码读取 os.environ 时才能拿到 .env 里的配置
load_dotenv()

from app import create_app
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

