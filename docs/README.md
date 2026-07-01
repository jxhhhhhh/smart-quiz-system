# 智能刷题系统 (Smart Quiz System)

这是一个基于 Python 和 Streamlit 的智能刷题系统，支持题目导入、多种模式刷题、答题统计、用户认证以及 AI 智能增强解析（含 OCR 图像识别）功能。该项目可作为 Python 课程设计或期末大作业的完整解决方案。

## 1. 项目功能说明

### 1.1 核心功能模块
- **配置管理 ([config.py](config.py))**: 统一管理数据库路径、AI 模型配置、难度级别等全局常量。
- **数据库管理 ([database.py](database.py))**: 使用 SQLite 数据库存储题库、答题记录、用户信息等 6 张表，支持单例模式和线程安全访问。
- **题目导入 ([question_importer.py](question_importer.py))**: 支持从格式化文本批量导入题目到数据库，支持学科分类设置和去重检测。
- **题目解析 ([parser.py](parser.py))**: 支持纯文本、PDF、DOCX 三种格式的题目解析，自动识别五种题型（单选/多选/判断/填空/简答），提供统一的答案判断函数 `check_answer()`。
- **AI 智能解析 ([ai_parser.py](ai_parser.py))**: 接入 DeepSeek / OpenAI 等大语言模型 API，对格式不规范的文本进行智能题目识别，返回结构化 JSON 数据。新增 `ai_parse_image()` 函数，支持 OCR 图像识别，可直接从图片中提取题目。
- **刷题练习 ([practice_session.py](practice_session.py))**:
  - **随机模式**: 从题库中随机抽取题目。
  - **错题重练**: 智能汇总历史错题并进行强化练习，支持自定义练习数量。
  - **难度专项**: 根据难度等级 (1-3) 进行针对性练习。
- **数据统计**: 自动计算准确率、每日练习量，并使用 Plotly 生成可视化学习报表。

### 1.2 AI 增强功能 ([ai_enhancement.py](ai_enhancement.py))
- 集成 OpenAI API，支持对题目进行智能解析。
- 自动生成题目的知识点标签、难度评估和详细解题思路。
- 支持一键批量增强题库中的所有题目。

### 1.3 用户认证与交互界面
- **Web 界面 ([web_interface.py](web_interface.py))**: 基于 Streamlit 构建，提供现代化、响应式的网页操作界面（推荐使用）。内置用户认证系统，支持登录和注册功能。
- **命令行界面 ([main.py](main.py))**: 提供传统的终端菜单交互模式，适合快速操作。

### 1.4 支持的题型

| 题型 | 标识 | 说明 |
|------|------|------|
| 单选题 | `single` | 有 A/B/C/D 选项，答案为单字母 |
| 多选题 | `multi` | 有选项，答案含多个字母（如 ABD） |
| 判断题 | `judge` | 选项为"正确/错误"或答案含 √/× |
| 填空题 | `fill` | 含 `___` 或无选项，答案为任意文本 |
| 简答题 | `short` | 论述/问答类题目，答案为较长文本 |

### 1.5 Web 界面功能页面

| 页面 | 功能 |
|------|------|
| 🏠 仪表盘 | 核心指标展示、题型分布、快速开始入口 |
| 📥 导入题目 | 文件上传（PDF/DOCX）+ 文本粘贴，支持正则解析、AI 智能解析和 OCR 图像识别三模式，学科必填 |
| 📝 刷题练习 | 三种模式（随机/错题/难度），题型筛选，支持中途退出、进度持久化和再来一组 |
| 📝 模拟考试 | 限时考试、自动交卷、超时强制提交 |
| 📅 间隔复习 | 基于艾宾浩斯遗忘曲线的间隔重复复习计划 |
| 📊 学习统计 | 近30天数据卡片、近7天每日趋势图、各题型正确率、学习建议 |
| ❌ 错题回顾 | 错题列表（按错误次数排序），自定义练习数量，一键开始错题练习 |
| 📋 题目管理 | 按学科/题型/关键词筛选，编辑（含选项修改）/删除/导出题目（支持 JSON 格式） |
| 📜 答题历史 | 筛选历史记录，导出 CSV（UTF-8 BOM 编码，兼容 Excel），查看详细答题数据 |

