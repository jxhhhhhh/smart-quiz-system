"""
Smart Quiz System - 配置文件
所有可配置项集中管理，避免硬编码。
支持从 .env 文件或环境变量读取敏感配置。
"""
import os

# 尝试加载 .env 文件（如果安装了 python-dotenv）
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # python-dotenv 未安装时忽略

# ═══════════════════════════════════════════════════════════
#  路径配置
# ═══════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "question_bank.db")

# 确保 data 目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════
#  AI API 配置（优先从环境变量读取）
# ═══════════════════════════════════════════════════════════
AI_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
AI_DEFAULT_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
AI_DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Mimo API 配置（小米创造者计划）
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_BASE_URL = os.environ.get("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MIMO_DEFAULT_MODEL = os.environ.get("MIMO_MODEL", "mimo-v2.5-pro")
AI_MAX_CHARS = 15000          # 单次解析最大字符数
AI_MAX_TOKENS = 8192          # LLM 最大输出 token
AI_TEMPERATURE = 0.1          # LLM 温度（越低越确定）

# OCR 图片识别配置（使用支持 Vision 的多模态模型）
OCR_MODEL = os.environ.get("OCR_MODEL", "deepseek-chat")  # 支持图片输入的模型
OCR_MAX_TOKENS = 16384        # OCR 解析最大输出 token

# ═══════════════════════════════════════════════════════════
#  解析配置
# ═══════════════════════════════════════════════════════════
CONF_HIGH = 0.8               # 置信度 ≥ 此值直接采纳
CONF_LOW = 0.5                # 置信度 < 此值交给 AI 重新解析
FUZZY_THRESHOLD = 0.75        # 模糊匹配相似度阈值

# ═══════════════════════════════════════════════════════════
#  Streamlit 配置
# ═══════════════════════════════════════════════════════════
STREAMLIT_PORT = 8501
STREAMLIT_PAGE_TITLE = "智能刷题系统"
STREAMLIT_PAGE_ICON = "📚"
STREAMLIT_LAYOUT = "wide"

# ═══════════════════════════════════════════════════════════
#  日志配置
# ═══════════════════════════════════════════════════════════
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
