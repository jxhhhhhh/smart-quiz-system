# 智能刷题系统 — 功能实现清单

## 一、功能实现总览

| 功能模块 | 实现文件 | 依托技术 | 状态 |
|---------|---------|---------|------|
| 数据库管理 | `database.py` | SQLite3（6张表）、单例模式、threading.Lock、线程安全 | ✅ 已完成 |
| 题目解析（正则） | `parser.py` | 正则表达式（re模块，20+预编译模式）、pdfplumber、python-docx | ✅ 已完成 |
| 题目解析（AI） | `ai_parser.py` | OpenAI SDK、DeepSeek API、文本解析+图片OCR | ✅ 已完成 |
| 题目导入 | `question_importer.py` | 双引擎（正则+AI）、去重检测、质量校验 | ✅ 已完成 |
| 刷题练习 | `practice_session.py` | 3种模式（随机/错题/难度）、进度持久化 | ✅ 已完成 |
| 模拟考试 | `mock_exam.py` | 限时考试、自动交卷、超时强制提交 | ✅ 已完成 |
| 间隔重复 | `spaced_repetition.py` | 艾宾浩斯遗忘曲线算法 | ✅ 已完成 |
| 学习统计 | `statistics.py` | Plotly图表、pandas数据分析 | ✅ 已完成 |
| 错题回顾 | `wrong_review.py` | 错题列表、一键练习、错题分析 | ✅ 已完成 |
| 题目管理 | `question_manage.py` | 分页浏览、JSON导出、批量操作 | ✅ 已完成 |
| 答题历史 | `history.py` | CSV导出（BOM编码）、分页浏览、筛选统计 | ✅ 已完成 |
| 仪表盘 | `dashboard.py` | 核心指标卡片、快速入口、数据概览 | ✅ 已完成 |
| Web界面 | `web_interface.py` + `page_modules/` | Streamlit、路由分发、用户认证 | ✅ 已完成 |
| 主题样式 | `styles.py` | 深色/浅色主题、响应式布局、CSS注入 | ✅ 已完成 |
| 命令行界面 | `main.py` | Python 内置 input/print | ✅ 已完成 |
| 单元测试 | `test_system.py` | unittest 模块、44个测试用例 | ✅ 已完成 |

---

## 二、各功能详细实现清单

### 2.1 数据库管理 (`database.py`)

| 功能点 | 实现方式 | 说明 |
|--------|---------|------|
| 连接管理 | `sqlite3.connect()` | 单例模式，相同路径只创建一次连接 |
| 线程安全 | `threading.Lock()` | execute/commit 方法加锁 |
| 外键约束 | `PRAGMA foreign_keys = ON` | SQLite 默认不启用，需手动开启 |
| 表结构创建 | `CREATE TABLE IF NOT EXISTS` | 6张表：questions、practice_records、favorites、import_history、users、exam_records |
| Schema 迁移 | `_add_column_if_missing()` | 自动添加缺失字段，兼容旧数据库 |
| 索引优化 | `CREATE INDEX IF NOT EXISTS` | 多个索引覆盖常用查询 |
| 级联删除 | `DELETE FROM` | 删除题目时同步删除关联答题记录 |

### 2.2 题目解析 — 正则模式 (`parser.py`)

| 功能点 | 实现方式 | 说明 |
|--------|---------|------|
| 全角→半角 | `str.maketrans()` + `translate()` | 模块级转换表，只构建一次 |
| 括号标准化 | `str.replace()` | `（）`→`()`、`【】`→`[]` |
| 控制字符清理 | `re.sub()` | 去除零宽字符、控制字符 |
| 正则预编译 | `re.compile()` | 20+预编译模式，模块级常量，避免重复编译 |
| 题号识别 | 正则 `QUESTION_START` | 支持 `1.`、`1、`、`第1题`、`(1)` 等格式 |
| 题目分割 | `split_into_blocks()` | 按题号分割，支持无题号题目（双空行分割） |
| 乱序选项合并 | `orphan_options` 逻辑 | 选项在题号前时自动合并到下一题 |
| 同行多选项 | `_extract_options_from_line()` | `A.xx B.xx C.xx D.xx` 自动拆分 |
| 代码行保护 | `_is_code_line()` | 跳过 import/def/class 等代码行 |
| 答案提取 | 多级正则匹配 | `我的答案`→`正确答案`→`答案`→`答`→括号答案 |
| 题型识别 | `detect_type()` | 标签优先→答案格式→题目特征，三级推断 |
| 答案标准化 | `normalize_answer()` | 判断统一符号、多选排序去重、填空忽略大小写 |
| 答案判断 | `check_answer()` | 支持括号忽略、包含匹配、多答案子集匹配、Levenshtein模糊匹配 |
| PDF 解析 | `pdfplumber` | 提取每页文本后走统一解析流程 |
| DOCX 解析 | `python-docx` | 提取段落后走统一解析流程 |

