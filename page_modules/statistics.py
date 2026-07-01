"""📊 学习统计页面"""
import pandas as pd
import plotly.express as px
import streamlit as st
from page_modules._common import TYPE_NAMES, render_footer, get_db, status_card_html


def render():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("学习统计")

    db = get_db()
    _uid = st.session_state.get('user_id', 0)

    # 日期范围选择
    col_range1, col_range2 = st.columns(2)
    with col_range1:
        stats_days = st.selectbox(
            "统计时间范围", ["近7天", "近14天", "近30天", "近90天", "全部"],
            index=2, key="stats_days_select"
        )
    days_map = {"近7天": 7, "近14天": 14, "近30天": 30, "近90天": 90, "全部": 9999}
    _days = days_map[stats_days]
    days_clause = f"AND practice_date >= datetime('now','localtime','-{_days} days')" if _days < 9999 else ""

    # 统计
    row = db.execute(
        f"SELECT COUNT(*) AS total, COALESCE(SUM(is_correct), 0) AS correct "
        f"FROM practice_records WHERE user_id = ? {days_clause}",
        (_uid,)
    ).fetchone()
    stats = {"total": row["total"], "correct": row["correct"],
             "accuracy": round((row["correct"] / row["total"] * 100) if row["total"] > 0 else 0, 2)}

    # 每日统计（图表天数与范围一致）
    chart_days = min(_days, 30) if _days < 9999 else 30
    daily_stats = [dict(r) for r in db.execute(
        "SELECT DATE(practice_date) AS date, COUNT(*) AS total, SUM(is_correct) AS correct "
        "FROM practice_records WHERE user_id = ? AND practice_date >= datetime('now','localtime',?) "
        "GROUP BY DATE(practice_date) ORDER BY date",
        (_uid, f"-{chart_days} days")
    ).fetchall()]
    for d in daily_stats:
        d["accuracy"] = round((d["correct"] / d["total"] * 100) if d["total"] > 0 else 0, 2)

    # 各题型正确率
    type_rows = db.execute(
        f"SELECT q.question_type, COUNT(*) AS total, COALESCE(SUM(r.is_correct), 0) AS correct "
        f"FROM practice_records r JOIN questions q ON r.question_id = q.id "
        f"WHERE r.user_id = ? {days_clause} "
        f"GROUP BY q.question_type",
        (_uid,)
    ).fetchall()
    type_accuracy = []
    for r in type_rows:
        d = dict(r)
        d["accuracy"] = round((d["correct"] / d["total"] * 100) if d["total"] > 0 else 0, 2)
        type_accuracy.append(d)

    # 最近答题记录
    recent_records = [dict(r) for r in db.execute(
        "SELECT r.*, q.question_content, q.correct_answer, q.question_type "
        "FROM practice_records r JOIN questions q ON r.question_id = q.id "
        "WHERE r.user_id = ? "
        "ORDER BY r.practice_date DESC LIMIT 5",
        (_uid,)
    ).fetchall()]

    # 统计卡片
    st.markdown(f"### 📈 {stats_days}学习数据")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%);
                    padding: 2rem; border-radius: 15px; color: white; text-align: center;
                    box-shadow: 0 10px 30px rgba(14, 165, 233, 0.35);">
            <h3 style="margin: 0; font-size: 3rem;">{stats['total']}</h3>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">答题总次数</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    padding: 2rem; border-radius: 15px; color: white; text-align: center;
                    box-shadow: 0 10px 30px rgba(16, 185, 129, 0.35);">
            <h3 style="margin: 0; font-size: 3rem;">{stats['correct']}</h3>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">正确答题数</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0ea5e9 0%, #14b8a6 100%);
                    padding: 2rem; border-radius: 15px; color: white; text-align: center;
                    box-shadow: 0 10px 30px rgba(14, 165, 233, 0.35);">
            <h3 style="margin: 0; font-size: 3rem;">{stats['accuracy']}%</h3>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">正确率</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 每日学习趋势图
    st.markdown(f"### 📊 近{chart_days}天学习趋势")
    if daily_stats:
        df = pd.DataFrame(daily_stats)
        df['date'] = pd.to_datetime(df['date'])

        col1, col2 = st.columns(2)
        with col1:
            fig1 = px.bar(df, x='date', y='total',
                         title='每日答题数量',
                         labels={'date': '日期', 'total': '答题数'},
                         color_discrete_sequence=['#0ea5e9'])
            fig1.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(size=12))
            st.plotly_chart(fig1, width="stretch")
        with col2:
            fig2 = px.line(df, x='date', y='accuracy',
                          title='每日正确率趋势',
                          labels={'date': '日期', 'accuracy': '正确率(%)'},
                          markers=True, color_discrete_sequence=['#10b981'])
            fig2.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                              font=dict(size=12), yaxis_range=[0, 100])
            st.plotly_chart(fig2, width="stretch")
    else:
        st.info("📝 暂无学习数据，快去开始练习吧！")

    # 各题型正确率
    st.markdown("### 📊 各题型正确率")
    if type_accuracy:
        df_type = pd.DataFrame(type_accuracy)
        df_type['题型'] = df_type['question_type'].map(TYPE_NAMES).fillna(df_type['question_type'])
        fig3 = px.bar(df_type, x='题型', y='accuracy', title='各题型正确率',
                      labels={'题型': '题型', 'accuracy': '正确率(%)'},
                      color='题型', color_discrete_sequence=['#0ea5e9', '#10b981', '#8b5cf6', '#f59e0b', '#ec4899'])
        fig3.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                          font=dict(size=12), yaxis_range=[0, 100], showlegend=False)
        st.plotly_chart(fig3, width="stretch")
    else:
        st.info("📝 暂无各题型统计数据")

    # 最近答题记录
    st.markdown("### 📝 最近答题记录")
    if recent_records:
        for record in recent_records:
            status_icon = "✅" if record['is_correct'] else "❌"
            status_color = "#10b981" if record['is_correct'] else "#ef4444"
            r_type = record.get('question_type', 'single')
            type_label = TYPE_NAMES.get(r_type, r_type)
            lines = [
                f"{status_icon} [{type_label}] {record['question_content'][:50]}... <span style='float:right;opacity:0.6;'>{record['practice_date']}</span>",
                f"你的答案：{record['user_answer']} | 正确答案：{record['correct_answer']} | 用时：{record['time_spent']:.1f}秒",
            ]
            st.markdown(status_card_html(lines, status_color), unsafe_allow_html=True)
    else:
        st.info("📝 暂无答题记录")

    # 学习建议
    _render_suggestions(db, stats, type_accuracy)

    render_footer()
    st.markdown('</div>', unsafe_allow_html=True)


