"""
AI 智能题目解析模块（优化版）
使用 OpenAI 兼容 API（DeepSeek / GPT / Qwen / Mimo 等）对文本进行智能题目识别。
增强：Prompt 稳定性、文本预处理、结果校验、长文本分片。
"""
import json
import re
import config
from parser import _TRANS_TABLE, _RE_CONTROL_CHARS, _RE_MULTI_BLANK

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ═══════════════════════════════════════════════════════════
#  文本预处理：清洗后再发给 AI
# ═══════════════════════════════════════════════════════════

def _preprocess_text(text: str) -> str:
    """发送给 AI 前的文本清洗，减少噪音，提高识别准确率。"""
    # 全角转半角（复用 parser.py 的转换表）
    text = text.translate(_TRANS_TABLE)

    # 统一标点
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("【", "[").replace("】", "]")
    text = text.replace("，", ",").replace("。", ".")

    # 去除零宽字符
    text = _RE_CONTROL_CHARS.sub('', text)

    # 压缩多余空行
    text = _RE_MULTI_BLANK.sub('\n\n', text)

    return text.strip()


# ═══════════════════════════════════════════════════════════
#  Prompt 设计
# ═══════════════════════════════════════════════════════════

SYSTEM_PROMPT = """你是专业题库解析AI。将用户提供的文本解析为结构化JSON数组。

=====题型规则=====
- single: 单选题（有ABCD选项，答案为单字母如A）
- multi: 多选题（有ABCD选项，答案为多字母如ABD）
- judge: 判断题（选项为"正确/错误"或"对/错"，答案为A或B）
- fill: 填空题（无选项，答案为短文本如3306、len）
- short: 简答题（无选项，答案为长文本段落）

=====识别优先级（从高到低）=====
1. 明确标注的题型：题号后括号内写明"单选题""多选题""判断题""填空题""简答题"
2. 选项数量：有ABCD选项→选择题；无选项→填空/简答
3. 答案格式：单字母→单选，多字母→多选，中文对错→判断，短文本→填空，长文本→简答

=====答案提取规则（优先级从高到低）=====
1. "正确答案：X"或"参考答案：X"后面的内容
2. "我的答案：X"后面的内容（忽略"得X分"等后缀）
3. 题干括号内的字母，如（ C ）→ 答案为C
4. 无标记时，根据上下文推断

=====必须清理的干扰内容=====
- "N分AI讲解"、"AI讲解"、"N分" → 全部删除
- "我的答案：X正确答案：Y" → 只保留正确答案Y
- "(1)"、"(2)"等编号标记 → 删除
- 教师批阅、批阅时间、得分 → 删除
- 试卷标题、章节标题（如"一.单选题（共10题）"） → 不作为题目
- "难度等级"等元数据行 → 删除

=====题干处理=====
- 删除题干中的内嵌答案，用空括号（  ）替代
- 保留题号（如"1."、"21."）
- 选项内容原样保留，不修改文字

=====JSON格式（字段不能增减）=====
[
  {
    "q_type": "single",
    "content": "1. 题目内容（  ）。",
    "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
    "correct_answer": "C",
    "subject": "学科名称",
    "difficulty": 2,
    "tags": "知识点1,知识点2"
  }
]

=====学科推断规则=====
根据题目内容自动推断学科，常见学科：Python、MySQL、数据结构、计算机网络、操作系统、思想政治、数学、英语等。
如果无法确定，填""。

=====difficulty规则=====
1=基础概念（定义、术语）
2=理解应用（比较、分析、应用）
3=综合分析（设计、评价、综合）

=====输出要求=====
- 只输出JSON数组，不要任何解释文字
- 不要输出```json```代码块标记
- 每道题必须有correct_answer
- 选择题必须有options
- 填空题和简答题options为null"""


REPAIR_PROMPT = """你是题目修复专家。以下题目解析结果有误，请修复。

原始文本：
{raw_block}

当前解析结果：
{parsed_json}

请修复并返回JSON对象（不是数组）：
{{
  "q_type": "single/multi/judge/fill/short",
  "content": "修复后的题干（删除内嵌答案，用空括号替代）",
  "options": {{"A":"...", "B":"..."}} 或 null,
  "correct_answer": "标准化答案",
  "subject": "学科",
  "difficulty": 1-3,
  "tags": "知识点1,知识点2"
}}"""


# ═══════════════════════════════════════════════════════════
#  核心函数
# ═══════════════════════════════════════════════════════════

def _build_client(api_key, base_url=None):
    """构建 OpenAI 客户端。"""
    if OpenAI is None:
        raise ImportError("openai 库未安装，请执行: pip install openai")
    if not api_key:
        raise ValueError("请输入 API Key")
    return OpenAI(api_key=api_key, base_url=base_url or config.AI_DEFAULT_BASE_URL)


