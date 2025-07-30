"""Core types and schemas."""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel
from enum import Enum


class ActionType(str, Enum):
    TOOL_USE = "tool_use"
    CONFIRMATION = "confirmation"


class ToolAction(BaseModel):
    type: ActionType = ActionType.TOOL_USE
    tool_name: str
    parameters: Dict[str, Any]


class ConfirmationAction(BaseModel):
    type: ActionType = ActionType.CONFIRMATION
    message: str
    destructive: bool = True


class Plan(BaseModel):
    actions: List[Union[ToolAction, ConfirmationAction]]


class ToolResult(BaseModel):
    success: bool
    output: Any
    error: Optional[str] = None


class Context(BaseModel):
    recent_summaries: List[str]
    modified_files: List[str]
    current_commit: str
    user_prompt: str


class ModelResponse(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None