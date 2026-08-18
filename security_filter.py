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
]

SECURITY_KEYWORDS = [
    {"keyword": "忽略所有指令", "type": "prompt_injection", "severity": "high"},
    {"keyword": "忘记所有指令", "type": "prompt_injection", "severity": "high"},
    {"keyword": "忽略之前的指令", "type": "prompt_injection", "severity": "high"},
    {"keyword": "忘记之前的指令", "type": "prompt_injection", "severity": "high"},
    {"keyword": "忽略上面的指令", "type": "prompt_injection", "severity": "high"},
    {"keyword": "不要遵守", "type": "prompt_injection", "severity": "medium"},
    {"keyword": "越狱", "type": "jailbreak", "severity": "high"},
    {"keyword": "解除限制", "type": "jailbreak", "severity": "high"},
    {"keyword": "绕过限制", "type": "jailbreak", "severity": "high"},
    {"keyword": "突破限制", "type": "jailbreak", "severity": "high"},
    {"keyword": "不受限制", "type": "jailbreak", "severity": "medium"},
    {"keyword": "系统提示", "type": "info_extraction", "severity": "medium"},
    {"keyword": "系统指令", "type": "info_extraction", "severity": "medium"},
    {"keyword": "初始提示", "type": "info_extraction", "severity": "medium"},
    {"keyword": "原始指令", "type": "info_extraction", "severity": "medium"},
    {"keyword": "显示你的提示", "type": "info_extraction", "severity": "medium"},
    {"keyword": "告诉我你的指令", "type": "info_extraction", "severity": "medium"},
    {"keyword": "你现在是", "type": "role_hijack", "severity": "high"},
    {"keyword": "假装你是", "type": "role_hijack", "severity": "medium"},
    {"keyword": "扮演", "type": "role_hijack", "severity": "low"},
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
        is_safe = all(t["severity"] != "high" and t["severity"] != "medium" for t in threats)
        if not is_safe or threats:
            self.intercept_log.append({"text_snippet": text[:50], "threats": threats})
            if len(self.intercept_log) > 1000:
                self.intercept_log = self.intercept_log[-500:]
        return is_safe, threats

    def get_intercept_log(self, limit: int = 100) -> List[Dict]:
        return self.intercept_log[-limit:]

    def clear_log(self):
        self.intercept_log = []