def _call_llm(client, model, system_msg, user_msg):
    """统一的 LLM 调用封装。"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=config.AI_TEMPERATURE,
        max_tokens=config.AI_MAX_TOKENS,
    )
    return response.choices[0].message.content.strip()


def _extract_json_array(text):
    """从 LLM 返回中提取 JSON 数组。
    如果找不到有效的 JSON 数组，抛出 ValueError 而非返回原文。
    """
    # 去掉 ```json ... ``` 包裹
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'```\s*$', '', text.strip())
    # 找到第一个 [ 和最后一个 ]
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    # 没有找到 JSON 数组，尝试找 JSON 对象
    obj_start = text.find('{')
    obj_end = text.rfind('}')
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        return text[obj_start:obj_end + 1]
    raise ValueError(f"AI 返回内容中未找到有效的 JSON 结构: {text[:200]}...")


def _normalize_question(q):
    """规范化单道题目的字段。"""
    valid_types = {"single", "multi", "judge", "fill", "short"}

    # 题型
    q_type = q.get("q_type") or q.get("question_type", "single")
    if q_type not in valid_types:
        # 智能修正：有ABCD选项但标为fill→改为single
        if q.get("options") and isinstance(q["options"], dict):
            q_type = "single" if len(q["options"]) <= 4 else "multi"
        else:
            q_type = "fill"

    # 题干
    content = (q.get("content") or q.get("question_content", "")).strip()
    if not content:
        return None

    # 选项
    options = q.get("options")
    if options and isinstance(options, dict):
        # 标准化选项 key 为大写
        options = {k.upper(): v for k, v in options.items()}
    elif options and not isinstance(options, dict):
        options = None

    # 答案
    answer = (q.get("correct_answer") or q.get("answer", "")).strip()
    if not answer:
        return None
    # 选择题答案标准化：去空格、大写、排序
    if q_type in ("single", "multi"):
        letters = re.findall(r'[A-F]', answer.upper())
        if letters:
            answer = "".join(sorted(set(letters)))
    elif q_type == "judge":
        if answer in ("A", "对", "正确", "√", "True", "true"):
            answer = "A"
        elif answer in ("B", "错", "错误", "×", "False", "false"):
            answer = "B"

    # 难度
    difficulty = q.get("difficulty", 2)
    if not isinstance(difficulty, int) or difficulty not in (1, 2, 3):
        difficulty = 2

    # 学科
    subject = str(q.get("subject", "")).strip()
    # 清理学科中的噪音
    subject = re.sub(r'^(一|二|三|四|五|六|七|八|九|十)\s*[.．、]', '', subject).strip()

    # 标签
    tags = q.get("tags", "")
    if isinstance(tags, list):
        tags = ", ".join(str(t).strip() for t in tags if t)

    return {
        "q_type": q_type,
        "content": content,
        "options": options,
        "answer": answer,
        "subject": subject,
        "difficulty": difficulty,
        "tags": tags,
    }


def _validate_questions(questions):
    """校验解析结果，过滤无效题目。"""
    valid = []
    for q in questions:
        if not q:
            continue
        # 选择题必须有选项
        if q["q_type"] in ("single", "multi", "judge") and not q.get("options"):
            continue
        # 选择题答案必须在选项范围内
        if q["q_type"] in ("single", "multi") and q.get("options"):
            valid_keys = set(q["options"].keys())
            for ch in q["answer"]:
                if ch not in valid_keys:
                    # 答案不在选项中，跳过
                    break
            else:
                valid.append(q)
            continue
        valid.append(q)
    return valid


def _split_text(text, max_chars=config.AI_MAX_CHARS):
    """将长文本按段落分割为多个片段。"""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_chars:
            if current:
                chunks.append(current)
            current = line
        else:
            current += "\n" + line
    if current:
        chunks.append(current)
    return chunks


# ═══════════════════════════════════════════════════════════
#  公开接口
# ═══════════════════════════════════════════════════════════

def ai_parse_questions(text, api_key, base_url=None, model=None):
    """调用 LLM 解析题目文本，返回结构化题目列表。

    Parameters
    ----------
    text : str
        待解析的原始文本
    api_key : str
        API 密钥
    base_url : str, optional
        API 地址，默认 DeepSeek
    model : str, optional
        模型名称，默认 deepseek-chat

    Returns
    -------
    list[dict]
        解析后的题目列表
    """
    client = _build_client(api_key, base_url)
    model = model or config.AI_DEFAULT_MODEL

    # 预处理
    text = _preprocess_text(text)

    # 长文本分片处理
    chunks = _split_text(text)
    all_questions = []

    for i, chunk in enumerate(chunks):
        user_msg = f"请解析以下题目文本（第{i+1}部分，共{len(chunks)}部分）：\n\n{chunk}"
        raw_response = _call_llm(client, model, SYSTEM_PROMPT, user_msg)
        json_str = _extract_json_array(raw_response)

        try:
            questions = json.loads(json_str)
        except json.JSONDecodeError as e:
            # 尝试修复常见JSON错误
            json_str = re.sub(r',\s*]', ']', json_str)
            json_str = re.sub(r',\s*}', '}', json_str)
            try:
                questions = json.loads(json_str)
            except json.JSONDecodeError:
                raise ValueError(f"AI 返回的内容无法解析为 JSON：{e}\n\n原始返回：\n{raw_response[:500]}")

        if not isinstance(questions, list):
            continue

        for q in questions:
            normalized = _normalize_question(q)
            if normalized:
                all_questions.append(normalized)

    # 校验
    all_questions = _validate_questions(all_questions)

    return all_questions


def ai_repair_question(raw_block, parsed_dict, api_key, base_url=None, model=None):
    """对单道低置信度题目调用 AI 修复。"""
    client = _build_client(api_key, base_url)
    model = model or config.AI_DEFAULT_MODEL

    parsed_json = json.dumps({
        "q_type": parsed_dict.get("q_type", ""),
        "content": parsed_dict.get("content", ""),
        "options": parsed_dict.get("options"),
        "answer": parsed_dict.get("answer", ""),
    }, ensure_ascii=False, indent=2)

    prompt = REPAIR_PROMPT.format(raw_block=raw_block[:3000], parsed_json=parsed_json)
    raw_response = _call_llm(client, model, "你是题目修复专家。", prompt)

    json_str = _extract_json_array(raw_response)
    # 修复：提取JSON对象而非数组
    obj_match = re.search(r'\{.*\}', json_str, re.DOTALL)
    if obj_match:
        json_str = obj_match.group()

    try:
        repaired = json.loads(json_str)
    except json.JSONDecodeError:
        parsed_dict.setdefault("subject", "")
        parsed_dict.setdefault("difficulty", 1)
        parsed_dict.setdefault("tags", "")
        return parsed_dict

    result = _normalize_question(repaired)
    if result is None:
        parsed_dict.setdefault("subject", "")
        parsed_dict.setdefault("difficulty", 1)
        parsed_dict.setdefault("tags", "")
        return parsed_dict

    return result


# ═══════════════════════════════════════════════════════════
#  多模态 OCR 解析（图片 → 题目）
# ═══════════════════════════════════════════════════════════

_OCR_SYSTEM_PROMPT = """你是一个专业的题目识别助手。请从图片中识别所有题目，并以 JSON 数组格式输出。

