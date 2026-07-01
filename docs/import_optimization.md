# 题目智能导入模块深度优化设计

---

## 一、优化背景与目标

### 1.1 现状分析

当前系统的题目导入模块已具备基础能力：正则表达式解析（格式规范文本的高速处理）、AI 智能解析（调用 DeepSeek API 对乱序文本进行结构化识别）、五种题型自动识别、答案标准化、预览编辑和去重导入。但在实际使用中，仍存在以下不足：

| 问题类别 | 具体表现 |
|---------|---------|
| 解析引擎单一 | 正则和 AI 二选一，无法协同；正则解析结果缺乏元数据，AI 解析成本高且无法保证 100% 准确 |
| 元数据缺失 | 正则模式下学科、难度、知识点标签全部为空，需用户手动逐题填写 |
| 去重粗糙 | 仅按题目内容+答案精确匹配，同义题干、选项乱序、标点差异均导致重复导入 |
| 质量校验缺失 | 空题干、缺失答案、题型误判等问题在导入后才被发现，缺乏导入前自动检测和修复 |
| 批量能力不足 | 不支持多文件同时导入，无进度反馈，导入失败无法导出重试 |
| 输入方式受限 | 仅支持文本和文档，不支持截图/拍照等图片输入 |

### 1.2 优化目标

围绕"智能导入"核心亮点，实现三大特性：

- **智能**：双层引擎协同、自动标注元数据、智能去重
- **自动化**：质量校验自动检测、批量导入自动处理、失败自动导出
- **结构化**：每道题具备完整的学科-章节-知识点-难度结构化元数据

---

## 二、优化方案详细设计

### 2.1 双层解析引擎：正则高速解析 + AI 智能兜底修复

#### 问题现状

当前系统将正则解析和 AI 解析作为两个独立的互斥选项。正则解析速度快（毫秒级）但无法处理格式混乱的文本，且不产出学科、难度、知识点等元数据；AI 解析能力强但响应慢（数秒）、有 API 调用成本，且偶尔返回格式错误的 JSON。用户必须自行判断使用哪种模式，选择不当则解析效果差。

#### 优化方案

设计"正则优先 + AI 兜底"的双层协同解析架构。正则引擎作为第一层高速处理，对每道题输出置信度评分；AI 引擎作为第二层，仅对低置信度题目进行修复和元数据补全。两层引擎各取所长，兼顾速度、成本和准确率。

#### 实现思路

**第一层：正则引擎高速解析 + 置信度评分**

为 `parse_block()` 函数增加置信度评分机制。评分维度包括：

```python
def _calc_confidence(block, parsed_result):
    """计算单题解析置信度（0.0 ~ 1.0）。"""
    score = 1.0
    content = parsed_result.get("content", "")
    answer = parsed_result.get("answer", "")
    options = parsed_result.get("options")
    q_type = parsed_result.get("q_type", "fill")

    # 1. 题目内容完整性（内容越完整，置信度越高）
    if len(content) < 10:
        score -= 0.3  # 内容过短，可能解析不完整

    # 2. 答案存在性
    if not answer:
        score -= 0.4  # 无答案，严重问题

    # 3. 选择题必须有选项
    if q_type in ("single", "multi") and not options:
        score -= 0.3

    # 4. 选项数量合理性（选择题至少2个选项）
    if options and len(options) < 2:
        score -= 0.2

    # 5. 答案范围校验（单选答案必须在选项范围内）
    if q_type == "single" and options and answer:
        if answer not in options:
            score -= 0.3

    # 6. 题型标签是否明确（有标签比推断更可靠）
    type_label = re.search(r'[（(]\s*(单选|多选|判断|填空|简答)\s*题?', block)
    if type_label:
        score += 0.1  # 有明确标签，额外加分

    return max(0.0, min(1.0, score))
```

对每道题计算置信度后，分为三档处理：

| 置信度 | 处理方式 | 说明 |
|--------|---------|------|
| ≥ 0.8 | 直接采纳 | 正则解析结果可靠，无需 AI 介入 |
| 0.5 ~ 0.8 | AI 修复 | 将原始文本块发送给 AI，要求修复并补全元数据 |
| < 0.5 | AI 重新解析 | 正则解析基本失败，完全依赖 AI 重新识别 |

