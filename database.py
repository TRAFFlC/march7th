"""
数据库管理模块 - MySQL 版本
Database Management Module - MySQL Version
"""

import os
import re
import pymysql
from pymysql.cursors import DictCursor
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import bcrypt

from personal_config import MYSQL_CONFIG


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


class DatabaseManager:
    def __init__(self, config: dict = None):
        self.config = config or MYSQL_CONFIG
        self._create_database_if_not_exists()
        self.connection = pymysql.connect(
            host=self.config['host'],
            port=self.config['port'],
            user=self.config['user'],
            password=self.config['password'],
            database=self.config['database'],
            charset=self.config.get('charset', 'utf8mb4'),
            cursorclass=DictCursor,
            autocommit=False
        )
        self.create_tables()
        self._create_default_admin()
    
    def _create_database_if_not_exists(self):
        temp_conn = pymysql.connect(
            host=self.config['host'],
            port=self.config['port'],
            user=self.config['user'],
            password=self.config['password'],
            charset=self.config.get('charset', 'utf8mb4'),
        )
        try:
            with temp_conn.cursor() as cursor:
                db_name = self.config['database']
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', db_name):
                    raise ValueError(f"Invalid database name: {db_name}")
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
        finally:
            temp_conn.close()
    
    def create_tables(self):
        with self.connection.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_username (username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    `character` VARCHAR(100) NOT NULL,
                    user_input TEXT NOT NULL,
                    bot_reply TEXT NOT NULL,
                    rating INT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_timestamp (timestamp)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    keyword VARCHAR(100) NOT NULL,
                    sentiment VARCHAR(20) NOT NULL,
                    count INT DEFAULT 1,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY uk_user_keyword_sentiment (user_id, keyword, sentiment),
                    INDEX idx_user_id (user_id),
                    INDEX idx_sentiment (sentiment),
                    INDEX idx_last_updated (last_updated)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS llm_test_conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    model VARCHAR(100) NOT NULL,
                    character_id VARCHAR(100),
                    user_input TEXT NOT NULL,
                    bot_reply TEXT NOT NULL,
                    temperature FLOAT DEFAULT 1.0,
                    top_p FLOAT DEFAULT 0.9,
                    use_rag BOOLEAN DEFAULT TRUE,
                    response_time FLOAT,
                    input_tokens INT,
                    output_tokens INT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_model (model),
                    INDEX idx_timestamp (timestamp)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    profile_summary TEXT,
                    total_tokens INT DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY uk_user_id (user_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_last_updated (last_updated)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_characters (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    character_id VARCHAR(100) NOT NULL,
                    character_data JSON NOT NULL,
                    source_id VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_character_id (character_id),
                    INDEX idx_source_id (source_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            cursor.execute("SHOW COLUMNS FROM user_characters LIKE 'source_id'")
            if not cursor.fetchone():
                print("[DB] 添加 user_characters.source_id 列...")
                cursor.execute('ALTER TABLE user_characters ADD COLUMN source_id VARCHAR(100)')
                cursor.execute('ALTER TABLE user_characters ADD INDEX idx_source_id (source_id)')
                print("[DB] user_characters.source_id 列添加成功")
            
            cursor.execute("SHOW COLUMNS FROM user_preferences LIKE 'last_updated'")
            if not cursor.fetchone():
                print("[DB] 添加 user_preferences.last_updated 列...")
                cursor.execute('''
                    ALTER TABLE user_preferences 
                    ADD COLUMN last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ''')
                cursor.execute('ALTER TABLE user_preferences ADD INDEX idx_last_updated (last_updated)')
                print("[DB] user_preferences.last_updated 列添加成功")
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback_details (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    conversation_id INT NOT NULL,
                    user_id INT NOT NULL,
                    feedback_type VARCHAR(50) NOT NULL,
                    context_snapshot JSON,
                    correction_suggestion TEXT,
                    model_name VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_conversation_id (conversation_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_feedback_type (feedback_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memory_anchors (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    character_id VARCHAR(100) NOT NULL,
                    content TEXT NOT NULL,
                    anchor_type VARCHAR(50) DEFAULT 'auto',
                    importance FLOAT DEFAULT 0.5,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_character (user_id, character_id),
                    INDEX idx_importance (importance DESC),
                    INDEX idx_anchor_type (anchor_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dialogue_sessions (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id INT NOT NULL,
                    character_id VARCHAR(100) NOT NULL,
                    title VARCHAR(255),
                    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INT DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_character_id (character_id),
                    INDEX idx_last_message_at (last_message_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            cursor.execute("SHOW COLUMNS FROM conversations LIKE 'session_id'")
            if not cursor.fetchone():
                print("[DB] 添加 conversations.session_id 列...")
                cursor.execute('ALTER TABLE conversations ADD COLUMN session_id VARCHAR(36)')
                cursor.execute('ALTER TABLE conversations ADD INDEX idx_session_id (session_id)')
                print("[DB] conversations.session_id 列添加成功")

            cursor.execute("SHOW COLUMNS FROM feedback_details LIKE 'confirmed'")
            if not cursor.fetchone():
                print("[DB] 添加 feedback_details.confirmed 列...")
                cursor.execute('ALTER TABLE feedback_details ADD COLUMN confirmed BOOLEAN DEFAULT FALSE')
                print("[DB] feedback_details.confirmed 列添加成功")

            cursor.execute("SHOW COLUMNS FROM feedback_details LIKE 'rag_updated'")
            if not cursor.fetchone():
                print("[DB] 添加 feedback_details.rag_updated 列...")
                cursor.execute('ALTER TABLE feedback_details ADD COLUMN rag_updated BOOLEAN DEFAULT FALSE')
                print("[DB] feedback_details.rag_updated 列添加成功")

            cursor.execute("SHOW COLUMNS FROM conversations LIKE 'needs_feedback'")
            if not cursor.fetchone():
                print("[DB] 添加 conversations.needs_feedback 列...")
                cursor.execute('ALTER TABLE conversations ADD COLUMN needs_feedback BOOLEAN DEFAULT FALSE')
                print("[DB] conversations.needs_feedback 列添加成功")

            cursor.execute("SHOW COLUMNS FROM users LIKE 'nickname'")
            if not cursor.fetchone():
                print("[DB] 添加 users.nickname 列...")
                cursor.execute('ALTER TABLE users ADD COLUMN nickname VARCHAR(100)')
                print("[DB] users.nickname 列添加成功")

            cursor.execute("SHOW COLUMNS FROM users LIKE 'avatar'")
            if not cursor.fetchone():
                print("[DB] 添加 users.avatar 列...")
                cursor.execute('ALTER TABLE users ADD COLUMN avatar VARCHAR(500)')
                print("[DB] users.avatar 列添加成功")

            cursor.execute("SHOW COLUMNS FROM conversations LIKE 'emotion'")
            if not cursor.fetchone():
                print("[DB] 添加 conversations.emotion 列...")
                cursor.execute('ALTER TABLE conversations ADD COLUMN emotion VARCHAR(20)')
                print("[DB] conversations.emotion 列添加成功")

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INT PRIMARY KEY DEFAULT 1,
                    settings_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            self.connection.commit()
    
    def _create_default_admin(self):
        with self.connection.cursor() as cursor:
            username = os.environ.get('ADMIN_USERNAME', 'admin')
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if not cursor.fetchone():
                password = os.environ.get('ADMIN_PASSWORD', 'admin')
                password_hash = hash_password(password)
                cursor.execute(
                    "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                    (username, password_hash)
                )
                self.connection.commit()
    
    @contextmanager
    def get_cursor(self):
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def get_connection(self):
        return self.connection
    
    def close(self):
        if self.connection:
            self.connection.close()


def create_user(db: DatabaseManager, username: str, password: str) -> Optional[int]:
    password_hash = hash_password(password)
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash)
            )
            return cursor.lastrowid
    except pymysql.IntegrityError:
        return None


def get_user_by_username(db: DatabaseManager, username: str) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()


def get_user_by_id(db: DatabaseManager, user_id: int) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()


def verify_user(db: DatabaseManager, username: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user_by_username(db, username)
    if user and verify_password(password, user['password_hash']):
        return user
    return None


def save_conversation(db: DatabaseManager, user_id: int, character: str, 
                      user_input: str, bot_reply: str, session_id: str = None,
                      emotion: str = None) -> Optional[int]:
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO conversations 
                   (user_id, `character`, user_input, bot_reply, session_id, emotion) 
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, character, user_input, bot_reply, session_id, emotion)
            )
            return cursor.lastrowid
    except Exception:
        return None


def get_conversations(db: DatabaseManager, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT * FROM conversations 
               WHERE user_id = %s 
               ORDER BY timestamp DESC 
               LIMIT %s""",
            (user_id, limit)
        )
        return cursor.fetchall()


def update_rating(db: DatabaseManager, conversation_id: int, rating: int) -> bool:
    if rating < 1 or rating > 5:
        return False
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE conversations SET rating = %s WHERE id = %s",
                (rating, conversation_id)
            )
            return cursor.rowcount > 0
    except Exception:
        return False


def set_needs_feedback(db: DatabaseManager, conversation_id: int, needs_feedback: bool) -> bool:
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE conversations SET needs_feedback = %s WHERE id = %s",
                (needs_feedback, conversation_id)
            )
            return cursor.rowcount > 0
    except Exception:
        return False


def get_all_conversations(db: DatabaseManager, limit: int = 100) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT c.*, u.username
               FROM conversations c
               JOIN users u ON c.user_id = u.id
               ORDER BY c.timestamp DESC
               LIMIT %s""",
            (limit,)
        )
        return cursor.fetchall()


def get_conversation_by_id(db: DatabaseManager, conversation_id: int) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT c.*, u.username
               FROM conversations c
               JOIN users u ON c.user_id = u.id
               WHERE c.id = %s""",
            (conversation_id,)
        )
        return cursor.fetchone()


def delete_conversation(db: DatabaseManager, conversation_id: int) -> bool:
    try:
        with db.get_cursor() as cursor:
            cursor.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
            return cursor.rowcount > 0
    except Exception:
        return False


def save_preference(db: DatabaseManager, user_id: int, keyword: str, sentiment: str) -> bool:
    if sentiment not in ('positive', 'negative'):
        return False
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO user_preferences (user_id, keyword, sentiment, count)
                   VALUES (%s, %s, %s, 1)
                   ON DUPLICATE KEY UPDATE count = count + 1""",
                (user_id, keyword, sentiment)
            )
            return True
    except Exception:
        return False


def get_preferences(db: DatabaseManager, user_id: int) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT * FROM user_preferences 
               WHERE user_id = %s 
               ORDER BY count DESC""",
            (user_id,)
        )
        return cursor.fetchall()


def get_top_positive_keywords(db: DatabaseManager, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT keyword, count FROM user_preferences 
               WHERE user_id = %s AND sentiment = 'positive' 
               ORDER BY count DESC 
               LIMIT %s""",
            (user_id, limit)
        )
        return cursor.fetchall()


def get_top_negative_keywords(db: DatabaseManager, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT keyword, count FROM user_preferences 
               WHERE user_id = %s AND sentiment = 'negative' 
               ORDER BY count DESC 
               LIMIT %s""",
            (user_id, limit)
        )
        return cursor.fetchall()


def get_preferences_with_decay(
    db: DatabaseManager, 
    user_id: int, 
    sentiment: str, 
    decay_rate: float = 0.1,
    limit: int = 5
) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT keyword, count, last_updated,
                      DATEDIFF(NOW(), last_updated) as days_ago
               FROM user_preferences 
               WHERE user_id = %s AND sentiment = %s""",
            (user_id, sentiment)
        )
        results = cursor.fetchall()
        
        for row in results:
            days_ago = row['days_ago'] or 0
            count = row['count']
            decayed_weight = count * (2.718281828 ** (-decay_rate * days_ago))
            row['decayed_weight'] = round(decayed_weight, 4)
        
        results.sort(key=lambda x: x['decayed_weight'], reverse=True)
        return results[:limit]


def get_all_preferences_with_decay(
    db: DatabaseManager,
    user_id: int,
    decay_rate: float = 0.1,
    limit: int = 10
) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT keyword, count, sentiment, last_updated,
                      DATEDIFF(NOW(), last_updated) as days_ago
               FROM user_preferences
               WHERE user_id = %s""",
            (user_id,)
        )
        raw_results = cursor.fetchall()
        results = []
        for row in raw_results:
            row_dict = dict(row) if isinstance(row, dict) else {
                'keyword': row[0],
                'count': row[1],
                'sentiment': row[2],
                'last_updated': row[3],
                'days_ago': row[4]
            }
            days_ago = row_dict['days_ago'] or 0
            count = row_dict['count']
            decayed_weight = count * (2.718281828 ** (-decay_rate * days_ago))
            row_dict['decayed_weight'] = round(decayed_weight, 4)
            results.append(row_dict)

        results.sort(key=lambda x: x['decayed_weight'], reverse=True)
        return results[:limit]


def get_preference_stats(
    db: DatabaseManager,
    user_id: int,
    days: int = 30
) -> Dict[str, Any]:
    top_positive = get_top_positive_keywords(db, user_id, limit=10)
    top_negative = get_top_negative_keywords(db, user_id, limit=10)
    interest_keywords = get_all_preferences_with_decay(db, user_id, limit=20)
    rating_dist = get_rating_distribution(db, user_id)
    conversation_trend = get_conversation_trend(db, user_id, days)

    return {
        "top_positive_keywords": top_positive,
        "top_negative_keywords": top_negative,
        "interest_keywords": interest_keywords,
        "rating_distribution": rating_dist,
        "conversation_trend": conversation_trend,
    }


def get_rating_distribution(db: DatabaseManager, user_id: int) -> Dict[str, int]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT rating, COUNT(*) as count
               FROM conversations
               WHERE user_id = %s AND rating IS NOT NULL
               GROUP BY rating""",
            (user_id,)
        )
        results = cursor.fetchall()

    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for row in results:
        if row['rating'] in distribution:
            distribution[row['rating']] = row['count']

    return distribution


def get_total_conversation_count(db: DatabaseManager, user_id: int) -> int:
    with db.get_cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) as count FROM conversations WHERE user_id = %s",
            (user_id,)
        )
        result = cursor.fetchone()
    return result['count'] if result else 0


def get_conversation_trend(
    db: DatabaseManager,
    user_id: int,
    days: int = 30
) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT DATE(timestamp) as date, COUNT(*) as count
               FROM conversations
               WHERE user_id = %s
                 AND timestamp >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
               GROUP BY DATE(timestamp)
               ORDER BY date ASC""",
            (user_id, days)
        )
        return cursor.fetchall()


_db_instance: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance


def close_db():
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None


def update_user_profile_info(db: DatabaseManager, user_id: int, nickname: str = None, avatar: str = None) -> bool:
    try:
        with db.get_cursor() as cursor:
            updates = []
            params = []
            if nickname is not None:
                updates.append("nickname = %s")
                params.append(nickname)
            if avatar is not None:
                updates.append("avatar = %s")
                params.append(avatar)
            if not updates:
                return False
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, params)
            return cursor.rowcount > 0
    except Exception:
        return False


def get_user_profile_info(db: DatabaseManager, user_id: int) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            "SELECT id, username, nickname, avatar, created_at FROM users WHERE id = %s",
            (user_id,)
        )
        return cursor.fetchone()


def save_feedback_detail(db: DatabaseManager, conversation_id: int, user_id: int,
                         feedback_type: str, context_snapshot: dict = None,
                         correction_suggestion: str = None, model_name: str = None,
                         confirmed: bool = False) -> Optional[int]:
    try:
        import json
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO feedback_details
                   (conversation_id, user_id, feedback_type, context_snapshot, correction_suggestion, model_name, confirmed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (conversation_id, user_id, feedback_type,
                 json.dumps(context_snapshot, ensure_ascii=False) if context_snapshot else None,
                 correction_suggestion, model_name, confirmed)
            )
            return cursor.lastrowid
    except Exception:
        return None


def get_feedback_details(db: DatabaseManager, conversation_id: int = None,
                         user_id: int = None, feedback_type: str = None,
                         limit: int = 50) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        query = "SELECT * FROM feedback_details WHERE 1=1"
        params = []

        if conversation_id is not None:
            query += " AND conversation_id = %s"
            params.append(conversation_id)
        if user_id is not None:
            query += " AND user_id = %s"
            params.append(user_id)
        if feedback_type is not None:
            query += " AND feedback_type = %s"
            params.append(feedback_type)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        return cursor.fetchall()


def get_feedback_detail_by_id(db: DatabaseManager, feedback_detail_id: int) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM feedback_details WHERE id = %s",
            (feedback_detail_id,)
        )
        return cursor.fetchone()


def confirm_feedback_detail(db: DatabaseManager, feedback_detail_id: int, user_id: int = None) -> bool:
    try:
        with db.get_cursor() as cursor:
            if user_id is not None:
                cursor.execute(
                    "UPDATE feedback_details SET confirmed = TRUE WHERE id = %s AND user_id = %s",
                    (feedback_detail_id, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE feedback_details SET confirmed = TRUE WHERE id = %s",
                    (feedback_detail_id,)
                )
            return cursor.rowcount > 0
    except Exception:
        return False


def update_feedback_rag_status(db: DatabaseManager, feedback_detail_id: int, rag_updated: bool = True) -> bool:
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE feedback_details SET rag_updated = %s WHERE id = %s",
                (rag_updated, feedback_detail_id)
            )
            return cursor.rowcount > 0
    except Exception:
        return False


def get_unprocessed_rag_feedbacks(db: DatabaseManager, limit: int = 100) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT fd.*, c.user_input as conv_user_input, c.bot_reply as conv_bot_reply, c.character as conv_character
               FROM feedback_details fd
               LEFT JOIN conversations c ON fd.conversation_id = c.id
               WHERE fd.confirmed = TRUE AND fd.rag_updated = FALSE
               ORDER BY fd.created_at ASC
               LIMIT %s""",
            (limit,)
        )
        return cursor.fetchall()


def get_think_leak_stats(db: DatabaseManager, model_name: str = None) -> Dict[str, Any]:
    with db.get_cursor() as cursor:
        if model_name:
            cursor.execute(
                """SELECT model_name, COUNT(*) as count
                   FROM feedback_details
                   WHERE feedback_type = 'think_leak' AND model_name = %s
                   GROUP BY model_name""",
                (model_name,)
            )
        else:
            cursor.execute(
                """SELECT model_name, COUNT(*) as count
                   FROM feedback_details
                   WHERE feedback_type = 'think_leak'
                   GROUP BY model_name"""
            )
        results = cursor.fetchall()

        by_model = {}
        total = 0
        for row in results:
            model = row['model_name'] or 'unknown'
            count = row['count']
            by_model[model] = count
            total += count

        return {"total_leaks": total, "by_model": by_model}


def get_user_characters(db: DatabaseManager, user_id: int) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT * FROM user_characters WHERE user_id = %s ORDER BY created_at DESC""",
            (user_id,)
        )
        return cursor.fetchall()


def get_all_user_characters(db: DatabaseManager) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT uc.*, u.username 
               FROM user_characters uc 
               JOIN users u ON uc.user_id = u.id 
               ORDER BY uc.created_at DESC"""
        )
        return cursor.fetchall()


def check_character_conflict(db: DatabaseManager, name: str, creator: str = None) -> Optional[Dict[str, Any]]:
    import json
    with db.get_cursor() as cursor:
        cursor.execute("SELECT * FROM user_characters")
        all_chars = cursor.fetchall()
        for uc in all_chars:
            char_data = json.loads(uc['character_data']) if isinstance(uc['character_data'], str) else uc['character_data']
            if char_data.get('name') == name:
                if creator is None or char_data.get('creator') == creator:
                    return {
                        "id": uc['id'],
                        "character_id": uc['character_id'],
                        "name": char_data.get('name'),
                        "creator": char_data.get('creator'),
                        "source_id": uc.get('source_id')
                    }
    return None


def get_user_character_by_source_id(db: DatabaseManager, source_id: str) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute("SELECT * FROM user_characters WHERE source_id = %s", (source_id,))
        return cursor.fetchone()


def create_user_character(db: DatabaseManager, user_id: int, character_id: str, character_data: dict, source_id: str = None) -> Optional[int]:
    try:
        import json
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO user_characters (user_id, character_id, character_data, source_id) 
                   VALUES (%s, %s, %s, %s)""",
                (user_id, character_id, json.dumps(character_data, ensure_ascii=False), source_id)
            )
            return cursor.lastrowid
    except Exception as e:
        print(f"创建用户角色失败: {e}")
        return None


def get_user_character_by_id(db: DatabaseManager, user_character_id: int) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute("SELECT * FROM user_characters WHERE id = %s", (user_character_id,))
        return cursor.fetchone()


def delete_user_character(db: DatabaseManager, user_character_id: int, user_id: int = None) -> bool:
    try:
        with db.get_cursor() as cursor:
            if user_id is not None:
                cursor.execute("DELETE FROM user_characters WHERE id = %s AND user_id = %s", (user_character_id, user_id))
            else:
                cursor.execute("DELETE FROM user_characters WHERE id = %s", (user_character_id,))
            return cursor.rowcount > 0
    except Exception:
        return False


def save_memory_anchor(db: DatabaseManager, user_id: int, character_id: str, content: str,
                        anchor_type: str = 'auto', importance: float = 0.5) -> Optional[int]:
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO memory_anchors (user_id, character_id, content, anchor_type, importance) VALUES (%s, %s, %s, %s, %s)",
            (user_id, character_id, content, anchor_type, importance)
        )
        conn.commit()
        anchor_id = cursor.lastrowid
        cursor.close()
        return anchor_id
    except Exception:
        return None


def get_memory_anchors(db: DatabaseManager, user_id: int, character_id: str,
                        active_only: bool = True) -> List[Dict[str, Any]]:
    conn = db.get_connection()
    try:
        query = "SELECT * FROM memory_anchors WHERE user_id = %s AND character_id = %s"
        params = [user_id, character_id]
        if active_only:
            query += " AND is_active = TRUE"
        query += " ORDER BY importance DESC, created_at DESC"
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        return results
    except Exception:
        return []


def get_memory_anchor_by_id(db: DatabaseManager, anchor_id: int) -> Optional[Dict[str, Any]]:
    conn = db.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM memory_anchors WHERE id = %s", (anchor_id,))
        result = cursor.fetchone()
        cursor.close()
        return result
    except Exception:
        return None


def update_memory_anchor(db: DatabaseManager, anchor_id: int, user_id: int = None, **kwargs) -> bool:
    conn = db.get_connection()
    try:
        allowed_fields = {'content', 'anchor_type', 'importance', 'is_active'}
        updates = []
        params = []
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = %s")
                params.append(value)
        if not updates:
            return False
        params.append(anchor_id)
        if user_id is not None:
            query = f"UPDATE memory_anchors SET {', '.join(updates)} WHERE id = %s AND user_id = %s"
            params.append(user_id)
        else:
            query = f"UPDATE memory_anchors SET {', '.join(updates)} WHERE id = %s"
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        cursor.close()
        return cursor.rowcount > 0
    except Exception:
        return False


def delete_memory_anchor(db: DatabaseManager, anchor_id: int, user_id: int = None) -> bool:
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute("DELETE FROM memory_anchors WHERE id = %s AND user_id = %s", (anchor_id, user_id))
        else:
            cursor.execute("DELETE FROM memory_anchors WHERE id = %s", (anchor_id,))
        conn.commit()
        cursor.close()
        return cursor.rowcount > 0
    except Exception:
        return False


def get_total_anchor_tokens(db: DatabaseManager, user_id: int, character_id: str) -> int:
    anchors = get_memory_anchors(db, user_id, character_id)
    total_chars = sum(len(a.get('content', '')) for a in anchors)
    return total_chars // 4


def update_user_character(db: DatabaseManager, user_character_id: int, character_data: dict, user_id: int = None) -> bool:
    try:
        import json
        with db.get_cursor() as cursor:
            if user_id is not None:
                cursor.execute(
                    "UPDATE user_characters SET character_data = %s WHERE id = %s AND user_id = %s",
                    (json.dumps(character_data, ensure_ascii=False), user_character_id, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE user_characters SET character_data = %s WHERE id = %s",
                    (json.dumps(character_data, ensure_ascii=False), user_character_id)
                )
            return cursor.rowcount > 0
    except Exception:
        return False


def get_user_profile(db: DatabaseManager, user_id: int) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM user_profiles WHERE user_id = %s",
            (user_id,)
        )
        return cursor.fetchone()


def create_user_profile(db: DatabaseManager, user_id: int) -> Optional[int]:
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO user_profiles (user_id) VALUES (%s)",
                (user_id,)
            )
            return cursor.lastrowid
    except pymysql.IntegrityError:
        return None


def update_user_profile(
    db: DatabaseManager,
    user_id: int,
    profile_summary: str,
    total_tokens: int = None
) -> bool:
    try:
        with db.get_cursor() as cursor:
            if total_tokens is not None:
                cursor.execute(
                    """UPDATE user_profiles 
                       SET profile_summary = %s, total_tokens = %s 
                       WHERE user_id = %s""",
                    (profile_summary, total_tokens, user_id)
                )
            else:
                cursor.execute(
                    """UPDATE user_profiles 
                       SET profile_summary = %s 
                       WHERE user_id = %s""",
                    (profile_summary, user_id)
                )
            return cursor.rowcount > 0
    except Exception:
        return False


def get_or_create_user_profile(db: DatabaseManager, user_id: int) -> Dict[str, Any]:
    profile = get_user_profile(db, user_id)
    if profile:
        return profile
    
    create_user_profile(db, user_id)
    return get_user_profile(db, user_id)


def get_conversation_tokens(db: DatabaseManager, user_id: int) -> int:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT SUM(LENGTH(user_input) + LENGTH(bot_reply)) as total_chars
               FROM conversations 
               WHERE user_id = %s""",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result['total_chars']:
            return result['total_chars'] // 4
        return 0


def get_recent_conversations_for_summary(
    db: DatabaseManager, 
    user_id: int, 
    limit: int = 50
) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT user_input, bot_reply, timestamp 
               FROM conversations 
               WHERE user_id = %s 
               ORDER BY timestamp DESC 
               LIMIT %s""",
            (user_id, limit)
        )
        return cursor.fetchall()


def save_llm_test_conversation(
    db: DatabaseManager,
    user_id: int,
    model: str,
    user_input: str,
    bot_reply: str,
    character_id: str = None,
    temperature: float = 1.0,
    top_p: float = 0.9,
    use_rag: bool = True,
    response_time: float = None,
    input_tokens: int = None,
    output_tokens: int = None,
) -> Optional[int]:
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO llm_test_conversations 
                   (user_id, model, character_id, user_input, bot_reply, 
                    temperature, top_p, use_rag, response_time, input_tokens, output_tokens)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, model, character_id, user_input, bot_reply,
                 temperature, top_p, use_rag, response_time, input_tokens, output_tokens)
            )
            return cursor.lastrowid
    except Exception as e:
        print(f"保存LLM测试对话失败: {e}")
        return None


def get_llm_test_conversations(
    db: DatabaseManager,
    user_id: int = None,
    model: str = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        query = "SELECT * FROM llm_test_conversations WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)
        if model:
            query += " AND model = %s"
            params.append(model)
        
        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        return cursor.fetchall()


def clear_llm_test_conversations(db: DatabaseManager, user_id: int = None) -> int:
    with db.get_cursor() as cursor:
        if user_id:
            cursor.execute("DELETE FROM llm_test_conversations WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("DELETE FROM llm_test_conversations")
        return cursor.rowcount


def get_conversation_by_user(db: DatabaseManager, conversation_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT * FROM conversations
               WHERE id = %s AND user_id = %s""",
            (conversation_id, user_id)
        )
        return cursor.fetchone()


