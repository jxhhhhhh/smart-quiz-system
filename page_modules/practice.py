"""📝 刷题练习页面"""
import time
import streamlit as st
from practice_session import PracticeSession
from parser import check_answer, normalize_answer
from page_modules._common import (
    TYPE_NAMES, TYPE_ICONS, safe_json_loads, truncate_text,
    render_footer, get_db, render_answer_controls,
)


def render():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("刷题练习")

    # 练习模式选择
    st.markdown("### 🎮 选择练习模式")
    mode = st.selectbox(
        "选择练习模式",
        ["🎲 随机模式", "❌ 错题重练", "⭐ 难度专项"],
        label_visibility="collapsed"
    )

    mode_descriptions = {
        "🎲 随机模式": "从题库中随机抽取题目，适合日常练习和综合复习",
        "❌ 错题重练": "优先展示历史错题，针对薄弱知识点进行强化训练",
        "⭐ 难度专项": "按难度等级筛选题目，进行专项突破训练"
    }
    st.info(f"💡 {mode_descriptions[mode]}")
    mode_map = {"🎲 随机模式": "random", "❌ 错题重练": "wrong", "⭐ 难度专项": "difficulty"}

    # 设置区域
    st.markdown("### ⚙️ 练习设置")
    col1, col2 = st.columns(2)

    with col1:
        if mode == "⭐ 难度专项":
            difficulty = st.select_slider(
                "难度等级",
                options=[1, 2, 3],
                value=2,
                format_func=lambda x: {1: "⭐ 简单", 2: "⭐⭐ 中等", 3: "⭐⭐⭐ 困难"}[x]
            )
        else:
            difficulty = None

    with col2:
        count = st.number_input("题目数量", min_value=1, max_value=100, value=5, step=1)

    col3, col4 = st.columns(2)

    with col3:
        q_type_filter = st.selectbox(
            "题型筛选",
            ["全部题型", "🔘 单选题", "☑️ 多选题", "⚖️ 判断题", "✏️ 填空题", "📝 简答题"],
        )
        type_filter_map = {
            "全部题型": None,
            "🔘 单选题": "single",
            "☑️ 多选题": "multi",
            "⚖️ 判断题": "judge",
            "✏️ 填空题": "fill",
            "📝 简答题": "short",
        }
        q_type = type_filter_map[q_type_filter]

    with col4:
        from page_modules._common import get_subjects
        subjects = get_subjects()
        subject_filter = st.selectbox(
            "学科筛选",
            ["全部学科"] + subjects,
        )
        subject_val = None if subject_filter == "全部学科" else subject_filter

    st.markdown("<br>", unsafe_allow_html=True)

    # Session state 初始化
    if 'current_questions' not in st.session_state:
        st.session_state.current_questions = []
        st.session_state.current_index = 0
        st.session_state.score = 0
        st.session_state.answered = False
        st.session_state.start_time = 0
        st.session_state.question_start_time = 0
        st.session_state.time_spent = 0
        st.session_state.multi_answers = []
        st.session_state.practice_finished = False

    # 检查是否有未完成的练习进度
    db = get_db()
    saved = db.load_practice_session(user_id=st.session_state.get('user_id', 0))
    if saved and not st.session_state.current_questions and not st.session_state.get('practice_finished', False):
        st.info(f"💡 发现未完成的练习（{saved['mode']}模式，进度 {saved['current_index']+1}/{len(saved['questions'])}，得分 {saved['score']}）")
        col_resume1, col_resume2, _ = st.columns([1, 1, 2])
        with col_resume1:
            if st.button("▶️ 继续上次练习", width="stretch"):
                st.session_state.current_questions = saved["questions"]
                st.session_state.current_index = saved["current_index"]
                st.session_state.score = saved["score"]
                st.session_state.answered = False
                st.session_state.start_time = time.time()
                st.session_state.question_start_time = time.time()
                st.session_state.multi_answers = []
                st.session_state.practice_finished = False
                st.session_state.last_practice_settings = saved.get("settings", {})
                st.rerun()
        with col_resume2:
            if st.button("🗑️ 丢弃进度", width="stretch"):
                db.clear_practice_session(user_id=st.session_state.get('user_id', 0))
                st.rerun()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🎯 开始练习", width="stretch"):
            st.session_state.last_practice_settings = {
                "mode": mode_map[mode], "count": count,
                "difficulty": difficulty, "q_type": q_type,
                "subject": subject_val,
            }
            session = PracticeSession()
            st.session_state.current_questions = session.get_questions(
                mode_map[mode], count, difficulty, q_type, subject_val
            )
            st.session_state.current_index = 0
            st.session_state.score = 0
            st.session_state.answered = False
            st.session_state.start_time = time.time()
            st.session_state.question_start_time = time.time()
            st.session_state.multi_answers = []
            # 清除旧的保存进度
            db.clear_practice_session(user_id=st.session_state.get('user_id', 0))

    # 题目展示
    if st.session_state.current_questions:
        _render_question()
    elif st.session_state.get('practice_finished', False):
        # 练习已完成，显示"再来一组"按钮
        _render_practice_finished()

    render_footer()
    st.markdown('</div>', unsafe_allow_html=True)