**第二层：AI 智能修复与元数据补全**

对需要 AI 介入的题目，构造专门的修复 Prompt：

```python
REPAIR_PROMPT = """你是题目修复专家。以下题目由自动解析系统处理，可能存在错误。
请根据原始文本修复问题，并补全元数据。

原始文本块：
{raw_block}

当前解析结果（可能有误）：
{parsed_json}

请修复以下问题并返回 JSON：
1. 修正题型识别错误
2. 补全缺失的选项或答案
3. 修正题干中的格式噪音
4. 推断学科分类
5. 评估难度等级（1-3）
6. 生成知识点标签（1-3个）

返回格式（单个 JSON 对象，不是数组）：
{{
  "q_type": "single",
  "content": "修复后的题目内容",
  "options": {{"A": "...", "B": "..."}},
  "answer": "A",
  "subject": "Python",
  "difficulty": 1,
  "tags": ["基础语法", "变量"]
}}"""
```

**协同流程**

```
原始文本
    │
    ▼
正则引擎：clean_text → split_into_blocks → parse_block（每题）
    │
    ├── 置信度 ≥ 0.8 ──→ 直接采纳 ✅
    │
    ├── 置信度 0.5~0.8 ─→ AI 修复（发送原始文本块 + 解析结果）→ 采纳修复结果 ✅
    │
    └── 置信度 < 0.5 ──→ AI 重新解析（发送原始文本块）→ 采纳 AI 结果 ✅
    │
    ▼
合并结果 → 预览确认
```

#### 预期效果

- **速度提升**：格式规范的题目（通常占 70%+）由正则引擎毫秒级处理，仅 30% 低置信度题目调用 AI，整体速度比全量 AI 解析快 3-5 倍
- **成本降低**：API 调用量减少约 70%，显著降低 DeepSeek/OpenAI 的 Token 消耗
- **准确率提升**：正则引擎擅长的格式规范题目保持高速，正则引擎薄弱的混乱题目由 AI 兜底，综合准确率接近 100%

---

### 2.2 智能学科、章节、知识点自动标注

#### 问题现状

正则模式导入的题目，学科字段为空、难度默认为 1、知识点标签为空。用户必须在"题目管理"页面逐题手动编辑，100 道题的标注工作量巨大。即使使用 AI 模式，学科推断也仅基于题目内容的浅层关键词匹配，缺乏对章节结构的理解。

#### 优化方案

设计三级自动标注体系：学科推断 → 章节映射 → 知识点生成。基于题库中已有题目的标注数据建立映射规则，新导入题目自动继承已有的标注模式。

#### 实现思路

**第一级：学科自动推断**

维护一个学科关键词库（可从已有题库自动学习），对题目内容进行匹配：

```python
# 学科关键词库（初始值 + 从题库自动学习）
SUBJECT_KEYWORDS = {
    "Python": ["python", "def ", "import ", "print(", "list", "dict", "tuple",
                "for循环", "if语句", "函数", "类", "模块", "异常", "列表推导"],
    "数据结构": ["栈", "队列", "链表", "二叉树", "排序算法", "哈希表", "图", "堆"],
    "计算机网络": ["TCP", "UDP", "IP地址", "HTTP", "路由器", "DNS", "OSI", "协议"],
    "操作系统": ["进程", "线程", "死锁", "内存管理", "虚拟内存", "文件系统", "调度"],
    "数据库": ["SQL", "SELECT", "INSERT", "索引", "事务", "范式", "主键", "外键"],
}

def infer_subject(content, options_text=""):
    """基于题目内容推断学科。"""
    text = (content + " " + options_text).lower()
    scores = {}
    for subject, keywords in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[subject] = score
    if scores:
        return max(scores, key=scores.get)
    return ""
```

此外，从数据库已有题目中自动学习学科关键词：统计每个学科下高频出现的词汇，扩充关键词库。

**第二级：章节智能映射**

