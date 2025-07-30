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


class PlanMetadata(BaseModel):
    step_number: int = 1
    is_final: bool = False
    confidence: float = 1.0
    reasoning: Optional[str] = None
    expected_follow_up: bool = True


class Plan(BaseModel):
    actions: List[Union[ToolAction, ConfirmationAction]]
    metadata: Optional[PlanMetadata] = None


class ToolResult(BaseModel):
    success: bool
    output: Any
    error: Optional[str] = None
    action_description: Optional[str] = None


class Context(BaseModel):
    recent_summaries: List[str]
    modified_files: List[str]
    current_commit: str
    user_prompt: str
    debug: bool = False


class ModelResponse(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None