"""
Smart Quiz System - 公共工具模块
集中管理页面间共享的常量、辅助函数和数据库缓存。
"""
import json
import streamlit as st
from database import DatabaseManager

# ═══════════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════════
TYPE_NAMES = {
    "single": "单选题",
    "multi": "多选题",
    "judge": "判断题",
    "fill": "填空题",
    "short": "简答题",
}
TYPE_ICONS = {
    "single": "🔘",
    "multi": "☑️",
    "judge": "⚖️",
    "fill": "✏️",
    "short": "📝",
}


# ═══════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════
def is_dark_mode():
    """检查当前是否为深色模式。"""
    return st.session_state.get('theme_mode', 'light') == 'dark'


def render_answer_controls(q_type: str, options: dict, key_prefix: str,
                           disabled: bool = False):
    """共享的答题控件渲染逻辑（practice.py 和 exam.py 共用）。
    
    Args:
        q_type: 题型 (single/multi/judge/fill/short)
        options: 选项字典
        key_prefix: Streamlit widget key 前缀
        disabled: 是否禁用控件
    
    Returns:
        user_answer: 用户选择的答案（str 或 None）
    """
    user_answer = None

    if q_type in ("single", "judge") and options:
        choice = st.radio(
            "选择答案：",
            list(options.keys()),
            format_func=lambda x: f"{x}. {options[x]}",
            key=f"{key_prefix}_radio",
            disabled=disabled,
        )
        user_answer = choice

    elif q_type == "multi" and options:
        st.markdown("**选择答案（可多选）：**")
        selected = []
        for key, val in options.items():
            if st.checkbox(
                f"{key}. {val}",
                key=f"{key_prefix}_{key}",
                disabled=disabled,
            ):
                selected.append(key)
        user_answer = "".join(sorted(selected)) if selected else None

    elif q_type == "short":
        fill_answer = st.text_area(
            "请输入你的回答：",
            key=f"{key_prefix}_short",
            disabled=disabled,
            height=120,
            placeholder="请在此输入简答内容..."
        )
        user_answer = fill_answer.strip() if fill_answer else None

    else:
        fill_answer = st.text_input(
            "请输入答案：",
            key=f"{key_prefix}_fill",
            disabled=disabled,
        )
        user_answer = fill_answer.strip() if fill_answer else None

    return user_answer


def status_card_html(lines, border_color="#0ea5e9", bg_light="#f0f9ff", bg_dark="#1e293b"):
    """生成适配深色/浅色模式的状态卡片 HTML。
    lines: 字符串列表，每行一个 <div> 内容。
    """
    bg = bg_dark if is_dark_mode() else bg_light
    text_color = "#e2e8f0" if is_dark_mode() else "#1e293b"
    inner = "".join(f'<div style="margin:0.2rem 0;">{line}</div>' for line in lines)
    return (f'<div style="background:{bg};padding:0.8rem 1rem;border-radius:10px;'
            f'margin-bottom:0.5rem;border-left:4px solid {border_color};'
            f'color:{text_color};font-size:14px;line-height:1.6;">{inner}</div>')


def info_card_html(lines, border_color="#10b981"):
    """绿色信息卡片。"""
    return status_card_html(lines, border_color, "#ecfdf5", "#064e3b")


def error_card_html(lines, border_color="#ef4444"):
    """红色错误卡片。"""
    return status_card_html(lines, border_color, "#fef2f2", "#450a0a")


def gradient_card_html(content_html, gradient_light, gradient_dark,
                       text_light="#374151", text_dark="#e2e8f0"):
    """生成适配深色/浅色模式的渐变卡片 HTML。
    content_html: 卡片内部的 HTML 字符串。
    gradient_light/dark: 浅色/深色模式下的 CSS background 值。
    """
    bg = gradient_dark if is_dark_mode() else gradient_light
    color = text_dark if is_dark_mode() else text_light
    return (f'<div style="background:{bg};padding:1.5rem;border-radius:15px;'
            f'margin-bottom:2rem;color:{color};">{content_html}</div>')


def safe_json_loads(s):
    """安全解析JSON，失败返回空字典"""
    if not s:
        return {}
    try:
        result = json.loads(s)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def truncate_text(text, max_len=100):
    """截断过长文本"""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def render_footer():
    """渲染页面底部"""
    st.markdown("---")
    st.markdown("""
    <div class="footer">
        <p>📚 智能刷题系统 v2.0 | 让学习更高效</p>
        <p>使用 Streamlit 构建 ❤️</p>
    </div>
    """, unsafe_allow_html=True)


def render_metric_card(title, value, gradient_css, shadow_css=""):
    """渲染带渐变背景的指标卡片。"""
    shadow = f"box-shadow: {shadow_css};" if shadow_css else ""
    return f"""
    <div style="background: {gradient_css};
                padding: 2rem; border-radius: 15px; color: white; text-align: center;
                {shadow}">
        <h3 style="margin: 0; font-size: 3rem;">{value}</h3>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">{title}</p>
    </div>
    """


def render_type_badge(q_type, index=None):
    """渲染题型标签徽章 HTML。"""
    type_label = TYPE_NAMES.get(q_type, q_type)
    type_icon = TYPE_ICONS.get(q_type, "📝")
    index_html = ""
    if index is not None:
        index_html = f"""<span style="background: linear-gradient(90deg, #0ea5e9, #10b981);
                   color: white; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.85rem;">
            第 {index} 题
        </span>"""
    return f"""
    <div style="margin-bottom: 1rem;">
        {index_html}
        <span style="background: #8b5cf6;
                   color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem; margin-left: 0.5rem;">
            {type_icon} {type_label}
        </span>
    </div>
    """


# ═══════════════════════════════════════════════════════════
#  数据库缓存查询（Streamlit 缓存）
# ═══════════════════════════════════════════════════════════
@st.cache_resource
def get_db():
    """缓存数据库连接，避免每次交互都重新创建。异常时友好提示。"""
    try:
        return DatabaseManager()
    except Exception as e:
        st.error(f"❌ 数据库连接失败：{e}")
        st.info("💡 请检查 data/question_bank.db 文件是否存在且未损坏。")
        st.stop()


@st.cache_data(ttl=15)
def get_stats(user_id=0):
    """获取全局统计数据（按用户隔离）"""
    db = get_db()
    row = db.execute(
        """
        SELECT
            COUNT(*)                      AS total,
            COALESCE(SUM(is_correct), 0)  AS correct
        FROM practice_records
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()
    total = row["total"]
    correct = row["correct"]
    accuracy = round((correct / total * 100) if total > 0 else 0, 2)
    return {"total": total, "correct": correct, "accuracy": accuracy}


@st.cache_data(ttl=5)
def get_total_questions():
    db = get_db()
    return db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]


@st.cache_data(ttl=5)
def get_subjects():
    db = get_db()
    subjects = db.execute(
        "SELECT DISTINCT subject FROM questions WHERE subject != ''"
    ).fetchall()
    return [s[0] for s in subjects]


@st.cache_data(ttl=5)
def get_question_type_counts():
    db = get_db()
    rows = db.execute(
        "SELECT question_type, COUNT(*) as cnt FROM questions GROUP BY question_type"
    ).fetchall()
    return {r["question_type"]: r["cnt"] for r in rows}


@st.cache_data(ttl=5)
def get_chapters():
    """获取所有章节列表。"""
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT chapter FROM questions WHERE chapter != '' ORDER BY chapter"
    ).fetchall()
    return [r[0] for r in rows]
