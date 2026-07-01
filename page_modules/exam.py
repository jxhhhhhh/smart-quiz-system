"""📝 模拟考试页面"""
import time
import json
import streamlit as st
from practice_session import PracticeSession
from parser import check_answer, normalize_answer
from page_modules._common import (
    TYPE_NAMES, TYPE_ICONS, safe_json_loads, truncate_text,
    render_footer, get_db, render_answer_controls,
)


def render():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("📝 模拟考试")

    # 初始化 session state
    for key, default in [
        ('exam_questions', []), ('exam_index', 0), ('exam_score', 0),
        ('exam_answered', False), ('exam_start_time', 0),
        ('exam_time_limit', 30), ('exam_finished', False),
        ('exam_question_start_time', 0), ('exam_time_spent', 0),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    if st.session_state.exam_questions:
        _render_exam()
    elif st.session_state.exam_finished:
        _render_result()
    else:
        _render_settings()

    render_footer()
    st.markdown('</div>', unsafe_allow_html=True)


def _render_settings():
    """渲染考试设置页面。"""
    st.markdown("### ⚙️ 考试设置")

    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]

    if total == 0:
        st.warning("⚠️ 题库为空，请先导入题目。")
        return

    col1, col2 = st.columns(2)
    with col1:
        count = st.number_input(
            "题目数量", min_value=1, max_value=min(100, total),
            value=min(20, total), step=1
        )
        time_limit = st.number_input(
            "考试时间（分钟）", min_value=5, max_value=180, value=30, step=5
        )
    with col2:
        subjects = [s[0] for s in db.execute(
            "SELECT DISTINCT subject FROM questions WHERE subject != ''"
        ).fetchall()]
        subject_filter = st.selectbox("学科筛选", ["全部学科"] + subjects)

        diff_filter = st.selectbox("难度筛选", ["全部难度", "⭐ 简单", "⭐⭐ 中等", "⭐⭐⭐ 困难"])
        diff_map = {"全部难度": None, "⭐ 简单": 1, "⭐⭐ 中等": 2, "⭐⭐⭐ 困难": 3}
        difficulty = diff_map[diff_filter]

    st.markdown("---")
    st.info(f"📊 当前题库共 {total} 道题目，将随机抽取 {count} 题进行考试。")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 开始考试", width="stretch", type="primary"):
            # 构建查询
            sql = "SELECT * FROM questions WHERE 1=1"
            params = []
            if subject_filter != "全部学科":
                sql += " AND subject = ?"
                params.append(subject_filter)
            if difficulty:
                sql += " AND difficulty = ?"
                params.append(difficulty)
            sql += " ORDER BY RANDOM() LIMIT ?"
            params.append(count)

            rows = db.execute(sql, params).fetchall()
            questions = []
            for r in rows:
                d = dict(r)
                try:
                    d["options"] = json.loads(d["options"])
                except (json.JSONDecodeError, TypeError):
                    d["options"] = {}
                if d.get("question_type") == "judge" and not d["options"]:
                    d["options"] = {"A": "正确", "B": "错误"}
                questions.append(d)

            if not questions:
                st.error("❌ 没有符合条件的题目。")
                return

            st.session_state.exam_questions = questions
            st.session_state.exam_index = 0
            st.session_state.exam_score = 0
            st.session_state.exam_answered = False
            st.session_state.exam_start_time = time.time()
            st.session_state.exam_time_limit = time_limit
            st.session_state.exam_finished = False
            st.session_state.exam_question_start_time = time.time()
            st.session_state.exam_time_spent = 0
            st.rerun()


