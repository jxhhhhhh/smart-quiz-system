# 智能刷题系统 (Smart Quiz System)

基于 Python + Streamlit 的智能刷题系统，支持题目导入、多模式刷题、AI 智能解析、用户登录、学习统计。

## 目录结构

```
.
├── config.py               # 统一配置文件（路径/AI/OCR/解析/日志）
├── database.py             # 数据库管理（单例模式、线程安全、6张表）
├── parser.py               # 正则解析引擎（题型识别、答案标准化、模糊匹配、20+预编译正则）
├── ai_parser.py            # AI 解析引擎（DeepSeek/OpenAI API + 多模态OCR）
├── ai_enhancement.py       # AI 增强功能（知识点标注、解题思路）
├── question_importer.py    # 题目导入器（双层解析、语义去重、质量检查）
├── practice_session.py     # 刷题逻辑（题目获取、答案检查、统计）
├── styles.py               # 主题样式（深色/浅色 CSS + 响应式布局）
├── logger.py               # 日志模块
├── main.py                 # CLI 入口
├── web_interface.py        # Streamlit Web 入口（路由分发 + 用户认证）
├── requirements.txt        # 依赖清单（已锁定版本）
├── .gitignore              # Git 忽略规则
├── page_modules/           # 页面渲染模块
│   ├── _common.py          # 公共常量、辅助函数、数据库缓存、主题工具
│   ├── dashboard.py        # 仪表盘
│   ├── import_page.py      # 导入题目（支持PDF/DOCX/图片）
│   ├── practice.py         # 刷题练习（进度持久化）
│   ├── exam.py             # 模拟考试（超时强制交卷）
│   ├── review_plan.py      # 间隔重复复习（艾宾浩斯曲线）
│   ├── statistics.py       # 学习统计
│   ├── wrong_review.py     # 错题回顾
│   ├── question_manage.py  # 题目管理（分页导航 + JSON导出）
│   └── history.py          # 答题历史（CSV导出 + 分页导航）
├── tests/                  # 测试用例
│   └── test_system.py      # 44 个单元测试
├── data/                   # 数据文件
│   └── question_bank.db    # SQLite 数据库（运行后自动生成）
└── docs/                   # 文档
    ├── README.md           # 详细说明文档
    ├── feature_practice.md # 功能文档
    ├── course_report.md    # 课程设计报告
    ├── project_intro.md    # 项目介绍
    ├── evaluation_report.md # 项目评估报告
    ├── implementation_checklist.md # 实现清单
    ├── import_optimization.md      # 导入优化设计
    └── ppt_content.md      # PPT 内容
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Web 界面
streamlit run web_interface.py

# 运行测试
python -m pytest tests/ -v
```

## 功能概览

| 功能 | 说明 |
|------|------|
| 题目导入 | 文本粘贴 / PDF / DOCX / 图片OCR，支持批量多文件 |
| 双层解析 | 正则高速 + AI 兜底，智能识别五种题型 |
| 语义去重 | MD5 指纹去重，容忍格式差异 |
| 质量检查 | 自动检测空题干、缺答案、选项异常 |
| 刷题练习 | 随机 / 错题 / 难度三种模式，进度持久化 |
| 模拟考试 | 限时考试、低时间警告、超时自动交卷 |
| 间隔重复 | 艾宾浩斯遗忘曲线复习计划 |
| 学习统计 | Plotly 可视化图表、智能学习建议 |
| 题目管理 | 编辑（含选项）/ 删除 / 收藏 / TXT+JSON导出 |
| 用户系统 | 注册/登录、SHA-256密码安全、数据隔离 |
| 深色主题 | 深色/浅色切换，移动端响应式布局 |

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.7+ | 核心语言 |
| SQLite3 | 数据库（6张表、5个索引） |
| Streamlit | Web 框架 |
| Plotly | 数据可视化 |
| OpenAI SDK | AI 解析（DeepSeek/OpenAI）+ OCR |
| pdfplumber | PDF 解析 |
| python-docx | Word 解析 |
| pytest | 测试框架（44个用例） |
