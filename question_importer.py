"""
Smart Quiz System - Question Importer
题目导入器：双层解析引擎、语义去重、质量检查、导入报告。

核心流程：
  原始文本 → 正则解析（高速）→ 置信度评分
      ├── ≥ 0.8 → 直接采纳
      ├── 0.5 ~ 0.8 → AI 修复 + 元数据补全
      └── < 0.5 → AI 重新解析
  → 语义去重 → 质量检查 → 批量入库 → 生成报告
"""
import hashlib
import json
import re
from database import DatabaseManager
from logger import get_logger
from parser import (
    parse_text, parse_text_with_confidence, clean_text, _TRANS_TABLE,
)

logger = get_logger("question_importer")


# ═══════════════════════════════════════════════════════════
#  语义指纹生成
# ═══════════════════════════════════════════════════════════

# 标点统一映射
_PUNCT_MAP = str.maketrans(
    '。？！，、；：“”‘’（）【】',
    '.?!,,;:""\'\'()[]'
)


def generate_fingerprint(content, options=None, answer=""):
    """生成题目的语义指纹，用于鲁棒性去重。

    标准化流程：
    1. 去除所有空白字符
    2. 全角转半角
    3. 统一标点符号
    4. 去除题号前缀
    5. 选项排序后拼接（消除选项顺序差异）
    6. MD5 哈希
    """
    text = content or ""
    text = re.sub(r'\s+', '', text)
    text = text.translate(_TRANS_TABLE)
    text = text.translate(_PUNCT_MAP)
    text = re.sub(
        r'^(第?\s*\d+\s*[题、.．。]|\d+[.．、。]\s*(?:[（(].*?[）)])?)',
        '', text
    )

    opt_str = ""
    if options and isinstance(options, dict):
        sorted_opts = sorted(options.items())
        opt_str = "".join(f"{k}{v}" for k, v in sorted_opts)
        opt_str = re.sub(r'\s+', '', opt_str)
        opt_str = opt_str.translate(_TRANS_TABLE).translate(_PUNCT_MAP)

    answer_clean = re.sub(r'\s+', '', (answer or "")).upper()
    full = f"{text}|{opt_str}|{answer_clean}"
    return hashlib.md5(full.encode('utf-8')).hexdigest()


# ═══════════════════════════════════════════════════════════
#  质量检查器
# ═══════════════════════════════════════════════════════════

class QualityChecker:
    """导入质量自动校验器。"""

    def __init__(self):
        self.issues = []  # [(index, severity, issue_type, message)]

    def check_all(self, questions):
        """对全部题目进行质量校验。"""
        self.issues = []
        for i, q in enumerate(questions):
            self._check_content(i, q)
            self._check_answer(i, q)
            self._check_options(i, q)
            self._check_consistency(i, q)
            self._check_answer_range(i, q)
        return self.issues

    def _check_content(self, idx, q):
        content = (q.get("content") or "").strip()
        if not content:
            self.issues.append((idx, "error", "empty_content", "题干为空"))
        elif len(content) < 5:
            self.issues.append((idx, "warning", "short_content",
                                f"题干过短（{len(content)}字）"))

    def _check_answer(self, idx, q):
        answer = (q.get("answer") or "").strip()
        q_type = q.get("q_type", "single")
        if not answer:
            self.issues.append((idx, "error", "missing_answer", "答案缺失"))
        elif q_type == "single" and len(answer) > 1 and answer.isalpha():
            self.issues.append((idx, "warning", "single_multi",
                                f"单选题答案'{answer}'含多个字母，可能应为多选"))

    def _check_options(self, idx, q):
        q_type = q.get("q_type", "single")
        options = q.get("options")
        if q_type in ("single", "multi"):
            if not options or not isinstance(options, dict):
                self.issues.append((idx, "error", "missing_options",
                                    f"选择题缺少选项"))
            elif len(options) < 2:
                self.issues.append((idx, "warning", "few_options",
                                    f"选项仅{len(options)}个，数量不足"))
        elif q_type == "judge":
            if not options or not isinstance(options, dict):
                self.issues.append((idx, "info", "judge_no_options",
                                    f"判断题无选项（仅靠答案判定）"))

    def _check_consistency(self, idx, q):
        q_type = q.get("q_type", "single")
        answer = (q.get("answer") or "").strip()
        options = q.get("options")
        if q_type == "judge" and answer and answer not in ("A", "B", "√", "×", "对", "错", "正确", "错误"):
            self.issues.append((idx, "warning", "judge_format",
                                f"判断题答案'{answer}'格式异常"))
        if q_type == "fill" and options:
            self.issues.append((idx, "info", "fill_has_opts",
                                "填空题包含选项，可能应为选择题"))

    def _check_answer_range(self, idx, q):
        q_type = q.get("q_type", "single")
        options = q.get("options")
        answer = (q.get("answer") or "").strip()
        if q_type in ("single", "multi") and options and answer:
            valid = set(options.keys())
            for ch in answer:
                if ch not in valid:
                    self.issues.append((idx, "error", "answer_range",
                                        f"答案'{answer}'中'{ch}'不在选项{valid}内"))
                    break

    def auto_fix(self, questions):
        """对可自动修复的问题进行批量修复。返回修复数量。"""
        fixed = 0
        for idx, severity, issue_type, msg in self.issues:
            q = questions[idx]
            if issue_type == "single_multi":
                q["q_type"] = "multi"
                fixed += 1
            elif issue_type == "judge_format":
                from parser import normalize_answer
                q["answer"] = normalize_answer(q["answer"], "judge")
                fixed += 1
            elif issue_type == "fill_has_opts":
                q["options"] = None
                fixed += 1
        return fixed

    def get_summary(self):
        """返回质量检查摘要。"""
        errors = sum(1 for _, s, _, _ in self.issues if s == "error")
        warnings = sum(1 for _, s, _, _ in self.issues if s == "warning")
        infos = sum(1 for _, s, _, _ in self.issues if s == "info")
        return {"errors": errors, "warnings": warnings, "infos": infos,
                "total_issues": len(self.issues)}