def _render_exam():
    """渲染考试答题页面。"""
    questions = st.session_state.exam_questions
    idx = st.session_state.exam_index
    q = questions[idx]
    q_type = q.get("question_type", "single")

    # 检查是否超时
    elapsed_min = (time.time() - st.session_state.exam_start_time) / 60
    if elapsed_min >= st.session_state.exam_time_limit:
        _finish_exam()
        st.rerun()
        return

    # 顶部信息栏
    remaining = st.session_state.exam_time_limit - elapsed_min
    remaining_sec = max(0, remaining * 60)

    # 低时间警告（<5分钟变红）
    if remaining < 1:
        st.error(f"🚨 **时间已到！** 正在自动交卷...")
        _finish_exam()
        st.rerun()
        return
    elif remaining < 5:
        st.warning(f"⚠️ **剩余不足 5 分钟！** 请尽快完成答题。")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📝 进度", f"{idx + 1}/{len(questions)}")
    with col2:
        st.metric("🎯 得分", st.session_state.exam_score)
    with col3:
        time_color = "🔴" if remaining < 5 else "🟢"
        st.metric(f"{time_color} 剩余", f"{remaining:.0f} 分钟")
    with col4:
        st.metric("⏰ 已用", f"{elapsed_min:.1f} 分钟")

    # 进度条
    st.progress((idx + 1) / len(questions))

    # JavaScript 自动刷新：考试结束时自动触发页面刷新
    refresh_ms = int(remaining_sec * 1000) + 1000  # 多1秒确保超时检查触发
    if refresh_ms > 0 and refresh_ms < 3600000:  # 限制在1小时内
        st.markdown(
            f'<script>setTimeout(function(){{window.parent.location.reload()}}, {refresh_ms})</script>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 题目卡片
    type_badge = TYPE_NAMES.get(q_type, q_type)
    type_icon = TYPE_ICONS.get(q_type, "📝")
    st.markdown(f"""
    <div style="margin-bottom: 1rem;">
        <span style="background: linear-gradient(90deg, #0ea5e9, #10b981);
                   color: white; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.85rem;">
            第 {idx + 1} 题
        </span>
        <span style="background: #8b5cf6;
                   color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem; margin-left: 0.5rem;">
            {type_icon} {type_badge}
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"**{truncate_text(q['question_content'], 500)}**")

    options = q.get('options', {})
    if isinstance(options, str):
        options = safe_json_loads(options)

    # 答题控件（复用公共渲染逻辑）
    user_answer = render_answer_controls(
        q_type, options,
        key_prefix=f"exam_q_{idx}",
        disabled=st.session_state.exam_answered,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if not st.session_state.exam_answered:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("✅ 提交答案", width="stretch"):
                if not user_answer:
                    st.warning("⚠️ 请先作答！")
                else:
                    time_spent = time.time() - st.session_state.exam_question_start_time
                    is_correct = check_answer(user_answer, q['correct_answer'], q_type)

                    db = get_db()
                    normalized_user = normalize_answer(user_answer, q_type)
                    db.insert_practice_record(
                        q['id'], normalized_user, int(is_correct), time_spent,
                        user_id=st.session_state.get('user_id', 0)
                    )

                    if is_correct:
                        st.success("🎉 回答正确！")
                        st.session_state.exam_score += 1
                    else:
                        st.error(f"❌ 回答错误！正确答案是：{q['correct_answer']}")

                    st.session_state.exam_answered = True
    else:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("➡️ 下一题", width="stretch"):
                st.session_state.exam_index += 1
                st.session_state.exam_answered = False
                st.session_state.exam_question_start_time = time.time()

                if st.session_state.exam_index >= len(questions):
                    _finish_exam()
                st.rerun()

    # 交卷按钮
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col3:
        if st.button("📋 交卷", width="stretch", type="secondary"):
            _finish_exam()
            st.rerun()


def _finish_exam():
    """结束考试，计算成绩。"""
    total_time = time.time() - st.session_state.exam_start_time
    st.session_state.exam_finished = True
    st.session_state.exam_final_score = st.session_state.exam_score
    st.session_state.exam_final_total = len(st.session_state.exam_questions)
    st.session_state.exam_final_time = total_time
    st.session_state.exam_questions = []


def _render_result():
    """渲染考试结果页面。"""
    score = st.session_state.get('exam_final_score', 0)
    total = st.session_state.get('exam_final_total', 0)
    total_time = st.session_state.get('exam_final_time', 0)

    st.balloons()

    accuracy = (score / total * 100) if total > 0 else 0
    minutes = total_time / 60

    from page_modules._common import is_dark_mode
    _dark = is_dark_mode()
    _bg = "linear-gradient(135deg, #1e293b, #0f3460)" if _dark else "linear-gradient(135deg, #dbeafe, #d1fae5)"
    _score_color = "#67e8f9" if _dark else "#0f766e"
    _text_color = "#e2e8f0" if _dark else "#475569"
    _sub_color = "#94a3b8" if _dark else "#718096"
    st.markdown(f"""
    <div style="text-align: center; padding: 2rem; background: {_bg};
                border-radius: 15px; margin-bottom: 2rem;">
        <h1 style="font-size: 3rem; margin: 0; color: {_score_color};">{score}/{total}</h1>
        <p style="font-size: 1.5rem; color: {_text_color}; margin: 0.5rem 0;">正确率：{accuracy:.1f}%</p>
        <p style="color: {_sub_color};">用时：{minutes:.1f} 分钟</p>
    </div>
    """, unsafe_allow_html=True)

    # 成绩评价
    if accuracy >= 90:
        st.success("🌟 优秀！你的掌握程度非常好！")
    elif accuracy >= 70:
        st.info("👍 良好！继续保持，针对错题进行复习。")
    elif accuracy >= 60:
        st.warning("💪 及格，但还有提升空间，建议多复习错题。")
    else:
        st.error("📚 不及格，建议系统复习后重新考试。")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🔁 再考一次", width="stretch"):
            st.session_state.exam_finished = False
            st.rerun()
    with col3:
        if st.button("🏠 返回设置", width="stretch"):
            st.session_state.exam_finished = False
            st.rerun()
