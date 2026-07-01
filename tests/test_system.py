"""
智能刷题系统 - 测试用例
覆盖：数据库、解析器、导入器、刷题、统计、收藏、导入历史、质量检查、
      AI解析、页面公共函数、正则预编译、CSV导出、集成测试
运行方式：cd 项目根目录 && python -m pytest tests/ -v
"""

import unittest
import os
import sys
import json
import csv
import io

# 确保能导入项目根目录的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from question_importer import (
    QuestionBankImporter, QualityChecker, ImportReport, generate_fingerprint
)
from practice_session import PracticeSession, QuestionPractice
from parser import (
    parse_text, normalize_answer, check_answer, calc_confidence,
    _levenshtein, _fuzzy_match, clean_text,
    _is_code_line, _extract_options_from_line, _extract_answer,
    _collect_options, split_into_blocks, detect_type,
    QUESTION_START, OPTION_LINE, ANSWER_LINE
)

# 测试数据库放在 data/ 目录
TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


# ═══════════════════════════════════════════════════════════
#  数据库模块测试
# ═══════════════════════════════════════════════════════════

class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        self.test_db = os.path.join(TEST_DATA_DIR, "test_question_bank.db")
        self.db = DatabaseManager(self.test_db)

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_create_tables(self):
        """测试表创建"""
        for table in ['questions', 'practice_records', 'favorites', 'import_history']:
            cur = self.db.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            self.assertIsNotNone(cur.fetchone(), f"表 {table} 未创建")

    def test_foreign_keys(self):
        """测试外键约束"""
        cur = self.db.execute("PRAGMA foreign_keys")
        self.assertEqual(cur.fetchone()[0], 1)

    def test_toggle_favorite(self):
        """测试收藏切换"""
        # 插入测试题目
        cur = self.db.execute(
            "INSERT INTO questions (question_content, correct_answer) VALUES (?, ?)",
            ("测试题", "A")
        )
        self.db.commit()
        qid = cur.lastrowid

        # 收藏
        result = self.db.toggle_favorite(qid)
        self.assertTrue(result)
        self.assertTrue(self.db.is_favorite(qid))

        # 取消收藏
        result = self.db.toggle_favorite(qid)
        self.assertFalse(result)
        self.assertFalse(self.db.is_favorite(qid))

    def test_import_history(self):
        """测试导入历史"""
        self.db.log_import("test.txt", 5, "Python", "regex")
        history = self.db.get_import_history(limit=1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['count'], 5)
        self.assertEqual(history[0]['subject'], "Python")


# ═══════════════════════════════════════════════════════════
#  解析器模块测试
# ═══════════════════════════════════════════════════════════

class TestParser(unittest.TestCase):

    def test_parse_single_choice(self):
        """测试单选题解析"""
        text = "1. 以下哪个是Python的内置函数？\nA. len\nB. length\nC. size\nD. count\n答案：A"
        result = parse_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['q_type'], 'single')
        self.assertEqual(result[0]['answer'], 'A')

    def test_parse_multi_choice(self):
        """测试多选题解析"""
        text = "1. 下列属于Python内置类型的是（多选）\nA. list\nB. dict\nC. array\nD. tuple\n答案：ABD"
        result = parse_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['q_type'], 'multi')
        self.assertEqual(result[0]['answer'], 'ABD')

    def test_parse_fill_blank(self):
        """测试填空题解析"""
        text = "1. _____ 函数用于获取列表长度。\n答案：len"
        result = parse_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['q_type'], 'fill')
        self.assertEqual(result[0]['answer'], 'len')

    def test_parse_short_answer(self):
        """测试简答题解析"""
        text = "1.（简答题）请简述列表和元组的区别。\n答案：列表可变，元组不可变。"
        result = parse_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['q_type'], 'short')

    def test_clean_text_fullwidth(self):
        """测试全角转半角"""
        result = clean_text("１２３ＡＢＣ")
        self.assertIn("123", result)
        self.assertIn("ABC", result)

    def test_calc_confidence_high(self):
        """测试高置信度"""
        parsed = {'q_type': 'single', 'content': 'Python是解释型语言',
                  'options': {'A': '正确', 'B': '错误'}, 'answer': 'A'}
        conf = calc_confidence("1. Python是解释型语言\nA.正确\nB.错误\n答案：A", parsed)
        self.assertGreaterEqual(conf, 0.8)

    def test_calc_confidence_low(self):
        """测试低置信度（无答案无选项）"""
        parsed = {'q_type': 'fill', 'content': '短', 'options': None, 'answer': ''}
        conf = calc_confidence("一些文本", parsed)
        self.assertLess(conf, 0.5)


