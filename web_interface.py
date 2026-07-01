"""
Smart Quiz System - Web Interface (Streamlit)
主入口文件：负责页面配置、侧边栏导航和路由分发。
各页面渲染逻辑已拆分到 pages/ 模块中。
"""
import streamlit as st

from styles import inject_theme
from page_modules._common import get_stats
from page_modules import (
    render_dashboard,
    render_import,
    render_practice,
    render_statistics,
    render_wrong_review,
    render_question_manage,
    render_history,
    render_exam,
    render_review_plan,
)

# ─── 页面配置 ───
from config import STREAMLIT_PAGE_TITLE, STREAMLIT_PAGE_ICON, STREAMLIT_LAYOUT
st.set_page_config(page_title=STREAMLIT_PAGE_TITLE, page_icon=STREAMLIT_PAGE_ICON, layout=STREAMLIT_LAYOUT)

# ─── 初始化主题状态 ───
if 'theme_mode' not in st.session_state:
    st.session_state.theme_mode = 'light'

# ─── 用户认证 ───
from page_modules._common import get_db

def _show_login_page():
    """显示登录/注册页面。"""
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0;">
        <div style="font-size: 3rem;">📚</div>
        <h1>智能刷题系统</h1>
        <p style="color: #94a3b8;">请登录或注册以继续使用</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔑 登录", "📝 注册"])

    with tab_login:
        with st.form("login_form"):
            login_user = st.text_input("用户名", placeholder="输入用户名")
            login_pass = st.text_input("密码", type="password", placeholder="输入密码")
            login_btn = st.form_submit_button("🔑 登录", width="stretch", type="primary")
            if login_btn:
                if not login_user or not login_pass:
                    st.error("⚠️ 请填写用户名和密码")
                else:
                    db = get_db()
                    user, err = db.login_user(login_user, login_pass)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.session_state.user_id = user["id"]
                        st.session_state.username = user["username"]
                        st.session_state.display_name = user["display_name"]
                        st.session_state.user_role = user["role"]
                        st.success(f"✅ 欢迎回来，{user['display_name']}！")
                        st.rerun()

    with tab_register:
        with st.form("register_form"):
            reg_user = st.text_input("用户名", placeholder="至少2个字符", key="reg_user")
            reg_name = st.text_input("显示名称", placeholder="可选", key="reg_name")
            reg_pass = st.text_input("密码", type="password", placeholder="至少6个字符", key="reg_pass")
            reg_pass2 = st.text_input("确认密码", type="password", placeholder="再次输入密码", key="reg_pass2")
            reg_btn = st.form_submit_button("📝 注册", width="stretch")
            if reg_btn:
                if not reg_user or not reg_pass:
                    st.error("⚠️ 请填写用户名和密码")
                elif reg_pass != reg_pass2:
                    st.error("⚠️ 两次输入的密码不一致")
                else:
                    db = get_db()
                    uid, err = db.register_user(reg_user, reg_pass, reg_name)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.success("✅ 注册成功！请登录。")

if 'user_id' not in st.session_state:
    _show_login_page()
    st.stop()

# ─── 注入主题 CSS ───
inject_theme()

# ─── 侧边栏 ───
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 0.6rem 0.5rem;">
        <div style="font-size: 2rem; margin-bottom: 0.3rem;">📚</div>
        <div style="color: #f1f5f9; font-size: 18px; font-weight: 700;">智能刷题系统</div>
        <div style="color: #94a3b8; font-size: 13px; margin-top: 0.2rem;">高效练习 · 智能统计</div>
    </div>
    """, unsafe_allow_html=True)

    # 用户信息
    display_name = st.session_state.get('display_name', st.session_state.get('username', '用户'))
    st.markdown(f"""
    <div style="text-align: center; padding: 0.3rem 0; margin-bottom: 0.5rem;">
        <span style="color: #38bdf8; font-size: 14px;">👤 {display_name}</span>
    </div>
    """, unsafe_allow_html=True)

    # 主题切换
    dark_mode = st.toggle("🌙 夜间模式", value=(st.session_state.theme_mode == 'dark'))
    if dark_mode and st.session_state.theme_mode != 'dark':
        st.session_state.theme_mode = 'dark'
        st.rerun()
    elif not dark_mode and st.session_state.theme_mode != 'light':
        st.session_state.theme_mode = 'light'
        st.rerun()

    st.markdown("---")

    # 支持程序化页面切换（在 radio 渲染前设置默认值）
    nav_options = ["🏠 仪表盘", "📥 导入题目", "📝 刷题练习", "📋 模拟考试",
                   "📅 间隔复习", "📊 学习统计", "❌ 错题回顾",
                   "📋 题目管理", "📜 答题历史"]

    if 'page_switch' in st.session_state and st.session_state.page_switch:
        target = st.session_state.page_switch
        if target in nav_options:
            st.session_state.nav_radio = target
        del st.session_state.page_switch

    # 导航菜单
    page = st.radio(
        "📋 导航菜单",
        nav_options,
        label_visibility="collapsed",
        key="nav_radio"
    )

    st.markdown("---")

    # 侧边栏统计
    stats = get_stats(user_id=st.session_state.get('user_id', 0))
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.05); padding: 0.7rem; border-radius: 8px; margin-top: 0.5rem; border: 1px solid #334155;">
        <div style="color: #94a3b8; margin: 0; font-size: 13px;">📈 累计答题</div>
        <div style="color: #38bdf8; margin: 0.3rem 0 0 0; font-size: 20px; font-weight: 700;">{stats['total']} 次</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🚪 退出登录", width="stretch"):
        for key in ['user_id', 'username', 'display_name', 'user_role']:
            st.session_state.pop(key, None)
        st.rerun()

# ─── 路由分发 ───
PAGE_RENDERERS = {
    "🏠 仪表盘": render_dashboard,
    "📥 导入题目": render_import,
    "📝 刷题练习": render_practice,
    "📋 模拟考试": render_exam,
    "📅 间隔复习": render_review_plan,
    "📊 学习统计": render_statistics,
    "❌ 错题回顾": render_wrong_review,
    "📋 题目管理": render_question_manage,
    "📜 答题历史": render_history,
}

renderer = PAGE_RENDERERS.get(page)
if renderer:
    renderer()
