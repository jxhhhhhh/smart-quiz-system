"""📋 题目管理页面"""
import json
from datetime import datetime
import streamlit as st
from page_modules._common import (
    TYPE_NAMES, TYPE_ICONS, safe_json_loads, truncate_text,
    render_footer, get_db, get_subjects, get_chapters, info_card_html,
)


def _build_where_clause(subject_filter, q_type_val, search_text, fav_only, chapter_filter="全部章节"):
    """构建筛选 WHERE 子句和参数（避免 count 和查询逻辑重复）。"""
    where = "WHERE 1=1"
    params = []
    if subject_filter != "全部学科":
        where += " AND subject = ?"
        params.append(subject_filter)
    if q_type_val:
        where += " AND question_type = ?"
        params.append(q_type_val)
    if search_text:
        where += " AND question_content LIKE ?"
        params.append(f"%{search_text}%")
    if fav_only:
        where += " AND id IN (SELECT question_id FROM favorites)"
    if chapter_filter != "全部章节":
        where += " AND chapter = ?"
        params.append(chapter_filter)
    return where, params


def render():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("题目管理")

    # 筛选条件
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        subjects = get_subjects()
        subject_filter = st.selectbox("按学科筛选", ["全部学科"] + subjects)

    with col2:
        type_filter = st.selectbox(
            "按题型筛选",
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
        q_type_val = type_filter_map[type_filter]

    with col3:
        chapters = get_chapters()
        chapter_filter = st.selectbox("按章节筛选", ["全部章节"] + chapters)

    with col4:
        search_text = st.text_input("🔍 搜索题目内容", placeholder="输入关键词...")

    col_fav, _ = st.columns([1, 3])
    with col_fav:
        fav_only = st.checkbox("⭐ 仅显示收藏题目", key="fav_only_filter")

    # 查询题目（复用 WHERE 构建逻辑）
    db = get_db()
    where_clause, params = _build_where_clause(subject_filter, q_type_val, search_text, fav_only, chapter_filter)
    sql = f"SELECT * FROM questions {where_clause}"
    count_sql = f"SELECT COUNT(*) FROM questions {where_clause}"
    total_count = db.execute(count_sql, params).fetchone()[0]

    # 分页
    PAGE_SIZE = 20
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    if 'qm_page' not in st.session_state:
        st.session_state.qm_page = 1

    col_pg1, col_pg2, col_pg3 = st.columns([1, 2, 1])
    with col_pg1:
        if st.button("⬅️ 上一页", disabled=(st.session_state.qm_page <= 1), key="qm_prev"):
            st.session_state.qm_page -= 1
            st.rerun()
    with col_pg2:
        page = st.number_input(
            f"页码（共 {total_pages} 页，{total_count} 题）",
            min_value=1, max_value=total_pages,
            value=st.session_state.qm_page, key="qm_page_input"
        )
        st.session_state.qm_page = page
    with col_pg3:
        if st.button("下一页 ➡️", disabled=(st.session_state.qm_page >= total_pages), key="qm_next"):
            st.session_state.qm_page += 1
            st.rerun()

    offset = (page - 1) * PAGE_SIZE
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([PAGE_SIZE, offset])
    rows = db.execute(sql, params).fetchall()

    st.markdown(f"### 📋 第 {page}/{total_pages} 页，共 {total_count} 道题目")

    # 操作按钮区
    _render_action_buttons(db, rows)

    # 批量操作区
    with st.expander("🔧 批量操作"):
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            batch_diff = st.selectbox(
                "批量设置难度",
                ["不修改", "1 - 基础", "2 - 应用", "3 - 综合"],
                key="qm_batch_diff"
            )
            if batch_diff != "不修改" and st.button("⭐ 应用难度", key="qm_apply_diff"):
                diff_val = int(batch_diff[0])
                for row in rows:
                    db.execute("UPDATE questions SET difficulty = ? WHERE id = ?",
                               (diff_val, row['id']))
                db.commit()
                st.success(f"✅ 已更新 {len(rows)} 道题目难度")
                st.rerun()
        with col_b2:
            batch_subj = st.text_input("批量设置学科", key="qm_batch_subj",
                                       placeholder="输入学科名称")
            if batch_subj.strip() and st.button("🏷️ 应用学科", key="qm_apply_subj"):
                for row in rows:
                    db.execute("UPDATE questions SET subject = ? WHERE id = ?",
                               (batch_subj.strip(), row['id']))
                db.commit()
                st.success(f"✅ 已更新 {len(rows)} 道题目学科")
                st.rerun()

    st.markdown("---")

    if rows:
        for row in rows:
            _render_question_item(db, row)
    else:
        st.info("📝 没有找到匹配的题目")

    render_footer()
    st.markdown('</div>', unsafe_allow_html=True)


def _render_action_buttons(db, rows):
    """渲染操作按钮区域。"""
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)

    with col_btn1:
        if rows and st.button("📥 导出TXT", width="stretch"):
            export_text = ""
            for row in rows:
                q = dict(row)
                opts = safe_json_loads(q.get("options", "{}"))
                q_type = q.get("question_type", "single")
                type_label = TYPE_NAMES.get(q_type, q_type)
                export_text += f"{q['id']}.({type_label}) {q['question_content']}\n"
                if opts:
                    for k, v in opts.items():
                        export_text += f"{k}. {v}\n"
                export_text += f"答案：{q['correct_answer']}\n\n"
            st.download_button(
                label="⬇️ 下载TXT",
                data=export_text,
                file_name=f"题库导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )

    with col_btn2:
        if st.button("📦 导出JSON", width="stretch"):
            import json as _json
            all_rows = db.execute("SELECT * FROM questions ORDER BY id").fetchall()
            export_data = []
            for row in all_rows:
                q = dict(row)
                q["options"] = safe_json_loads(q.get("options", "{}"))
                export_data.append(q)
            json_str = _json.dumps(export_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="⬇️ 下载JSON",
                data=json_str.encode('utf-8-sig'),
                file_name=f"题库导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

    with col_btn3:
        if st.button("📦 导出Anki", width="stretch"):
            import csv as _csv
            import io as _io
            all_rows = db.execute("SELECT * FROM questions ORDER BY id").fetchall()
            output = _io.StringIO()
            writer = _csv.writer(output, delimiter='\t')
            for row in all_rows:
                q = dict(row)
                opts = safe_json_loads(q.get("options", "{}"))
                opts_text = "<br>".join(f"{k}. {v}" for k, v in opts.items())
                front = f"{q['question_content']}<br><br>{opts_text}" if opts_text else q['question_content']
                back = q['correct_answer']
                writer.writerow([front, back])
            anki_data = output.getvalue().encode('utf-8-sig')
            st.download_button(
                label="⬇️ 下载Anki TSV",
                data=anki_data,
                file_name=f"anki_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tsv",
                mime="text/tab-separated-values"
            )

    with col_btn4:
        if st.button("🗑️ 删除当前页", type="secondary", width="stretch"):
            st.session_state.confirm_batch_delete = True

    # ── 数据备份/恢复 ──
    with st.expander("💾 数据备份与恢复"):
        col_backup1, col_backup2 = st.columns(2)
        with col_backup1:
            # 备份：导出完整 SQLite 数据库
            import shutil
            from config import DB_PATH
            backup_data = None
            try:
                with open(DB_PATH, "rb") as f:
                    backup_data = f.read()
            except Exception:
                pass
            if backup_data:
                st.download_button(
                    label="⬇️ 下载数据库备份",
                    data=backup_data,
                    file_name=f"question_bank_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                    mime="application/octet-stream",
                    key="backup_db_btn"
                )
        with col_backup2:
            uploaded_backup = st.file_uploader(
                "📤 恢复数据库备份", type=["db"], key="restore_db_upload"
            )
            if uploaded_backup:
                if st.button("⚠️ 确认恢复（将覆盖当前数据）", type="primary"):
                    try:
                        with open(DB_PATH, "wb") as f:
                            f.write(uploaded_backup.read())
                        st.success("✅ 数据库已恢复，请刷新页面。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 恢复失败：{e}")

    # 批量删除确认
    if st.session_state.get('confirm_batch_delete', False):
        st.warning(f"⚠️ 确定要删除当前页的 {len(rows)} 道题目吗？此操作不可撤销！")
        col_c1, col_c2, _ = st.columns([1, 1, 2])
        with col_c1:
            if st.button("✅ 确认删除", type="primary"):
                ids = [row['id'] for row in rows]
                placeholders = ','.join('?' * len(ids))
                db.execute(f"DELETE FROM practice_records WHERE question_id IN ({placeholders})", ids)
                db.execute(f"DELETE FROM favorites WHERE question_id IN ({placeholders})", ids)
                db.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", ids)
                db.commit()
                st.success(f"✅ 已删除 {len(rows)} 道题目")
                st.session_state.confirm_batch_delete = False
                st.rerun()
        with col_c2:
            if st.button("❌ 取消"):
                st.session_state.confirm_batch_delete = False
                st.rerun()


def _render_question_item(db, row):
    """渲染单个题目项。"""
    q = dict(row)
    q_type = q.get("question_type", "single")
    type_label = TYPE_NAMES.get(q_type, q_type)
    type_icon = TYPE_ICONS.get(q_type, "📝")
    opts = safe_json_loads(q.get("options", "{}"))

    is_fav = db.is_favorite(q['id'])
    fav_icon = "⭐" if is_fav else "☆"

    with st.expander(f"{fav_icon} {type_icon} [{type_label}] {truncate_text(q['question_content'], 50)} (ID:{q['id']})"):
        st.markdown(f"**{truncate_text(q['question_content'], 300)}**")

        if opts:
            for k, v in opts.items():
                st.markdown(f"- {k}. {v}")

        col_a, col_b, col_c = st.columns([3, 1, 1])
        with col_a:
            st.markdown(info_card_html([
                f"✅ 正确答案：{q['correct_answer']}",
                f"📁 学科：{q.get('subject', '') or '未分类'} | ⭐ 难度：{q.get('difficulty', 1)}",
            ]), unsafe_allow_html=True)
        with col_b:
            if st.button("🗑️ 删除", key=f"del_{q['id']}", type="secondary"):
                db.delete_question(q['id'])
                st.success(f"已删除题目 ID:{q['id']}")
                st.rerun()
        with col_c:
            fav_btn_label = "⭐ 取消收藏" if is_fav else "☆ 收藏"
            if st.button(fav_btn_label, key=f"fav_{q['id']}"):
                db.toggle_favorite(q['id'])
                st.rerun()

        # 编辑功能
        with st.expander("✏️ 编辑题目"):
            new_content = st.text_area("题目内容", value=q['question_content'], key=f"edit_content_{q['id']}")
            new_answer = st.text_input("正确答案", value=q['correct_answer'], key=f"edit_answer_{q['id']}")
            new_difficulty = st.select_slider(
                "难度等级", options=[1, 2, 3], value=q.get('difficulty', 1),
                format_func=lambda x: {1: "⭐ 简单", 2: "⭐⭐ 中等", 3: "⭐⭐⭐ 困难"}[x],
                key=f"edit_diff_{q['id']}"
            )
            new_subject = st.text_input("学科分类", value=q.get('subject', ''), key=f"edit_subject_{q['id']}")

            # 选项编辑（选择题/判断题才显示）
            if q_type in ("single", "multi", "judge"):
                st.markdown("**选项编辑**")
                if opts:
                    new_opts = {}
                    for k, v in opts.items():
                        new_val = st.text_input(f"选项 {k}", value=v, key=f"edit_opt_{q['id']}_{k}")
                        new_opts[k] = new_val
                else:
                    st.caption("暂无选项，可手动添加")
                    new_opts = None

            if st.button("💾 保存修改", key=f"save_{q['id']}"):
                # 构建更新语句
                update_fields = "question_content=?, correct_answer=?, difficulty=?, subject=?"
                update_params = [new_content, new_answer, new_difficulty, new_subject]

                # 如果有选项更新
                if q_type in ("single", "multi", "judge") and opts and new_opts:
                    update_fields += ", options=?"
                    import json
                    update_params.append(json.dumps(new_opts, ensure_ascii=False))

                update_params.append(q['id'])
                db.execute(
                    f"UPDATE questions SET {update_fields} WHERE id=?",
                    update_params
                )
                db.commit()
                st.success("✅ 保存成功！")
                st.rerun()
