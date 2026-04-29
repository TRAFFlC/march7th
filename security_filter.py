import re
from typing import Dict, Any, List, Tuple

SECURITY_PATTERNS = [
    {"pattern": r"ignore\s+(all\s+)?previous\s+instructions", "type": "prompt_injection", "severity": "high"},
    {"pattern": r"forget\s+(all\s+)?previous\s+instructions", "type": "prompt_injection", "severity": "high"},
    {"pattern": r"you\s+are\s+now\s+a", "type": "role_hijack", "severity": "high"},
    {"pattern": r"pretend\s+(to\s+be|you\s+are)", "type": "role_hijack", "severity": "medium"},
    {"pattern": r"jailbreak", "type": "jailbreak", "severity": "high"},
    {"pattern": r"DAN\s+mode", "type": "jailbreak", "severity": "high"},
    {"pattern": r"system\s*:\s*", "type": "system_injection", "severity": "high"},
    {"pattern": r"<\|im_start\|>", "type": "token_injection", "severity": "high"},
    {"pattern": r"\[INST\]", "type": "token_injection", "severity": "high"},
    {"pattern": r"reveal\s+your\s+(system|initial)\s+prompt", "type": "info_extraction", "severity": "medium"},
    {"pattern": r"show\s+me\s+your\s+instructions", "type": "info_extraction", "severity": "medium"},
    {"pattern": r"from\s+now\s+on\s+you\s+are", "type": "role_hijack", "severity": "high"},
    {"pattern": r"act\s+as\s+(if\s+you\s+(are|were)|a|an)", "type": "role_hijack", "severity": "medium"},
    {"pattern": r"bypass\s+(all\s+)?(restrictions|safety|filters|rules)", "type": "jailbreak", "severity": "high"},
    {"pattern": r"developer\s+mode", "type": "jailbreak", "severity": "high"},
    {"pattern": r"ignore\s+(all\s+)?(safety|security)\s+rules", "type": "jailbreak", "severity": "high"},
    {"pattern": r"tell\s+me\s+your\s+(system|initial|original)\s+prompt", "type": "info_extraction", "severity": "medium"},
    {"pattern": r"output\s+your\s+prompt", "type": "info_extraction", "severity": "medium"},
    {"pattern": r"display\s+your\s+instructions", "type": "info_extraction", "severity": "medium"},
]

SECURITY_KEYWORDS = [
    {"keyword": "忽略所有指令", "type": "prompt_injection", "severity": "high"},
    {"keyword": "忘记所有指令", "type": "prompt_injection", "severity": "high"},
    {"keyword": "越狱", "type": "jailbreak", "severity": "high"},
    {"keyword": "解除限制", "type": "jailbreak", "severity": "high"},
    {"keyword": "绕过限制", "type": "jailbreak", "severity": "high"},
    {"keyword": "系统提示", "type": "info_extraction", "severity": "medium"},
    {"keyword": "你现在是", "type": "role_hijack", "severity": "high"},
    {"keyword": "假装你是", "type": "role_hijack", "severity": "high"},
    {"keyword": "从现在起你是", "type": "role_hijack", "severity": "high"},
    {"keyword": "忽略以上设定", "type": "prompt_injection", "severity": "high"},
    {"keyword": "忽略以上指令", "type": "prompt_injection", "severity": "high"},
    {"keyword": "告诉我你的指令", "type": "info_extraction", "severity": "medium"},
    {"keyword": "显示系统提示", "type": "info_extraction", "severity": "medium"},
    {"keyword": "输出你的prompt", "type": "info_extraction", "severity": "medium"},
    {"keyword": "输出你的提示", "type": "info_extraction", "severity": "medium"},
    {"keyword": "解除所有限制", "type": "jailbreak", "severity": "high"},
    {"keyword": "忽略安全规则", "type": "jailbreak", "severity": "high"},
    {"keyword": "开发者模式", "type": "jailbreak", "severity": "high"},
]


class SecurityFilter:
    def __init__(self, enabled: bool = True, custom_patterns: List[Dict] = None):
        self.enabled = enabled
        self.patterns = SECURITY_PATTERNS.copy()
        self.keywords = SECURITY_KEYWORDS.copy()
        if custom_patterns:
            self.patterns.extend(custom_patterns)
        self.intercept_log = []

    def check(self, text: str) -> Tuple[bool, List[Dict[str, Any]]]:
        if not self.enabled:
            return True, []
        threats = []
        for p in self.patterns:
            if re.search(p["pattern"], text, re.IGNORECASE):
                threats.append({"type": p["type"], "severity": p["severity"], "matched_pattern": p["pattern"]})
        for k in self.keywords:
            if k["keyword"] in text:
                threats.append({"type": k["type"], "severity": k["severity"], "matched_keyword": k["keyword"]})
        is_safe = len(threats) == 0
        if not is_safe:
            self.intercept_log.append({"text_snippet": text[:50], "threats": threats})
        return is_safe, threats

    def get_intercept_log(self, limit: int = 100) -> List[Dict]:
        return self.intercept_log[-limit:]

    def clear_log(self):
        self.intercept_log = []