# ═══════════════════════════════════════════════════════════
#  答案标准化与判断测试
# ═══════════════════════════════════════════════════════════

class TestAnswerCheck(unittest.TestCase):

    def test_single_exact(self):
        """单选题精确匹配"""
        self.assertTrue(check_answer("A", "A", "single"))

    def test_single_case_insensitive(self):
        """单选题大小写不敏感"""
        self.assertTrue(check_answer("a", "A", "single"))

    def test_multi_order_independent(self):
        """多选题顺序无关"""
        self.assertTrue(check_answer("BDA", "ABD", "multi"))

    def test_judge_a_is_correct(self):
        """判断题 A=正确"""
        self.assertTrue(check_answer("A", "√", "judge"))

    def test_judge_b_is_wrong(self):
        """判断题 B=错误"""
        self.assertTrue(check_answer("B", "×", "judge"))

    def test_fill_exact(self):
        """填空题精确匹配"""
        self.assertTrue(check_answer("len", "len", "fill"))

    def test_fill_bracket_ignore(self):
        """填空题忽略括号"""
        self.assertTrue(check_answer("len", "len()", "fill"))

    def test_fill_case_insensitive(self):
        """填空题忽略大小写"""
        self.assertTrue(check_answer("Len", "len", "fill"))

    def test_fill_fuzzy_match(self):
        """填空题模糊匹配"""
        self.assertTrue(check_answer("prnt", "print", "fill"))

    def test_fill_contains(self):
        """填空题包含匹配"""
        self.assertTrue(check_answer("内置函数len", "len", "fill"))

    def test_normalize_multi_sort(self):
        """多选答案排序去重"""
        self.assertEqual(normalize_answer("BDA", "multi"), "ABD")

    def test_normalize_judge(self):
        """判断答案标准化"""
        self.assertEqual(normalize_answer("对", "judge"), "√")
        self.assertEqual(normalize_answer("错", "judge"), "×")


# ═══════════════════════════════════════════════════════════
#  模糊匹配测试
# ═══════════════════════════════════════════════════════════

class TestFuzzyMatch(unittest.TestCase):

    def test_identical(self):
        self.assertTrue(_fuzzy_match("print", "print"))

    def test_one_char_diff(self):
        self.assertTrue(_fuzzy_match("prnt", "print"))

    def test_short_exact_required(self):
        """短字符串要求精确匹配"""
        self.assertFalse(_fuzzy_match("ab", "ac"))

    def test_levenshtein(self):
        self.assertEqual(_levenshtein("kitten", "sitting"), 3)


# ═══════════════════════════════════════════════════════════
#  语义指纹测试
# ═══════════════════════════════════════════════════════════

class TestFingerprint(unittest.TestCase):

    def test_same_content_same_fingerprint(self):
        """相同内容生成相同指纹"""
        fp1 = generate_fingerprint("Python是解释型", {'A': '对', 'B': '错'}, "A")
        fp2 = generate_fingerprint("Python是解释型", {'A': '对', 'B': '错'}, "A")
        self.assertEqual(fp1, fp2)

    def test_option_order_independent(self):
        """选项顺序不同生成相同指纹"""
        fp1 = generate_fingerprint("题目", {'A': '甲', 'B': '乙'}, "A")
        fp2 = generate_fingerprint("题目", {'B': '乙', 'A': '甲'}, "A")
        self.assertEqual(fp1, fp2)

    def test_space_independent(self):
        """空格差异生成相同指纹"""
        fp1 = generate_fingerprint("Python 是 语言", None, "A")
        fp2 = generate_fingerprint("Python是语言", None, "A")
        self.assertEqual(fp1, fp2)

    def test_different_content_different_fingerprint(self):
        """不同内容生成不同指纹"""
        fp1 = generate_fingerprint("题目A", None, "A")
        fp2 = generate_fingerprint("题目B", None, "A")
        self.assertNotEqual(fp1, fp2)


