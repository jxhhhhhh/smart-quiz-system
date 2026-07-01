"""
Smart Quiz System - Practice Session
Provides question retrieval by mode and answer checking with statistics.
"""
import json
from database import DatabaseManager
from parser import normalize_answer, check_answer


class PracticeSession:
    """Fetches questions for the user according to the chosen practice mode.

    Modes
    -----
    random     -- pick *count* questions at random from the full pool
    wrong      -- pick questions the user has previously answered incorrectly
    difficulty -- pick questions that match the requested difficulty level
    """

    VALID_MODES = ("random", "wrong", "difficulty")

    def __init__(self):
        self.db = DatabaseManager()

    def get_questions(self, mode, count, difficulty=None, q_type=None, subject=None):
        """Return up to *count* question rows (as dicts) for the given *mode*."""
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Choose from {self.VALID_MODES}")

        if mode == "difficulty" and difficulty is None:
            raise ValueError("A difficulty level must be provided for 'difficulty' mode")

        type_clause = ""
        type_params = []
        if q_type:
            type_clause += " AND question_type = ?"
            type_params.append(q_type)
        if subject:
            type_clause += " AND subject = ?"
            type_params.append(subject)

        if mode == "random":
            rows = self.db.execute(
                f"SELECT * FROM questions WHERE 1=1{type_clause} ORDER BY RANDOM() LIMIT ?",
                type_params + [count],
            ).fetchall()

        elif mode == "wrong":
            rows = self.db.execute(
                f"""
                SELECT q.*
                FROM questions q
                JOIN (
                    SELECT question_id, SUM(1 - is_correct) AS wrong_count
                    FROM practice_records
                    GROUP BY question_id
                    HAVING wrong_count > 0
                ) r ON q.id = r.question_id
                WHERE 1=1{type_clause}
                ORDER BY r.wrong_count DESC
                LIMIT ?
                """,
                type_params + [count],
            ).fetchall()

        else:  # difficulty
            rows = self.db.execute(
                f"SELECT * FROM questions WHERE difficulty = ?{type_clause} ORDER BY RANDOM() LIMIT ?",
                [difficulty] + type_params + [count],
            ).fetchall()

        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row):
        """Convert a sqlite3.Row into a plain dict, decoding the JSON options."""
        d = dict(row)
        try:
            d["options"] = json.loads(d["options"])
        except (json.JSONDecodeError, TypeError):
            d["options"] = {}

        if d.get("question_type") == "judge" and not d["options"]:
            d["options"] = {"A": "正确", "B": "错误"}

        if d.get("question_type") in ("fill", "short") and not d["options"]:
            d["options"] = {}

        return d

    def close(self):
        """关闭数据库连接。CLI/测试场景下调用；Web 界面由 get_db() 缓存管理生命周期，无需手动调用。"""
        self.db.close()


class QuestionPractice:
    """Handles answer checking and practice statistics for individual questions."""

    def __init__(self):
        self.db = DatabaseManager()

    def check_answer(self, question_id, user_answer, time_spent=0.0):
        """Check *user_answer* against the stored correct answer."""
        row = self.db.execute(
            "SELECT correct_answer, question_type FROM questions WHERE id = ?",
            (question_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Question id {question_id} not found")

        q_type = row["question_type"] or "single"
        correct = row["correct_answer"]

        is_correct = int(check_answer(user_answer, correct, q_type))
        normalized_user = normalize_answer(user_answer, q_type)

        self.db.execute(
            "INSERT INTO practice_records (question_id, user_answer, is_correct, time_spent) VALUES (?, ?, ?, ?)",
            (question_id, normalized_user, is_correct, time_spent),
        )
        self.db.commit()

        return bool(is_correct)

    def get_practice_statistics(self, days=30):
        """Calculate practice statistics for the last *days* days."""
        row = self.db.execute(
            """SELECT COUNT(*) AS total, COALESCE(SUM(is_correct), 0) AS correct
               FROM practice_records
               WHERE practice_date >= datetime('now', 'localtime', ?)""",
            (f"-{days} days",),
        ).fetchone()

        total = row["total"]
        correct = row["correct"]
        accuracy = (correct / total * 100) if total > 0 else 0.0
        return {"total": total, "correct": correct, "accuracy": round(accuracy, 2)}

    def get_accuracy_by_type(self, days=30):
        """Calculate accuracy grouped by question type."""
        rows = self.db.execute(
            """SELECT q.question_type, COUNT(*) AS total,
                      COALESCE(SUM(r.is_correct), 0) AS correct
               FROM practice_records r
               JOIN questions q ON r.question_id = q.id
               WHERE r.practice_date >= datetime('now', 'localtime', ?)
               GROUP BY q.question_type""",
            (f"-{days} days",),
        ).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            total = d["total"]
            d["accuracy"] = round((d["correct"] / total * 100) if total > 0 else 0, 2)
            result.append(d)
        return result

    def get_wrong_questions(self, limit=20):
        """获取错题列表，按错误次数排序"""
        rows = self.db.execute(
            """SELECT q.*, r.wrong_count, r.last_wrong_date
               FROM questions q
               JOIN (
                   SELECT question_id, SUM(1 - is_correct) AS wrong_count,
                          MAX(practice_date) AS last_wrong_date
                   FROM practice_records
                   GROUP BY question_id
                   HAVING wrong_count > 0
               ) r ON q.id = r.question_id
               ORDER BY r.wrong_count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            try:
                d["options"] = json.loads(d["options"])
            except (json.JSONDecodeError, TypeError):
                d["options"] = {}
            result.append(d)
        return result

    def get_recent_records(self, limit=10):
        """获取最近的答题记录"""
        rows = self.db.execute(
            """SELECT r.*, q.question_content, q.correct_answer, q.question_type
               FROM practice_records r
               JOIN questions q ON r.question_id = q.id
               ORDER BY r.practice_date DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_daily_stats(self, days=7):
        """获取每日统计数据（用于图表）"""
        rows = self.db.execute(
            """SELECT DATE(practice_date) AS date, COUNT(*) AS total,
                      SUM(is_correct) AS correct
               FROM practice_records
               WHERE practice_date >= datetime('now', 'localtime', ?)
               GROUP BY DATE(practice_date)
               ORDER BY date""",
            (f"-{days} days",),
        ).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            d["accuracy"] = round((d["correct"] / d["total"] * 100) if d["total"] > 0 else 0, 2)
            result.append(d)
        return result

    def close(self):
        """关闭数据库连接（CLI/测试用，Web 界面不要调用）。"""
        self.db.close()