# ═══════════════════════════════════════════════════════════
#  导入报告
# ═══════════════════════════════════════════════════════════

class ImportReport:
    """导入结果报告。"""

    def __init__(self):
        self.total = 0
        self.imported = 0
        self.skipped_dup = 0
        self.skipped_quality = 0
        self.failed = 0
        self.repaired_by_ai = 0
        self.dup_details = []      # [(index, question_content, matched_id)]
        self.fail_details = []     # [(index, question_content, error_msg)]
        self.quality_issues = []   # QualityChecker.issues

    def to_dict(self):
        return {
            "total": self.total,
            "imported": self.imported,
            "skipped_dup": self.skipped_dup,
            "skipped_quality": self.skipped_quality,
            "failed": self.failed,
            "repaired_by_ai": self.repaired_by_ai,
            "dup_details": self.dup_details,
            "fail_details": self.fail_details,
            "quality_issues": self.quality_issues,
        }

    def summary_text(self):
        """生成人类可读的报告摘要。"""
        lines = [
            f"📊 导入报告",
            f"  总计：{self.total} 题",
            f"  ✅ 成功导入：{self.imported} 题",
            f"  ⏭️ 重复跳过：{self.skipped_dup} 题",
            f"  ⚠️ 质量跳过：{self.skipped_quality} 题",
            f"  ❌ 导入失败：{self.failed} 题",
        ]
        if self.repaired_by_ai:
            lines.append(f"  🤖 AI 修复：{self.repaired_by_ai} 题")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  AI 兜底修复核心逻辑（可被 import_page.py 复用）
# ═══════════════════════════════════════════════════════════

