import re
from typing import List, Dict, Any, Optional

ANCHOR_PATTERNS = [
    {"pattern": r"我叫(.{1,10})", "type": "self_intro", "importance": 0.9},
    {"pattern": r"我是(.{1,10})", "type": "self_intro", "importance": 0.9},
    {"pattern": r"我的名字是(.{1,10})", "type": "self_intro", "importance": 0.9},
    {"pattern": r"我喜欢(.{1,20})", "type": "preference", "importance": 0.7},
    {"pattern": r"我不喜欢(.{1,20})", "type": "preference", "importance": 0.7},
    {"pattern": r"我最爱(.{1,20})", "type": "preference", "importance": 0.8},
    {"pattern": r"记住(.{1,30})", "type": "explicit", "importance": 0.95},
    {"pattern": r"别忘了(.{1,30})", "type": "explicit", "importance": 0.95},
    {"pattern": r"不要忘记(.{1,30})", "type": "explicit", "importance": 0.95},
    {"pattern": r"我住在(.{1,20})", "type": "location", "importance": 0.7},
    {"pattern": r"我在(.{1,20})工作", "type": "occupation", "importance": 0.7},
    {"pattern": r"我今年(.{1,5})岁", "type": "personal", "importance": 0.8},
    {"pattern": r"我生日是(.{1,15})", "type": "personal", "importance": 0.8},
]


def extract_anchors_from_text(text: str) -> List[Dict[str, Any]]:
    anchors = []
    for pattern_def in ANCHOR_PATTERNS:
        matches = re.finditer(pattern_def["pattern"], text)
        for match in matches:
            anchors.append({
                "content": match.group(0),
                "anchor_type": pattern_def["type"],
                "importance": pattern_def["importance"],
            })
    return anchors


def should_create_anchor(text: str, existing_anchors: List[Dict[str, Any]] = None) -> bool:
    new_anchors = extract_anchors_from_text(text)
    if not new_anchors:
        return False
    if existing_anchors is None:
        return True
    existing_contents = {a.get("content", "") for a in existing_anchors}
    for anchor in new_anchors:
        if anchor["content"] not in existing_contents:
            return True
    return False
