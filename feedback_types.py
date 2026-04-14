from enum import Enum


class FeedbackType(str, Enum):
    FACT_ERROR = "fact_error"
    ROLE_DEVIATION = "role_deviation"
    HISTORY_FORGET = "history_forget"
    THINK_LEAK = "think_leak"


FEEDBACK_TYPE_LABELS = {
    FeedbackType.FACT_ERROR: "事实不符",
    FeedbackType.ROLE_DEVIATION: "偏离角色",
    FeedbackType.HISTORY_FORGET: "遗忘历史",
    FeedbackType.THINK_LEAK: "思考泄露",
}

FEEDBACK_TYPE_DESCRIPTIONS = {
    FeedbackType.FACT_ERROR: "回答内容与角色设定或已知事实不一致",
    FeedbackType.ROLE_DEVIATION: "回答偏离了角色的性格或说话风格",
    FeedbackType.HISTORY_FORGET: "回答忽略了之前的对话历史或上下文",
    FeedbackType.THINK_LEAK: "回答中暴露了模型的思考过程（如内部推理、分析步骤）",
}
