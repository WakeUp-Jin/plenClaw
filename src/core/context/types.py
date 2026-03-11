from enum import Enum


class ContextType(Enum):
    SYSTEM_PROMPT = "system_prompt"
    MEMORY = "memory"
    CONVERSATION = "conversation"
    TOOL_SEQUENCE = "tool_sequence"