def get_conversations_by_user(db: DatabaseManager, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT c.*, u.username
               FROM conversations c
               JOIN users u ON c.user_id = u.id
               WHERE c.user_id = %s
               ORDER BY c.timestamp DESC
               LIMIT %s""",
            (user_id, limit)
        )
        return cursor.fetchall()


def search_conversations(db: DatabaseManager, keyword: str = None, user_id: int = None,
                         character: str = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        query = "SELECT c.*, u.username FROM conversations c LEFT JOIN users u ON c.user_id = u.id WHERE 1=1"
        params = []
        if keyword:
            query += " AND (c.user_input LIKE %s OR c.bot_reply LIKE %s)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if user_id is not None:
            query += " AND c.user_id = %s"
            params.append(user_id)
        if character:
            query += " AND c.character = %s"
            params.append(character)
        query += " ORDER BY c.timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cursor.execute(query, params)
        return cursor.fetchall()


def count_search_results(db: DatabaseManager, keyword: str = None, user_id: int = None,
                         character: str = None) -> int:
    with db.get_cursor() as cursor:
        query = "SELECT COUNT(*) as total FROM conversations c WHERE 1=1"
        params = []
        if keyword:
            query += " AND (c.user_input LIKE %s OR c.bot_reply LIKE %s)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if user_id is not None:
            query += " AND c.user_id = %s"
            params.append(user_id)
        if character:
            query += " AND c.character = %s"
            params.append(character)
        cursor.execute(query, params)
        result = cursor.fetchone()
        return result.get('total', 0) if result else 0


def create_session(db: DatabaseManager, user_id: int, character_id: str, title: str = None) -> str:
    import uuid
    session_id = str(uuid.uuid4())
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO dialogue_sessions (id, user_id, character_id, title)
                   VALUES (%s, %s, %s, %s)""",
                (session_id, user_id, character_id, title)
            )
            return session_id
    except Exception as e:
        print(f"创建会话失败: {e}")
        return None


