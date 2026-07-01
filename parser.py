"""
题目解析模块
支持：
  1. 学习通复制的乱序纯文本（自动清洗 + 识别题型）
  2. PDF 文件（pdfplumber）
  3. DOCX 文件（python-docx）

修复内容：
  - 同行多选项拆分（A.xx B.xx C.xx D.xx）
  - 乱序选项（选项在题目之前）自动关联
  - 代码块内容保护
  - 教师批阅标记完全清理
  - 无题号题目支持
  - 答案范围校验
  - 简答题/论述题类型支持
  - 更多答案格式识别（答案是X、答案X、答：X 等）
"""
import re

# ═══════════════════════════════════════════════════════════
#  预编译正则表达式（模块级，只编译一次）
# ═══════════════════════════════════════════════════════════

# clean_text 使用的模式
_RE_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​‌‍﻿]')
_RE_MULTI_BLANK = re.compile(r'\n{3,}')

# _clean_content 使用的模式
_RE_AI_EXPLAIN = re.compile(r'\d*分?AI讲解')
_RE_SCORE_ONLY = re.compile(r'^\s*\d+分\s*$', re.MULTILINE)
_RE_TYPE_LABEL_PAREN = re.compile(
    r'[（(]\s*(?:单选|多选|判断|填空|简答|论述|问答|简述|解释|分析)\s*题?\s*[,，]?\s*\d*\s*分?\s*[）)]')
_RE_TYPE_LABEL_BRACKET = re.compile(
    r'\[[单多判填简论]选?题?\]|（[单多判填简论]选?题?）|【[单多判填简论]选?题?】')
_RE_BLANK_LINES = re.compile(r'\n{3,}')

# 答案提取使用的模式
_RE_MY_ANS_SINGLE = re.compile(r'我的答案[：:]\s*([A-Fa-f])\s*[:：]')
_RE_MY_ANS_MULTI = re.compile(r'我的答案[：:]\s*([A-Fa-f]{2,})\s*[:；;]')
_RE_MY_ANS_JUDGE = re.compile(r'我的答案[：:]\s*(对|错|正确|错误)\s*[:；;]?')
_RE_MY_ANS_JUDGE2 = re.compile(r'我的答案[：:]\s*(对|错|正确|错误)\s*正确答案')
_RE_PAREN_ANS = re.compile(r'[（(]\s*([A-Fa-f])\s*[）)]\s*$', re.MULTILINE)
_RE_PAREN_MULTI = re.compile(r'[（(]\s*([A-Fa-f]{2,})\s*[）)]')
_RE_PAREN_ANY = re.compile(r'[（(]\s*([A-Fa-f]{1,6})\s*[）)]')
_RE_ANS_LETTERS = re.compile(r'[A-Fa-f]')
_RE_STRIP_PAREN_NUM = re.compile(r'^\(\d+\)\s*')
_RE_BRACKET_CONTENT = re.compile(r'[()（）]')
_RE_ANSWER_SANITIZE = re.compile(r'[\s,，、]+')
_RE_ANSWER_SPLIT = re.compile(r'[,，、;；\s]+')

# 判断题清理
_RE_JUDGE_AI = re.compile(r'.*批阅.*答案.*?(对|错|正确|错误)', re.DOTALL)
_RE_JUDGE_PAREN = re.compile(r'[（(]\s*(对|错|正确|错误)\s*[）)]')

# ═══════════════════════════════════════════════════════════
#  全角→半角 转换表（模块级，只构建一次）
# ═══════════════════════════════════════════════════════════

_FULLWIDTH = (
    "０１２３４５６７８９"
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
)
_HALFWIDTH = (
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)
_TRANS_TABLE = str.maketrans(_FULLWIDTH, _HALFWIDTH)


# ═══════════════════════════════════════════════════════════
#  第一步：文本预处理
# ═══════════════════════════════════════════════════════════

def clean_text(raw: str) -> str:
    text = raw.translate(_TRANS_TABLE)
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("【", "[").replace("】", "]")
    # 去除零宽/控制字符（保留换行）
    text = _RE_CONTROL_CHARS.sub('', text)
    # 超过两个连续空行压为两个
    text = _RE_MULTI_BLANK.sub('\n\n', text)
    return text.strip()


