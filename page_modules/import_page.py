"""📥 导入题目页面"""
import os
import re
import streamlit as st
from question_importer import QuestionBankImporter, QualityChecker, generate_fingerprint
from page_modules._common import TYPE_NAMES, TYPE_ICONS, render_footer


def render():
    st.markdown('<div class="fade-in">', unsafe_allow_html=True)
    st.title("导入题目")

    from page_modules._common import is_dark_mode
    _dark = is_dark_mode()
    _bg = "linear-gradient(135deg, #1e293b 0%, #0f3460 100%)" if _dark else "linear-gradient(135deg, #dbeafe 0%, #d1fae5 100%)"
    _title_color = "#67e8f9" if _dark else "#0f766e"
    _text_color = "#e2e8f0" if _dark else "#374151"
    _sub_color = "#94a3b8" if _dark else "#475569"
    _accent_color = "#34d399" if _dark else "#059669"
    _code_bg = "#1e293b" if _dark else "white"
    _hr_color = "#334155" if _dark else "#e5e7eb"
    st.markdown(f"""
    <div style="background: {_bg};
                padding: 1.5rem; border-radius: 15px; margin-bottom: 2rem;">
        <h4 style="margin: 0 0 1rem 0; color: {_title_color};">📋 支持的格式</h4>
        <div style="display: flex; gap: 2rem; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 200px;">
                <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: {_text_color};">📄 文件导入</p>
                <p style="margin: 0; color: {_sub_color}; font-size: 0.9rem;">PDF 文件、Word 文档 (.docx)</p>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: {_text_color};">📝 文本粘贴</p>
                <p style="margin: 0; color: {_sub_color}; font-size: 0.9rem;">学习通复制文本等</p>
            </div>
        </div>
        <div style="background: {_code_bg}; padding: 1rem; border-radius: 10px; margin-top: 1rem; font-family: monospace; font-size: 0.85rem;">
            <p style="margin: 0.3rem 0; color: {_text_color};">1. Python是一种解释型语言。</p>
            <p style="margin: 0.3rem 0; color: {_sub_color};">A. 正确 &nbsp;&nbsp; B. 错误</p>
            <p style="margin: 0.3rem 0; color: {_accent_color}; font-weight: bold;">答案：A</p>
            <hr style="margin: 0.5rem 0; border: none; border-top: 1px dashed {_hr_color};">
            <p style="margin: 0.3rem 0; color: {_text_color};">2. 下列属于Python内置数据类型的是（多选）</p>
            <p style="margin: 0.3rem 0; color: {_sub_color};">A. list &nbsp; B. dict &nbsp; C. array &nbsp; D. tuple</p>
            <p style="margin: 0.3rem 0; color: {_accent_color}; font-weight: bold;">答案：ABD</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 初始化 session state
    if 'parsed_questions' not in st.session_state:
        st.session_state.parsed_questions = None
        st.session_state.parse_source = ""
        st.session_state.import_report = None

    # ─── 学科分类（必填） ───
    from page_modules._common import get_subjects
    existing_subjects = get_subjects()
    st.markdown("### 🏷️ 学科分类（必填）")
    col_subj1, col_subj2 = st.columns([2, 1])
    with col_subj1:
        if existing_subjects:
            subject_choice = st.selectbox(
                "选择已有学科或自定义输入",
                ["-- 请选择学科 --"] + existing_subjects + ["自定义..."],
                key="subject_select"
            )
        else:
            subject_choice = "自定义..."
    with col_subj2:
        if subject_choice == "自定义...":
            custom_subject = st.text_input("输入学科名称", placeholder="如：Python、数学...",
                                           key="custom_subject_input")
            import_subject = custom_subject.strip() if custom_subject else ""
        elif subject_choice == "-- 请选择学科 --":
            import_subject = ""
        else:
            import_subject = subject_choice
            st.success(f"📁 学科：{import_subject}")

    st.markdown("---")

    # ─── 解析方式选择 ───
    st.markdown("### 🔧 解析方式")
    parse_mode = st.radio(
        "选择解析方式",
        [
            "🤖 AI 智能解析（推荐，适合各种格式）",
            "⚡ 双层解析（正则+AI，最佳质量）",
            "📐 正则解析（快速，仅适合标准格式）",
        ],
        label_visibility="collapsed",
        key="parse_mode_select"
    )
    is_pure_ai = "AI" in parse_mode and "双层" not in parse_mode
    is_dual_mode = "双层" in parse_mode

    # API 配置（AI 模式需要）
    api_key = ""
    base_url = ""
    model = ""
    if is_pure_ai:
        from config import AI_API_KEY
        col_api1, col_api2 = st.columns(2)
        with col_api1:
            api_key = st.text_input("🔑 API Key", type="password",
                                    value=AI_API_KEY,
                                    placeholder="在 .env 或环境变量中配置 DEEPSEEK_API_KEY",
                                    key="ai_api_key_input")
        with col_api2:
            api_preset = st.selectbox("预设模型",
                                      ["DeepSeek", "Mimo", "OpenAI", "Custom"],
                                      key="ai_preset_select")
        if api_preset == "DeepSeek":
            base_url = "https://api.deepseek.com"
            model = "deepseek-chat"
        elif api_preset == "Mimo":
            from config import MIMO_API_KEY, MIMO_BASE_URL
            base_url = MIMO_BASE_URL
            if not api_key and MIMO_API_KEY:
                api_key = MIMO_API_KEY
            mimo_models = ["mimo-v2.5-pro", "mimo-v2.5", "mimo-v2-pro", "mimo-v2-omni"]
            model = st.selectbox("Mimo 模型", mimo_models, key="mimo_model_select")
        elif api_preset == "OpenAI":
            base_url = "https://api.openai.com/v1"
            model = "gpt-4o-mini"
        else:
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                base_url = st.text_input("Base URL", value="https://api.deepseek.com",
                                         key="ai_base_url_input")
            with col_c2:
                model = st.text_input("模型名称", value="deepseek-chat",
                                      key="ai_model_input")

    st.markdown("---")

    # ─── 文件上传（支持批量） ───
    st.markdown("### 📄 文件导入（支持多文件批量上传）")
    uploaded_files = st.file_uploader(
        "上传 PDF、DOCX 或图片文件（可同时选择多个，图片需使用 AI 模式）",
        type=["pdf", "docx", "png", "jpg", "jpeg", "bmp"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.caption(f"已选择 {len(uploaded_files)} 个文件：{', '.join(f.name for f in uploaded_files)}")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔍 解析文件预览", width="stretch", key="parse_file"):
                if not import_subject:
                    st.error("⚠️ 请先填写学科分类！")
                elif (is_dual_mode or is_pure_ai) and not api_key:
                    st.error("⚠️ 使用 AI 功能需要填写 API Key！")
                else:
                    all_questions = []
                    parse_errors = []
                    progress = st.progress(0)
                    status = st.empty()

                    for fi, uploaded_file in enumerate(uploaded_files):
                        status.text(f"⏳ 正在解析 [{fi+1}/{len(uploaded_files)}] {uploaded_file.name}...")
                        progress.progress((fi) / len(uploaded_files))

                        temp_path = f"_temp_upload_{uploaded_file.name}"
                        try:
                            with open(temp_path, "wb") as f:
                                f.write(uploaded_file.read())
                            _do_parse_file(temp_path, uploaded_file.name,
                                           import_subject, is_dual_mode, is_pure_ai,
                                           api_key, base_url, model)
                            # _do_parse_file 会设置 st.session_state.parsed_questions
                            if st.session_state.parsed_questions:
                                all_questions.extend(st.session_state.parsed_questions)
                        except Exception as e:
                            parse_errors.append(f"{uploaded_file.name}: {e}")
                        finally:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)

                    progress.progress(1.0)
                    status.text(f"✅ 解析完成！共识别 {len(all_questions)} 道题目")

                    st.session_state.parsed_questions = all_questions
                    st.session_state.parse_source = f"批量导入({len(uploaded_files)}个文件)"

                    if parse_errors:
                        for err in parse_errors:
                            st.warning(f"⚠️ {err}")

    st.markdown("---")

    # ─── 文本粘贴 ───
    st.markdown("### 📝 文本粘贴导入")
    text_input = st.text_area("在此粘贴题目内容：", height=300,
                              placeholder="请按照上述格式粘贴题目...")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔍 解析预览", width="stretch", key="parse_text"):
            if not text_input:
                st.warning("⚠️ 请先粘贴题目内容。")
            elif not import_subject:
                st.error("⚠️ 请先填写学科分类！")
            elif (is_dual_mode or is_pure_ai) and not api_key:
                st.error("⚠️ 使用 AI 功能需要填写 API Key！")
            else:
                spinner_text = "⏳ 正在智能解析..." if is_dual_mode else (
                    "⏳ AI 正在解析，请稍候..." if is_pure_ai else "⏳ 正在解析...")
                with st.spinner(spinner_text):
                    try:
                        _do_parse_text(text_input, import_subject,
                                       is_dual_mode, is_pure_ai,
                                       api_key, base_url, model)
                    except Exception as e:
                        st.error(f"❌ 解析失败：{e}")
                        st.session_state.parsed_questions = None

    # ─── 预览区域（支持内联编辑 + 质量检查） ───
    if st.session_state.parsed_questions is not None:
        questions = st.session_state.parsed_questions
        st.markdown("---")
        st.markdown(f"### 👀 解析预览（共 {len(questions)} 道题）")

        if not questions:
            st.warning("⚠️ 未能识别出任何题目，请检查格式或尝试其他解析模式。")
        else:
            # 质量检查
            checker = QualityChecker()
            issues = checker.check_all(questions)
            summary = checker.get_summary()

            # 质量概览
            if summary["total_issues"] > 0:
                col_q1, col_q2, col_q3 = st.columns(3)
                with col_q1:
                    st.metric("❌ 错误", summary["errors"])
                with col_q2:
                    st.metric("⚠️ 警告", summary["warnings"])
                with col_q3:
                    st.metric("ℹ️ 提示", summary["infos"])

                # 一键修复
                auto_fixable = [i for i in issues if i[1] in ("warning", "info")]
                if auto_fixable:
                    if st.button(f"🔧 一键修复 {len(auto_fixable)} 个问题"):
                        fixed = checker.auto_fix(questions)
                        st.session_state.parsed_questions = questions
                        st.success(f"✅ 已自动修复 {fixed} 个问题")
                        st.rerun()

                # 问题详情
                with st.expander("📋 质量检查详情"):
                    for idx, severity, issue_type, msg in issues:
                        icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[severity]
                        q = questions[idx] if idx < len(questions) else {}
                        q_type = q.get("q_type", "unknown")
                        type_label = TYPE_NAMES.get(q_type, q_type)
                        content = q.get("content", "（无内容）")[:60]
                        answer = q.get("answer", "（无答案）")
                        opts = q.get("options")
                        opts_str = ", ".join(f"{k}.{v}" for k, v in opts.items()) if opts else "无选项"

                        st.markdown(f"""
                        <div style="padding:0.6rem 0.8rem; margin-bottom:0.5rem; border-radius:8px;
                                    border-left:3px solid {'#ef4444' if severity=='error' else '#f59e0b' if severity=='warning' else '#0ea5e9'};
                                    background:rgba(0,0,0,0.02);">
                            <div style="font-weight:600; margin-bottom:0.3rem;">{icon} 第{idx+1}题 【{type_label}】 {msg}</div>
                            <div style="font-size:13px; opacity:0.8; line-height:1.5;">
                                <b>题干：</b>{content}<br>
                                <b>选项：</b>{opts_str}<br>
                                <b>答案：</b>{answer}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            # 题型统计
            type_counts = {}
            for q in questions:
                t = q.get("q_type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1
            cols = st.columns(len(type_counts))
            for i, (t, cnt) in enumerate(type_counts.items()):
                with cols[i]:
                    st.metric(f"{TYPE_ICONS.get(t, '📝')} {TYPE_NAMES.get(t, t)}", f"{cnt} 题")

            # AI 推断的学科
            ai_subjects = set(q.get("subject", "") for q in questions if q.get("subject"))
            if ai_subjects and not import_subject:
                st.info(f"🤖 AI 推断的学科：{', '.join(ai_subjects)}")

            # 题目列表（可编辑）
            TYPE_OPTIONS = ["single", "multi", "judge", "fill", "short"]
            TYPE_LABEL_MAP = {v: f"{TYPE_ICONS.get(v, '📝')} {TYPE_NAMES.get(v, v)}" for v in TYPE_OPTIONS}

            # 预览分页：默认显示前20题
            PREVIEW_PAGE_SIZE = 20
            total_preview = len(questions)
            if total_preview > PREVIEW_PAGE_SIZE:
                if 'preview_page' not in st.session_state:
                    st.session_state.preview_page = 1
                total_preview_pages = (total_preview + PREVIEW_PAGE_SIZE - 1) // PREVIEW_PAGE_SIZE
                col_pp1, col_pp2, col_pp3 = st.columns([1, 2, 1])
                with col_pp2:
                    preview_page = st.number_input(
                        f"预览页码（共 {total_preview_pages} 页）",
                        min_value=1, max_value=total_preview_pages,
                        value=st.session_state.preview_page, key="preview_page_input"
                    )
                    st.session_state.preview_page = preview_page
                preview_start = (preview_page - 1) * PREVIEW_PAGE_SIZE
                preview_end = min(preview_start + PREVIEW_PAGE_SIZE, total_preview)
            else:
                preview_start = 0
                preview_end = total_preview

            for i in range(preview_start, preview_end):
                q = questions[i]
                q_type = q.get("q_type", "single")
                type_label = TYPE_NAMES.get(q_type, q_type)
                type_icon = TYPE_ICONS.get(q_type, "📝")

                with st.expander(f"{type_icon} 第{i+1}题 [{type_label}] {q['content'][:40]}..."):
                    new_type = st.selectbox("题型", TYPE_OPTIONS,
                                            index=TYPE_OPTIONS.index(q_type) if q_type in TYPE_OPTIONS else 0,
                                            format_func=lambda x: TYPE_LABEL_MAP[x],
                                            key=f"edit_type_{i}")
                    new_content = st.text_area("题目内容", value=q.get("content", ""),
                                               key=f"edit_content_{i}", height=80)

                    opts = q.get("options") or {}
                    if new_type in ("single", "multi", "judge"):
                        st.markdown("**选项**（每行格式：`A.选项内容`）")
                        opts_text = "\n".join(f"{k}.{v}" for k, v in opts.items()) if opts else ""
                        new_opts_text = st.text_area("选项", value=opts_text,
                                                     key=f"edit_opts_{i}", height=80,
                                                     placeholder="A.选项1\nB.选项2\nC.选项3\nD.选项4")
                        new_opts = {}
                        for line in new_opts_text.strip().split("\n"):
                            line = line.strip()
                            if not line:
                                continue
                            m = re.match(r'^([A-Fa-f])[.．、。）)]\s*(.+)$', line)
                            if m:
                                new_opts[m.group(1).upper()] = m.group(2).strip()
                        if not new_opts:
                            new_opts = None
                    else:
                        new_opts = None

                    new_answer = st.text_input("正确答案", value=q.get("answer", ""),
                                               key=f"edit_answer_{i}")
                    new_difficulty = st.select_slider(
                        "难度等级", options=[1, 2, 3], value=q.get("difficulty", 1),
                        format_func=lambda x: {1: "⭐ 基础", 2: "⭐⭐ 应用", 3: "⭐⭐⭐ 综合"}[x],
                        key=f"edit_diff_{i}")

                    questions[i] = {
                        "q_type": new_type,
                        "content": new_content.strip(),
                        "options": new_opts,
                        "answer": new_answer.strip(),
                        "subject": q.get("subject", ""),
                        "chapter": q.get("chapter", ""),
                        "difficulty": new_difficulty,
                        "tags": q.get("tags", ""),
                    }

            # 批量操作
            st.markdown("---")
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                if len(questions) > 1:
                    del_indices = st.multiselect("🗑️ 选择要删除的题目", range(len(questions)),
                                                  format_func=lambda x: f"第{x+1}题: {questions[x]['content'][:30]}...",
                                                  key="batch_delete_select")
                    if del_indices and st.button("🗑️ 删除选中", key="batch_delete_btn"):
                        for idx in sorted(del_indices, reverse=True):
                            questions.pop(idx)
                        st.session_state.parsed_questions = questions
                        st.rerun()
            with col_b2:
                batch_diff = st.selectbox("⭐ 批量设置难度",
                                          ["不修改", "1 - 基础", "2 - 应用", "3 - 综合"],
                                          key="batch_diff_select")
                if batch_diff != "不修改" and st.button("⭐ 应用", key="batch_diff_btn"):
                    for q in questions:
                        q["difficulty"] = int(batch_diff[0])
                    st.rerun()
            with col_b3:
                batch_subj = st.text_input("🏷️ 批量设置学科", key="batch_subj_input",
                                           placeholder="输入学科名称")
                if batch_subj.strip() and st.button("🏷️ 应用", key="batch_subj_btn"):
                    for q in questions:
                        q["subject"] = batch_subj.strip()
                    st.rerun()

            # 确认导入（复用 QuestionBankImporter 的事务保护逻辑）
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("✅ 确认导入", width="stretch", key="confirm_import"):
                    final_questions = st.session_state.parsed_questions

                    with st.spinner("⏳ 正在导入..."):
                        importer = QuestionBankImporter()
                        count, errors, report = importer._insert_questions(
                            final_questions, source=st.session_state.parse_source
                        )
                        # 记录导入历史
                        if count > 0:
                            from page_modules._common import get_db
                            db = get_db()
                            db.log_import(
                                source=st.session_state.parse_source,
                                count=count,
                                subject=import_subject,
                                parse_mode="dual" if is_dual_mode else ("AI" if is_pure_ai else "regex"),
                                user_id=st.session_state.get('user_id', 0)
                            )

                    # 导入报告
                    st.markdown("---")
                    st.markdown("### 📊 导入报告")
                    skipped_dup = report.get('skipped_dup', 0)
                    skipped_quality = report.get('skipped_quality', 0)
                    failed = report.get('failed', 0)
                    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                    with col_r1:
                        st.metric("📝 总计", report.get('total', 0))
                    with col_r2:
                        st.metric("✅ 成功", count)
                    with col_r3:
                        st.metric("⏭️ 重复跳过", skipped_dup)
                    with col_r4:
                        st.metric("❌ 失败", skipped_quality + failed)

                    if count > 0:
                        st.success(f"✅ 成功导入 {count} 道题目！")
                        st.balloons()
                    if skipped_dup > 0:
                        st.info(f"⏭️ 跳过 {skipped_dup} 道重复题目")
                    if errors:
                        with st.expander(f"⚠️ {len(errors)} 条详情"):
                            for e in errors:
                                st.text(e)

                    st.session_state.parsed_questions = None

    # ─── 导入历史 ───
    st.markdown("---")
    with st.expander("📜 导入历史（最近 10 次）"):
        from page_modules._common import get_db
        db = get_db()
        history = db.get_import_history(limit=10, user_id=st.session_state.get('user_id', 0))
        if history:
            for h in history:
                mode_icon = "⚡" if h.get('parse_mode') == 'dual' else (
                    "🤖" if h.get('parse_mode') == 'AI' else "📐")
                _card_bg = "#1e293b" if _dark else "white"
                _time_color = "#94a3b8" if _dark else "#718096"
                _success_color = "#34d399" if _dark else "#059669"
                _text_color2 = "#e2e8f0" if _dark else "#1e293b"
                st.markdown(f"""
                <div style="background: {_card_bg}; padding: 0.8rem; border-radius: 8px;
                            margin-bottom: 0.5rem; border-left: 4px solid #0ea5e9;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: {_text_color2};">{mode_icon} <b>{h.get('source', '未知')}</b> — {h.get('subject', '未分类')}</span>
                        <span style="color: {_time_color}; font-size: 0.85rem;">{h.get('imported_at', '')}</span>
                    </div>
                    <div style="color: {_success_color}; margin-top: 0.3rem;">✅ 导入 {h.get('count', 0)} 道题目</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("暂无导入记录")

    render_footer()
    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
#  解析调度函数
# ═══════════════════════════════════════════════════════════

def _do_parse_text(text, subject, is_dual, is_pure_ai, api_key, base_url, model):
    """文本粘贴的解析调度。AI 失败时自动回退到正则。"""
    if is_pure_ai:
        try:
            from ai_parser import ai_parse_questions
            questions = ai_parse_questions(text, api_key, base_url, model)
        except Exception as e:
            st.warning(f"⚠️ AI 解析失败（{e}），自动切换为正则解析")
            from parser import parse_text
            questions = parse_text(text)
        for q in questions:
            if subject:
                q["subject"] = subject
    elif is_dual:
        from parser import parse_text_with_confidence
        parsed = parse_text_with_confidence(text)
        if not parsed:
            st.session_state.parsed_questions = []
            return
        _ai_fallback(parsed, api_key, base_url, model)
        for q in parsed:
            q.pop("raw_block", None)
            if subject:
                q["subject"] = subject
            elif not q.get("subject"):
                q["subject"] = ""
        questions = parsed
    else:
        from parser import parse_text
        questions = parse_text(text)
        for q in questions:
            q["subject"] = subject

    st.session_state.parsed_questions = questions
    st.session_state.parse_source = "手动粘贴"


def _do_parse_file(temp_path, filename, subject, is_dual, is_pure_ai,
                   api_key, base_url, model):
    """文件导入的解析调度。"""
    # 图片文件：使用多模态 LLM 直接识别
    img_exts = (".png", ".jpg", ".jpeg", ".bmp")
    if filename.lower().endswith(img_exts):
        with open(temp_path, "rb") as f:
            image_bytes = f.read()
        try:
            from ai_parser import ai_parse_image
            questions = ai_parse_image(image_bytes, api_key, base_url, model)
        except Exception as e:
            st.error(f"⚠️ 图片识别失败（{e}）")
            questions = []
        for q in questions:
            if subject:
                q["subject"] = subject
        st.session_state.parsed_questions = questions
        return

    if filename.lower().endswith(".pdf"):
        raw_text = _extract_text_from_file(temp_path, "pdf")
    else:
        raw_text = _extract_text_from_file(temp_path, "docx")

    if is_pure_ai:
        try:
            from ai_parser import ai_parse_questions
            questions = ai_parse_questions(raw_text, api_key, base_url, model)
        except Exception as e:
            st.warning(f"⚠️ AI 解析失败（{e}），自动切换为正则解析")
            from parser import parse_text
            questions = parse_text(raw_text)
        for q in questions:
            if subject:
                q["subject"] = subject
    elif is_dual:
        from parser import parse_text_with_confidence
        parsed = parse_text_with_confidence(raw_text)
        if not parsed:
            st.session_state.parsed_questions = []
            return
        try:
            _ai_fallback(parsed, api_key, base_url, model)
        except Exception as e:
            st.warning(f"⚠️ AI 修复失败（{e}），使用正则解析结果")
        for q in parsed:
            q.pop("raw_block", None)
            if subject:
                q["subject"] = subject
            elif not q.get("subject"):
                q["subject"] = ""
        questions = parsed
    else:
        from parser import parse_text
        questions = parse_text(raw_text)
        for q in questions:
            q["subject"] = subject

    st.session_state.parsed_questions = questions
    st.session_state.parse_source = filename


def _ai_fallback(parsed, api_key, base_url, model):
    """对低置信度题目执行 AI 修复（带 Streamlit 进度条）。"""
    from question_importer import ai_fallback_core

    progress = st.progress(0)
    status = st.empty()

    def on_progress(done, total, message):
        status.text(f"🤖 {message}")
        if total > 0:
            progress.progress(done / total)

    ai_fallback_core(parsed, api_key, base_url, model, on_progress=on_progress)
    progress.progress(1.0)



def _extract_text_from_file(filepath, file_type):
    """从文件提取纯文本（统一入口，复用 QuestionBankImporter 的提取方法）。"""
    from question_importer import QuestionBankImporter
    importer = QuestionBankImporter()
    try:
        if file_type == "pdf":
            return importer._extract_pdf(filepath)
        else:
            return importer._extract_docx(filepath)
    finally:
        importer.close()