基于知识点标签的层次结构，自动推断章节归属。维护一个章节-关键词映射表：

```python
CHAPTER_MAP = {
    "Python": {
        "第一章 基础语法": ["变量", "数据类型", "运算符", "输入输出", "注释"],
        "第二章 流程控制": ["if", "for", "while", "break", "continue", "循环"],
        "第三章 函数": ["def", "函数", "参数", "返回值", "递归", "lambda"],
        "第四章 数据结构": ["列表", "元组", "字典", "集合", "字符串"],
        "第五章 面向对象": ["类", "对象", "继承", "封装", "多态", "__init__"],
        "第六章 文件操作": ["open", "read", "write", "文件", "with语句"],
        "第七章 异常处理": ["try", "except", "异常", "raise", "finally"],
    }
}

def infer_chapter(subject, content, tags=""):
    """根据学科和题目内容推断章节。"""
    if subject not in CHAPTER_MAP:
        return ""
    text = content + " " + tags
    for chapter, keywords in CHAPTER_MAP[subject].items():
        if any(kw in text for kw in keywords):
            return chapter
    return ""
```

**第三级：知识点自动生成**

对没有知识点标签的题目（正则模式），使用轻量级方法生成：

```python
def extract_keywords_from_content(content, options=None):
    """从题目内容中提取知识点关键词（无需 AI）。"""
    keywords = []

    # 1. 提取代码关键字
    code_kw = re.findall(r'\b(import|def|class|for|while|if|elif|else|try|except|'
                         r'return|yield|lambda|with|as|from|raise|True|False|None)\b', content)
    keywords.extend(set(code_kw))

    # 2. 提取数据类型相关词
    type_kw = re.findall(r'\b(list|dict|tuple|set|str|int|float|bool|type)\b', content)
    keywords.extend(set(type_kw))

    # 3. 提取函数/方法名
    func_kw = re.findall(r'\b([a-zA-Z_]\w*)\s*\(', content)
    keywords.extend(set(func_kw[:3]))  # 最多取3个

    # 4. 从选项中提取共性概念
    if options:
        all_opts = " ".join(str(v) for v in options.values())
        concept_kw = re.findall(r'\b[一-龥]{2,4}\b', all_opts)
        # 取出现频率最高的词
        from collections import Counter
        common = Counter(concept_kw).most_common(3)
        keywords.extend([w for w, _ in common])

    return ", ".join(list(dict.fromkeys(keywords))[:5])  # 去重，最多5个
```

#### 预期效果

- **零手动标注**：正则模式导入的题目自动获得学科、章节、知识点三级元数据
- **标注准确率**：学科推断准确率 ≥ 90%（基于关键词匹配），知识点覆盖率 ≥ 80%
- **增量学习**：随着题库增长，学科关键词库自动扩充，推断准确率持续提升

---

### 2.3 基于语义指纹的鲁棒性去重

#### 问题现状

当前去重机制为精确匹配 `question_content` 和 `correct_answer`，存在以下问题：

| 场景 | 当前行为 | 期望行为 |
|------|---------|---------|
| 题干多一个空格 | 当作新题导入（误判） | 应识别为重复 |
| 选项顺序不同（A/B互换） | 当作新题导入（误判） | 应识别为重复 |
| 标点符号差异（。vs .） | 当作新题导入（误判） | 应识别为重复 |
| 同义改写（"下列正确的" vs "以下正确的是"） | 当作新题导入 | 应标记为疑似重复 |

#### 优化方案

设计"文本指纹 + 结构指纹"双维度去重机制。对每道题生成标准化的语义指纹，通过指纹比对实现鲁棒性去重。

#### 实现思路

**文本指纹：标准化后哈希**

对题目内容进行深度标准化后取哈希值，消除格式差异：