# ═══════════════════════════════════════════════════════════
#  第二步：题目分割
# ═══════════════════════════════════════════════════════════

# 匹配行首题号：1. / 1、/ 第1题 / (1) / 1.(单选题，2 分) 等
QUESTION_START = re.compile(
    r'^(?:第?\s*\d+\s*[题、]|\d+[.．、。]\s*(?:[（(].*?[）)])?)',
    re.MULTILINE
)


# 章节标题检测：一. 单选题 / 二. 填空题 / 三. 判断题 等
_SECTION_HEADER = re.compile(
    r'^[一二三四五六七八九十]+\s*[.．、]\s*(单选|多选|判断|填空|简答|选择|综合)',
    re.MULTILINE
)


def _collect_split_positions(text: str) -> list:
    """收集所有分割点位置（题号 + 章节标题）。"""
    positions = [m.start() for m in QUESTION_START.finditer(text)]
    header_positions = [m.start() for m in _SECTION_HEADER.finditer(text)]
    return sorted(set(positions + header_positions))


def _split_by_positions(text: str, positions: list) -> list:
    """按位置列表将文本分割为块。"""
    blocks = []
    prefix = text[:positions[0]].strip()
    if prefix:
        blocks.append(prefix)
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        block = text[pos:end].strip()
        if block:
            blocks.append(block)
    return blocks


def _merge_orphan_options(blocks: list) -> list:
    """将孤立的选项合并到下一个有题号的块中。"""
    merged = []
    orphan_options = ""
    for block in blocks:
        if QUESTION_START.match(block):
            if orphan_options:
                block = orphan_options + "\n" + block
                orphan_options = ""
            merged.append(block)
        elif _SECTION_HEADER.match(block.strip().split('\n')[0]):
            if orphan_options:
                merged.append(orphan_options)
                orphan_options = ""
            merged.append(block)
        else:
            has_options = bool(OPTION_LINE.search(block))
            if has_options:
                orphan_options = block
            else:
                if orphan_options:
                    orphan_options += "\n" + block
                else:
                    merged.append(block)
    if orphan_options:
        merged.append(orphan_options)
    return merged


def _fix_short_answer_blocks(blocks: list) -> list:
    """简答题答案文本处理：无选项无答案标记的块，将后续文本作为答案。"""
    final = []
    for block in blocks:
        lines = block.split('\n')
        if QUESTION_START.match(block) and not OPTION_LINE.search(block):
            question_line = lines[0]
            rest_lines = [l for l in lines[1:] if l.strip()]
            if rest_lines:
                rest_text = '\n'.join(rest_lines).strip()
                has_ans = bool(ANSWER_LINE.search(rest_text) or ANSWER_LOOSE.search(rest_text))
                starts_with_ans = bool(re.match(r'^(我的答案|正确答案|参考答案|答案)[：:]', rest_text))
                if not has_ans and not starts_with_ans and rest_text:
                    first_line = rest_lines[0].strip()
                    if re.match(r'^\(\d+\)\s*$', first_line):
                        actual_answer = '\n'.join(rest_lines[1:]).strip()
                        if actual_answer:
                            block = question_line + "\n答案：" + actual_answer
                    else:
                        block = question_line + "\n答案：" + rest_text
        final.append(block)
    return final


def split_into_blocks(text: str) -> list:
    """将文本分割为题目块。每个块以题号行开始。
    如果选项出现在题号之前，会将其合并到下一个题目块中。
    如果答案文本出现在题号之后（无"答案："前缀），会合并到上一个题目块。
    """
    positions = _collect_split_positions(text)
    if not positions:
        return [b.strip() for b in text.split('\n\n') if b.strip()]

    blocks = _split_by_positions(text, positions)
    merged = _merge_orphan_options(blocks)
    return _fix_short_answer_blocks(merged)


# ═══════════════════════════════════════════════════════════
#  第三步：单题解析
# ═══════════════════════════════════════════════════════════

# 选项行：A. / A、/ A) / A。 后面跟内容
OPTION_LINE = re.compile(r'^([A-Fa-f])[.．、。）)]\s*(.+)$', re.MULTILINE)
# 匹配裸选项标记（字母+标点，后面无内容或只有空白）
_OPTION_BARE = re.compile(r'^([A-Fa-f])[.．、。）)]\s*$', re.MULTILINE)

