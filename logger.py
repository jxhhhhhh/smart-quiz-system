"""
Smart Quiz System - Logging Module
统一日志配置，所有模块通过 get_logger(name) 获取 logger。
支持控制台和文件双通道输出。
"""
import logging
import os

from config import LOG_LEVEL, LOG_FORMAT, DATA_DIR

# 日志级别（环境变量优先，其次 config.py）
_LOG_LEVEL = os.environ.get("QUIZ_LOG_LEVEL", LOG_LEVEL).upper()
_LOG_FORMAT = os.environ.get("QUIZ_LOG_FORMAT", LOG_FORMAT)

# 配置文件日志
_LOG_FILE = os.path.join(DATA_DIR, "app.log")

# 根 logger 配置
root_logger = logging.getLogger()
root_logger.setLevel(_LOG_LEVEL)

# 控制台 handler
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root_logger.addHandler(console_handler)

# 文件 handler（自动轮转，最大 5MB，保留 3 个备份）
try:
    from logging.handlers import RotatingFileHandler
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        file_handler = RotatingFileHandler(
            _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root_logger.addHandler(file_handler)
except (OSError, PermissionError):
    pass  # 文件日志不可用时只输出到控制台


def get_logger(name: str) -> logging.Logger:
    """返回以 *name* 命名的 logger 实例。"""
    return logging.getLogger(name)
