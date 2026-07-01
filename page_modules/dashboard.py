"""🏠 仪表盘页面"""
import streamlit as st
from page_modules._common import (
    TYPE_NAMES, TYPE_ICONS, render_footer,
    get_stats, get_total_questions, get_subjects, get_question_type_counts,
)


def render():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("欢迎使用智能刷题系统")

    from page_modules._common import is_dark_mode
    _sub_color = "#94a3b8" if is_dark_mode() else "#718096"
    st.markdown(f"""
    <div style="text-align: center; color: {_sub_color}; margin-bottom: 2rem;">
        <p style="font-size: 1.1rem;">🎯 高效练习 · 📊 智能统计 · 🤖 多题型支持</p>
    </div>
    """, unsafe_allow_html=True)

    stats = get_stats()
    total_questions = get_total_questions()
    subjects = get_subjects()
    type_counts = get_question_type_counts()

    # 核心指标卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📚 题库总量", f"{total_questions} 题", help="题库中的题目总数")
    with col2:
        st.metric("✍️ 答题总次数", f"{stats['total']} 次", help="累计答题次数")
    with col3:
        st.metric("🎯 总体正确率", f"{stats['accuracy']}%", help="所有答题的正确率")
    with col4:
        st.metric("📖 学科分类", f"{len(subjects)} 个", help="题库中的学科数量")

    st.markdown("<br>", unsafe_allow_html=True)

    # 题型分布
    if type_counts:
        st.markdown("### 📋 题型分布")
        cols = st.columns(len(type_counts))
        for i, (q_type, cnt) in enumerate(type_counts.items()):
            with cols[i]:
                name = TYPE_NAMES.get(q_type, q_type)
                icon = TYPE_ICONS.get(q_type, "📝")
                st.metric(f"{icon} {name}", f"{cnt} 题")

    st.markdown("<br>", unsafe_allow_html=True)

    # 快速开始
    st.markdown("### 🚀 快速开始")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📥 导入题目", width="stretch"):
            st.session_state.page_switch = "📥 导入题目"
            st.rerun()
        st.caption("文本/PDF/DOCX批量导入，支持AI智能解析")
    with col2:
        if st.button("📝 刷题练习", width="stretch"):
            st.session_state.page_switch = "📝 刷题练习"
            st.rerun()
        st.caption("随机/错题/难度三种模式")
    with col3:
        if st.button("📋 模拟考试", width="stretch"):
            st.session_state.page_switch = "📋 模拟考试"
            st.rerun()
        st.caption("限时考试，自动交卷评分")

    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button("📅 间隔复习", width="stretch"):
            st.session_state.page_switch = "📅 间隔复习"
            st.rerun()
        st.caption("艾宾浩斯遗忘曲线，科学复习")
    with col5:
        if st.button("❌ 错题回顾", width="stretch"):
            st.session_state.page_switch = "❌ 错题回顾"
            st.rerun()
        st.caption("错题汇总，一键重练")
    with col6:
        if st.button("📊 学习统计", width="stretch"):
            st.session_state.page_switch = "📊 学习统计"
            st.rerun()
        st.caption("可视化数据分析")

    render_footer()
    st.markdown('</div>', unsafe_allow_html=True)
