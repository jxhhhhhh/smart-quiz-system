# 智能刷题系统（Smart Quiz System）— 项目详细介绍

---

## 一、项目概述

### 1.1 项目简介

智能刷题系统是一个基于 Python + Streamlit 构建的综合性学习辅助平台，面向高校学生，旨在解决课程复习和备考过程中的刷题效率问题。系统集题目导入、智能解析、多模式练习、科学复习、数据统计、用户管理于一体。

### 1.2 核心特性

- **双层解析引擎**：正则高速解析 + AI 智能兜底，置信度评分自动路由
- **多模态导入**：支持文本粘贴、PDF/DOCX 文件上传、图片 OCR 识别
- **五种题型**：单选题、多选题、判断题、填空题、简答题
- **三种练习模式**：随机模式、错题重练、难度专项
- **科学复习**：艾宾浩斯遗忘曲线间隔重复
- **数据可视化**：Plotly 交互式图表 + 智能学习建议
- **用户系统**：注册/登录、密码安全、数据隔离
- **深色主题**：深色/浅色切换 + 移动端响应式布局

---

## 二、背景与问题分析

### 2.1 领域背景

本项目属于**教育信息化**领域。在当前高等教育中，学生日常学习和考试备考高度依赖大量的练习题训练。

### 2.2 痛点分析

| 痛点 | 描述 | 本系统解决方案 |
|------|------|--------------|
| 题目整理繁琐 | 从学习通复制的文本格式混乱，手动整理耗时 | 双层解析引擎自动识别，支持批量导入 |
| 缺乏智能复习 | 无法根据遗忘曲线科学安排复习 | 艾宾浩斯间隔重复，自动提醒复习 |
| 错题管理困难 | 纸质错题本易丢失，无法统计分析 | 自动记录错题，按错误次数排序，一键重练 |
| 统计分析缺失 | 无法量化学习进度和薄弱环节 | Plotly 可视化图表 + 智能学习建议 |

---

## 三、技术架构

### 3.1 四层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户交互层（Presentation）                  │
│  web_interface.py ──→ page_modules/（9个页面模块）+ main.py    │
│  styles.py（主题CSS）  _common.py（公共组件）                   │
├─────────────────────────────────────────────────────────────┤
│                    业务逻辑层（Business Logic）                │
│  question_importer.py（导入引擎）  practice_session.py（练习）  │
│  ai_enhancement.py（AI增强）                                   │
├─────────────────────────────────────────────────────────────┤
│                    数据处理层（Data Processing）               │
│  parser.py（正则解析引擎）  ai_parser.py（AI解析引擎）          │
├─────────────────────────────────────────────────────────────┤
│                    数据存储层（Data Storage）                  │
│  database.py（SQLite 单例管理器）                              │
│  config.py（集中配置）  logger.py（统一日志）                   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 技术栈

| 技术领域 | 选用方案 | 说明 |
|---------|---------|------|
| 编程语言 | Python 3.14.0 | 核心语言 |
| Web 框架 | Streamlit | 纯 Python 构建 Web 界面 |
| 数据库 | SQLite3 | 嵌入式数据库，单例模式管理 |
| 数据可视化 | Plotly | 交互式图表 |
| AI 解析 | OpenAI SDK | 兼容 DeepSeek/OpenAI |
| 文件解析 | pdfplumber + python-docx | PDF 和 Word 解析 |
| 测试框架 | pytest | 44 个单元测试 |

---

## 四、核心功能详解

### 4.1 智能导入模块

**双层解析引擎**：

```
输入 → 正则解析（快速）→ 置信度评分
    ├─ ≥ 0.8 → 直接采纳
    ├─ 0.5~0.8 → AI 逐题修复
    └─ < 0.5 → AI 整段重新解析
→ 语义指纹去重（MD5）→ 质量检查 → 批量入库
```

**支持的输入方式**：
- 文本粘贴（学习通复制文本）
- PDF / DOCX 文件上传（支持批量）
- 图片 OCR（多模态 LLM Vision API，支持 PNG/JPG/BMP）

**去重机制**：对题目内容进行标准化处理（去空格、全角转半角、统一标点、排序选项、大写答案）后生成 MD5 指纹，语义相同但格式不同的题目会被识别为重复。

**质量检查**：自动检测空题干、缺少答案、选择题无选项、答案超出选项范围等问题，支持自动修复。

### 4.2 刷题练习模块

**三种练习模式**：
- **随机模式**：从题库中随机抽取指定数量的题目
- **错题重练**：按错误次数排序，优先展示高频错题
- **难度专项**：按难度等级（1-3）筛选题目

**进度持久化**：每次答题后自动保存进度到数据库，浏览器关闭或页面刷新后可恢复。

**答案判断逻辑**：
- 选择题：标准化后精确匹配
- 判断题：统一符号后匹配
- 填空题/简答题：多层匹配（精确→去括号→包含→多答案子集→Levenshtein模糊）

### 4.3 模拟考试模块

- 用户设置考试参数（题数、时长、题型、学科）
- 实时倒计时显示
- 低时间（<5分钟）警告
- JavaScript 定时器确保超时自动交卷
- 考试结果：成绩、正确率、用时

### 4.4 间隔重复复习

基于艾宾浩斯遗忘曲线理论，在学习后的第 1、2、4、7、15、30 天安排复习。系统自动追踪答题记录，将题目分为"今日到期"、"即将到期"、"已掌握"三类，在合适的时间提醒复习。

### 4.5 学习统计

使用 Plotly 生成交互式图表：
- 近 30 天数据卡片
- 每日答题数量柱状图
- 每日正确率趋势折线图
- 各题型正确率柱状图
- 智能学习建议（基于弱项分析）

