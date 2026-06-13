"""
全局配置文件
"""
import os
from pathlib import Path

# 优先加载 .env 文件中的环境变量
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

# ==================== LLM 配置 ====================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-v4-flash")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")

# ==================== 博客服务器配置 ====================
BLOG_SERVER_HOST = os.getenv("BLOG_SERVER_HOST", "127.0.0.1")
BLOG_SERVER_PORT = int(os.getenv("BLOG_SERVER_PORT", "5000"))
BLOG_API_URL = f"http://{BLOG_SERVER_HOST}:{BLOG_SERVER_PORT}"
BLOG_API_KEY = os.getenv("BLOG_API_KEY", "rl-agent-blog-api-key-2024")

# ==================== 数据存储配置 ====================
DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data.db"))
DRAFT_DIR = os.getenv("DRAFT_DIR", os.path.join(os.path.dirname(__file__), "drafts"))

# ==================== 抓取配置 ====================
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
PLAYWRIGHT_TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))  # 请求间隔(秒)

# ==================== arXiv 配置 ====================
ARXIV_CATEGORIES = ["cs.LG", "cs.AI", "cs.CL", "stat.ML"]
ARXIV_MAX_RESULTS = int(os.getenv("ARXIV_MAX_RESULTS", "20"))

# ==================== 调度配置 ====================
SCHEDULE_INTERVAL_HOURS = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "24"))
SCHEDULE_RUN_TIME = os.getenv("SCHEDULE_RUN_TIME", "09:00")  # 每日运行时间

# ==================== 日志配置 ====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", os.path.join(os.path.dirname(__file__), "logs", "agent.log"))