# ═══════════════════════════════════════════════════════════
#  质量检查测试
# ═══════════════════════════════════════════════════════════

class TestQualityChecker(unittest.TestCase):

    def test_empty_content(self):
        """空题干检测"""
        checker = QualityChecker()
        issues = checker.check_all([{'q_type': 'single', 'content': '', 'options': None, 'answer': ''}])
        types = [i[2] for i in issues]
        self.assertIn('empty_content', types)
        self.assertIn('missing_answer', types)

    def test_single_multi_answer(self):
        """单选题多字母答案警告"""
        checker = QualityChecker()
        issues = checker.check_all([{
            'q_type': 'single', 'content': '题目',
            'options': {'A': 'a', 'B': 'b'}, 'answer': 'AB'
        }])
        types = [i[2] for i in issues]
        self.assertIn('single_multi', types)

    def test_auto_fix(self):
        """自动修复"""
        checker = QualityChecker()
        questions = [{'q_type': 'single', 'content': '题目',
                      'options': {'A': 'a', 'B': 'b'}, 'answer': 'AB'}]
        checker.check_all(questions)
        fixed = checker.auto_fix(questions)
        self.assertEqual(fixed, 1)
        self.assertEqual(questions[0]['q_type'], 'multi')


# ═══════════════════════════════════════════════════════════
#  导入器测试
# ═══════════════════════════════════════════════════════════

class TestQuestionImporter(unittest.TestCase):

    def setUp(self):
        self.test_db = os.path.join(TEST_DATA_DIR, "test_importer.db")
        self.importer = QuestionBankImporter()
        self.importer.db = DatabaseManager(self.test_db)

    def tearDown(self):
        self.importer.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_import_valid_questions(self):
        """测试导入有效题目"""
        text = """
1. 以下哪个是Python的内置数据类型？
A. list
B. array
C. vector
D. ArrayList
答案：A

2. Python中用于输出的函数是？
A. print()
B. echo()
C. console.log()
D. printf()
答案：A
"""
        count, errors, report = self.importer.import_from_text(text)
        self.assertEqual(count, 2)
        self.assertEqual(report['imported'], 2)

    def test_import_dedup(self):
        """测试语义去重"""
        text = "1. 测试题\nA. 对\nB. 错\n答案：A"
        count1, _, _ = self.importer.import_from_text(text)
        count2, _, _ = self.importer.import_from_text(text)
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 0)  # 重复跳过

    def test_import_invalid_format(self):
        """测试导入无效格式"""
        text = "这是一段无效的题目格式"
        count, errors, report = self.importer.import_from_text(text)
        self.assertEqual(count, 0)

    def test_import_missing_answer(self):
        """测试导入缺少答案的题目"""
        text = "1. 没有答案的题\nA. 选项A\nB. 选项B"
        count, errors, report = self.importer.import_from_text(text)
        self.assertEqual(count, 0)


# ═══════════════════════════════════════════════════════════
#  刷题练习测试
# ═══════════════════════════════════════════════════════════

class TestPracticeSession(unittest.TestCase):

    def setUp(self):
        self.test_db = os.path.join(TEST_DATA_DIR, "test_practice.db")
        self.db = DatabaseManager(self.test_db)
        for i in range(3):
            self.db.execute(
                "INSERT INTO questions (subject, question_content, options, correct_answer, difficulty) VALUES (?,?,?,?,?)",
                ("Python", f"测试题{i+1}", '{"A":"a","B":"b"}', "A", (i % 3) + 1)
            )
        self.db.commit()
        self.session = PracticeSession()
        self.session.db = self.db

    def tearDown(self):
        self.session.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_random_mode(self):
        questions = self.session.get_questions("random", 2)
        self.assertEqual(len(questions), 2)

    def test_difficulty_mode(self):
        questions = self.session.get_questions("difficulty", 10, difficulty=1)
        self.assertTrue(all(q['difficulty'] == 1 for q in questions))

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            self.session.get_questions("invalid", 1)