def ai_fallback_core(parsed, api_key, base_url=None, model=None,
                     on_progress=None):
    """AI 兜底修复核心逻辑（可被 import_page.py 复用）。

    Parameters
    ----------
    parsed : list[dict]
        带置信度的题目列表（就地修改）
    api_key, base_url, model : API 配置
    on_progress : callable, optional
        进度回调 on_progress(done, total, message)

    Returns
    -------
    int
        AI 修复的题目数量
    """
    from ai_parser import ai_repair_question, ai_parse_questions

    need_repair = []
    need_reparse = []

    for i, q in enumerate(parsed):
        conf = q.get("confidence", 1.0)
        if conf >= QuestionBankImporter.CONF_HIGH:
            continue
        elif conf >= QuestionBankImporter.CONF_LOW:
            need_repair.append(i)
        else:
            need_reparse.append(i)

    total = len(need_repair) + len(need_reparse)
    if total == 0:
        return 0

    done = 0
    repaired_count = 0

    # AI 修复低置信度题目
    for idx in need_repair:
        if on_progress:
            on_progress(done, total, f"AI 修复中... ({done+1}/{total})")
        try:
            raw_block = parsed[idx].get("raw_block", parsed[idx].get("content", ""))
            result = ai_repair_question(
                raw_block, parsed[idx], api_key, base_url, model
            )
            result["confidence"] = 1.0
            result.pop("raw_block", None)
            parsed[idx] = result
            repaired_count += 1
        except Exception as e:
            logger.warning("AI 修复第 %d 题失败: %s", idx, e)
        done += 1

    # AI 重新解析极低置信度题目
    if need_reparse:
        if on_progress:
            on_progress(done, total, "AI 重新解析中...")
        raw_blocks = [parsed[i].get("raw_block", "") for i in need_reparse]
        combined = "\n\n".join(raw_blocks)
        try:
            ai_results = ai_parse_questions(combined, api_key, base_url, model)
            for j, idx in enumerate(need_reparse):
                if j < len(ai_results):
                    ai_results[j]["confidence"] = 1.0
                    ai_results[j].pop("raw_block", None)
                    parsed[idx] = ai_results[j]
                    repaired_count += 1
        except Exception as e:
            logger.warning("AI 批量重新解析失败: %s", e)

    if on_progress:
        on_progress(total, total, f"✅ AI 处理完成，共修复 {repaired_count} 道题目")

    return repaired_count


