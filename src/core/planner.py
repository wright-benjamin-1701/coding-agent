"""
Task planning and decomposition for complex operations
"""
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from .config import ConfigManager, get_config


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskStep:
    """Individual step in a task plan"""
    id: str
    description: str
    tool: str
    parameters: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    estimated_duration: Optional[int] = None  # seconds


@dataclass
class TaskPlan:
    """Complete task execution plan"""
    id: str
    title: str
    description: str
    steps: List[TaskStep]
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    total_estimated_duration: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskPlanner:
    """Plans and decomposes complex tasks into executable steps"""
    
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or get_config()
        self.active_plans: Dict[str, TaskPlan] = {}
        self.completed_plans: List[TaskPlan] = []
        self.plan_counter = 0
    
    async def create_plan(self, user_request: str, context: Dict[str, Any]) -> TaskPlan:
        """Create a task plan from user request"""
        
        self.plan_counter += 1
        plan_id = f"plan_{self.plan_counter}_{int(time.time())}"
        
        # Analyze request complexity and decompose
        analysis = await self._analyze_request_complexity(user_request, context)
        
        # Generate steps based on analysis
        steps = await self._generate_steps(analysis, context)
        
        # Calculate dependencies and estimates
        self._calculate_dependencies(steps)
        total_duration = self._estimate_total_duration(steps)
        
        plan = TaskPlan(
            id=plan_id,
            title=analysis.get("title", "User Task"),
            description=user_request,
            steps=steps,
            priority=self._determine_priority(analysis),
            total_estimated_duration=total_duration,
            metadata={
                "complexity": analysis.get("complexity", "medium"),
                "requires_user_input": analysis.get("requires_user_input", False),
                "can_be_paused": analysis.get("can_be_paused", True),
                "tools_needed": analysis.get("tools_needed", [])
            }
        )
        
        self.active_plans[plan_id] = plan
        return plan
    
    async def _analyze_request_complexity(self, request: str, _context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze request to determine complexity and requirements"""
        
        # Simple analysis based on keywords and patterns
        analysis = {
            "complexity": "medium",
            "requires_user_input": False,
            "can_be_paused": True,
            "tools_needed": [],
            "estimated_steps": 1,
            "title": "Task"
        }
        
        request_lower = request.lower()
        
        # Determine complexity
        high_complexity_indicators = [
            "refactor", "migrate", "implement", "create project", "setup", "deploy",
            "analyze entire", "multiple files", "across all", "throughout"
        ]
        
        low_complexity_indicators = [
            "show", "list", "display", "what is", "help", "status", "simple"
        ]
        
        if any(indicator in request_lower for indicator in high_complexity_indicators):
            analysis["complexity"] = "high"
            analysis["estimated_steps"] = 5
        elif any(indicator in request_lower for indicator in low_complexity_indicators):
            analysis["complexity"] = "low"
            analysis["estimated_steps"] = 1
        else:
            analysis["estimated_steps"] = 3
        
        # Determine required tools
        tool_indicators = {
            "file": ["read", "write", "create", "edit", "file"],
            "git": ["commit", "branch", "merge", "git", "repository"],
            "search": ["find", "search", "look for", "locate"],
            "refactor": ["rename", "extract", "refactor", "reorganize"],
            "debug": ["error", "bug", "debug", "fix", "problem", "issue"]
        }
        
        for tool, keywords in tool_indicators.items():
            if any(keyword in request_lower for keyword in keywords):
                analysis["tools_needed"].append(tool)
        
        # Determine if user input might be needed
        clarification_indicators = [
            "best way", "should i", "how to", "which", "what approach", "prefer"
        ]
        
        if any(indicator in request_lower for indicator in clarification_indicators):
            analysis["requires_user_input"] = True
        
        # Generate appropriate title
        if "git" in analysis["tools_needed"]:
            analysis["title"] = "Git Operation"
        elif "refactor" in analysis["tools_needed"]:
            analysis["title"] = "Code Refactoring"
        elif "search" in analysis["tools_needed"]:
            analysis["title"] = "Code Search"
        elif any(word in request_lower for word in ["create", "implement", "build"]):
            analysis["title"] = "Development Task"
        else:
            analysis["title"] = "General Task"
        
        return analysis
    
    async def _generate_steps(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> List[TaskStep]:
        """Generate concrete steps based on analysis"""
        
        steps: List[TaskStep] = []
        step_counter = 0
        
        def create_step(description: str, tool: str, parameters: Dict[str, Any], 
                       dependencies: Optional[List[str]] = None, duration: int = 30) -> TaskStep:
            nonlocal step_counter
            step_counter += 1
            return TaskStep(
                id=f"step_{step_counter}",
                description=description,
                tool=tool,
                parameters=parameters,
                dependencies=dependencies or [],
                estimated_duration=duration
            )
        
        tools_needed = analysis.get("tools_needed", [])
        complexity = analysis.get("complexity", "medium")
        
        # Add context gathering step for complex tasks
        if complexity in ["medium", "high"]:
            steps.append(create_step(
                "Gather project context and understand current state",
                "context",
                {"action": "analyze_project"},
                duration=10
            ))
        
        # Add tool-specific steps
        if "search" in tools_needed:
            steps.append(create_step(
                "Search codebase for relevant information",
                "search",
                {"query": "determined_at_runtime", "search_type": "text"},
                dependencies=["step_1"] if steps else [],
                duration=20
            ))
        
        if "file" in tools_needed:
            steps.append(create_step(
                "Read/write files as needed",
                "file",
                {"action": "determined_at_runtime"},
                duration=15
            ))
        
        if "git" in tools_needed:
            steps.append(create_step(
                "Perform git operations",
                "git",
                {"action": "determined_at_runtime"},
                duration=10
            ))
        
        if "refactor" in tools_needed:
            steps.append(create_step(
                "Refactor code as requested",
                "refactor",
                {"action": "determined_at_runtime"},
                duration=60
            ))
        
        if "debug" in tools_needed:
            steps.append(create_step(
                "Analyze and fix issues",
                "debug",
                {"action": "analyze_error"},
                duration=45
            ))
        
        # Add verification step for complex operations
        if complexity == "high" and len(steps) > 2:
            steps.append(create_step(
                "Verify changes and ensure everything works correctly",
                "verification",
                {"action": "verify_changes"},
                dependencies=[step.id for step in steps[-2:]],
                duration=20
            ))
        
        # Add summary step for analysis tasks
        # Check both the analysis title and the original user request
        title_text = analysis.get("title", "").lower()
        user_request = context.get("user_request", "").lower() if context else ""
        
        analysis_keywords = ["analysis", "analyze", "summary", "summarize", "explain", "understand", "describe", "overview", "what", "how"]
        
        should_add_summary = (
            any(word in title_text for word in analysis_keywords) or
            any(word in user_request for word in analysis_keywords) or
            # Also add summary if we're working with files and searching (likely analysis)
            ("file" in analysis.get("tools_needed", []) and "search" in analysis.get("tools_needed", [])) or
            # Check if tools_needed from context analysis indicate analysis work
            (tools_needed and "file" in tools_needed and "search" in tools_needed)
        )
        
        if should_add_summary:
            steps.append(create_step(
                "Generate comprehensive summary of findings",
                "summary",
                {
                    "task_description": "determined_at_runtime",
                    "focus": "overview"
                },
                dependencies=[step.id for step in steps[-2:]] if len(steps) >= 2 else [steps[-1].id] if steps else [],
                duration=15
            ))
        
        # Add final reporting step
        steps.append(create_step(
            "Summarize results and provide final report",
            "reporting",
            {"action": "generate_summary"},
            dependencies=[steps[-1].id] if steps else [],
            duration=5
        ))
        
        return steps
    
    def _calculate_dependencies(self, steps: List[TaskStep]) -> None:
        """Calculate and set dependencies between steps"""
        
        # For now, use simple sequential dependencies
        # More sophisticated dependency analysis could be added
        for i in range(1, len(steps)):
            if not steps[i].dependencies:
                steps[i].dependencies = [steps[i-1].id]
    
    def _estimate_total_duration(self, steps: List[TaskStep]) -> int:
        """Estimate total duration considering dependencies"""
        
        # Simple sum for sequential tasks
        # Could be improved with parallel execution analysis
        return sum(step.estimated_duration or 30 for step in steps)
    
    def _determine_priority(self, analysis: Dict[str, Any]) -> TaskPriority:
        """Determine task priority based on analysis"""
        
        complexity = analysis.get("complexity", "medium")
        tools_needed = analysis.get("tools_needed", [])
        
        # High priority for critical operations
        if "git" in tools_needed and complexity == "high":
            return TaskPriority.HIGH
        
        # Medium priority for refactoring and debugging
        if any(tool in tools_needed for tool in ["refactor", "debug"]):
            return TaskPriority.MEDIUM
        
        # Low priority for simple queries
        if complexity == "low":
            return TaskPriority.LOW
        
        return TaskPriority.MEDIUM
    
    def get_next_executable_step(self, plan_id: str) -> Optional[TaskStep]:
        """Get the next step that can be executed"""
        
        if plan_id not in self.active_plans:
            return None
        
        plan = self.active_plans[plan_id]
        
        for step in plan.steps:
            if step.status != TaskStatus.PENDING:
                continue
            
            # Check if all dependencies are completed
            if self._are_dependencies_completed(step, plan):
                return step
        
        return None
    
    def _are_dependencies_completed(self, step: TaskStep, plan: TaskPlan) -> bool:
        """Check if all step dependencies are completed"""
        
        if not step.dependencies:
            return True
        
        step_status_map = {s.id: s.status for s in plan.steps}
        
        for dep_id in step.dependencies:
            if dep_id not in step_status_map:
                return False
            if step_status_map[dep_id] != TaskStatus.COMPLETED:
                return False
        
        return True
    
    def update_step_status(self, plan_id: str, step_id: str, status: TaskStatus, 
                          result: Any = None, error: Optional[str] = None) -> bool:
        """Update step status and result"""
        
        if plan_id not in self.active_plans:
            return False
        
        plan = self.active_plans[plan_id]
        
        for step in plan.steps:
            if step.id == step_id:
                step.status = status
                step.result = result
                step.error = error
                
                if status == TaskStatus.IN_PROGRESS:
                    step.started_at = time.time()
                elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    step.completed_at = time.time()
                
                # Update plan status if needed
                self._update_plan_status(plan)
                return True
        
        return False
    
    def _update_plan_status(self, plan: TaskPlan) -> None:
        """Update overall plan status based on step statuses"""
        
        step_statuses = [step.status for step in plan.steps]
        
        if all(status == TaskStatus.COMPLETED for status in step_statuses):
            plan.status = TaskStatus.COMPLETED
            plan.completed_at = time.time()
            # Move to completed plans
            if plan.id in self.active_plans:
                del self.active_plans[plan.id]
                self.completed_plans.append(plan)
        
        elif any(status == TaskStatus.FAILED for status in step_statuses):
            plan.status = TaskStatus.FAILED
        elif any(status == TaskStatus.IN_PROGRESS for status in step_statuses):
            if plan.status == TaskStatus.PENDING:
                plan.status = TaskStatus.IN_PROGRESS
                plan.started_at = time.time()
        elif any(status == TaskStatus.PAUSED for status in step_statuses):
            plan.status = TaskStatus.PAUSED
    
    def pause_plan(self, plan_id: str) -> bool:
        """Pause plan execution"""
        
        if plan_id not in self.active_plans:
            return False
        
        plan = self.active_plans[plan_id]
        if not plan.metadata.get("can_be_paused", True):
            return False
        
        plan.status = TaskStatus.PAUSED
        
        # Pause any in-progress steps
        for step in plan.steps:
            if step.status == TaskStatus.IN_PROGRESS:
                step.status = TaskStatus.PAUSED
        
        return True
    
    def resume_plan(self, plan_id: str) -> bool:
        """Resume paused plan execution"""
        
        if plan_id not in self.active_plans:
            return False
        
        plan = self.active_plans[plan_id]
        if plan.status != TaskStatus.PAUSED:
            return False
        
        plan.status = TaskStatus.IN_PROGRESS
        
        # Resume paused steps
        for step in plan.steps:
            if step.status == TaskStatus.PAUSED:
                step.status = TaskStatus.PENDING
        
        return True
    
    def cancel_plan(self, plan_id: str) -> bool:
        """Cancel plan execution"""
        
        if plan_id not in self.active_plans:
            return False
        
        plan = self.active_plans[plan_id]
        plan.status = TaskStatus.CANCELLED
        
        # Cancel all pending and in-progress steps
        for step in plan.steps:
            if step.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.PAUSED]:
                step.status = TaskStatus.CANCELLED
        
        # Move to completed plans
        del self.active_plans[plan_id]
        self.completed_plans.append(plan)
        
        return True
    
    def get_plan_progress(self, plan_id: str) -> Dict[str, Any]:
        """Get plan execution progress"""
        
        plan = self.active_plans.get(plan_id) or next(
            (p for p in self.completed_plans if p.id == plan_id), None
        )
        
        if not plan:
            return {}
        
        total_steps = len(plan.steps)
        completed_steps = sum(1 for step in plan.steps if step.status == TaskStatus.COMPLETED)
        failed_steps = sum(1 for step in plan.steps if step.status == TaskStatus.FAILED)
        
        progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        return {
            "plan_id": plan.id,
            "title": plan.title,
            "status": plan.status.value,
            "progress_percentage": progress_percentage,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "failed_steps": failed_steps,
            "estimated_remaining_time": self._estimate_remaining_time(plan),
            "elapsed_time": self._calculate_elapsed_time(plan)
        }
    
    def _estimate_remaining_time(self, plan: TaskPlan) -> Optional[int]:
        """Estimate remaining execution time"""
        
        if plan.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return 0
        
        remaining_time = 0
        for step in plan.steps:
            if step.status == TaskStatus.PENDING:
                remaining_time += step.estimated_duration or 30
        
        return remaining_time
    
    def _calculate_elapsed_time(self, plan: TaskPlan) -> Optional[int]:
        """Calculate elapsed execution time"""
        
        if not plan.started_at:
            return 0
        
        end_time = plan.completed_at or time.time()
        return int(end_time - plan.started_at)
    
    def get_active_plans(self) -> List[TaskPlan]:
        """Get all active plans"""
        return list(self.active_plans.values())
    
    def get_plan_summary(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed plan summary"""
        
        plan = self.active_plans.get(plan_id) or next(
            (p for p in self.completed_plans if p.id == plan_id), None
        )
        
        if not plan:
            return None
        
        return {
            "id": plan.id,
            "title": plan.title,
            "description": plan.description,
            "status": plan.status.value,
            "priority": plan.priority.value,
            "created_at": plan.created_at,
            "started_at": plan.started_at,
            "completed_at": plan.completed_at,
            "total_estimated_duration": plan.total_estimated_duration,
            "steps": [
                {
                    "id": step.id,
                    "description": step.description,
                    "tool": step.tool,
                    "status": step.status.value,
                    "dependencies": step.dependencies,
                    "estimated_duration": step.estimated_duration,
                    "error": step.error
                }
                for step in plan.steps
            ],
            "metadata": plan.metadata,
            "progress": self.get_plan_progress(plan_id)
        }


# Global task planner instance
_task_planner: Optional[TaskPlanner] = None


def get_task_planner() -> TaskPlanner:
    """Get global task planner instance"""
    global _task_planner
    if _task_planner is None:
        _task_planner = TaskPlanner()
    return _task_planner