# 同行多选项：A.xx B.xx C.xx D.xx 或 A.xx  B.xx  C.xx  D.xx
INLINE_OPTIONS = re.compile(
    r'([A-Fa-f])[.．、。）)]\s*(.+?)(?=\s+[A-Fa-f][.．、。）)]|\s*$)'
)

# 答案行 —— 支持多种格式：
#   答案：X / 正确答案：X / 参考答案：X / 我的答案：X
#   答案是X / 答案X / 答：X
ANSWER_LINE = re.compile(
    r'(?:正确答案|参考答案|我的答案)[ \t]*[：:][ \t]*(.+?)[ \t]*$',
    re.IGNORECASE | re.MULTILINE
)

# 答案标记在单独一行，答案在下一行的格式（优先正确答案/参考答案）
ANSWER_NEXT_LINE = re.compile(
    r'(?:正确答案|参考答案)[ \t]*[：:][ \t]*\n[ \t]*(.+?)[ \t]*$',
    re.IGNORECASE | re.MULTILINE
)

# 我的答案在单独一行，答案在下一行（优先级较低）
MY_ANSWER_NEXT_LINE = re.compile(
    r'我的答案[ \t]*[：:][ \t]*\n[ \t]*(.+?)[ \t]*$',
    re.IGNORECASE | re.MULTILINE
)

# 更宽泛的答案匹配（用于备选）
ANSWER_LOOSE = re.compile(
    r'(?:答案|答)[ \t]*(?:是|[:：])[ \t]*(.+?)[ \t]*$',
    re.IGNORECASE | re.MULTILINE
)

# 最宽松：答案后面直接跟字母，没有冒号（如"答案A"）
ANSWER_BARE = re.compile(
    r'答案\s*([A-Fa-f](?:\s*[A-Fa-f])*)\s*$',
    re.MULTILINE
)

JUDGE_KEYWORDS = re.compile(r'(√|×|对|错|正确|错误|✓|✗|True|False)', re.IGNORECASE)

FILL_BLANK = re.compile(r'_{3,}|_{1,}\s*\(\s*\)\s*_{1,}|（\s*）')

SHORT_ANSWER_LABEL = re.compile(r'[（(]\s*(简答|论述|问答|简述|解释|分析)\s*题?', re.IGNORECASE)

# _extract_answer 中使用的内联正则（预编译）
_RE_PAREN_AFTER_NUM = re.compile(r'^\d+[.．、。]\s*[（(]\s*([A-Fa-f]{1,6})\s*[）)]', re.MULTILINE)
_RE_PAREN_AT_END = re.compile(r'[（(]\s*([A-Fa-f]{1,6})\s*[）)]\s*[。.]?\s*$', re.MULTILINE)

# _collect_options 中使用的内联正则
_RE_INLINE_OPT_START = re.compile(r'(?:^|\s)([A-F])[.．、。）)]\s*')

# _is_code_line 中使用的内联正则
_RE_CODE_PATTERNS = [
    re.compile(r'^(import|from|def|class|if|else|elif|for|while|try|except|finally|with|return|print|raise)'),
    re.compile(r'^[a-zA-Z_]\w*\s*[=\(]'),
    re.compile(r'^\s*(#|//)'),
    re.compile(r'^\s*\{'),
    re.compile(r'^\s*\['),
    re.compile(r'^\s*\('),
]

_JUDGE_VALS = frozenset({'正确', '错误', '对', '错', 'True', 'False', '√', '×'})

# 标题行检测模式
_TITLE_PATTERNS = [
    re.compile(r'^\d{4}[-—]\d{4}'),           # 年份开头
    re.compile(r'^第\s*[一二三四五六七八九十]+'),  # "第一章"等
    re.compile(r'^[期末复习题库考试测验]+'),       # 标题关键词
]

# 教师批阅相关标记
TEACHER_MARKS = re.compile(
    r'(?:教师批阅|批阅时间|批阅教师|得分|得分情况).*',
    re.IGNORECASE
)