```python
import hashlib

def generate_text_fingerprint(content, options=None, answer=""):
    """生成题目的文本指纹，用于去重比较。

    标准化流程：
    1. 去除所有空白字符
    2. 全角转半角
    3. 统一标点符号
    4. 去除题号
    5. 排序选项（消除选项顺序差异）
    """
    text = content

    # 1. 去除空白
    text = re.sub(r'\s+', '', text)

    # 2. 全角转半角（数字、字母）
    text = text.translate(_TRANS_TABLE)

    # 3. 统一标点
    punct_map = str.maketrans('。？！，、；：""''（）【】', '.?!,,;:""\'\'()[]')
    text = text.translate(punct_map)

    # 4. 去除题号
    text = re.sub(r'^(第?\s*\d+\s*[题、.．。]|\d+[.．、。]\s*(?:[（(].*?[）)])?)', '', text)

    # 5. 选项标准化（排序后拼接）
    opt_str = ""
    if options:
        sorted_opts = sorted(options.items())
        opt_str = "".join(f"{k}{v}" for k, v in sorted_opts)
        opt_str = re.sub(r'\s+', '', opt_str)

    # 6. 拼接并取哈希
    full_text = text + "|" + opt_str + "|" + answer.strip().upper()
    return hashlib.md5(full_text.encode('utf-8')).hexdigest()


def generate_structure_fingerprint(q_type, options, answer):
    """生成结构指纹：题型 + 选项数量 + 答案格式。

    用于检测"题干相似但选项/答案不同"的变体题目。
    """
    opt_count = len(options) if options else 0
    answer_len = len(answer) if answer else 0
    return f"{q_type}_{opt_count}_{answer_len}"
```

**去重流程**

```python
def check_duplicate_with_fingerprint(db, content, options, answer):
    """基于指纹的智能去重。

    返回：
    - "exact"：精确重复（指纹完全匹配），跳过
    - "similar"：疑似重复（指纹接近），提示用户确认
    - "unique"：新题，正常导入
    """
    # 1. 计算新题的指纹
    new_fp = generate_text_fingerprint(content, options, answer)

    # 2. 从数据库获取所有题目的指纹（缓存优化）
    existing_fps = db.cursor.execute(
        "SELECT id, question_content, fingerprint FROM questions"
    ).fetchall()

    for row in existing_fps:
        existing_fp = row['fingerprint'] if row['fingerprint'] else \
                      generate_text_fingerprint(row['question_content'], None, "")

        # 3. 精确匹配
        if new_fp == existing_fp:
            return "exact", row['id']

        # 4. 相似度匹配（对题干内容做编辑距离比较）
        clean_new = re.sub(r'\s+', '', content)
        clean_old = re.sub(r'\s+', '', row['question_content'])
        if len(clean_new) > 10 and len(clean_old) > 10:
            from parser import _levenshtein
            dist = _levenshtein(clean_new[:100], clean_old[:100])
            max_len = max(len(clean_new[:100]), len(clean_old[:100]))
            if dist / max_len < 0.1:  # 相似度 > 90%
                return "similar", row['id']

    return "unique", None
```

**数据库扩展**

在 `questions` 表中新增 `fingerprint` 字段，导入时自动生成：

```sql
ALTER TABLE questions ADD COLUMN fingerprint TEXT NOT NULL DEFAULT '';
CREATE INDEX idx_questions_fingerprint ON questions(fingerprint);
```

#### 预期效果

- **消除格式差异导致的重复**：空格、标点、全角半角、选项顺序等差异均被标准化
- **疑似重复智能提示**：相似度 90% 以上的题目标记为"疑似重复"，由用户决定是否导入
- **查询性能优化**：通过指纹索引，去重查询从逐题比较变为哈希查找，速度提升一个数量级

---

### 2.4 导入质量自动校验与批量修复

#### 问题现状

当前系统在导入前仅展示预览，用户需要逐题人工检查。对于批量导入 100+ 道题的场景，人工检查效率低且容易遗漏。常见质量问题包括：空题干、缺失答案、选择题无选项、题型识别错误、答案超出选项范围等。这些问题在导入后才暴露，需要用户返回"题目管理"页面逐题修改。

#### 优化方案

在导入前增加自动质量校验环节，对每道题进行多维度检测，输出质量报告，并提供一键批量修复能力。

#### 实现思路

**质量校验引擎**

