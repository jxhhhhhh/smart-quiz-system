"""❌ 错题回顾页面"""
import json
import time
import streamlit as st
from practice_session import PracticeSession
from page_modules._common import (
    TYPE_NAMES, TYPE_ICONS, safe_json_loads, truncate_text,
    render_footer, get_db, info_card_html, status_card_html,
)


def render():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("错题回顾")

    db = get_db()
    _uid = st.session_state.get('user_id', 0)

    total_wrong = db.execute(
        "SELECT COUNT(DISTINCT question_id) FROM practice_records WHERE user_id = ? AND is_correct = 0",
        (_uid,)
    ).fetchone()[0]

    show_count = st.slider("显示错题数量", min_value=5, max_value=max(5, total_wrong),
                           value=min(20, total_wrong), step=5) if total_wrong > 0 else 20

    wrong_rows = db.execute(
        """
        SELECT q.*, r.wrong_count, r.last_wrong_date
        FROM questions q
        JOIN (
            SELECT question_id, SUM(1 - is_correct) AS wrong_count,
                   MAX(practice_date) AS last_wrong_date
            FROM practice_records
            WHERE user_id = ?
            GROUP BY question_id
            HAVING wrong_count > 0
        ) r ON q.id = r.question_id
        ORDER BY r.wrong_count DESC
        LIMIT ?
        """,
        (_uid, show_count)
    ).fetchall()
    wrong_questions = []
    for row in wrong_rows:
        d = dict(row)
        try:
            d["options"] = json.loads(d["options"])
        except (json.JSONDecodeError, TypeError):
            d["options"] = {}
        wrong_questions.append(d)

    if wrong_questions:
        st.markdown(f"### 📚 共有 {total_wrong} 道错题")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            practice_count = st.number_input(
                "练习题目数量", min_value=1, max_value=total_wrong,
                value=min(20, total_wrong), step=1, key="wrong_practice_count"
            )
        with col3:
            if st.button("🎯 开始错题练习", width="stretch"):
                session = PracticeSession()
                st.session_state.current_questions = session.get_questions("wrong", practice_count)
                st.session_state.current_index = 0
                st.session_state.score = 0
                st.session_state.answered = False
                st.session_state.start_time = time.time()
                st.session_state.question_start_time = time.time()
                st.session_state.multi_answers = []
                st.session_state.practice_finished = False
                st.session_state.page_switch = "📝 刷题练习"
                st.rerun()

        for i, q in enumerate(wrong_questions, 1):
            options = q.get('options', {})
            if isinstance(options, str):
                options = safe_json_loads(options)

            r_type = q.get('question_type', 'single')
            type_label = TYPE_NAMES.get(r_type, r_type)
            type_icon = TYPE_ICONS.get(r_type, "📝")

            with st.expander(f"❌ 错题 {i}: {truncate_text(q['question_content'], 50)} ({type_icon}{type_label} · 错{q['wrong_count']}次)"):
                st.markdown(f"**{truncate_text(q['question_content'], 300)}**")

                if options:
                    for key, value in options.items():
                        st.markdown(f"- {key}. {value}")

                st.markdown(info_card_html([f"✅ 正确答案：{q['correct_answer']}"]),
                            unsafe_allow_html=True)

                st.markdown(status_card_html(
                    [f"📊 错误次数：{q['wrong_count']}次 | 📅 最近错误：{q['last_wrong_date']}"],
                    border_color="#6b7280"), unsafe_allow_html=True)
    else:
        from page_modules._common import is_dark_mode
        _dark = is_dark_mode()
        _sub_color = "#94a3b8" if _dark else "#718096"
        st.markdown(f"""
        <div style="text-align: center; padding: 3rem;">
            <h2 style="color: #28a745;">🎉 太棒了！</h2>
            <p style="color: {_sub_color}; font-size: 1.1rem;">你还没有错题，继续保持！</p>
        </div>
        """, unsafe_allow_html=True)

    render_footer()
    st.markdown('</div>', unsafe_allow_html=True)