### 2.3 题目解析 — AI 模式 (`ai_parser.py`)

| 功能点 | 实现方式 | 说明 |
|--------|---------|------|
| API 调用 | `openai.OpenAI` 客户端 | 支持自定义 base_url，兼容 DeepSeek/OpenAI/Qwen |
| Prompt 设计 | System Prompt + User Prompt | 要求返回严格 JSON 数组 |
| 长文本处理 | 截断至 15000 字符 | 避免超出 token 限制 |
| JSON 提取 | 正则 `re.search(r'\[.*\]', ...)` | 兼容 markdown 代码块包裹 |
| 结果校验 | 类型/内容/答案验证 | 过滤无效题目 |
| 错误处理 | try/except + 详细错误信息 | API 失败时给出明确提示 |
| 图片OCR识别 | 图片转base64 + 多模态API | 支持截图/拍照导入，OCR提取文字后走AI解析 |

### 2.4 题目导入 (`question_importer.py`)

| 功能点 | 实现方式 | 说明 |
|--------|---------|------|
| 文本导入 | `import_from_text()` | 调用 parser.parse_text() |
| 文件导入 | `import_from_file()` | 根据扩展名选择 parse_pdf/parse_docx |
| 双引擎支持 | 正则/AI模式切换 | 正则快速解析或AI智能解析可选 |
| 去重检测 | `SELECT ... WHERE content=? AND answer=?` | 按内容+答案查重 |
| 质量校验 | 内容长度、选项完整性、答案有效性 | 过滤低质量题目 |
| 学科设置 | 导入时传入 subject 参数 | 由 import_page.py 提供 |
| 错误收集 | `errors` 列表 | 单题失败不影响其他题目 |

### 2.5 刷题练习 (`practice_session.py`)

| 功能点 | 实现方式 | 说明 |
|--------|---------|------|
| 随机模式 | `ORDER BY RANDOM() LIMIT ?` | SQLite 随机排序 |
| 错题模式 | JOIN 子查询统计 wrong_count | 按错误次数降序 |
| 难度模式 | `WHERE difficulty = ?` | 按难度筛选 |
| 题型筛选 | `AND question_type = ?` | 可选参数 |
| 判断题默认选项 | `_row_to_dict()` 自动补充 | `{"A":"正确","B":"错误"}` |
| 答案校验 | 调用 `parser.check_answer()` | 统一判断逻辑 |
| 答题记录 | `INSERT INTO practice_records` | 记录答案、对错、用时 |
| 统计查询 | 多种 SQL 聚合 | 总计/每日/按题型/错题列表 |
| 进度持久化 | `st.session_state` | 刷新页面不丢失练习进度 |

### 2.6 模拟考试 (`mock_exam.py`)

| 功能点 | 实现方式 | 说明 |
|--------|---------|------|
| 考试模式 | 限时+题目数量可配置 | 模拟真实考试环境 |
| 超时强制提交 | 定时检测+自动交卷 | 时间到自动提交并显示成绩 |
| 成绩统计 | SQL聚合查询 | 总分、正确率、用时统计 |

### 2.7 间隔重复 (`spaced_repetition.py`)

| 功能点 | 实现方式 | 说明 |
|--------|---------|------|
| 艾宾浩斯算法 | 遗忘曲线间隔计算 | 根据记忆强度安排复习时间 |
| 复习计划 | 动态计算下次复习时间 | 自动调整间隔周期 |
| 记忆强度更新 | 根据答题结果调整 | 答对延长间隔，答错缩短间隔 |

### 2.8 Web 界面 (`web_interface.py` + `page_modules/`)

| 功能点 | 实现文件 | 实现方式 | 说明 |
|--------|---------|---------|------|
| 路由分发 | `web_interface.py` | `st.radio` + `PAGE_RENDERERS` 字典 | 多页面导航 |
| 程序化跳转 | `web_interface.py` | `st.session_state.page_switch` | 支持代码触发页面切换 |
| 用户认证 | `web_interface.py` | users表+登录注册 | 多用户登录支持 |
| 主题切换 | `styles.py` | CSS 注入 + `st.session_state.theme_mode` | 深色/浅色一键切换 |
| 数据库缓存 | `_common.py` | `@st.cache_resource` | 避免重复创建连接 |
| 统计缓存 | `_common.py` | `@st.cache_data(ttl=5)` | 5 秒内不重复查询 |

### 2.9 各页面功能

#### 仪表盘 (`dashboard.py`)

| 功能点 | 实现方式 |
|--------|---------|
| 核心指标卡片 | `st.metric()` × 4 |
| 题型分布 | 动态 `st.columns()` + `st.metric()` |
| 快速开始入口 | `st.button()` + `st.session_state.page_switch` |