```python
class ImportQualityChecker:
    """导入质量自动校验器。"""

    def __init__(self):
        self.issues = []  # [(question_index, severity, issue_type, message, auto_fixable)]

    def check_all(self, questions):
        """对所有题目进行全面质量校验。"""
        self.issues = []
        for i, q in enumerate(questions):
            self._check_content(i, q)
            self._check_answer(i, q)
            self._check_options(i, q)
            self._check_type_consistency(i, q)
            self._check_answer_range(i, q)
        return self.issues

    def _check_content(self, idx, q):
        """检测题干问题。"""
        content = q.get("content", "").strip()
        if not content:
            self.issues.append((idx, "error", "empty_content", "题干为空", False))
        elif len(content) < 5:
            self.issues.append((idx, "warning", "short_content",
                               f"题干过短（{len(content)}字），可能解析不完整", False))

    def _check_answer(self, idx, q):
        """检测答案问题。"""
        answer = q.get("answer", "").strip()
        q_type = q.get("q_type", "single")
        if not answer:
            self.issues.append((idx, "error", "missing_answer", "答案缺失", False))
        elif q_type == "single" and len(answer) > 1 and answer.isalpha():
            self.issues.append((idx, "warning", "multi_answer_for_single",
                               f"单选题答案为'{answer}'（多个字母），可能是多选题", True))

    def _check_options(self, idx, q):
        """检测选项问题。"""
        q_type = q.get("q_type", "single")
        options = q.get("options")
        if q_type in ("single", "multi", "judge"):
            if not options or not isinstance(options, dict):
                self.issues.append((idx, "error", "missing_options",
                                   f"{TYPE_NAMES.get(q_type)}缺少选项", False))
            elif len(options) < 2:
                self.issues.append((idx, "warning", "too_few_options",
                                   f"选项数量不足（仅{len(options)}个）", False))

    def _check_type_consistency(self, idx, q):
        """检测题型与内容的一致性。"""
        content = q.get("content", "")
        q_type = q.get("q_type", "single")
        answer = q.get("answer", "")

        # 判断题答案应该只有 A/B 或 √/×
        if q_type == "judge" and answer not in ("A", "B", "√", "×"):
            self.issues.append((idx, "warning", "judge_answer_format",
                               f"判断题答案'{answer}'格式异常", True))

        # 填空题不应有选项
        if q_type == "fill" and q.get("options"):
            self.issues.append((idx, "info", "fill_has_options",
                               "填空题包含选项，可能应为选择题", True))

    def _check_answer_range(self, idx, q):
        """检测答案是否在选项范围内。"""
        q_type = q.get("q_type", "single")
        options = q.get("options")
        answer = q.get("answer", "")
        if q_type in ("single", "multi") and options and answer:
            valid_keys = set(options.keys())
            for ch in answer:
                if ch not in valid_keys:
                    self.issues.append((idx, "error", "answer_out_of_range",
                                       f"答案'{answer}'中的'{ch}'不在选项{valid_keys}范围内", False))
                    break

    def auto_fix(self, questions):
        """对可自动修复的问题进行批量修复。"""
        fixed_count = 0
        for idx, severity, issue_type, msg, auto_fixable in self.issues:
            if not auto_fixable:
                continue
            q = questions[idx]
            if issue_type == "multi_answer_for_single":
                # 单选题答案有多个字母 → 改为多选题
                q["q_type"] = "multi"
                fixed_count += 1
            elif issue_type == "judge_answer_format":
                # 判断题答案标准化
                from parser import normalize_answer
                q["answer"] = normalize_answer(q["answer"], "judge")
                fixed_count += 1
            elif issue_type == "fill_has_options":
                # 填空题有选项 → 删除选项
                q["options"] = None
                fixed_count += 1
        return fixed_count
```

**前端展示质量报告**

在预览区域顶部展示质量校验结果：

