"""📜 答题历史页面"""
from datetime import datetime
import streamlit as st
from page_modules._common import TYPE_NAMES, truncate_text, render_footer, get_db, status_card_html


def render():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("答题历史")

    # 筛选条件
    col1, col2, col3 = st.columns(3)

    with col1:
        days_filter = st.selectbox("时间范围", ["最近7天", "最近30天", "最近90天", "全部"], index=1)
        days_map = {"最近7天": 7, "最近30天": 30, "最近90天": 90, "全部": 9999}
        days = days_map[days_filter]

    with col2:
        result_filter = st.selectbox("答题结果", ["全部", "✅ 正确", "❌ 错误"])

    with col3:
        pass  # 占位，保持布局

    # 查询答题记录
    db = get_db()
    _uid = st.session_state.get('user_id', 0)
    base_sql = """
        SELECT r.*, q.question_content, q.correct_answer, q.question_type, q.subject
        FROM practice_records r
        JOIN questions q ON r.question_id = q.id
        WHERE r.user_id = ? AND r.practice_date >= datetime('now', 'localtime', ?)
    """
    params = [_uid, f"-{days} days"]

    if result_filter == "✅ 正确":
        base_sql += " AND r.is_correct = 1"
    elif result_filter == "❌ 错误":
        base_sql += " AND r.is_correct = 0"

    # 分页
    count_sql = base_sql.replace(
        "SELECT r.*, q.question_content, q.correct_answer, q.question_type, q.subject",
        "SELECT COUNT(*)"
    )
    total_count = db.execute(count_sql, params).fetchone()[0]
    PAGE_SIZE = 20
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    if 'hist_page' not in st.session_state:
        st.session_state.hist_page = 1

    col_pg1, col_pg2, col_pg3 = st.columns([1, 2, 1])
    with col_pg1:
        if st.button("⬅️ 上一页", disabled=(st.session_state.hist_page <= 1), key="hist_prev"):
            st.session_state.hist_page -= 1
            st.rerun()
    with col_pg2:
        page = st.number_input(
            f"页码（共 {total_pages} 页，{total_count} 条）",
            min_value=1, max_value=total_pages,
            value=st.session_state.hist_page, key="hist_page_input"
        )
        st.session_state.hist_page = page
    with col_pg3:
        if st.button("下一页 ➡️", disabled=(st.session_state.hist_page >= total_pages), key="hist_next"):
            st.session_state.hist_page += 1
            st.rerun()

    offset = (page - 1) * PAGE_SIZE
    sql = base_sql + " ORDER BY r.practice_date DESC LIMIT ? OFFSET ?"
    params.extend([PAGE_SIZE, offset])

    records = [dict(r) for r in db.execute(sql, params).fetchall()]

    # 统计信息（基于全部筛选结果）
    stats_sql = base_sql.replace(
        "SELECT r.*, q.question_content, q.correct_answer, q.question_type, q.subject",
        "SELECT COUNT(*), SUM(r.is_correct)"
    )
    stats_params = [_uid, f"-{days} days"]
    stats_row = db.execute(stats_sql, stats_params).fetchone()
    total_records = stats_row[0] if stats_row else 0
    total_correct = stats_row[1] if stats_row and stats_row[1] else 0
    accuracy = (total_correct / total_records * 100) if total_records > 0 else 0

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.metric("📝 总记录数", total_records)
    with col_s2:
        st.metric("✅ 全部正确数", total_correct)
    with col_s3:
        st.metric("🎯 全部正确率", f"{accuracy:.1f}%")

    st.markdown("---")

    if records:
        # 导出功能（使用 csv 模块确保格式正确）
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["序号", "时间", "题型", "题目", "用户答案", "正确答案", "是否正确", "用时(秒)"])
        for i, r in enumerate(records, 1):
            r_type = r.get('question_type', 'single')
            type_label = TYPE_NAMES.get(r_type, r_type)
            status = "正确" if r['is_correct'] else "错误"
            content = r['question_content'].replace('\n', ' ')[:50]
            writer.writerow([i, r['practice_date'], type_label, content,
                             r['user_answer'], r['correct_answer'], status,
                             f"{r['time_spent']:.1f}"])
        export_text = output.getvalue()
        # 添加 UTF-8 BOM 以便 Excel 正确识别中文编码
        export_bytes = export_text.encode('utf-8-sig')

        st.download_button(
            label="📥 导出答题记录",
            data=export_bytes,
            file_name=f"答题记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

        # 记录列表
        for i, r in enumerate(records, 1):
            status_icon = "✅" if r['is_correct'] else "❌"
            status_color = "#10b981" if r['is_correct'] else "#ef4444"
            r_type = r.get('question_type', 'single')
            type_label = TYPE_NAMES.get(r_type, r_type)

            lines = [
                f"{status_icon} [{type_label}] {truncate_text(r['question_content'], 50)} <span style='float:right;opacity:0.6;'>{r['practice_date']}</span>",
                f"你的答案：{r['user_answer']} | 正确答案：{r['correct_answer']} | 用时：{r['time_spent']:.1f}秒",
            ]
            st.markdown(status_card_html(lines, status_color), unsafe_allow_html=True)
    else:
        st.info("📝 暂无答题记录")

    render_footer()
    st.markdown('</div>', unsafe_allow_html=True)