def get_session(db: DatabaseManager, session_id: str) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM dialogue_sessions WHERE id = %s",
            (session_id,)
        )
        return cursor.fetchone()


def get_user_sessions(db: DatabaseManager, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT * FROM dialogue_sessions 
               WHERE user_id = %s 
               ORDER BY last_message_at DESC 
               LIMIT %s""",
            (user_id, limit)
        )
        return cursor.fetchall()


def update_session(db: DatabaseManager, session_id: str, **kwargs) -> bool:
    allowed_fields = {'title', 'last_message_at', 'message_count'}
    updates = []
    params = []
    for key, value in kwargs.items():
        if key in allowed_fields:
            updates.append(f"{key} = %s")
            params.append(value)
    if not updates:
        return False
    params.append(session_id)
    try:
        with db.get_cursor() as cursor:
            query = f"UPDATE dialogue_sessions SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, params)
            return cursor.rowcount > 0
    except Exception as e:
        print(f"更新会话失败: {e}")
        return False


def update_conversation_title(db: DatabaseManager, session_id: str, user_id: int, title: str) -> bool:
    try:
        with db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE dialogue_sessions SET title = %s WHERE id = %s AND user_id = %s",
                (title, session_id, user_id)
            )
            return cursor.rowcount > 0
    except Exception as e:
        print(f"更新会话标题失败: {e}")
        return False


def delete_session(db: DatabaseManager, session_id: str) -> bool:
    try:
        with db.get_cursor() as cursor:
            cursor.execute("DELETE FROM dialogue_sessions WHERE id = %s", (session_id,))
            return cursor.rowcount > 0
    except Exception as e:
        print(f"删除会话失败: {e}")
        return False


def get_session_conversations(db: DatabaseManager, session_id: str) -> List[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute(
            """SELECT * FROM conversations 
               WHERE session_id = %s 
               ORDER BY timestamp ASC""",
            (session_id,)
        )
        return cursor.fetchall()


def get_user_by_username(db: DatabaseManager, username: str) -> Optional[Dict[str, Any]]:
    with db.get_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()


def verify_user(db: DatabaseManager, username: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user_by_username(db, username)
    if user and verify_password(password, user['password_hash']):
        return user
    return None


def get_db():
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance


def get_settings(db: DatabaseManager) -> dict:
    import json
    try:
        with db.get_cursor() as cursor:
            cursor.execute("SELECT settings_json FROM settings WHERE id = 1")
            row = cursor.fetchone()
            if row and row['settings_json']:
                return json.loads(row['settings_json'])
            return {}
    except Exception as e:
        print(f"获取设置失败: {e}")
        return {}


def save_settings(db: DatabaseManager, settings: dict) -> bool:
    import json
    try:
        settings_json = json.dumps(settings, ensure_ascii=False)
        with db.get_cursor() as cursor:
            cursor.execute("SELECT id FROM settings WHERE id = 1")
            if cursor.fetchone():
                cursor.execute(
                    "UPDATE settings SET settings_json = %s WHERE id = 1",
                    (settings_json,)
                )
            else:
                cursor.execute(
                    "INSERT INTO settings (id, settings_json) VALUES (1, %s)",
                    (settings_json,)
                )
            return True
    except Exception as e:
        print(f"保存设置失败: {e}")
        return False