## 2. 运行指南 (如何启动)

### 2.1 环境要求
- **Python 版本**: 3.7 或更高版本
- **操作系统**: Windows, macOS, Linux

### 2.2 安装依赖
在项目根目录下打开终端，执行以下命令安装所需的 Python 库：
```bash
pip install -r requirements.txt
```
或者手动安装：
```bash
pip install pandas streamlit plotly openai pdfplumber python-docx
```

### 2.3 启动方式

#### 方式一：启动 Web 界面（推荐）
Web 界面提供了最完整的用户体验，包含图表统计和交互式答题。
```bash
streamlit run web_interface.py
```
*启动后，终端会显示一个本地 URL（通常为 http://localhost:8501），在浏览器中打开即可。首次使用需注册账号并登录。*

#### 方式二：启动命令行界面 (CLI)
如果你习惯使用终端，可以使用 CLI 版本：
```bash
python main.py
```

### 2.4 使用 AI 功能（可选）

#### AI 增强解析
如果你想使用 AI 增强功能，需要获取 OpenAI API Key：
1. 访问 [OpenAI 平台](https://platform.openai.com/) 获取 API Key。
2. 在 Web 界面的"AI 分析"页面中输入 Key。
3. 点击"开始批量增强"即可为题目生成解析。

#### AI 智能导入
导入题目时可选择"AI 智能解析"模式：
1. 在导入页面选择"🤖 AI 智能解析"。
2. 填入 API Key（默认使用 DeepSeek，也可自定义为 OpenAI 等）。
3. 粘贴文本或上传文件，AI 会自动识别题目结构。

#### OCR 图像识别
支持从图片中直接识别题目：
1. 在导入页面选择 OCR 图像识别模式。
2. 上传包含题目的图片文件。
3. 系统通过多模态 AI 模型自动识别图片中的文字并提取题目结构。

### 2.5 运行测试
```bash
python -m pytest tests/ -v
```

## 3. 数据库结构

数据库文件路径：`data/question_bank.db`（运行后自动生成）

### 3.1 questions (题目表)
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | INTEGER | 主键，自增 |
| subject | TEXT | 学科/分类 |
| question_content | TEXT | 题目正文 |
| options | TEXT | 选项 (JSON 格式存储) |
| correct_answer | TEXT | 正确答案 (如 A, ABD, √, len) |
| difficulty | INTEGER | 难度 (1-3) |
| tags | TEXT | 知识点标签 |
| ai_enhanced | INTEGER | 是否已 AI 增强 (0/1) |
| question_type | TEXT | 题型 (single/multi/judge/fill/short) |
| source | TEXT | 来源（文件名/手动粘贴） |
| created_at | TEXT | 创建时间 |

### 3.2 practice_records (答题记录表)
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| record_id | INTEGER | 主键，自增 |
| question_id | INTEGER | 外键，关联题目 ID |
| user_answer | TEXT | 用户提交的答案 |
| is_correct | INTEGER | 是否正确 (0/1) |
| time_spent | REAL | 答题用时 (秒) |
| practice_date | TEXT | 答题时间 |
| user_id | INTEGER | 外键，关联用户 ID |

### 3.3 favorites (题目收藏表)
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | INTEGER | 主键，自增 |
| question_id | INTEGER | 外键，关联题目 ID (UNIQUE) |
| created_at | TEXT | 收藏时间 |
| user_id | INTEGER | 外键，关联用户 ID |

### 3.4 import_history (导入历史表)
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | INTEGER | 主键，自增 |
| source | TEXT | 导入来源 |
| count | INTEGER | 导入题目数量 |
| subject | TEXT | 学科分类 |
| parse_mode | TEXT | 解析模式 (regex/ai) |
| imported_at | TEXT | 导入时间 |
| user_id | INTEGER | 外键，关联用户 ID |

### 3.5 users (用户表)
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | INTEGER | 主键，自增 |
| username | TEXT | 用户名 (UNIQUE) |
| password_hash | TEXT | 密码哈希 |
| display_name | TEXT | 显示名称 |
| role | TEXT | 角色 (默认 user) |
| created_at | TEXT | 注册时间 |

### 3.6 practice_sessions (练习进度表)
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | INTEGER | 主键，自增 |
| session_key | TEXT | 会话标识 |
| questions_json | TEXT | 当前题目列表 (JSON) |
| current_index | INTEGER | 当前进度索引 |
| score | INTEGER | 当前得分 |
| mode | TEXT | 练习模式 (random/wrong/difficulty) |
| settings_json | TEXT | 练习配置 (JSON) |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

## 4. 项目文件结构
```text
.
├── config.py               # 全局配置模块（数据库路径、AI 模型、难度级别等）
├── database.py             # 数据库核心模块（单例模式、线程安全，6 张表）
├── parser.py               # 题目解析模块（文本/PDF/DOCX + 答案判断）
├── ai_parser.py            # AI 智能解析模块（DeepSeek/OpenAI API + OCR 图像识别）
├── question_importer.py    # 题目解析与导入模块
├── practice_session.py     # 刷题逻辑与统计模块
├── ai_enhancement.py       # AI 增强功能模块
├── styles.py               # 主题样式模块（深色/浅色 CSS + 响应式布局）
├── logger.py               # 统一日志模块
├── main.py                 # 命令行入口
├── web_interface.py        # Streamlit Web 界面入口（路由分发 + 用户认证）
├── page_modules/           # 页面渲染模块
│   ├── __init__.py         # 模块导出
│   ├── _common.py          # 公共常量、辅助函数、数据库缓存
│   ├── dashboard.py        # 🏠 仪表盘
│   ├── import_page.py      # 📥 导入题目
│   ├── practice.py         # 📝 刷题练习（含进度持久化）
│   ├── exam.py             # 📝 模拟考试（限时考试 + 超时强制交卷）
│   ├── review_plan.py      # 📅 间隔重复复习（艾宾浩斯曲线）
│   ├── statistics.py       # 📊 学习统计
│   ├── wrong_review.py     # ❌ 错题回顾
│   ├── question_manage.py  # 📋 题目管理（支持 JSON 导出）
│   └── history.py          # 📜 答题历史（UTF-8 BOM CSV 导出）
├── tests/                  # 测试目录
│   └── test_system.py      # 单元测试（44 个测试用例）
├── data/                   # 数据目录
│   └── question_bank.db    # SQLite 数据库文件 (运行后自动生成)
├── requirements.txt        # 依赖库清单
├── README.md               # 项目说明文档
├── 功能文档_刷题练习.md     # 功能详细文档
├── 课程设计报告.md          # 课程设计报告
└── PPT内容.md              # 演示文稿内容
```

## 5. 技术栈

| 技术领域 | 选用方案 | 说明 |
|---------|---------|------|
| 数据库 | SQLite3 | Python 内置，轻量级嵌入式数据库，单例模式管理连接 |
| Web 框架 | Streamlit | 专为数据应用设计，纯 Python 构建 Web 界面 |
| 数据可视化 | Plotly | 交互式图表（柱状图、折线图等） |
| 文件解析 | pdfplumber + python-docx | PDF 和 Word 文档解析 |
| AI 解析 | OpenAI SDK + DeepSeek API | 大语言模型智能题目识别 |
| AI 增强 | OpenAI API | 题目分析、知识点标注、解题思路生成 |
| OCR 识别 | 多模态大语言模型 | 从图片中识别并提取题目（ai_parse_image） |
| 用户认证 | hashlib (SHA-256) | 密码哈希存储，登录/注册验证 |
| 答案标准化 | 正则表达式 (re) | 多格式答案匹配和标准化 |
| 日志 | logging | 统一日志模块，便于调试和追踪 |
| 测试框架 | pytest | 44 个测试用例，覆盖核心功能 |

## 6. 依赖库清单

| 库名 | 用途 | 必需/可选 |
|------|------|----------|
| streamlit | Web 界面框架 | 必需 |
| pandas | 数据处理 | 必需 |
| plotly | 数据可视化 | 必需 |
| openai | AI 解析、增强和 OCR 图像识别 | 可选（AI 功能需要） |
| pdfplumber | PDF 文件解析 | 可选（PDF 导入需要） |
| python-docx | Word 文件解析 | 可选（DOCX 导入需要） |
| pytest | 单元测试框架 | 可选（运行测试需要） |
