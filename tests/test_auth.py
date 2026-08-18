"""
认证 API 端点测试
Tests for authentication API endpoints
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
import jwt

from personal_config import JWT_CONFIG


class TestUserRegistration:
    """用户注册测试"""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient, mock_db_functions):
        """测试成功注册用户"""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "password": "newpassword123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["role"] == "user"

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient, mock_db_functions):
        """测试缺少字段时注册失败"""
        response = await client.post(
            "/api/auth/register",
            json={"username": "testuser"}
        )
        
        assert response.status_code == 422
        
        response = await client.post(
            "/api/auth/register",
            json={"password": "testpassword123"}
        )
        
        assert response.status_code == 422
        
        response = await client.post(
            "/api/auth/register",
            json={}
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_username(self, client: AsyncClient, mock_db_functions):
        """测试用户名过短时注册失败"""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "ab",
                "password": "validpassword123"
            }
        )
        
        assert response.status_code == 400
        assert "用户名至少3个字符" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient, mock_db_functions):
        """测试密码过短时注册失败"""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "validuser",
                "password": "12345"
            }
        )
        
        assert response.status_code == 400
        assert "密码至少8个字符" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient, test_user: dict, mock_db_functions):
        """测试重复用户名注册失败"""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": test_user["username"],
                "password": "anotherpassword123"
            }
        )
        
        assert response.status_code == 400
        assert "用户名已存在" in response.json()["detail"]


class TestUserLogin:
    """用户登录测试"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: dict, mock_db_functions):
        """测试成功登录返回 JWT token"""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": test_user["password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data
        assert data["user"]["username"] == test_user["username"]
        assert data["user"]["role"] == test_user["role"]

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient, test_user: dict, mock_db_functions):
        """测试错误密码登录失败"""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": test_user["username"],
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert "用户名或密码错误" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient, mock_db_functions):
        """测试不存在的用户登录失败"""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "nonexistentuser",
                "password": "somepassword123"
            }
        )
        
        assert response.status_code == 401
        assert "用户名或密码错误" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client: AsyncClient, mock_db_functions):
        """测试缺少字段时登录失败"""
        response = await client.post(
            "/api/auth/login",
            json={"username": "testuser"}
        )
        
        assert response.status_code == 422
        
        response = await client.post(
            "/api/auth/login",
            json={"password": "testpassword"}
        )
        
        assert response.status_code == 422


class TestJWTAuthentication:
    """JWT 认证测试"""

    @pytest.mark.asyncio
    async def test_protected_route_with_valid_token(self, client: AsyncClient, auth_headers: dict):
        """测试使用有效 token 访问受保护路由"""
        response = await client.get("/api/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "user" in data

    @pytest.mark.asyncio
    async def test_protected_route_without_token(self, client: AsyncClient):
        """测试无 token 访问受保护路由"""
        response = await client.get("/api/auth/me")
        
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_protected_route_with_invalid_token(self, client: AsyncClient):
        """测试使用无效 token 访问受保护路由"""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == 401
        assert "无效或过期的令牌" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_protected_route_with_expired_token(self, client: AsyncClient, test_user: dict):
        """测试使用过期 token 访问受保护路由"""
        JWT_SECRET = JWT_CONFIG.get("secret", "march7th_secret_key_2024")
        JWT_ALGORITHM = "HS256"
        
        expire = datetime.utcnow() - timedelta(hours=1)
        payload = {
            "user_id": test_user["id"],
            "username": test_user["username"],
            "role": test_user["role"],
            "exp": expire,
        }
        expired_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401
        assert "无效或过期的令牌" in response.json()["detail"]


class TestAdminRoutes:
    """管理员路由测试"""

    @pytest.mark.asyncio
    async def test_admin_access_with_admin_role(self, client: AsyncClient, admin_auth_headers: dict, mock_db_functions):
        """测试管理员可以访问管理员路由"""
        response = await client.get("/api/admin/users", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "users" in data

    @pytest.mark.asyncio
    async def test_admin_access_with_user_role(self, client: AsyncClient, auth_headers: dict, mock_db_functions):
        """测试普通用户无法访问管理员路由"""
        response = await client.get("/api/admin/users", headers=auth_headers)
        
        assert response.status_code == 403
        assert "需要管理员权限" in response.json()["detail"]