def _extract_options_from_line(line: str) -> dict:
    """从一行中提取多个选项，支持同行多选项格式。
    例如：'A.print() B.echo() C.console.log() D.printf()'
    返回：{'A': 'print()', 'B': 'echo()', 'C': 'console.log()', 'D': 'printf()'}
    """
    options = {}
    # 只匹配大写字母A-F作为选项标记，且前面是空格或行首
    option_starts = list(_RE_INLINE_OPT_START.finditer(line))
    if len(option_starts) < 2:
        return options  # 少于2个选项不算同行多选项

    for i, m in enumerate(option_starts):
        key = m.group(1).upper()
        start = m.end()
        end = option_starts[i+1].start() if i+1 < len(option_starts) else len(line)
        value = line[start:end].strip()
        if value:
            options[key] = value
    return options


def _is_code_line(line: str) -> bool:
    """判断一行是否是代码行（非选项行）"""
    stripped = line.strip()
    for pattern in _RE_CODE_PATTERNS:
        if pattern.match(stripped):
            return True
    return False


def _collect_options(block: str) -> dict:
    """从题目块中收集所有选项，支持同行和换行两种格式。"""
    options = {}
    all_lines = [l.strip() for l in block.split('\n')]

    for li, line in enumerate(all_lines):
        if not line:
            continue

        # 跳过明显是代码的行
        if _is_code_line(line):
            continue

        # 跳过题号行
        if QUESTION_START.match(line):
            continue

        # 跳过答案行
        if ANSWER_LINE.match(line) or ANSWER_LOOSE.match(line):
            continue

        # 跳过教师批阅行
        if TEACHER_MARKS.match(line):
            continue

        # 先尝试同行多选项
        inline_opts = _extract_options_from_line(line)
        if len(inline_opts) > 1:
            options.update(inline_opts)
            continue

        # 单行单选项
        m = OPTION_LINE.match(line)
        if m:
            key = m.group(1).upper()
            value = m.group(2).strip()
            if value:
                options[key] = value
            else:
                # 标记为空（如 "A."），尝试取下一行作为选项内容
                for next_line in all_lines[li+1:]:
                    next_stripped = next_line.strip()
                    if next_stripped and not OPTION_LINE.match(next_stripped) \
                       and not _OPTION_BARE.match(next_stripped) \
                       and not ANSWER_LINE.match(next_stripped) \
                       and not ANSWER_LOOSE.match(next_stripped):
                        options[key] = next_stripped
                        break
                    elif next_stripped:
                        break
            continue

        # 裸选项标记（如 "A." 后换行，内容在下一行）
        bare = _OPTION_BARE.match(line)
        if bare:
            key = bare.group(1).upper()
            for next_line in all_lines[li+1:]:
                next_stripped = next_line.strip()
                if next_stripped and not OPTION_LINE.match(next_stripped) \
                   and not _OPTION_BARE.match(next_stripped) \
                   and not ANSWER_LINE.match(next_stripped) \
                   and not ANSWER_LOOSE.match(next_stripped):
                    options[key] = next_stripped
                    break
                elif next_stripped:
                    break

    return options