#### 导入题目 (`import_page.py`)

| 功能点 | 实现方式 | 说明 |
|--------|---------|------|
| 学科必填 | `st.selectbox()` + `st.text_input()` | 未填写时禁用解析 |
| 解析模式切换 | `st.radio()` | 正则/AI 双模式 |
| AI 配置 | `st.text_input()` + `st.selectbox()` | API Key、预设模型、自定义 |
| 文件上传 | `st.file_uploader()` | PDF/DOCX/图片 |
| 文本粘贴 | `st.text_area()` | 多行文本输入 |
| 解析预览 | `st.expander()` 列表 | 展示每道题详情 |
| AI结果内联编辑 | 编辑按钮+表单 | 预览页可修正AI识别错误（题型、内容、选项、答案） |
| 批量学科设置 | 批量修改功能 | 已导入题目可批量归类 |
| 确认导入 | `st.button()` + `QuestionBankImporter` | 二次确认后入库 |

#### 刷题练习 (`practice.py`)

| 功能点 | 实现方式 | 说明 |
|--------|---------|------|
| 模式选择 | `st.selectbox()` | 随机/错题/难度 |
| 难度滑块 | `st.select_slider()` | 1-3 级 |
| 题目数量 | `st.number_input()` | 1-100 |
| 题型筛选 | `st.selectbox()` | 全部/单选/多选/判断/填空/简答 |
| 进度条 | `st.progress()` | 实时更新 |
| 计时显示 | `st.metric()` | 本题用时 + 总用时 |
| 单选/判断 | `st.radio()` | 提交后 disabled |
| 多选 | `st.checkbox()` × N | 提交后 disabled |
| 填空/简答 | `st.text_input()` / `st.text_area()` | 提交后 disabled |
| 提交答案 | `st.button()` + `check_answer()` | 即时反馈对错 |
| 下一题 | `st.button()` | 更新 index |
| 中途退出 | `st.button()` | 清空状态回到设置页 |
| 练习完成 | `_render_practice_finished()` | 显示成绩+评价+再来一组/返回设置 |
| 再来一组 | `st.button()` | 使用上次设置重新出题 |

#### 学习统计 (`statistics.py`)

| 功能点 | 实现方式 |
|--------|---------|
| 30天数据卡片 | SQL 聚合 + HTML 渐变卡片 |
| 每日趋势图 | `px.bar()` + `px.line()` |
| 题型正确率 | `px.bar()` |
| 最近记录 | SQL 查询 + HTML 卡片 |
| 学习建议 | 规则引擎（弱项/趋势/总体/错题） |

#### 错题回顾 (`wrong_review.py`)

| 功能点 | 实现方式 |
|--------|---------|
| 错题列表 | SQL JOIN 查询 + `st.expander()` |
| 显示数量 | `st.slider()` |
| 自定义练习数量 | `st.number_input()` |
| 一键练习 | `st.button()` + 跳转到练习页 |

#### 题目管理 (`question_manage.py`)

| 功能点 | 实现方式 |
|--------|---------|
| 多维筛选 | `st.selectbox()` × 2 + `st.text_input()` |
| 题目列表 | `st.expander()` 列表 + 分页浏览 |
| 编辑（含选项） | `st.text_area()` + `st.text_input()` + `st.select_slider()` |
| 单题删除 | `st.button()` + `db.delete_question()` |
| 批量删除 | `st.button()` + 二次确认 + SQL 批量删除 |
| 导出 TXT | `st.download_button()` |
| 导出 JSON | `st.download_button()` | 支持JSON格式导出，便于数据迁移 |

#### 答题历史 (`history.py`)

| 功能点 | 实现方式 |
|--------|---------|
| 时间筛选 | `st.selectbox()` |
| 结果筛选 | `st.selectbox()` |
| 分页浏览 | 分页组件 | 支持翻页浏览大量记录 |
| 统计概览 | `st.metric()` × 3 |
| 记录列表 | SQL 查询 + HTML 卡片 |
| 导出 CSV | `st.download_button()` | 带BOM编码，Excel直接打开不乱码 |

#### 题目收藏

| 功能点 | 实现方式 |
|--------|---------|
| 收藏/取消收藏 | `st.button()` + favorites表 |
| 收藏列表 | SQL查询 + `st.expander()` |

#### 导入历史

| 功能点 | 实现方式 |
|--------|---------|
| 导入记录 | import_history表 | 记录每次导入的时间、数量、来源 |
| 历史查询 | SQL查询 + 列表展示 |

---

## 三、可优化功能清单

### 3.1 高优先级 — 已全部完成

