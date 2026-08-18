"""
Pytest 配置文件 - 包含测试 fixtures
"""

import asyncio
import sqlite3
from typing import Generator, AsyncGenerator
from contextlib import contextmanager
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from api.main import app


class TestDatabaseManager:
    """测试用数据库管理器 - 使用内存 SQLite"""
    
    def __init__(self):
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.create_tables()
    
    def create_tables(self):
        cursor = self.connection.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                character TEXT NOT NULL,
                user_input TEXT NOT NULL,
                bot_reply TEXT NOT NULL,
                rating INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                sentiment TEXT NOT NULL,
                count INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, keyword, sentiment)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS llm_test_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                character_id TEXT,
                user_input TEXT NOT NULL,
                bot_reply TEXT NOT NULL,
                temperature REAL DEFAULT 1.0,
                top_p REAL DEFAULT 0.9,
                use_rag INTEGER DEFAULT 1,
                response_time REAL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
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
    
    def close(self):
        if self.connection:
            self.connection.close()


_test_db_instance: TestDatabaseManager = None


def get_test_db() -> TestDatabaseManager:
    global _test_db_instance
    if _test_db_instance is None:
        _test_db_instance = TestDatabaseManager()
    return _test_db_instance


def hash_password_test(password: str) -> str:
    import bcrypt
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password_test(password: str, password_hash: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


def create_test_user(db: TestDatabaseManager, username: str, password: str, role: str = 'user') -> int:
    password_hash = hash_password_test(password)
    with db.get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role)
        )
        return cursor.lastrowid


def get_test_user_by_username(db: TestDatabaseManager, username: str):
    with db.get_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def verify_test_user(db: TestDatabaseManager, username: str, password: str):
    user = get_test_user_by_username(db, username)
    if user and verify_password_test(password, user['password_hash']):
        return user
    return None


def get_all_test_users(db: TestDatabaseManager):
    with db.get_cursor() as cursor:
        cursor.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def save_test_conversation(db: TestDatabaseManager, user_id: int, character: str,
                           user_input: str, bot_reply: str, session_id: str = None,
                           emotion: str = None) -> int:
    with db.get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO conversations (user_id, `character`, user_input, bot_reply) VALUES (?, ?, ?, ?)",
            (user_id, character, user_input, bot_reply)
        )
        return cursor.lastrowid


def get_test_conversation_by_id(db: TestDatabaseManager, conversation_id: int) -> dict:
    with db.get_cursor() as cursor:
        cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_test_rating(db: TestDatabaseManager, conversation_id: int, rating: int) -> bool:
    with db.get_cursor() as cursor:
        cursor.execute(
            "UPDATE conversations SET rating = ? WHERE id = ?", (rating, conversation_id))
        return cursor.rowcount > 0


def set_needs_feedback_test(db: TestDatabaseManager, conversation_id: int, needs_feedback: bool) -> bool:
    return True


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def test_db() -> Generator[TestDatabaseManager, None, None]:
    db = TestDatabaseManager()
    yield db
    db.close()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from rate_limiter import rate_limiter
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest_asyncio.fixture(scope="function")
async def client(test_db: TestDatabaseManager) -> AsyncGenerator[AsyncClient, None]:
    import database
    original_get_db = database.get_db
    
    database.get_db = lambda: test_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    database.get_db = original_get_db


@pytest.fixture(scope="function")
def test_user(test_db: TestDatabaseManager) -> dict:
    user_id = create_test_user(test_db, "testuser", "testpassword123", "user")
    return {
        "id": user_id,
        "username": "testuser",
        "password": "testpassword123",
        "role": "user"
    }


@pytest.fixture(scope="function")
def admin_user(test_db: TestDatabaseManager) -> dict:
    user_id = create_test_user(test_db, "adminuser", "adminpassword123", "admin")
    return {
        "id": user_id,
        "username": "adminuser",
        "password": "adminpassword123",
        "role": "admin"
    }


@pytest.fixture(scope="function")
def auth_headers(test_user: dict) -> dict:
    from datetime import timedelta
    import jwt
    from personal_config import JWT_CONFIG
    
    JWT_SECRET = JWT_CONFIG.get("secret", "march7th_secret_key_2024")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_HOURS = JWT_CONFIG.get("expire_hours", 24)
    
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "user_id": test_user["id"],
        "username": test_user["username"],
        "role": test_user["role"],
        "exp": expire,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_auth_headers(admin_user: dict) -> dict:
    from datetime import timedelta
    import jwt
    from personal_config import JWT_CONFIG
    
    JWT_SECRET = JWT_CONFIG.get("secret", "march7th_secret_key_2024")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_HOURS = JWT_CONFIG.get("expire_hours", 24)
    
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "user_id": admin_user["id"],
        "username": admin_user["username"],
        "role": admin_user["role"],
        "exp": expire,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def mock_db_functions(test_db: TestDatabaseManager):
    import database
    from unittest.mock import MagicMock

    original_functions = {
        'get_db': database.get_db,
        'create_user': getattr(database, 'create_user', None),
        'get_user_by_username': getattr(database, 'get_user_by_username', None),
        'verify_user': getattr(database, 'verify_user', None),
        'get_all_users': getattr(database, 'get_all_users', None),
        'save_conversation': getattr(database, 'save_conversation', None),
        'get_conversation_by_id': getattr(database, 'get_conversation_by_id', None),
        'update_rating': getattr(database, 'update_rating', None),
        'set_needs_feedback': getattr(database, 'set_needs_feedback', None),
    }

    def mock_get_db():
        return test_db

    def mock_create_user(db, username: str, password: str, role: str = 'user'):
        return create_test_user(db, username, password, role)

    def mock_get_user_by_username(db, username: str):
        return get_test_user_by_username(db, username)

    def mock_verify_user(db, username: str, password: str):
        return verify_test_user(db, username, password)

    def mock_get_all_users(db):
        return get_all_test_users(db)

    def mock_save_conversation(db, user_id: int, character: str, user_input: str, bot_reply: str, session_id: str = None, emotion: str = None):
        return save_test_conversation(db, user_id, character, user_input, bot_reply, session_id, emotion)

    def mock_get_conversation_by_id(db, conversation_id: int):
        return get_test_conversation_by_id(db, conversation_id)

    def mock_update_rating(db, conversation_id: int, rating: int):
        return update_test_rating(db, conversation_id, rating)

    def mock_set_needs_feedback(db, conversation_id: int, needs_feedback: bool):
        return set_needs_feedback_test(db, conversation_id, needs_feedback)

    database.get_db = mock_get_db
    database.create_user = mock_create_user
    database.get_user_by_username = mock_get_user_by_username
    database.verify_user = mock_verify_user
    database.get_all_users = mock_get_all_users
    database.save_conversation = mock_save_conversation
    database.get_conversation_by_id = mock_get_conversation_by_id
    database.update_rating = mock_update_rating
    database.set_needs_feedback = mock_set_needs_feedback

    import persona_manager
    original_persona_manager = persona_manager.get_persona_manager
    persona_manager.get_persona_manager = MagicMock(
        return_value=MagicMock(save_dialogue=MagicMock(return_value="test_record_id")))

    yield test_db

    for name, func in original_functions.items():
        if func is not None:
            setattr(database, name, func)
    persona_manager.get_persona_manager = original_persona_manager
