"""📅 间隔重复复习页面（艾宾浩斯遗忘曲线）"""
import time
import streamlit as st
from page_modules._common import (
    TYPE_NAMES, TYPE_ICONS, safe_json_loads, truncate_text,
    render_footer, get_db, error_card_html,
)

# 艾宾浩斯复习间隔（天数）
REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30]


def render():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("📅 间隔重复复习")

    from page_modules._common import is_dark_mode
    _dark = is_dark_mode()
    _bg = "linear-gradient(135deg, #422006, #713f12)" if _dark else "linear-gradient(135deg, #fef3c7, #fde68a)"
    _title_color = "#fcd34d" if _dark else "#92400e"
    _text_color = "#fde68a" if _dark else "#78350f"
    st.markdown(f"""
    <div style="background: {_bg};
                padding: 1.5rem; border-radius: 15px; margin-bottom: 2rem;">
        <h4 style="margin: 0 0 0.5rem 0; color: {_title_color};">🧠 艾宾浩斯遗忘曲线</h4>
        <p style="margin: 0; color: {_text_color}; font-size: 0.9rem;">
            根据遗忘曲线理论，学习后的第 1、2、4、7、15、30 天是最佳复习时间点。<br>
            系统会自动追踪你的答题记录，在合适的时间提醒你复习错题。
        </p>
    </div>
    """, unsafe_allow_html=True)

    db = get_db()

    # 获取所有有答题记录的题目及其最后答题时间
    rows = db.execute("""
        SELECT q.id, q.question_content, q.question_type, q.correct_answer,
               q.subject, q.difficulty,
               MAX(r.practice_date) AS last_practice,
               SUM(CASE WHEN r.is_correct = 0 THEN 1 ELSE 0 END) AS wrong_count,
               COUNT(r.record_id) AS total_count
        FROM questions q
        JOIN practice_records r ON q.id = r.question_id
        GROUP BY q.id
        ORDER BY last_practice DESC
    """).fetchall()

    if not rows:
        st.info("📝 暂无答题记录，开始练习后系统会自动生成复习计划。")
        render_footer()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # 计算每道题的复习状态
    from datetime import datetime
    now = datetime.now()
    due_today = []
    due_soon = []
    mastered = []
    no_wrong = []

    for row in rows:
        d = dict(row)
        last_str = d['last_practice']
        if not last_str:
            continue
        try:
            last_dt = datetime.strptime(last_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue

        days_since = (now - last_dt).days
        wrong = d['wrong_count'] or 0

        if wrong == 0:
            # 全对的题目，标记为已掌握
            no_wrong.append(d)
            continue

        # 根据错误次数和上次复习时间判断是否需要复习
        # 错误越多，复习间隔越短
        interval_idx = min(wrong - 1, len(REVIEW_INTERVALS) - 1)
        target_interval = REVIEW_INTERVALS[interval_idx]

        d['days_since'] = days_since
        d['target_interval'] = target_interval
        d['days_overdue'] = days_since - target_interval

        if days_since >= target_interval:
            due_today.append(d)
        elif days_since >= target_interval - 1:
            due_soon.append(d)
        else:
            mastered.append(d)

    # 按逾期天数排序
    due_today.sort(key=lambda x: -x['days_overdue'])

    # 统计卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔴 今日待复习", f"{len(due_today)} 题")
    with col2:
        st.metric("🟡 即将到期", f"{len(due_soon)} 题")
    with col3:
        st.metric("🟢 已掌握", f"{len(mastered)} 题")
    with col4:
        st.metric("✅ 全对题目", f"{len(no_wrong)} 题")

    st.markdown("---")

    # 今日待复习
    if due_today:
        st.markdown(f"### 🔴 今日待复习（{len(due_today)} 题）")

        # 筛选
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            subjects = list(set(d.get('subject', '') for d in due_today if d.get('subject')))
            subj_filter = st.selectbox("按学科筛选", ["全部"] + subjects, key="review_subj")
        with col_filter2:
            show_count = st.number_input(
                "显示数量", min_value=1, max_value=len(due_today),
                value=min(20, len(due_today)), step=1, key="review_count"
            )

        filtered = due_today
        if subj_filter != "全部":
            filtered = [d for d in filtered if d.get('subject') == subj_filter]
        filtered = filtered[:show_count]

        for i, d in enumerate(filtered, 1):
            q_type = d.get('question_type', 'single')
            type_icon = TYPE_ICONS.get(q_type, "📝")
            type_label = TYPE_NAMES.get(q_type, q_type)

            with st.expander(
                f"{type_icon} 第{i}题 [{type_label}] "
                f"{truncate_text(d['question_content'], 40)} "
                f"(错{d['wrong_count']}次, {d['days_since']}天未复习)"
            ):
                st.markdown(f"**{d['question_content']}**")
                st.markdown(error_card_html([
                    f"❌ 错误次数：{d['wrong_count']}次 | 📅 上次练习：{d['last_practice']} | ⏰ 逾期：{d['days_overdue']}天",
                ]), unsafe_allow_html=True)

        # 一键开始复习
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🎯 开始复习这些题目", width="stretch", type="primary"):
                from practice_session import PracticeSession
                question_ids = [d['id'] for d in filtered]
                session = PracticeSession()
                # 获取这些题目的完整数据（单次查询替代逐个查询）
                if question_ids:
                    placeholders = ','.join(['?'] * len(question_ids))
                    rows = session.db.execute(
                        f"SELECT * FROM questions WHERE id IN ({placeholders})",
                        question_ids
                    ).fetchall()
                    questions = [session._row_to_dict(r) for r in rows]
                else:
                    questions = []

                st.session_state.current_questions = questions
                st.session_state.current_index = 0
                st.session_state.score = 0
                st.session_state.answered = False
                st.session_state.start_time = time.time()
                st.session_state.question_start_time = time.time()
                st.session_state.multi_answers = []
                st.session_state.practice_finished = False
                st.session_state.page_switch = "📝 刷题练习"
                st.rerun()

    elif due_soon:
        st.info("✅ 今天没有需要复习的题目！明天有 {} 题到期。".format(len(due_soon)))
    else:
        st.success("🎉 太棒了！所有题目都在掌握中，没有需要复习的内容。")

    # 复习间隔说明
    with st.expander("📖 复习间隔说明"):
        st.markdown("""
        | 错误次数 | 复习间隔 | 说明 |
        |---------|---------|------|
        | 1 次 | 1 天后 | 第一次错，1天后复习 |
        | 2 次 | 2 天后 | 第二次错，2天后复习 |
        | 3 次 | 4 天后 | 第三次错，4天后复习 |
        | 4 次 | 7 天后 | 第四次错，一周后复习 |
        | 5 次 | 15 天后 | 第五次错，半个月后复习 |
        | 6+ 次 | 30 天后 | 多次错误，一个月后复习 |
        """)

    render_footer()
    st.markdown('</div>', unsafe_allow_html=True)