| 优化项 | 状态 | 实现说明 |
|--------|------|---------|
| 填空题模糊匹配（Levenshtein） | ✅ 已完成 | 引入编辑距离算法，容忍拼写错误，如 `pirnt`→`print` |
| AI解析结果内联编辑 | ✅ 已完成 | import_page.py 预览页添加编辑按钮，可修正题型、内容、选项、答案 |
| 批量设置学科 | ✅ 已完成 | import_page.py 支持批量修改学科功能 |

### 3.2 中优先级 — 已全部完成

| 优化项 | 状态 | 实现说明 |
|--------|------|---------|
| 练习进度持久化 | ✅ 已完成 | 使用 `st.session_state` 持久化，刷新不丢进度 |
| 题目收藏 | ✅ 已完成 | 新增 favorites 表 + 收藏按钮 |
| 导入历史记录 | ✅ 已完成 | import_history 表记录每次导入的时间、数量、来源 |

### 3.3 低优先级 — 已全部完成

| 优化项 | 状态 | 实现说明 |
|--------|------|---------|
| 多用户登录 | ✅ 已完成 | 新增 users 表 + 登录注册认证 |
| 模拟考试 | ✅ 已完成 | mock_exam.py 实现限时考试+自动交卷+成绩统计 |
| 间隔重复 | ✅ 已完成 | spaced_repetition.py 实现艾宾浩斯算法安排复习 |
| 移动端适配 | ✅ 已完成 | styles.py 响应式CSS布局，手机体验优化 |
| JSON导出 | ✅ 已完成 | question_manage.py 支持导出整个题库为JSON格式 |

### 3.4 新增已完成功能

| 优化项 | 状态 | 实现说明 |
|--------|------|---------|
| OCR图片识别导入 | ✅ 已完成 | ai_parser.py 支持图片base64+多模态API，截图/拍照直接导入 |
| 正则预编译优化 | ✅ 已完成 | parser.py 20+正则模式全部预编译为模块级常量 |
| CSV导出BOM编码 | ✅ 已完成 | history.py 导出CSV带BOM，Excel直接打开不乱码 |
| 题目管理分页 | ✅ 已完成 | question_manage.py 支持分页浏览大量题目 |
| 答题历史分页 | ✅ 已完成 | history.py 支持分页浏览历史记录 |

---

## 四、导入题库功能优化方向

### 4.1 已实现的优化

| 优化项 | 说明 |
|--------|------|
| AI 智能解析 | 接入 DeepSeek API，格式无关的智能识别 |
| 学科必填 | 导入前必须选择学科，确保数据完整性 |
| 双模式切换 | 正则（快速）/ AI（准确）可选 |
| 去重检测 | 按内容+答案查重，避免重复导入 |
| 预览确认 | 导入前展示解析结果，用户确认后入库 |
| AI结果内联编辑 | 预览页可修正AI识别错误 |
| OCR图片识别 | 支持截图/拍照导入 |
| 批量学科设置 | 已导入题目可批量归类 |
| 导入历史记录 | 可追溯每次导入记录 |

### 4.2 可进一步优化的方向

| 方向 | 具体方案 | 难度 | 价值 |
|------|---------|------|------|
| **智能学科识别** | AI 解析时自动推断学科（如"Python基础"、"数据结构"） | 低 | 中 |
| **难度自动评估** | AI 根据题目内容自动评估难度等级（1-3） | 低 | 中 |
| **知识点标签生成** | AI 自动为每道题生成知识点标签（如"列表操作"、"函数定义"） | 低 | 中 |
| **批量文件导入** | 支持同时上传多个文件，批量解析导入 | 中 | 中 |
| **导入模板下载** | 提供标准格式模板，用户按模板整理后导入 | 低 | 中 |
| **增量更新** | 已有题目更新内容而非跳过，支持"覆盖导入"模式 | 中 | 低 |
| **导入进度条** | 大批量导入时显示进度（已导入/总数） | 低 | 低 |
| **导入结果报告** | 导入完成后生成详细报告（成功/跳过/失败数量及原因） | 低 | 低 |
| **题库合并** | 支持从另一个数据库文件导入题目 | 中 | 低 |
| **在线题库对接** | 对接公开题库 API，直接搜索导入 | 高 | 中 |

### 4.3 优化优先级建议

**短期（1-2天可完成）**：
1. 智能学科识别 — 减少用户手动输入
2. 难度自动评估 — 减少用户手动设置
3. 导入进度条 — 提升大批量导入体验

**中期（3-5天可完成）**：
1. 批量文件导入 — 提升效率
2. 导入模板下载 — 降低使用门槛
3. 知识点标签生成 — 丰富题目元数据
4. 导入结果报告 — 提升导入透明度

**长期（需要较多开发）**：
1. 在线题库对接 — 丰富题库来源
2. 题库合并 — 跨库数据整合