```python
# 在 import_page.py 的预览区域中
checker = ImportQualityChecker()
issues = checker.check_all(questions)

if issues:
    errors = [i for i in issues if i[1] == "error"]
    warnings = [i for i in issues if i[1] == "warning"]
    infos = [i for i in issues if i[1] == "info"]

    # 质量概览卡片
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("❌ 错误", len(errors))
    with col2:
        st.metric("⚠️ 警告", len(warnings))
    with col3:
        st.metric("ℹ️ 提示", len(infos))

    # 一键修复按钮
    auto_fixable = [i for i in issues if i[4]]  # auto_fixable=True
    if auto_fixable:
        if st.button(f"🔧 一键修复 {len(auto_fixable)} 个问题"):
            fixed = checker.auto_fix(questions)
            st.success(f"✅ 已自动修复 {fixed} 个问题")
            st.rerun()

    # 问题详情列表
    with st.expander("📋 查看质量报告详情"):
        for idx, severity, issue_type, msg, _ in issues:
            icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[severity]
            st.markdown(f"{icon} **第{idx+1}题**：{msg}")
```

#### 预期效果

- **导入前发现问题**：在预览阶段即可检测出所有质量问题，避免"导入后才发现"的尴尬
- **一键批量修复**：可自动修复的问题（题型错误、答案格式等）一键处理，减少手动修改
- **质量报告透明**：错误/警告/提示三级分类，用户清楚知道每道题的问题所在

---

### 2.5 批量文件导入、进度反馈与失败报告

#### 问题现状

当前系统仅支持单文件上传，不支持同时导入多个 PDF/DOCX 文件。导入过程中无进度反馈，用户面对大量题目时不知道导入进度。导入失败的题目仅在页面上显示错误信息，无法导出重试。

#### 优化方案

支持多文件批量上传、分步进度反馈、导入结果报告导出（含失败题目可导出为文本重新导入）。

#### 实现思路

**多文件上传**

```python
# import_page.py
uploaded_files = st.file_uploader(
    "上传文件（支持多选）",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True,  # Streamlit 原生支持多文件
    help="支持 PDF、Word、TXT 格式，可同时选择多个文件"
)
```

**带进度的批量导入**

```python
def batch_import_with_progress(questions, source, db):
    """带进度反馈的批量导入。"""
    total = len(questions)
    success = 0
    skipped = 0
    failed = []
    failed_questions = []  # 记录失败的题目原文，用于导出重试

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, q in enumerate(questions):
        status_text.text(f"正在导入第 {i+1}/{total} 题...")
        progress_bar.progress((i + 1) / total)

        try:
            # 去重检查
            existing = db.cursor.execute(
                "SELECT id FROM questions WHERE fingerprint = ?",
                (q.get("fingerprint", ""),)
            ).fetchone()

            if existing:
                skipped += 1
                continue

            # 插入
            db.cursor.execute(
                """INSERT INTO questions
                   (subject, question_content, options, correct_answer,
                    difficulty, question_type, source, tags, fingerprint)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (q.get("subject", ""), q["content"],
                 json.dumps(q.get("options") or {}, ensure_ascii=False),
                 q["answer"], q.get("difficulty", 1),
                 q.get("q_type", "single"), source,
                 q.get("tags", ""), q.get("fingerprint", ""))
            )
            success += 1

        except Exception as e:
            failed.append(f"第{i+1}题: {str(e)}")
            failed_questions.append(q)

    db.conn.commit()
    progress_bar.progress(1.0)
    status_text.text("导入完成！")

    return {
        "total": total,
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "failed_questions": failed_questions,
    }
```

**失败题目导出**

```python
def export_failed_questions(failed_questions):
    """将导入失败的题目导出为文本，方便修正后重新导入。"""
    export_text = ""
    for i, q in enumerate(failed_questions, 1):
        q_type = q.get("q_type", "single")
        export_text += f"{i}. [{TYPE_NAMES.get(q_type, q_type)}] {q.get('content', '')}\n"
        opts = q.get("options")
        if opts:
            for k, v in opts.items():
                export_text += f"  {k}. {v}\n"
        export_text += f"  答案：{q.get('answer', '（缺失）')}\n"
        export_text += f"  学科：{q.get('subject', '')} | 难度：{q.get('difficulty', 1)}\n\n"
    return export_text
```

**导入结果报告**

在导入完成后展示详细报告：