class QuestionBankImporter:
    """题目导入器，支持双层解析、语义去重、质量检查。"""

    # 置信度阈值
    CONF_HIGH = 0.8    # ≥ 直接采纳
    CONF_LOW = 0.5     # < AI 重新解析

    def __init__(self):
        self.db = DatabaseManager()

    # ── 公开接口（保持兼容） ──

    def import_from_text(self, text, subject="", api_key=None,
                         base_url=None, model=None):
        """从文本导入题目。保持原有接口兼容。"""
        report = ImportReport()
        parsed = parse_text_with_confidence(text)
        report.total = len(parsed)

        if not parsed:
            return 0, ["未能识别出任何题目"], report.to_dict()

        if api_key:
            repaired = ai_fallback_core(parsed, api_key, base_url, model)
            report.repaired_by_ai = repaired
            for q in parsed:
                q.pop("raw_block", None)

        for q in parsed:
            if subject:
                q["subject"] = subject
            elif not q.get("subject"):
                q["subject"] = ""

        count, errors = self._import_with_checks(parsed, "手动粘贴", report)

        if count > 0:
            self.db.log_import("手动粘贴", count, subject,
                               "dual" if api_key else "regex")

        return count, errors, report.to_dict()

    def import_from_file(self, filepath, subject="", api_key=None,
                         base_url=None, model=None):
        """从文件导入题目。保持原有接口兼容。"""
        import os

        # 图片文件：使用多模态 LLM 直接识别
        img_exts = (".png", ".jpg", ".jpeg", ".bmp")
        if filepath.lower().endswith(img_exts):
            if not api_key:
                raise ValueError("图片导入需要配置 API Key")
            from ai_parser import ai_parse_image
            with open(filepath, "rb") as f:
                image_bytes = f.read()
            parsed = ai_parse_image(image_bytes, api_key, base_url, model)
            source = os.path.basename(filepath)
            report = ImportReport()
            report.total = len(parsed)
            if not parsed:
                return 0, ["未能从图片中识别出任何题目"], report.to_dict()
            for q in parsed:
                if subject:
                    q["subject"] = subject
                elif not q.get("subject"):
                    q["subject"] = ""
            count, errors = self._import_with_checks(parsed, source, report)
            if count > 0:
                self.db.log_import(source, count, subject, "ocr")
            return count, errors, report.to_dict()

        if filepath.lower().endswith(".pdf"):
            raw_text = self._extract_pdf(filepath)
        elif filepath.lower().endswith(".docx"):
            raw_text = self._extract_docx(filepath)
        elif filepath.lower().endswith(".doc"):
            raise ValueError("不支持旧版 .doc 格式，请将其另存为 .docx 后再导入。")
        else:
            raise ValueError(f"不支持的文件格式：{filepath}")

        source = os.path.basename(filepath)
        report = ImportReport()

        parsed = parse_text_with_confidence(raw_text)
        report.total = len(parsed)

        if not parsed:
            return 0, ["未能从文件中识别出任何题目"], report.to_dict()

        if api_key:
            repaired = ai_fallback_core(parsed, api_key, base_url, model)
            report.repaired_by_ai = repaired
            for q in parsed:
                q.pop("raw_block", None)

        for q in parsed:
            if subject:
                q["subject"] = subject
            elif not q.get("subject"):
                q["subject"] = ""

        count, errors = self._import_with_checks(parsed, source, report)

        if count > 0:
            self.db.log_import(source, count, subject,
                               "dual" if api_key else "regex")

        return count, errors, report.to_dict()

    def _insert_questions(self, questions, source=""):
        """保持原有接口兼容（供 import_page.py 直接调用）。"""
        report = ImportReport()
        report.total = len(questions)
        count, errors = self._import_with_checks(questions, source, report)
        return count, errors, report.to_dict()

    # ── 内部方法 ──

    def _import_with_checks(self, questions, source, report):
        """语义去重 + 质量检查 + 批量入库。"""
        # 1. 质量检查
        checker = QualityChecker()
        issues = checker.check_all(questions)
        report.quality_issues = issues

        # 过滤掉有 error 级别问题的题目
        error_indices = {idx for idx, severity, _, _ in issues if severity == "error"}
        valid_questions = []
        for i, q in enumerate(questions):
            if i in error_indices:
                report.skipped_quality += 1
                report.fail_details.append((i, q.get("content", "")[:50], "质量检查不通过"))
            else:
                valid_questions.append(q)

        # 2. 语义去重 + 入库（事务保护）
        count = 0
        errors = []
        critical_error = False

        # 开启事务
        self.db.execute("BEGIN TRANSACTION")
        try:
            for q in valid_questions:
                try:
                    fp = generate_fingerprint(
                        q.get("content", ""),
                        q.get("options"),
                        q.get("answer", "")
                    )

                    # 指纹去重
                    existing = self.db.execute(
                        "SELECT id, question_content FROM questions WHERE fingerprint = ?",
                        (fp,)
                    ).fetchone()

                    if existing:
                        report.skipped_dup += 1
                        report.dup_details.append(
                            (count + report.skipped_dup,
                             q.get("content", "")[:50],
                             existing["id"])
                        )
                        continue

                    # 入库
                    self.db.execute(
                        """INSERT INTO questions
                           (subject, question_content, options, correct_answer,
                            difficulty, question_type, source, tags, chapter, fingerprint)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            q.get("subject", ""),
                            q["content"],
                            json.dumps(q.get("options") or {}, ensure_ascii=False),
                            q["answer"],
                            q.get("difficulty", 1),
                            q.get("q_type", "single"),
                            source,
                            q.get("tags", ""),
                            q.get("chapter", ""),
                            fp,
                        )
                    )
                    count += 1
                except Exception as exc:
                    report.failed += 1
                    report.fail_details.append(
                        (count + report.failed, q.get("content", "")[:50], str(exc))
                    )
                    errors.append(str(exc))
                    # 数据库级错误（非数据问题）触发回滚
                    if "database" in str(exc).lower() or "locked" in str(exc).lower():
                        critical_error = True
                        break

            if critical_error:
                self.db.execute("ROLLBACK")
                count = 0
                errors.append("⚠️ 数据库异常，已回滚所有操作")
            else:
                self.db.execute("COMMIT")
        except Exception as outer_exc:
            self.db.execute("ROLLBACK")
            count = 0
            errors.append(f"⚠️ 导入异常已回滚：{outer_exc}")

        report.imported = count
        if report.skipped_dup > 0:
            errors.append(f"跳过 {report.skipped_dup} 道重复题目")

        return count, errors

    def _extract_pdf(self, filepath):
        """从 PDF 提取纯文本。"""
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            text = "\n".join(t for page in pdf.pages if (t := page.extract_text()))
        return text or ""

    def _extract_docx(self, filepath):
        """从 DOCX 提取纯文本。"""
        from docx import Document
        doc = Document(filepath)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return text or ""

    def close(self):
        """关闭数据库连接。"""
        self.db.close()