### 4.6 用户认证系统

- 用户注册（用户名 ≥2 字符，密码 ≥4 字符）
- SHA-256 + 随机盐密码哈希
- 登录会话管理（st.session_state）
- 数据隔离（practice_records、favorites、import_history 按 user_id 隔离）

---

## 五、数据库设计

### 5.1 表结构总览

| 表名 | 用途 | 主要字段 |
|------|------|---------|
| questions | 题目存储 | id, subject, question_content, options(JSON), correct_answer, difficulty, question_type, fingerprint |
| practice_records | 答题记录 | record_id, question_id(FK), user_id, user_answer, is_correct, time_spent |
| favorites | 题目收藏 | id, question_id(FK, UNIQUE), user_id |
| import_history | 导入历史 | id, source, count, subject, parse_mode, user_id |
| users | 用户管理 | id, username(UNIQUE), password_hash, display_name, role |
| practice_sessions | 练习会话 | id, questions_json, current_index, score, mode, user_id |

### 5.2 索引设计

| 索引名 | 表 | 字段 | 用途 |
|--------|------|------|------|
| idx_questions_subject | questions | subject | 按学科筛选 |
| idx_questions_difficulty | questions | difficulty | 按难度筛选 |
| idx_records_question_id | practice_records | question_id | 关联查询 |
| idx_records_practice_date | practice_records | practice_date | 时间范围查询 |
| idx_questions_fingerprint | questions | fingerprint | 语义去重 |

---

## 六、项目文件结构

```
.
├── config.py               # 统一配置（路径/AI/OCR/解析/日志）
├── database.py             # 数据库管理（单例+线程安全+6表+5索引）
├── parser.py               # 正则解析引擎（20+预编译正则+答案判断+模糊匹配）
├── ai_parser.py            # AI解析引擎（文本解析+图片OCR）
├── ai_enhancement.py       # AI增强（知识点标注+解题思路）
├── question_importer.py    # 题目导入器（双层解析+去重+质量检查）
├── practice_session.py     # 刷题逻辑（题目获取+答案检查+统计）
├── styles.py               # 主题样式（深色/浅色+响应式布局 773行CSS）
├── logger.py               # 统一日志模块
├── main.py                 # CLI入口（支持5种题型）
├── web_interface.py        # Web入口（路由分发+用户认证）
├── requirements.txt        # 依赖清单（版本范围锁定）
├── page_modules/           # 页面渲染模块（9个页面）
│   ├── _common.py          # 公共工具（常量/辅助函数/DB缓存/主题工具）
│   ├── dashboard.py        # 仪表盘
│   ├── import_page.py      # 导入题目（PDF/DOCX/图片/文本）
│   ├── practice.py         # 刷题练习（进度持久化）
│   ├── exam.py             # 模拟考试（超时强制交卷）
│   ├── review_plan.py      # 间隔重复（艾宾浩斯曲线）
│   ├── statistics.py       # 学习统计（Plotly图表）
│   ├── wrong_review.py     # 错题回顾
│   ├── question_manage.py  # 题目管理（分页+JSON导出）
│   └── history.py          # 答题历史（CSV导出+分页）
├── tests/
│   └── test_system.py      # 44个单元测试
├── data/
│   └── question_bank.db    # SQLite数据库
└── docs/                   # 文档（8个文件）
```

---

## 七、运行指南

### 7.1 环境要求
- Python 3.7+
- Windows / macOS / Linux

### 7.2 安装与启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动Web界面（推荐）
streamlit run web_interface.py

# 启动CLI界面
python main.py

# 运行测试
python -m pytest tests/ -v
```

### 7.3 AI功能配置

在项目根目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
OCR_MODEL=deepseek-chat
```

---

## 八、项目特色与创新

1. **双层解析引擎**：正则高速 + AI 智能兜底，置信度评分自动路由，兼顾速度和准确率
2. **语义指纹去重**：MD5 哈希去重，容忍格式差异，避免重复导入
3. **多模态 OCR**：使用大语言模型 Vision API 识别图片中的题目，无需安装 Tesseract
4. **练习进度持久化**：答题进度自动保存，支持中断恢复
5. **艾宾浩斯间隔重复**：科学安排复习时间，提升记忆效果
6. **深色/浅色主题**：全局 CSS 适配，移动端响应式布局
7. **统一答案判断**：5 层匹配策略，支持括号忽略、包含匹配、模糊匹配
8. **正则预编译**：20+ 个高频正则模块级预编译，提升解析性能

---

## 九、已完成优化

| 优化项 | 状态 | 说明 |
|--------|------|------|
| CSV 导出 Excel 兼容 | ✅ | 添加 UTF-8 BOM 编码 |
| 短字符串答案误判 | ✅ | 包含匹配添加长度保护 |
| N+1 查询优化 | ✅ | WHERE IN 替代逐个查询 |
| 深色模式 CSS | ✅ | 6 处硬编码修复 |
| db.cursor 直接访问 | ✅ | 8 处替换为 db.execute() |
| 分页导航改进 | ✅ | 上一页/下一页按钮 |
| 考试超时强制交卷 | ✅ | JS 定时器 + 低时间警告 |
| 练习进度持久化 | ✅ | 数据库保存/恢复 |
| OCR 图片导题 | ✅ | 多模态 LLM Vision API |
| 多用户登录系统 | ✅ | SHA-256 + 盐 |
| 移动端响应式布局 | ✅ | 媒体查询 |
| JSON 全量导出 | ✅ | 题目管理页 |
| 正则预编译 | ✅ | 20+ 模式 |