def _extract_answer(block: str) -> str:
    """从题目块中提取答案，支持多种格式。"""
    # 优先匹配"我的答案"（平台格式，可能含干扰信息）
    # 单字母答案：我的答案:C:xxx
    my_ans_match = _RE_MY_ANS_SINGLE.search(block)
    if my_ans_match:
        return my_ans_match.group(1).upper()

    # 多字母答案：我的答案:ABD:xxx
    my_ans_multi = _RE_MY_ANS_MULTI.search(block)
    if my_ans_multi:
        return my_ans_multi.group(1).upper()

    # 中文判断答案：我的答案:对 或 我的答案:错
    my_ans_judge = _RE_MY_ANS_JUDGE.search(block)
    if my_ans_judge:
        return my_ans_judge.group(1)

    # 中文答案无分隔符：我的答案:对正确答案:对 → 提取"对"
    my_ans_judge_inline = _RE_MY_ANS_JUDGE2.search(block)
    if my_ans_judge_inline:
        return my_ans_judge_inline.group(1)

    # 题号后括号答案格式：1.（ C ）题目内容 或 1. ( ABC ) 题目内容
    paren_after_num = _RE_PAREN_AFTER_NUM.search(block.strip())
    if paren_after_num:
        ans = paren_after_num.group(1).upper()
        if ans.strip():
            return "".join(sorted(set(ans)))

    # 题目末尾括号答案格式：题目内容（ A ）。 或 题目内容(ABCD)
    paren_at_end = _RE_PAREN_AT_END.search(block.strip())
    if paren_at_end:
        ans = paren_at_end.group(1).upper()
        if ans.strip():
            return "".join(sorted(set(ans)))

    # 标准格式：答案：X / 正确答案：X / 参考答案：X（同行）
    ans_match = ANSWER_LINE.search(block)
    if ans_match:
        return ans_match.group(1).strip()

    # 答案标记在单独一行，答案在下一行（优先正确答案）
    ans_next = ANSWER_NEXT_LINE.search(block)
    if ans_next:
        return ans_next.group(1).strip()

    # 我的答案在单独一行，答案在下一行（优先级较低）
    my_ans_next = MY_ANSWER_NEXT_LINE.search(block)
    if my_ans_next:
        return my_ans_next.group(1).strip()

    # 宽松格式：答案是X / 答：X / 答:X
    ans_loose = ANSWER_LOOSE.search(block)
    if ans_loose:
        return ans_loose.group(1).strip()

    # 最宽松：答案后面直接跟字母（如"答案A"、"答案 ABD"）
    ans_bare = ANSWER_BARE.search(block)
    if ans_bare:
        return ans_bare.group(1).strip()

    # 任意位置括号答案（兜底）：围绕（ D  ）这个主题
    # 放在最后，避免干扰上面的显式答案标记
    paren_any = _RE_PAREN_ANY.search(block)
    if paren_any:
        ans = paren_any.group(1).upper()
        if ans.strip():
            return "".join(sorted(set(ans)))

    # 括号答案格式：（C）或 (C) —— 仅在题干末尾
    paren_ans = _RE_PAREN_ANS.search(block)
    if paren_ans:
        return paren_ans.group(1).upper()

    return ""


def _clean_answer(raw_answer: str) -> str:
    """清理提取出的答案文本：去除编号标记、全角转半角、去首尾空白。"""
    if not raw_answer:
        return ""
    ans = raw_answer.strip()
    # 去除编号标记：(1) 、(2) 等
    ans = re.sub(r'^\(\d+\)\s*', '', ans)
    # 全角转半角
    ans = ans.translate(_TRANS_TABLE)
    # 去除首尾空白和分号
    ans = ans.strip().rstrip(';；')
    return ans


def detect_type(block: str, options: dict) -> str:
    """检测题型：single / multi / judge / fill / short"""
    # 先从题号行的括号中提取题型标签
    type_label = re.search(r'[（(]\s*(单选|多选|判断|填空|简答|论述|问答|简述|解释|分析)\s*题?', block)

    if options:
        # 如果有明确的题型标签，优先使用
        if type_label:
            label = type_label.group(1)
            if label == '多选':
                return 'multi'
            if label == '判断':
                return 'judge'
            if label == '填空':
                return 'fill'
            if label == '单选':
                return 'single'
            if label in ('简答', '论述', '问答', '简述', '解释', '分析'):
                return 'short'

        # 从"我的答案"中提取纯字母
        my_ans = re.search(r'我的答案[：:]\s*([A-Fa-f])\s*[:：]', block)
        if my_ans:
            return 'single'

        # 优先匹配 正确答案/参考答案/我的答案 格式
        ans_match = ANSWER_LINE.search(block)
        if ans_match:
            ans_text = ans_match.group(1).strip()
            m = re.match(r'^([A-Fa-f])\s*[:：]', ans_text)
            if m:
                return 'single'
            letters = re.findall(r'[A-F]', ans_text.upper())
            if len(letters) > 1:
                return 'multi'

        # 兜底匹配 答案：XX 格式（ANSWER_LOOSE）
        ans_loose = ANSWER_LOOSE.search(block)
        if ans_loose:
            ans_text = ans_loose.group(1).strip()
            letters = re.findall(r'[A-F]', ans_text.upper())
            if len(letters) > 1:
                return 'multi'

        # 括号内答案判断多选：（ABCD）→ multi
        paren_ans = re.search(r'[（(]\s*([A-Fa-f]{2,})\s*[）)]', block)
        if paren_ans:
            return 'multi'

        if len(options) == 2 and all(v.strip() in _JUDGE_VALS for v in options.values()):
            return 'judge'
        return 'single'

    # 无选项时，判断题型
    # 题目行有问号（如"是什么？""有哪些？"）→ 简答题
    first_line = block.strip().split('\n')[0].strip()
    if re.search(r'[？?]\s*$', first_line):
        return 'short'

    if type_label:
        label = type_label.group(1)
        if label == '判断':
            return 'judge'
        if label in ('单选', '多选'):
            return 'single'
        if label in ('简答', '论述', '问答', '简述', '解释', '分析'):
            return 'short'
        return 'fill'

    if SHORT_ANSWER_LABEL.search(block):
        return 'short'

    if FILL_BLANK.search(block):
        return 'fill'

    # 判断题关键词：仅当答案本身是判断值时才算
    # 避免答案文本中的"正确""是"等词被误判
    if JUDGE_KEYWORDS.search(block):
        ans = _extract_answer(block)
        if ans:
            ans = ans.strip()
            # 明确的判断值直接判定
            if ans in ('√', '×', '对', '错', '正确', '错误', 'True', 'False'):
                return 'judge'
            # A/B 只有在选项也是判断值时才算判断题
            if ans in ('A', 'B'):
                opts = _collect_options(block)
                if opts and all(v.strip() in _JUDGE_VALS for v in opts.values()):
                    return 'judge'

    return 'fill'