class TestQuestionPractice(unittest.TestCase):

    def setUp(self):
        self.test_db = os.path.join(TEST_DATA_DIR, "test_check.db")
        # 清理旧的单例和数据库文件
        import database
        if database._instance is not None:
            try:
                database._instance.conn.close()
            except Exception:
                pass
            database._instance = None
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.db = DatabaseManager(self.test_db)
        self.db.execute(
            "INSERT INTO questions (id, question_content, options, correct_answer) VALUES (?,?,?,?)",
            (1, "测试题", '{"A":"a","B":"b"}', "A")
        )
        self.db.commit()
        self.practice = QuestionPractice()
        self.practice.db = self.db

    def tearDown(self):
        self.practice.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_correct_answer(self):
        self.assertTrue(self.practice.check_answer(1, "A", 5.0))

    def test_wrong_answer(self):
        self.assertFalse(self.practice.check_answer(1, "B", 5.0))

    def test_statistics(self):
        self.practice.check_answer(1, "A", 5.0)
        self.practice.check_answer(1, "B", 3.0)
        stats = self.practice.get_practice_statistics(days=1)
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['correct'], 1)
        self.assertEqual(stats['accuracy'], 50.0)


# ═══════════════════════════════════════════════════════════
#  集成测试
# ═══════════════════════════════════════════════════════════

class TestIntegration(unittest.TestCase):
    """端到端集成测试：从文本导入 → 练习 → 统计 → 错题。"""

    def setUp(self):
        self.test_db = os.path.join(TEST_DATA_DIR, "test_integration.db")
        import database
        if database._instance is not None:
            try:
                for conn in database._instance._connections.values():
                    conn.close()
            except Exception:
                pass
            database._instance = None
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.db = DatabaseManager(self.test_db)

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_full_workflow(self):
        """完整工作流：导入 → 随机练习 → 错题 → 统计。"""
        text = """
1. Python中用于输出的函数是？
A. print()
B. echo()
C. console.log()
D. printf()
答案：A

2. 下列哪些是Python关键字？（多选）
A. if
B. elif
C. when
D. else
答案：ABD

3. Python是一种编译型语言。
A. 正确
B. 错误
答案：B

4. len()函数用于获取列表长度。
答案：正确

5.（简答题）请写出Python中创建空列表的两种方式。
答案：[] 或 list()
"""
        importer = QuestionBankImporter()
        importer.db = self.db
        count, errors, report = importer.import_from_text(text, subject="Python")
        self.assertEqual(count, 5)

        session = PracticeSession()
        session.db = self.db
        questions = session.get_questions("random", 5)
        self.assertEqual(len(questions), 5)

        practice = QuestionPractice()
        practice.db = self.db
        # 用第1题的正确答案验证能答对
        q1_correct = questions[0]['correct_answer']
        self.assertTrue(practice.check_answer(questions[0]['id'], q1_correct, 5.0))
        # 第2题故意答错
        self.assertFalse(practice.check_answer(questions[1]['id'], "ZZ_WRONG_ANSWER", 3.0))

        stats = practice.get_practice_statistics(days=1)
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['correct'], 1)

        wrong_questions = practice.get_wrong_questions(limit=10)
        self.assertGreaterEqual(len(wrong_questions), 1)

        importer.close()
        session.close()
        practice.close()


# ═══════════════════════════════════════════════════════════
#  公共模块测试
# ═══════════════════════════════════════════════════════════

