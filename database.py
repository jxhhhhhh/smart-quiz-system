"""
Smart Quiz System - Database Module
Manages SQLite database connection and schema creation for the question bank.
支持单例模式：多次实例化只创建一个连接。

线程安全：使用 WAL 模式 + 每线程独立连接池。
"""

import json
import sqlite3
import os
import threading
from logger import get_logger
from config import DB_PATH

logger = get_logger("database")

# 模块级单例引用
_instance = None
_instance_lock = threading.Lock()


class DatabaseManager:
    """Centralised database manager.  Every other module should obtain a
    connection through this class rather than calling sqlite3 directly.

    采用单例模式：相同 db_name 只创建一次连接，避免重复开销。
    线程安全：每个线程持有独立的 sqlite3 连接，使用 WAL 模式避免锁冲突。
    """

    def __new__(cls, db_name=None):
        global _instance
        target = db_name or DB_PATH
        # 双重检查锁定：外层无锁快速路径
        if _instance is not None and _instance.db_name == target:
            return _instance
        with _instance_lock:
            if _instance is not None and _instance.db_name == target:
                return _instance
            inst = super().__new__(cls)
            inst.db_name = target
            inst._lock = threading.Lock()
            inst._connections = {}  # thread_id -> sqlite3.Connection
            # 主连接用于初始化 schema
            main_conn = sqlite3.connect(target, check_same_thread=False)
            main_conn.row_factory = sqlite3.Row
            main_conn.execute("PRAGMA journal_mode=WAL")
            main_conn.execute("PRAGMA foreign_keys=ON")
            inst._main_conn = main_conn
            inst._main_cursor = main_conn.cursor()
            inst._thread_id = threading.get_ident()
            inst._connections[inst._thread_id] = main_conn
            inst.create_tables()
            logger.info("数据库连接已创建（WAL模式）: %s", target)
            _instance = inst
        return _instance

    def __init__(self, db_name=None):
        # 实际初始化在 __new__ 中完成，__init__ 仅做兼容
        pass

    def _get_conn(self):
        """获取当前线程的数据库连接（线程安全）。
        定期清理已终止线程的连接，防止连接泄漏。
        """
        import gc
        tid = threading.get_ident()
        if tid not in self._connections:
            # 清理已不存在的线程的连接
            dead_tids = [t for t in self._connections if t != self._thread_id
                         and t not in {th.ident for th in threading.enumerate()}]
            for dead_tid in dead_tids:
                try:
                    self._connections.pop(dead_tid).close()
                except Exception:
                    pass
            conn = sqlite3.connect(self.db_name, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._connections[tid] = conn
        return self._connections[tid]

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def _add_column_if_missing(self, table, column, col_def):
        """Add a column to *table* if it doesn't already exist.
        表名和列名通过白名单校验，防止注入。
        """
        import re
        # 校验标识符：仅允许字母、数字、下划线
        ident_re = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
        if not ident_re.match(table) or not ident_re.match(column):
            raise ValueError(f"非法标识符: table={table}, column={column}")
        conn = self._get_conn()
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")

    def create_tables(self):
        """Create all required tables and indexes if they do not exist."""
        conn = self._get_conn()

        # -- questions table ------------------------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                subject          TEXT    NOT NULL DEFAULT '',
                question_content TEXT    NOT NULL,
                options          TEXT    NOT NULL DEFAULT '[]',
                correct_answer   TEXT    NOT NULL,
                difficulty       INTEGER NOT NULL DEFAULT 1,
                tags             TEXT    NOT NULL DEFAULT '',
                ai_enhanced      INTEGER NOT NULL DEFAULT 0,
                question_type    TEXT    NOT NULL DEFAULT 'single',
                source           TEXT    NOT NULL DEFAULT '',
                created_at       TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        # -- Migrate: add columns that may be missing in older databases ----
        self._add_column_if_missing("questions", "question_type", "TEXT NOT NULL DEFAULT 'single'")
        self._add_column_if_missing("questions", "source", "TEXT NOT NULL DEFAULT ''")
        self._add_column_if_missing("questions", "chapter", "TEXT NOT NULL DEFAULT ''")
        self._add_column_if_missing("questions", "fingerprint", "TEXT NOT NULL DEFAULT ''")

        # -- practice_records table -----------------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS practice_records (
                record_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id    INTEGER NOT NULL,
                user_answer    TEXT    NOT NULL,
                is_correct     INTEGER NOT NULL DEFAULT 0,
                time_spent     REAL    NOT NULL DEFAULT 0.0,
                practice_date  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        """)

        # -- favorites table (题目收藏) ------------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL UNIQUE,
                created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        """)

        # -- import_history table (导入历史) --------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT NOT NULL DEFAULT '',
                count       INTEGER NOT NULL DEFAULT 0,
                subject     TEXT NOT NULL DEFAULT '',
                parse_mode  TEXT NOT NULL DEFAULT 'regex',
                imported_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        # -- users table (用户管理) ----------------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT    NOT NULL UNIQUE,
                password_hash   TEXT    NOT NULL,
                display_name    TEXT    NOT NULL DEFAULT '',
                role            TEXT    NOT NULL DEFAULT 'user',
                created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        # -- practice_sessions table (练习进度持久化) -----------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS practice_sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key     TEXT    NOT NULL DEFAULT 'default',
                questions_json  TEXT    NOT NULL DEFAULT '[]',
                current_index   INTEGER NOT NULL DEFAULT 0,
                score           INTEGER NOT NULL DEFAULT 0,
                mode            TEXT    NOT NULL DEFAULT 'random',
                settings_json   TEXT    NOT NULL DEFAULT '{}',
                created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        # -- Migrate: add user_id columns to existing tables ----------------
        self._add_column_if_missing("practice_records", "user_id", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing("favorites", "user_id", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing("import_history", "user_id", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing("practice_sessions", "user_id", "INTEGER NOT NULL DEFAULT 0")

        # -- Indexes for common query patterns ------------------------------
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_subject
            ON questions(subject)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_difficulty
            ON questions(difficulty)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_records_question_id
            ON practice_records(question_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_records_practice_date
            ON practice_records(practice_date)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_fingerprint
            ON questions(fingerprint)
        """)

        conn.commit()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def execute(self, sql, params=None):
        """Thread-safe execute wrapper."""
        conn = self._get_conn()
        with self._lock:
            if params:
                return conn.execute(sql, params)
            return conn.execute(sql)

    def commit(self):
        """Thread-safe commit wrapper."""
        with self._lock:
            self._get_conn().commit()

    def rollback(self):
        """Thread-safe rollback wrapper."""
        with self._lock:
            try:
                self._get_conn().rollback()
            except Exception:
                pass  # 如果没有活跃事务，忽略

    def close(self):
        """Close all underlying connections and clear singleton."""
        global _instance
        with self._lock:
            for conn in self._connections.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()
            if _instance is self:
                _instance = None
            logger.info("数据库连接已关闭")

    def delete_question(self, question_id):
        """Delete a question and its related practice records."""
        conn = self._get_conn()
        with self._lock:
            conn.execute(
                "DELETE FROM practice_records WHERE question_id = ?", (question_id,)
            )
            conn.execute(
                "DELETE FROM favorites WHERE question_id = ?", (question_id,)
            )
            conn.execute(
                "DELETE FROM questions WHERE id = ?", (question_id,)
            )
            conn.commit()
            logger.info("已删除题目 id=%d 及其关联记录", question_id)

    # ── 练习记录（绑定 user_id） ──

    def insert_practice_record(self, question_id, user_answer, is_correct,
                               time_spent, user_id=0):
        """插入一条答题记录。"""
        conn = self._get_conn()
        with self._lock:
            conn.execute(
                """INSERT INTO practice_records
                   (question_id, user_answer, is_correct, time_spent, user_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (question_id, user_answer, is_correct, time_spent, user_id),
            )
            conn.commit()

    # ── 收藏相关 ──

    def toggle_favorite(self, question_id, user_id=0):
        """切换收藏状态，返回 True=已收藏，False=已取消。"""
        conn = self._get_conn()
        with self._lock:
            existing = conn.execute(
                "SELECT id FROM favorites WHERE question_id = ? AND user_id = ?",
                (question_id, user_id)
            ).fetchone()
            if existing:
                conn.execute(
                    "DELETE FROM favorites WHERE question_id = ? AND user_id = ?",
                    (question_id, user_id)
                )
                conn.commit()
                return False
            else:
                conn.execute(
                    "INSERT INTO favorites (question_id, user_id) VALUES (?, ?)",
                    (question_id, user_id)
                )
                conn.commit()
                return True

    def is_favorite(self, question_id, user_id=0):
        """检查题目是否已收藏。"""
        conn = self._get_conn()
        with self._lock:
            row = conn.execute(
                "SELECT id FROM favorites WHERE question_id = ? AND user_id = ?",
                (question_id, user_id)
            ).fetchone()
            return row is not None

    def get_favorite_ids(self, user_id=0):
        """获取所有收藏的题目 ID 集合。"""
        conn = self._get_conn()
        with self._lock:
            rows = conn.execute(
                "SELECT question_id FROM favorites WHERE user_id = ?",
                (user_id,)
            ).fetchall()
            return {r[0] for r in rows}

    # ── 导入历史相关 ──

    def log_import(self, source, count, subject="", parse_mode="regex", user_id=0):
        """记录一次导入操作。"""
        conn = self._get_conn()
        with self._lock:
            conn.execute(
                "INSERT INTO import_history (source, count, subject, parse_mode, user_id) VALUES (?, ?, ?, ?, ?)",
                (source, count, subject, parse_mode, user_id)
            )
            conn.commit()

    def get_import_history(self, limit=20, user_id=0):
        """获取最近的导入历史。"""
        conn = self._get_conn()
        with self._lock:
            rows = conn.execute(
                "SELECT * FROM import_history WHERE user_id = ? ORDER BY imported_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Practice session persistence
    # ------------------------------------------------------------------

    def save_practice_session(self, questions, current_index, score, mode="random",
                             settings=None, user_id=0):
        """保存练习进度到数据库。"""
        conn = self._get_conn()
        with self._lock:
            # 只保留一个活跃session，先清除旧的
            conn.execute(
                "DELETE FROM practice_sessions WHERE session_key = ? AND user_id = ?",
                ("default", user_id)
            )
            conn.execute(
                """INSERT INTO practice_sessions
                   (session_key, questions_json, current_index, score, mode, settings_json, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("default", json.dumps(questions, ensure_ascii=False),
                 current_index, score, mode,
                 json.dumps(settings or {}, ensure_ascii=False), user_id)
            )
            conn.commit()

    def load_practice_session(self, user_id=0):
        """加载未完成的练习进度，返回 dict 或 None。"""
        conn = self._get_conn()
        with self._lock:
            row = conn.execute(
                "SELECT * FROM practice_sessions WHERE session_key = ? AND user_id = ? ORDER BY updated_at DESC LIMIT 1",
                ("default", user_id)
            ).fetchone()
            if not row:
                return None
            return {
                "questions": json.loads(row["questions_json"]),
                "current_index": row["current_index"],
                "score": row["score"],
                "mode": row["mode"],
                "settings": json.loads(row["settings_json"]),
            }

    def clear_practice_session(self, user_id=0):
        """清除已保存的练习进度。"""
        conn = self._get_conn()
        with self._lock:
            conn.execute(
                "DELETE FROM practice_sessions WHERE session_key = ? AND user_id = ?",
                ("default", user_id)
            )
            conn.commit()

    # ------------------------------------------------------------------
    # User authentication
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_password(password, salt=None):
        """使用 PBKDF2-SHA256 + salt 对密码进行哈希（100,000次迭代）。
        返回格式：pbkdf2:iterations:salt:hash
        """
        import hashlib
        import secrets
        iterations = 100_000
        if salt is None:
            salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations)
        hashed = dk.hex()
        return f"pbkdf2:{iterations}:{salt}:{hashed}"

    @staticmethod
    def _verify_password(password, stored_hash):
        """验证密码是否匹配存储的哈希值。
        兼容旧版 SHA-256 格式（salt$hash），新密码使用 PBKDF2。
        """
        import hashlib
        # 新版 PBKDF2 格式
        if stored_hash.startswith("pbkdf2:"):
            parts = stored_hash.split(":")
            if len(parts) != 4:
                return False
            _, iterations_str, salt, expected = parts
            iterations = int(iterations_str)
            dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations)
            return dk.hex() == expected
        # 旧版 SHA-256 格式（向后兼容）
        if "$" in stored_hash:
            salt, expected = stored_hash.split("$", 1)
            hashed = hashlib.sha256((salt + password).encode()).hexdigest()
            return hashed == expected
        return False

    def register_user(self, username, password, display_name=""):
        """注册新用户。返回 (user_id, error_msg)。"""
        conn = self._get_conn()
        if not username or len(username) < 2:
            return None, "用户名至少需要2个字符"
        if not password or len(password) < 6:
            return None, "密码至少需要6个字符"
        with self._lock:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing:
                return None, "用户名已存在"
            password_hash = self._hash_password(password)
            conn.execute(
                "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
                (username, password_hash, display_name or username)
            )
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0], None

    def login_user(self, username, password):
        """用户登录验证。返回 (user_dict, error_msg)。"""
        conn = self._get_conn()
        with self._lock:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not row:
                return None, "用户名不存在"
            if not self._verify_password(password, row["password_hash"]):
                return None, "密码错误"
            return {
                "id": row["id"],
                "username": row["username"],
                "display_name": row["display_name"],
                "role": row["role"],
            }, None

    def get_user_by_id(self, user_id):
        """根据 ID 获取用户信息。"""
        conn = self._get_conn()
        with self._lock:
            row = conn.execute(
                "SELECT id, username, display_name, role, created_at FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            return dict(row) if row else None