def _clean_content(block: str) -> str:
    """清理题目内容，去除选项、答案、教师批阅等标记。
    保留题号，答案位置替换为空括号（  ）。
    """
    content = block

    # 题号后括号答案 → 保留题号，去除答案：1.（ C ）题目 → 1.题目
    content = re.sub(
        r'^(\d+[.．、。])\s*[（(]\s*[A-Fa-f]{1,6}\s*[）)]',
        r'\1', content.strip(), count=1
    )

    # 题目末尾括号答案 → 替换为空括号：题目（ A ）。→ 题目（  ）。
    # 支持多个字母答案如（ABCD）
    content = re.sub(
        r'[（(]\s*[A-Fa-f]{1,6}\s*[）)]',
        '（  ）', content
    )

    # 去除教师批阅相关行（整行删除）
    content = re.sub(r'^.*教师批阅.*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^.*批阅时间.*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^.*批阅教师.*$', '', content, flags=re.MULTILINE)

    # 去除"我的答案"行（含得分信息，整行删除）
    content = re.sub(r'^.*我的答案[：:].*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^.*得\d+分.*$', '', content, flags=re.MULTILINE)

    # 去除"AI讲解"、"N分AI讲解"等平台噪音
    content = _RE_AI_EXPLAIN.sub('', content)
    content = _RE_SCORE_ONLY.sub('', content)

    # 去除答案行（多种格式）
    content = ANSWER_LINE.sub('', content)
    content = ANSWER_LOOSE.sub('', content)
    content = ANSWER_BARE.sub('', content)

    # 去除选项行
    content = OPTION_LINE.sub('', content)

    # 去除题型标签
    content = _RE_TYPE_LABEL_PAREN.sub('', content)
    content = _RE_TYPE_LABEL_BRACKET.sub('', content)

    # 清理多余空白
    content = _RE_BLANK_LINES.sub('\n\n', content)
    content = content.strip()

    return content