class TestCommonModule(unittest.TestCase):
    """测试 page_modules._common 中的辅助函数。"""

    def test_safe_json_loads_valid(self):
        from page_modules._common import safe_json_loads
        result = safe_json_loads('{"A": "选项A", "B": "选项B"}')
        self.assertEqual(result, {"A": "选项A", "B": "选项B"})

    def test_safe_json_loads_invalid(self):
        from page_modules._common import safe_json_loads
        self.assertEqual(safe_json_loads("无效JSON"), {})
        self.assertEqual(safe_json_loads(None), {})
        self.assertEqual(safe_json_loads(""), {})

    def test_truncate_text(self):
        from page_modules._common import truncate_text
        self.assertEqual(truncate_text("短文本", 100), "短文本")
        self.assertTrue(truncate_text("长" * 120, 100).endswith("..."))
        self.assertEqual(truncate_text("", 10), "")
        self.assertEqual(truncate_text(None, 10), "")


# ═══════════════════════════════════════════════════════════
#  日志模块测试
# ═══════════════════════════════════════════════════════════

class TestLogger(unittest.TestCase):

    def test_get_logger(self):
        from logger import get_logger
        log = get_logger("test")
        self.assertEqual(log.name, "test")


# ═══════════════════════════════════════════════════════════
#  AI 解析模块测试
# ═══════════════════════════════════════════════════════════

class TestAIParserHelpers(unittest.TestCase):
    """测试 ai_parser 中不依赖 API 的辅助函数。"""

    def test_extract_json_array_from_markdown(self):
        from ai_parser import _extract_json_array
        text = '```json\n[{"q_type": "single"}]\n```'
        result = _extract_json_array(text)
        self.assertEqual(result, '[{"q_type": "single"}]')

    def test_extract_json_array_plain(self):
        from ai_parser import _extract_json_array
        text = 'some text [{"q_type": "single"}] more text'
        result = _extract_json_array(text)
        self.assertEqual(result, '[{"q_type": "single"}]')

    def test_extract_json_array_no_json(self):
        from ai_parser import _extract_json_array
        with self.assertRaises(ValueError):
            _extract_json_array("no json here")

    def test_extract_json_object(self):
        from ai_parser import _extract_json_array
        text = 'result: {"q_type": "single", "answer": "A"}'
        result = _extract_json_array(text)
        self.assertIn('"q_type"', result)

    def test_normalize_question_basic(self):
        from ai_parser import _normalize_question
        q = {
            "q_type": "single",
            "content": "题目内容",
            "options": {"a": "选项A", "b": "选项B"},
            "correct_answer": "A",
        }
        result = _normalize_question(q)
        self.assertIsNotNone(result)
        self.assertEqual(result["q_type"], "single")
        self.assertEqual(result["options"]["A"], "选项A")
        self.assertEqual(result["answer"], "A")

    def test_normalize_question_judge(self):
        from ai_parser import _normalize_question
        q = {
            "q_type": "judge",
            "content": "判断题",
            "options": {"A": "正确", "B": "错误"},
            "correct_answer": "对",
        }
        result = _normalize_question(q)
        self.assertEqual(result["answer"], "A")

    def test_normalize_question_empty_content(self):
        from ai_parser import _normalize_question
        result = _normalize_question({"q_type": "single", "content": "", "correct_answer": "A"})
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════
#  密码哈希测试（PBKDF2）
# ═══════════════════════════════════════════════════════════

class TestPasswordHashing(unittest.TestCase):
    """测试密码哈希的安全性。"""

    def test_pbkdf2_hash_format(self):
        from database import DatabaseManager
        hashed = DatabaseManager._hash_password("test123")
        self.assertTrue(hashed.startswith("pbkdf2:"))
        parts = hashed.split(":")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[1], "100000")

    def test_pbkdf2_verify_correct(self):
        from database import DatabaseManager
        hashed = DatabaseManager._hash_password("mypassword")
        self.assertTrue(DatabaseManager._verify_password("mypassword", hashed))

    def test_pbkdf2_verify_wrong(self):
        from database import DatabaseManager
        hashed = DatabaseManager._hash_password("mypassword")
        self.assertFalse(DatabaseManager._verify_password("wrongpassword", hashed))

    def test_legacy_sha256_still_works(self):
        """测试旧版 SHA-256 格式仍然可以验证。"""
        from database import DatabaseManager
        # 模拟旧格式
        import hashlib
        salt = "testsalt123"
        hashed = hashlib.sha256((salt + "oldpassword").encode()).hexdigest()
        legacy_hash = f"{salt}${hashed}"
        self.assertTrue(DatabaseManager._verify_password("oldpassword", legacy_hash))

    def test_different_passwords_different_hashes(self):
        from database import DatabaseManager
        h1 = DatabaseManager._hash_password("pass1")
        h2 = DatabaseManager._hash_password("pass2")
        self.assertNotEqual(h1, h2)

    def test_same_password_different_salts(self):
        from database import DatabaseManager
        h1 = DatabaseManager._hash_password("samepass")
        h2 = DatabaseManager._hash_password("samepass")
        self.assertNotEqual(h1, h2)  # 不同 salt 产生不同 hash


