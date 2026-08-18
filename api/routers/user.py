"""
用户信息与画像路由
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user
from ..schemas import UserProfileUpdate

router = APIRouter()


@router.get("/api/user/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    from database import get_db, get_user_profile_info

    db = get_db()
    profile = get_user_profile_info(db, user['user_id'])

    if not profile:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "success": True,
        "profile": {
            "id": profile['id'],
            "username": profile['username'],
            "nickname": profile.get('nickname') or profile['username'],
            "avatar": profile.get('avatar'),
            "role": profile['role'],
            "created_at": str(profile['created_at']) if profile.get('created_at') else None,
        }
    }


@router.put("/api/user/profile")
async def update_user_profile(data: UserProfileUpdate, user: dict = Depends(get_current_user)):
    from database import get_db, update_user_profile_info

    if data.nickname is None and data.avatar is None:
        raise HTTPException(status_code=400, detail="至少需要提供一个字段")

    if data.nickname is not None and len(data.nickname) > 100:
        raise HTTPException(status_code=400, detail="昵称不能超过100个字符")

    if data.avatar is not None and len(data.avatar) > 500:
        raise HTTPException(status_code=400, detail="头像URL不能超过500个字符")

    db = get_db()
    success = update_user_profile_info(
        db, user['user_id'], data.nickname, data.avatar)

    if not success:
        raise HTTPException(status_code=500, detail="更新失败")

    return {"success": True, "message": "个人信息已更新"}


@router.get("/api/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    from database import get_db, get_user_profile
    from profile_summary import get_profile_summary_manager

    db = get_db()
    profile = get_user_profile(db, user['user_id'])

    manager = get_profile_summary_manager()
    should_regenerate = manager.should_regenerate(user['user_id'])

    return {
        "success": True,
        "profile": {
            "summary": profile.get('profile_summary') if profile else None,
            "total_tokens": profile.get('total_tokens', 0) if profile else 0,
            "last_updated": str(profile['last_updated']) if profile and profile.get('last_updated') else None,
        },
        "should_regenerate": should_regenerate,
    }


@router.post("/api/profile/regenerate")
async def regenerate_profile(user: dict = Depends(get_current_user)):
    from profile_summary import get_profile_summary_manager

    manager = get_profile_summary_manager()
    summary = manager.update_profile_summary(user['user_id'])

    if not summary:
        raise HTTPException(status_code=500, detail="画像生成失败，请确保有足够的对话历史")

    return {
        "success": True,
        "message": "画像已重新生成",
        "summary": summary,
    }


@router.get("/api/user/preference/stats")
async def get_preference_stats(user: dict = Depends(get_current_user), days: int = 30):
    from database import get_db, get_preference_stats, get_total_conversation_count

    db = get_db()
    stats = get_preference_stats(db, user['user_id'], days)

    total_conversations = get_total_conversation_count(db, user['user_id'])
    total_rated_conversations = sum(stats['rating_distribution'].values())
    avg_rating = 0
    if total_rated_conversations > 0:
        weighted_sum = sum(
            r * c for r, c in stats['rating_distribution'].items())
        avg_rating = round(weighted_sum / total_rated_conversations, 2)

    return {
        "success": True,
        "stats": {
            "top_positive_keywords": stats['top_positive_keywords'],
            "top_negative_keywords": stats['top_negative_keywords'],
            "interest_keywords": stats['interest_keywords'],
            "rating_distribution": stats['rating_distribution'],
            "conversation_trend": [
                {"date": str(item['date']), "count": item['count']}
                for item in stats['conversation_trend']
            ],
            "summary": {
                "total_conversations": total_conversations,
                "total_rated_conversations": total_rated_conversations,
                "avg_rating": avg_rating,
            }
        }
    }