def parse_block(block: str) -> dict:
    """解析单个题目块，返回结构化数据。"""
    stripped = block.strip()
    if re.fullmatch(r'[\d\s\n]+', stripped):
        return None

    # 过滤掉太短且没有选项的文本
    if len(stripped) < 5 and not OPTION_LINE.search(stripped):
        return None

    # 过滤掉标题行（如"2025-2026第二学期期末复习题库（2026年5月）"）
    for pat in _TITLE_PATTERNS:
        if pat.match(stripped) and not QUESTION_START.match(stripped):
            return None

    # 收集选项
    options = _collect_options(block)

    # 提取答案（使用多级匹配）
    answer = _clean_answer(_extract_answer(block))

    # 答案标准化（仅当答案是选项字母时）
    stripped_ans = _RE_ANSWER_SANITIZE.sub('', answer)
    if stripped_ans and re.fullmatch(r'[A-Fa-f]+', stripped_ans):
        answer = "".join(sorted(set(l.upper() for l in stripped_ans)))

    # 清理题目内容
    content = _clean_content(block)

    if not content:
        return None

    # 没有题号、没有选项、没有答案的文本，不认为是题目
    has_question_number = bool(QUESTION_START.search(block))
    if not has_question_number and not options and not answer:
        return None

    # 检测题型
    q_type = detect_type(block, options)

    # 答案范围校验（单选题答案不能超出选项范围）
    if q_type == 'single' and options and answer:
        valid_keys = set(options.keys())
        if answer and answer not in valid_keys:
            if len(answer) == 1 and answer.isalpha():
                answer = ""  # 清空无效答案

    # 选择题/判断题没有答案时，不认为是有效题目
    if q_type in ('single', 'multi', 'judge') and options and not answer:
        return None

    # 填空题/简答题没有答案时，也不认为是有效题目
    if q_type in ('fill', 'short') and not answer:
        return None

    return {
        "q_type": q_type,
        "content": content,
        "options": options if options else None,
        "answer": answer,
    }


def parse_text(raw: str) -> list:
    """解析文本，返回题目列表。"""
    cleaned = clean_text(raw)
    blocks = split_into_blocks(cleaned)
    return [q for b in blocks if (q := parse_block(b))]


def calc_confidence(block: str, parsed: dict) -> float:
    """计算单题正则解析置信度（0.0 ~ 1.0）。

    评分维度：
    - 题目内容完整性
    - 答案存在性
    - 选项与题型一致性
    - 题型标签明确性

    注意：block 参数仅用于检测题型标签，核心评分基于 parsed 字典。
    """
    if parsed is None:
        return 0.0

    score = 1.0
    content = parsed.get("content", "")
    answer = parsed.get("answer", "")
    options = parsed.get("options")
    q_type = parsed.get("q_type", "fill")

    # 内容过短
    if len(content) < 10:
        score -= 0.3

    # 无答案
    if not answer:
        score -= 0.4

    # 选择题无选项
    if q_type in ("single", "multi") and not options:
        score -= 0.3

    # 选项数量不足
    if options and len(options) < 2:
        score -= 0.2

    # 单选答案超出选项范围
    if q_type == "single" and options and answer and answer not in options:
        score -= 0.3

    # 有明确题型标签加分（用 parsed.content 检测而非原始 block，减少依赖）
    if q_type in ("single", "multi", "judge", "fill", "short"):
        # 已经成功识别出合理题型，加分
        score += 0.05
    if re.search(r'[（(]\s*(单选|多选|判断|填空|简答)\s*题?', block):
        score += 0.05

    return max(0.0, min(1.0, round(score, 2)))


def parse_text_with_confidence(raw: str) -> list:
    """解析文本，返回带置信度的题目列表。

    Returns
    -------
    list[dict]
        每项包含 q_type, content, options, answer, confidence, raw_block
    """
    cleaned = clean_text(raw)
    blocks = split_into_blocks(cleaned)
    results = []
    for block in blocks:
        parsed = parse_block(block)
        conf = calc_confidence(block, parsed)
        if parsed is not None:
            parsed["confidence"] = conf
            parsed["raw_block"] = block
            results.append(parsed)
        elif conf == 0.0 and len(block.strip()) >= 10:
            # 跳过标题行（parse_block 已返回 None 说明不是题目）
            stripped = block.strip()
            is_title = any(pat.match(stripped) for pat in _TITLE_PATTERNS)
            if is_title or not QUESTION_START.match(stripped):
                continue
            # 正则完全失败但文本块足够长，标记为需要 AI 修复
            results.append({
                "q_type": "fill",
                "content": block.strip()[:200],
                "options": None,
                "answer": "",
                "confidence": 0.0,
                "raw_block": block,
            })
    return results


# ═══════════════════════════════════════════════════════════
#  PDF / DOCX 读取
# ═══════════════════════════════════════════════════════════
#  答案标准化
# ═══════════════════════════════════════════════════════════

