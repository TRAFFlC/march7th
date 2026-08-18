"""
认证相关路由
"""
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..deps import (
    create_token,
    ensure_password_complexity,
    get_client_ip,
    get_current_user,
    get_admin_user,
    read_shared_token_payload,
    write_shared_token,
    SHARED_TOKEN_FILE,
)
from ..schemas import UserLogin, UserRegister
from rate_limiter import rate_limiter

router = APIRouter()


@router.post("/api/auth/login")
async def login(data: UserLogin, request: Request, response: Response):
    from database import get_db, verify_user

    rate_limiter.check(
        f"login:{get_client_ip(request)}", limit=5, window_seconds=300, response=response
    )

    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    db = get_db()
    user = verify_user(db, data.username, data.password)

    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(user['id'], user['username'], user['role'])

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "role": user['role'],
        }
    }


@router.post("/api/auth/register")
async def register(data: UserRegister, request: Request, response: Response):
    from database import get_db, create_user, get_user_by_username

    rate_limiter.check(
        f"register:{get_client_ip(request)}", limit=3, window_seconds=3600, response=response
    )

    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    if len(data.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少3个字符")

    ensure_password_complexity(data.password)

    db = get_db()

    existing = get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user_id = create_user(db, data.username, data.password, 'user')
    if not user_id:
        raise HTTPException(status_code=500, detail="注册失败")

    token = create_token(user_id, data.username, 'user')

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user_id,
            "username": data.username,
            "role": "user",
        }
    }


@router.get("/api/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"success": True, "user": user}


@router.post("/api/auth/share-token")
async def share_token(user: dict = Depends(get_current_user)):
    token = create_token(user['user_id'], user['username'], user['role'])
    data = {
        "token": token,
        "user": user,
        "created_at": time.time(),
    }
    write_shared_token(data)
    return {"success": True, "message": "Token shared"}


@router.get("/api/auth/shared-token")
async def get_shared_token(request: Request, response: Response):
    rate_limiter.check(
        f"shared_token:{get_client_ip(request)}", limit=10, window_seconds=60, response=response
    )
    try:
        payload = read_shared_token_payload()
    except HTTPException:
        return {"success": False, "message": "No valid shared token"}
    return {"success": True, "token": payload.get("token"), "user": payload.get("user")}


@router.delete("/api/auth/shared-token")
async def delete_shared_token(user: dict = Depends(get_current_user)):
    if os.path.exists(SHARED_TOKEN_FILE):
        os.remove(SHARED_TOKEN_FILE)
    return {"success": True, "message": "Shared token deleted"}