# ═══════════════════════════════════════════════════════════
#  边界条件测试
# ═══════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    """测试边界条件和极端场景。"""

    def test_parse_empty_text(self):
        result = parse_text("")
        self.assertEqual(result, [])

    def test_parse_whitespace_only(self):
        result = parse_text("   \n\n  \t  ")
        self.assertEqual(result, [])

    def test_parse_single_char(self):
        result = parse_text("A")
        self.assertEqual(result, [])

    def test_parse_very_long_content(self):
        """测试超长题干不会崩溃"""
        long_content = "这是一道很长的题目" * 100
        text = f"1. {long_content}\nA. 对\nB. 错\n答案：A"
        result = parse_text(text)
        self.assertEqual(len(result), 1)

    def test_check_answer_empty(self):
        self.assertFalse(check_answer("", "A", "single"))
        self.assertFalse(check_answer("A", "", "single"))

    def test_normalize_answer_empty(self):
        self.assertEqual(normalize_answer("", "single"), "")
        self.assertEqual(normalize_answer("", "multi"), "")
        self.assertEqual(normalize_answer("", "judge"), "")
        self.assertEqual(normalize_answer("", "fill"), "")

    def test_fill_answer_multi_part(self):
        """填空题多答案用分号分隔"""
        self.assertTrue(check_answer("len; list", "len; list", "fill"))

    def test_judge_chinese_variants(self):
        """判断题各种中文变体"""
        self.assertTrue(check_answer("正确", "√", "judge"))  # 正确→√, √==√
        self.assertFalse(check_answer("对", "×", "judge"))   # 对→√, √≠×
        self.assertTrue(check_answer("√", "正确", "judge"))  # √==√
        self.assertTrue(check_answer("错", "×", "judge"))    # 错→×, ×==×

    def test_multi_choice_exact(self):
        """多选题精确匹配（顺序无关）"""
        self.assertTrue(check_answer("ABC", "ABC", "multi"))
        self.assertTrue(check_answer("CBA", "ABC", "multi"))


# ═══════════════════════════════════════════════════════════
#  解析器高级场景测试
# ═══════════════════════════════════════════════════════════

class TestParserAdvanced(unittest.TestCase):
    """测试解析器的高级场景。"""

    def test_parse_inline_options(self):
        """测试同行多选项（每行一个选项）"""
        text = "1. Python内置类型\nA. list\nB. dict\nC. array\nD. tuple\n答案：ABD"
        result = parse_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['q_type'], 'multi')
        self.assertEqual(result[0]['answer'], 'ABD')

    def test_parse_judge_with_options(self):
        """测试带选项的判断题"""
        text = "1. Python是解释型语言\nA. 正确\nB. 错误\n答案：A"
        result = parse_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['q_type'], 'judge')

    def test_parse_multiple_questions(self):
        """测试多道题目的解析"""
        text = """
1. 第一题
A. 选项A
B. 选项B
答案：A

2. 第二题
A. 对
B. 错
答案：B

3. _____ 是Python的输出函数。
答案：print
"""
        result = parse_text(text)
        self.assertGreaterEqual(len(result), 3)

    def test_detect_type_from_label(self):
        """测试从题号括号中检测题型"""
        text = "1.（多选题）下列正确的有\nA. a\nB. b\nC. c\nD. d\n答案：AB"
        result = parse_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['q_type'], 'multi')


if __name__ == '__main__':
    unittest.main()