def normalize_answer(ans: str, q_type: str) -> str:
    """标准化答案，用于比较"""
    if not ans:
        return ""
    ans = ans.strip()
    if q_type == "judge":
        if ans in ("A", "对", "正确", "√", "True", "true", "✓"):
            return "√"
        if ans in ("B", "错", "错误", "×", "False", "false", "✗"):
            return "×"
        return ans
    if q_type == "multi":
        letters = sorted(set(_RE_ANS_LETTERS.findall(ans.upper())))
        return "".join(letters)
    if q_type == "single":
        return ans.upper()[:1]
    # 填空/简答：去首尾空格，忽略大小写
    return ans.strip().lower()


def _levenshtein(s1: str, s2: str) -> int:
    """计算两个字符串的 Levenshtein 编辑距离。"""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev[j + 1] + 1
            deletions = curr[j] + 1
            substitutions = prev[j] + (c1 != c2)
            curr.append(min(insertions, deletions, substitutions))
        prev = curr
    return prev[-1]


def _fuzzy_match(user: str, correct: str, threshold: float = 0.75) -> bool:
    """模糊匹配：编辑距离 / 较长字符串长度 >= threshold 视为匹配。
    短字符串（<=3字符）要求完全匹配，避免误判。
    """
    if not user or not correct:
        return False
    # 短字符串不做模糊匹配
    if len(user) <= 3 or len(correct) <= 3:
        return user == correct
    dist = _levenshtein(user, correct)
    max_len = max(len(user), len(correct))
    return (dist / max_len) <= (1 - threshold)


def check_answer(user_answer: str, correct_answer: str, q_type: str) -> bool:
    """统一答案判断逻辑，返回用户答案是否正确。

    支持所有题型：single / multi / judge / fill / short
    填空/简答题支持：精确匹配、括号忽略、包含匹配、多答案子集、模糊匹配。
    """
    normalized_user = normalize_answer(user_answer, q_type)
    normalized_correct = normalize_answer(correct_answer, q_type)

    if q_type in ("fill", "short"):
        if normalized_user == normalized_correct:
            return True

        # 去除括号及其内容后比较（如 len() 和 len 视为相同）
        clean_user = _RE_BRACKET_CONTENT.sub('', normalized_user).strip()
        clean_correct = _RE_BRACKET_CONTENT.sub('', normalized_correct).strip()
        if clean_user == clean_correct:
            return True

        # 用户答案包含正确答案，或正确答案包含用户答案
        # 当两个字符串都很短（≤3字符）时跳过包含匹配，避免 "id" 匹配 "hidden" 等误判
        if clean_correct:
            both_short = len(clean_correct) <= 3 and len(clean_user) <= 3
            if not both_short and (clean_correct in clean_user or clean_user in clean_correct):
                return True

        # 多答案模式：逗号/分号分隔后，用户答案是正确答案的子集或超集
        correct_parts = set(_RE_ANSWER_SPLIT.split(clean_correct)) - {''}
        user_parts = set(_RE_ANSWER_SPLIT.split(clean_user)) - {''}
        if correct_parts and user_parts:
            if user_parts == correct_parts:
                return True
            if correct_parts.issubset(user_parts):
                return True

        # 模糊匹配：容忍拼写错误（如 pirnt → print）
        if _fuzzy_match(clean_user, clean_correct):
            return True

        return False

    return normalized_user == normalized_correct


# ═══════════════════════════════════════════════════════════
#  快速测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    sample = """
1、Python是一种解释型语言。
A. 正确
B. 错误
答案：A

2.下列属于Python内置数据类型的是（多选）
A. list
B. dict
C. array
D. tuple
答案：ABD

3、_____ 函数用于获取列表长度。
答案：len

4.以下哪个是合法的Python变量名？
A. 1abc
B. _abc
C. abc!
D. for
答案：B

5.（简答题）请简述Python中列表和元组的区别。
答案：列表是可变的，用方括号表示；元组是不可变的，用圆括号表示。
"""
    for i, q in enumerate(parse_text(sample), 1):
        print(f"\n第{i}题 [{q['q_type']}]")
        print(f"  题干: {q['content']}")
        print(f"  选项: {q['options']}")
        print(f"  答案: {q['answer']}")