每道题目格式：
{
  "q_type": "single|multi|judge|fill|short",
  "content": "题目内容",
  "options": {"A":"选项A内容","B":"选项B内容",...},
  "correct_answer": "正确答案",
  "subject": "学科（如果能识别）",
  "difficulty": 1,
  "tags": ""
}

要求：
1. 准确识别图片中的所有文字内容
2. 正确区分题目类型（单选/多选/判断/填空/简答）
3. 完整提取选项内容和正确答案
4. 如果图片模糊或无法识别，尽量推测并标注
5. 只输出 JSON 数组，不要其他文字"""


def ai_parse_image(image_bytes: bytes, api_key: str = "",
                    base_url: str = "", model: str = "") -> list:
    """使用多模态 LLM 识别图片中的题目。

    Args:
        image_bytes: 图片的二进制内容。
        api_key: API 密钥，为空则使用配置默认值。
        base_url: API 地址，为空则使用配置默认值。
        model: 模型名称，为空则使用配置默认值。

    Returns:
        解析后的题目列表。
    """
    import base64

    api_key = api_key or config.AI_API_KEY
    base_url = base_url or config.AI_DEFAULT_BASE_URL
    model = model or config.OCR_MODEL

    if not api_key:
        raise ValueError("未配置 API Key，请在 .env 文件中设置 DEEPSEEK_API_KEY")

    client = _build_client(api_key, base_url)

    # 将图片编码为 base64
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    # 检测图片类型
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        media_type = "image/png"
    elif image_bytes[:2] == b'\xff\xd8':
        media_type = "image/jpeg"
    elif image_bytes[:4] == b'GIF8':
        media_type = "image/gif"
    elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        media_type = "image/webp"
    else:
        media_type = "image/png"  # 默认

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _OCR_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "请识别这张图片中的所有题目，按 JSON 数组格式输出。"},
                {"type": "image_url", "image_url": {
                    "url": f"data:{media_type};base64,{b64_image}"
                }}
            ]}
        ],
        temperature=0.05,
        max_tokens=config.OCR_MAX_TOKENS,
    )

    content = response.choices[0].message.content
    if not content:
        return []

    # 提取 JSON 数组
    json_str = _extract_json_array(content)
    if not json_str:
        return []

    try:
        raw_list = json.loads(json_str)
    except json.JSONDecodeError:
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        try:
            raw_list = json.loads(json_str)
        except json.JSONDecodeError:
            return []

    results = []
    for item in raw_list:
        normalized = _normalize_question(item)
        if normalized is not None:
            results.append(normalized)
    return results
