"""
记忆锚点路由
"""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user
from ..schemas import MemoryAnchorCreate, MemoryAnchorUpdate

router = APIRouter()


@router.get("/api/memory/anchors/{character_id}")
async def get_anchors(character_id: str, user: dict = Depends(get_current_user)):
    from database import get_memory_anchors, get_db
    db = get_db()
    anchors = get_memory_anchors(
        db, user_id=user['user_id'], character_id=character_id)
    return {"anchors": anchors}


@router.post("/api/memory/anchors")
async def create_anchor(data: MemoryAnchorCreate, user: dict = Depends(get_current_user)):
    from database import save_memory_anchor, get_db
    db = get_db()
    anchor_id = save_memory_anchor(db, user_id=user['user_id'], character_id=data.character_id,
                                   content=data.content, anchor_type=data.anchor_type,
                                   importance=data.importance)
    if anchor_id:
        return {"success": True, "anchor_id": anchor_id}
    raise HTTPException(status_code=500, detail="Failed to create anchor")


@router.put("/api/memory/anchors/{anchor_id}")
async def update_anchor(anchor_id: int, data: MemoryAnchorUpdate, user: dict = Depends(get_current_user)):
    from database import update_memory_anchor, get_db
    db = get_db()
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if update_memory_anchor(db, anchor_id, user_id=user['user_id'], **updates):
        return {"success": True}
    raise HTTPException(status_code=404, detail="锚点不存在或无权限")


@router.delete("/api/memory/anchors/{anchor_id}")
async def delete_anchor(anchor_id: int, user: dict = Depends(get_current_user)):
    from database import delete_memory_anchor, get_db
    db = get_db()
    if delete_memory_anchor(db, anchor_id, user_id=user['user_id']):
        return {"success": True}
    raise HTTPException(status_code=404, detail="锚点不存在或无权限")
