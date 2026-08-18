"""
会话管理路由
"""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user, MAX_SESSIONS_LIMIT
from ..schemas import SessionCreate

router = APIRouter()


@router.post("/api/sessions")
async def create_session(data: SessionCreate, user: dict = Depends(get_current_user)):
    from database import get_db, create_session as db_create_session

    db = get_db()
    session_id = db_create_session(
        db, user['user_id'], data.character_id, data.title)

    if not session_id:
        raise HTTPException(status_code=500, detail="创建会话失败")

    return {
        "success": True,
        "session_id": session_id,
        "session": {
            "id": session_id,
            "user_id": user['user_id'],
            "character_id": data.character_id,
            "title": data.title,
            "message_count": 0,
        }
    }


@router.get("/api/sessions")
async def get_sessions(user: dict = Depends(get_current_user), limit: int = 50):
    from database import get_db, get_user_sessions

    limit = min(limit, MAX_SESSIONS_LIMIT)
    db = get_db()
    sessions = get_user_sessions(db, user['user_id'], limit)

    result = []
    for session in sessions:
        result.append({
            "id": session['id'],
            "character_id": session['character_id'],
            "title": session['title'],
            "last_message_at": str(session['last_message_at']) if session.get('last_message_at') else None,
            "created_at": str(session['created_at']) if session.get('created_at') else None,
            "message_count": session.get('message_count', 0),
        })

    return {"success": True, "sessions": result}


@router.get("/api/sessions/{session_id}")
async def get_session_detail(session_id: str, user: dict = Depends(get_current_user)):
    from database import get_db, get_session, get_session_conversations

    db = get_db()
    session = get_session(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session['user_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    conversations = get_session_conversations(db, session_id)

    messages = []
    for conv in conversations:
        messages.append({
            "id": conv['id'],
            "user_input": conv['user_input'],
            "bot_reply": conv['bot_reply'],
            "rating": conv['rating'],
            "timestamp": str(conv['timestamp']) if conv.get('timestamp') else None,
        })

    return {
        "success": True,
        "session": {
            "id": session['id'],
            "character_id": session['character_id'],
            "title": session['title'],
            "last_message_at": str(session['last_message_at']) if session.get('last_message_at') else None,
            "created_at": str(session['created_at']) if session.get('created_at') else None,
            "message_count": session.get('message_count', 0),
        },
        "messages": messages
    }


@router.post("/api/sessions/{session_id}/restore")
async def restore_session(session_id: str, user: dict = Depends(get_current_user)):
    from database import get_db, get_session
    from voice_chat import get_controller

    db = get_db()
    session = get_session(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session['user_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    controller = get_controller(user_id=user["user_id"])
    success = controller.switch_session(session_id, user['user_id'])

    if not success:
        raise HTTPException(status_code=500, detail="会话恢复失败")

    return {
        "success": True,
        "message": "会话已恢复",
        "session": {
            "id": session['id'],
            "character_id": session['character_id'],
            "title": session['title'],
            "message_count": session.get('message_count', 0),
        },
        "history_turns": controller.llm.get_history_length()
    }


@router.delete("/api/sessions/{session_id}")
async def delete_session_by_id(session_id: str, user: dict = Depends(get_current_user)):
    from database import get_db, get_session, delete_session as db_delete_session

    db = get_db()
    session = get_session(db, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session['user_id'] != user['user_id']:
        raise HTTPException(status_code=403, detail="无权删除该会话")

    success = db_delete_session(db, session_id)

    if not success:
        raise HTTPException(status_code=500, detail="删除会话失败")

    return {"success": True, "message": "会话已删除"}