def _render_question():
    """渲染当前题目及答题交互。"""
    q = st.session_state.current_questions[st.session_state.current_index]
    q_type = q.get("question_type", "single")

    # 计算当前用时
    if not st.session_state.answered:
        current_time = time.time() - st.session_state.question_start_time
    else:
        current_time = st.session_state.time_spent

    # 进度条和统计信息
    progress = (st.session_state.current_index + 1) / len(st.session_state.current_questions)
    st.progress(progress)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📝 题目进度", f"{st.session_state.current_index + 1}/{len(st.session_state.current_questions)}")
    with col2:
        st.metric("🎯 当前得分", st.session_state.score)
    with col3:
        st.metric("⏱️ 本题用时", f"{current_time:.1f}秒")
    with col4:
        total_time = time.time() - st.session_state.start_time
        st.metric("⏰ 总用时", f"{total_time:.1f}秒")

    st.markdown("<br>", unsafe_allow_html=True)

    # 题目卡片
    type_badge = TYPE_NAMES.get(q_type, q_type)
    type_icon = TYPE_ICONS.get(q_type, "📝")
    st.markdown(f"""
    <div class="question-card">
        <div style="margin-bottom: 1rem;">
            <span style="background: linear-gradient(90deg, #0ea5e9, #10b981);
                       color: white; padding: 0.3rem 1rem; border-radius: 20px; font-size: 0.85rem;">
                第 {st.session_state.current_index + 1} 题
            </span>
            <span style="background: #8b5cf6;
                       color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem; margin-left: 0.5rem;">
                {type_icon} {type_badge}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"**{truncate_text(q['question_content'], 500)}**")

    # 收藏按钮
    db = get_db()
    q_id = q.get('id')
    _uid = st.session_state.get('user_id', 0)
    if q_id:
        is_fav = db.is_favorite(q_id, user_id=_uid)
        fav_label = "⭐ 已收藏" if is_fav else "☆ 收藏"
        if st.button(fav_label, key=f"fav_{st.session_state.current_index}"):
            db.toggle_favorite(q_id, user_id=_uid)
            st.rerun()

    options = q.get('options', {})
    if isinstance(options, str):
        options = safe_json_loads(options)

    # 根据题型渲染不同的输入控件
    user_answer = render_answer_controls(
        q_type, options,
        key_prefix=f"q_{st.session_state.current_index}",
        disabled=st.session_state.answered,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if not st.session_state.answered:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("✅ 提交答案", width="stretch"):
                if not user_answer:
                    st.warning("⚠️ 请先作答！")
                else:
                    st.session_state.time_spent = time.time() - st.session_state.question_start_time

                    # 使用统一的答案判断逻辑
                    is_correct = check_answer(
                        user_answer, q['correct_answer'], q_type
                    )

                    db = get_db()
                    normalized_user = normalize_answer(user_answer, q_type)
                    db.insert_practice_record(
                        q['id'], normalized_user, int(is_correct),
                        st.session_state.time_spent,
                        user_id=st.session_state.get('user_id', 0)
                    )

                    if is_correct:
                        st.success(f"🎉 回答正确！用时：{st.session_state.time_spent:.1f}秒")
                        st.session_state.score += 1
                    else:
                        st.error(f"❌ 回答错误！正确答案是：{q['correct_answer']} | 用时：{st.session_state.time_spent:.1f}秒")

                    st.session_state.answered = True

                    # 保存练习进度
                    db.save_practice_session(
                        st.session_state.current_questions,
                        st.session_state.current_index,
                        st.session_state.score,
                        mode=st.session_state.get('last_practice_settings', {}).get('mode', 'random'),
                        settings=st.session_state.get('last_practice_settings', {}),
                        user_id=st.session_state.get('user_id', 0)
                    )
    else:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("⬅️ 上一题", disabled=(st.session_state.current_index <= 0),
                         width="stretch"):
                st.session_state.current_index -= 1
                st.session_state.answered = False
                st.session_state.question_start_time = time.time()
                st.rerun()
        with col2:
            if st.button("➡️ 下一题", width="stretch"):
                st.session_state.current_index += 1
                st.session_state.answered = False
                st.session_state.question_start_time = time.time()

                if st.session_state.current_index >= len(st.session_state.current_questions):
                    total_time = time.time() - st.session_state.start_time
                    st.session_state.practice_finished = True
                    st.session_state.final_score = st.session_state.score
                    st.session_state.final_total = len(st.session_state.current_questions)
                    st.session_state.final_time = total_time
                    st.session_state.current_questions = []
                    # 练习完成，清除保存的进度
                    get_db().clear_practice_session(user_id=st.session_state.get('user_id', 0))
                    st.rerun()

    # 中途退出按钮
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col3:
        if st.button("🚪 退出练习", width="stretch"):
            st.session_state.current_questions = []
            st.session_state.practice_finished = False
            get_db().clear_practice_session(user_id=st.session_state.get('user_id', 0))
            st.rerun()


def _render_practice_finished():
    """渲染练习完成后的结果页面。"""
    score = st.session_state.get('final_score', 0)
    total = st.session_state.get('final_total', 0)
    total_time = st.session_state.get('final_time', 0)

    st.balloons()
    st.success(f"🎊 练习完成！最终得分：{score}/{total} | 总用时：{total_time:.1f}秒")

    if total > 0:
        accuracy = score / total * 100
        if accuracy >= 90:
            st.info("🌟 太棒了！你的正确率超过90%！")
        elif accuracy >= 70:
            st.info("👍 不错！继续保持！")
        elif accuracy >= 50:
            st.info("💪 还需努力，加油！")
        else:
            st.info("📚 建议多复习错题，巩固知识点！")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🔁 再来一组", width="stretch"):
            settings = st.session_state.get('last_practice_settings')
            if settings:
                session = PracticeSession()
                st.session_state.current_questions = session.get_questions(
                    settings["mode"], settings["count"],
                    settings["difficulty"], settings["q_type"],
                    settings.get("subject")
                )
                st.session_state.current_index = 0
                st.session_state.score = 0
                st.session_state.answered = False
                st.session_state.start_time = time.time()
                st.session_state.question_start_time = time.time()
                st.session_state.multi_answers = []
                st.session_state.practice_finished = False
                st.rerun()
    with col3:
        if st.button("🏠 返回设置", width="stretch"):
            st.session_state.current_questions = []
            st.session_state.practice_finished = False
            st.rerun()