def _render_suggestions(db, stats, type_accuracy):
    """渲染学习建议区域。"""
    st.markdown("### 💡 学习建议")

    if stats['total'] == 0:
        st.info("📝 还没有答题记录，快去开始练习吧！")
        return

    suggestions = []

    if type_accuracy:
        weakest = min(type_accuracy, key=lambda x: x.get("accuracy", 100))
        if weakest.get("accuracy", 100) < 60:
            w_name = TYPE_NAMES.get(weakest["question_type"], weakest["question_type"])
            suggestions.append(f"🎯 **{w_name}**是你的薄弱环节（正确率仅{weakest['accuracy']}%），建议专项练习")

    _uid = st.session_state.get('user_id', 0)
    r7 = db.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(is_correct), 0) AS correct "
        "FROM practice_records WHERE user_id = ? AND practice_date >= datetime('now','localtime','-7 days')",
        (_uid,)
    ).fetchone()
    p7 = db.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(is_correct), 0) AS correct "
        "FROM practice_records WHERE user_id = ? AND practice_date >= datetime('now','localtime','-14 days') "
        "AND practice_date < datetime('now','localtime','-7 days')",
        (_uid,)
    ).fetchone()

    if r7['total'] > 0 and p7['total'] > 0:
        recent_acc = round(r7['correct'] / r7['total'] * 100, 2)
        prev_acc = round(p7['correct'] / p7['total'] * 100, 2)
        diff = recent_acc - prev_acc
        if diff > 5:
            suggestions.append(f"📈 最近一周正确率提升了{diff:.1f}%，继续保持！")
        elif diff < -5:
            suggestions.append(f"📉 最近一周正确率下降了{abs(diff):.1f}%，注意调整学习节奏")

    if stats['accuracy'] >= 90:
        suggestions.append("🌟 总体表现非常优秀！可以尝试挑战更高难度的题目")
    elif stats['accuracy'] >= 70:
        suggestions.append("👍 不错的正确率，建议针对错题进行重点复习")
    elif stats['accuracy'] >= 50:
        suggestions.append("💪 还需努力，建议使用错题重练模式加强薄弱环节")
    else:
        suggestions.append("📚 建议多花时间复习基础知识，从简单难度开始练习")

    wrong_count = db.execute(
        "SELECT COUNT(DISTINCT question_id) FROM practice_records WHERE user_id = ? AND is_correct = 0",
        (_uid,)
    ).fetchone()[0]
    if wrong_count > 0:
        suggestions.append(f"📖 你有 {wrong_count} 道错题待复习，建议定期回顾")

    for s in suggestions:
        if "薄弱" in s or "下降" in s:
            st.warning(s)
        elif "优秀" in s or "提升" in s:
            st.success(s)
        else:
            st.info(s)
