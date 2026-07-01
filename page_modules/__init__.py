"""
Smart Quiz System - Pages Package
每个页面模块导出 render() 函数，由 web_interface.py 路由调用。
"""
from page_modules.dashboard import render as render_dashboard
from page_modules.import_page import render as render_import
from page_modules.practice import render as render_practice
from page_modules.statistics import render as render_statistics
from page_modules.wrong_review import render as render_wrong_review
from page_modules.question_manage import render as render_question_manage
from page_modules.history import render as render_history
from page_modules.exam import render as render_exam
from page_modules.review_plan import render as render_review_plan

__all__ = [
    "render_dashboard",
    "render_import",
    "render_practice",
    "render_statistics",
    "render_wrong_review",
    "render_question_manage",
    "render_history",
    "render_exam",
    "render_review_plan",
]