```python
# 展示导入结果
st.markdown("### 📊 导入结果报告")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📝 总数", result["total"])
with col2:
    st.metric("✅ 成功", result["success"])
with col3:
    st.metric("⏭️ 跳过", result["skipped"])
with col4:
    st.metric("❌ 失败", len(result["failed"]))

# 失败题目导出
if result["failed_questions"]:
    export_text = export_failed_questions(result["failed_questions"])
    st.download_button(
        label="📥 导出失败题目（可修正后重新导入）",
        data=export_text,
        file_name=f"导入失败_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain"
    )
```

#### 预期效果

- **批量效率提升**：支持多文件同时上传，一次操作导入整个文件夹的题库
- **进度可视化**：导入过程中实时显示进度条和当前状态，用户不再"干等"
- **失败可恢复**：失败题目可导出为文本，修正后重新导入，避免数据丢失

---

### 2.6 可选扩展：OCR 图片题目导入

#### 问题现状

当前系统仅支持文本和文档输入。实际场景中，学生经常遇到以下情况：教材上的纸质题目、课堂 PPT 截图、手写笔记拍照、考试试卷扫描件。这些图片格式的题目无法直接导入系统，需要手动逐题输入。

#### 优化方案

集成 OCR（光学字符识别）能力，支持从截图/拍照中提取文本，再走现有的解析流程。

#### 实现思路

**技术选型**

| 方案 | 依赖库 | 优点 | 缺点 |
|------|--------|------|------|
| 方案 A：在线 API | 百度 OCR API / 腾讯 OCR API | 识别率高，支持手写体 | 需要网络，有调用成本 |
| 方案 B：本地模型 | `paddleocr`（PaddlePaddle） | 离线可用，免费 | 安装体积大（~500MB） |
| 方案 C：AI 多模态 | DeepSeek Vision / GPT-4o | 直接理解题目语义 | 成本最高，速度最慢 |

**推荐方案**：方案 A（百度 OCR API）作为主方案，方案 C（AI 多模态）作为备选。

**实现流程**

```python
# ocr_importer.py（新建模块）

def ocr_extract_text(image_path, api_key=None):
    """从图片中提取文本。

    Parameters
    ----------
    image_path : str
        图片文件路径（支持 jpg/png/bmp）
    api_key : str, optional
        百度 OCR API Key（为空时使用 AI 多模态方案）

    Returns
    -------
    str
        识别出的文本内容
    """
    if api_key:
        return _baidu_ocr(image_path, api_key)
    else:
        return _ai_multimodal_ocr(image_path)


def _baidu_ocr(image_path, api_key):
    """调用百度 OCR API 识别图片文本。"""
    import base64
    import requests

    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()

    url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "image": image_base64,
        "language_type": "CHN_ENG",  # 中英混合
    }

    # 获取 access_token
    token_url = f"https://aip.baidubce.com/oauth/2.0/token"
    token_params = {
        "grant_type": "client_credentials",
        "client_id": api_key.split(":")[0],
        "client_secret": api_key.split(":")[1],
    }
    token_resp = requests.post(token_url, params=token_params)
    access_token = token_resp.json().get("access_token")

    # 调用 OCR
    resp = requests.post(f"{url}?access_token={access_token}",
                         headers=headers, data=data)
    result = resp.json()
    lines = [item["words"] for item in result.get("words_result", [])]
    return "\n".join(lines)


def _ai_multimodal_ocr(image_path):
    """使用 AI 多模态模型识别图片中的题目。"""
    import base64
    from openai import OpenAI

    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()

    client = OpenAI(
        api_key="your-api-key",
        base_url="https://api.deepseek.com"
    )

    response = client.chat.completions.create(
        model="deepseek-chat",  # 或使用支持视觉的模型
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "请识别图片中的所有题目内容，原样输出文本。"},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }}
            ]
        }]
    )
    return response.choices[0].message.content
```

**前端集成**

```python
# import_page.py 中新增图片导入区域
st.markdown("### 📷 图片导入（OCR）")
uploaded_images = st.file_uploader(
    "上传题目截图或照片",
    type=["jpg", "jpeg", "png", "bmp"],
    accept_multiple_files=True,
    help="支持手机拍照、截图、扫描件"
)

if uploaded_images:
    ocr_mode = st.radio(
        "识别方式",
        ["🤖 AI 多模态识别（推荐，需 API Key）", "📝 百度 OCR（需百度 API Key）"],
        key="ocr_mode_select"
    )

    if st.button("🔍 开始识别"):
        all_text = ""
        for img in uploaded_images:
            temp_path = f"_temp_ocr_{img.name}"
            with open(temp_path, "wb") as f:
                f.write(img.read())

            with st.spinner(f"正在识别 {img.name}..."):
                text = ocr_extract_text(temp_path, api_key)
                all_text += f"\n\n--- {img.name} ---\n{text}"

            if os.path.exists(temp_path):
                os.remove(temp_path)

        # 将识别结果填入文本框，走正常解析流程
        st.session_state.ocr_text = all_text
        st.success(f"✅ 识别完成！共识别 {len(uploaded_images)} 张图片。")
        st.text_area("识别结果（可手动修正后解析）", value=all_text, height=300)
```

#### 预期效果

- **输入方式扩展**：从"文本+文档"扩展到"文本+文档+图片"，覆盖纸质教材、课堂截图、手写笔记等场景
- **无缝衔接**：OCR 识别的文本直接进入现有的解析流程（正则/AI），无需额外开发解析逻辑
- **灵活部署**：支持在线 API（轻量级）和本地模型（离线级）两种方案，适应不同网络环境

---

## 三、优化方案总结

| 优化项 | 核心技术 | 亮点 | 实现难度 |
|--------|---------|------|---------|
| 双层解析引擎 | 置信度评分 + AI 修复 Prompt | 速度提升 3-5 倍，成本降低 70% | ⭐⭐⭐ |
| 智能元数据标注 | 关键词匹配 + 章节映射 + 自动学习 | 零手动标注，三级结构化元数据 | ⭐⭐ |
| 语义指纹去重 | 文本标准化 + MD5 指纹 + 编辑距离 | 消除格式差异，相似度 90% 检测 | ⭐⭐ |
| 质量自动校验 | 多维度检测 + 一键批量修复 | 导入前发现问题，自动修复率 ≥ 60% | ⭐⭐ |
| 批量导入与进度 | 多文件上传 + 进度条 + 失败导出 | 批量效率提升，失败可恢复 | ⭐ |
| OCR 图片导入 | 百度 OCR / AI 多模态 | 输入方式扩展到图片 | ⭐⭐⭐ |

**整体架构图**

```
                    ┌─────────────────────────────────────┐
                    │           用户输入层                  │
                    │  文本粘贴 │ 文件上传（多选） │ 图片上传  │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │           预处理层                    │
                    │  文本清洗 │ PDF/DOCX 提取 │ OCR 识别  │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        双层解析引擎                   │
                    │  ┌──────────┐    ┌──────────────┐   │
                    │  │ 正则引擎  │───→│ 置信度评分    │   │
                    │  │ (高速)   │    │ ≥0.8 直接采纳 │   │
                    │  └──────────┘    │ <0.8 AI修复   │   │
                    │                  └──────┬───────┘   │
                    │  ┌──────────┐           │           │
                    │  │ AI 引擎  │←──────────┘           │
                    │  │ (兜底)   │                       │
                    │  └──────────┘                       │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        智能标注层                    │
                    │  学科推断 │ 章节映射 │ 知识点生成     │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        质量校验层                    │
                    │  自动检测 │ 一键修复 │ 质量报告       │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        去重与入库层                   │
                    │  语义指纹 │ 相似度检测 │ 批量导入      │
                    │  进度反馈 │ 失败导出   │ 导入历史      │
                    └─────────────────────────────────────┘
```

该优化方案在保持 Python 课程设计的技术可行性的前提下，通过正则与 AI 的协同、自动标注、语义指纹去重、质量校验等手段，将"题目导入"从一个基础的文本解析功能，升级为具备"智能识别、自动标注、鲁棒去重、质量保障"四大能力的智能导入引擎，充分体现"智能""自动化""结构化"三大设计亮点。
