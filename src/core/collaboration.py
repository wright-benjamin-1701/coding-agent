"""
Collaboration and handoff features for team integration
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

from .config import ConfigManager, get_config


@dataclass
class SessionState:
    """Represents the current session state"""
    session_id: str
    started_at: float
    project_path: str
    conversation_history: List[Dict[str, Any]]
    active_tasks: List[Dict[str, Any]]
    project_context: Optional[Dict[str, Any]]
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HandoffPackage:
    """Package containing all information for handoff"""
    id: str
    created_at: float
    session_state: SessionState
    summary: str
    next_steps: List[str]
    context_notes: List[str]
    files_modified: List[str]
    git_status: Optional[Dict[str, Any]]
    format: str = "markdown"
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Manages session persistence and recovery"""
    
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or get_config()
        self.session_dir = Path(self.config.config.agent.session_dir)
        self.session_dir.mkdir(exist_ok=True)
        self.current_session: Optional[SessionState] = None
    
    def start_session(self, project_path: str) -> SessionState:
        """Start a new session"""
        
        session_id = f"session_{int(time.time())}"
        
        self.current_session = SessionState(
            session_id=session_id,
            started_at=time.time(),
            project_path=project_path,
            conversation_history=[],
            active_tasks=[],
            project_context=None,
            metadata={
                "agent_version": "1.0.0",
                "user_agent": "coding-agent"
            }
        )
        
        if self.config.config.agent.auto_save_session:
            self.save_session()
        
        return self.current_session
    
    def update_session(self, **updates) -> None:
        """Update current session with new information"""
        
        if not self.current_session:
            return
        
        for key, value in updates.items():
            if hasattr(self.current_session, key):
                setattr(self.current_session, key, value)
        
        if self.config.config.agent.auto_save_session:
            self.save_session()
    
    def save_session(self) -> bool:
        """Save current session to disk"""
        
        if not self.current_session:
            return False
        
        try:
            session_file = self.session_dir / f"{self.current_session.session_id}.json"
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.current_session), f, indent=2, default=str)
            
            return True
        except Exception as e:
            print(f"Warning: Could not save session: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[SessionState]:
        """Load session from disk"""
        
        try:
            session_file = self.session_dir / f"{session_id}.json"
            
            if not session_file.exists():
                return None
            
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Convert back to SessionState
            self.current_session = SessionState(**session_data)
            return self.current_session
        
        except Exception as e:
            print(f"Warning: Could not load session {session_id}: {e}")
            return None
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions"""
        
        sessions = []
        
        for session_file in self.session_dir.glob("session_*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                sessions.append({
                    "session_id": session_data.get("session_id"),
                    "started_at": session_data.get("started_at"),
                    "project_path": session_data.get("project_path"),
                    "conversation_length": len(session_data.get("conversation_history", [])),
                    "active_tasks": len(session_data.get("active_tasks", [])),
                    "file": str(session_file)
                })
            
            except Exception:
                continue
        
        # Sort by start time (newest first)
        sessions.sort(key=lambda x: x.get("started_at", 0), reverse=True)
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        
        try:
            session_file = self.session_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
                return True
        except Exception as e:
            print(f"Warning: Could not delete session {session_id}: {e}")
        
        return False
    
    def get_current_session(self) -> Optional[SessionState]:
        """Get current session state"""
        return self.current_session


class HandoffManager:
    """Manages handoff packages for team collaboration"""
    
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or get_config()
        self.handoff_dir = Path("handoffs")
        self.handoff_dir.mkdir(exist_ok=True)
    
    async def create_handoff_package(
        self, 
        session_state: SessionState,
        summary: str,
        next_steps: List[str],
        include_context: bool = True,
        include_history: bool = True,
        format: str = "markdown"
    ) -> HandoffPackage:
        """Create a comprehensive handoff package"""
        
        handoff_id = f"handoff_{int(time.time())}"
        
        # Gather additional context
        context_notes = await self._generate_context_notes(session_state)
        files_modified = await self._get_modified_files(session_state.project_path)
        git_status = await self._get_git_status(session_state.project_path)
        
        # Create filtered session state based on preferences
        filtered_session = self._filter_session_state(
            session_state, 
            include_context, 
            include_history
        )
        
        handoff_package = HandoffPackage(
            id=handoff_id,
            created_at=time.time(),
            session_state=filtered_session,
            summary=summary,
            next_steps=next_steps,
            context_notes=context_notes,
            files_modified=files_modified,
            git_status=git_status,
            format=format,
            metadata={
                "created_by": "coding-agent",
                "project_name": Path(session_state.project_path).name,
                "session_duration": time.time() - session_state.started_at
            }
        )
        
        # Save handoff package
        await self._save_handoff_package(handoff_package)
        
        return handoff_package
    
    def _filter_session_state(
        self, 
        session_state: SessionState, 
        include_context: bool, 
        include_history: bool
    ) -> SessionState:
        """Filter session state based on handoff preferences"""
        
        filtered_session = SessionState(
            session_id=session_state.session_id,
            started_at=session_state.started_at,
            project_path=session_state.project_path,
            conversation_history=session_state.conversation_history if include_history else [],
            active_tasks=session_state.active_tasks,
            project_context=session_state.project_context if include_context else None,
            user_preferences=session_state.user_preferences,
            metadata=session_state.metadata
        )
        
        # Limit conversation history to recent items if included
        if include_history and len(filtered_session.conversation_history) > 20:
            filtered_session.conversation_history = filtered_session.conversation_history[-20:]
        
        return filtered_session
    
    async def _generate_context_notes(self, session_state: SessionState) -> List[str]:
        """Generate contextual notes for handoff"""
        
        notes = []
        
        # Session information
        duration = time.time() - session_state.started_at
        notes.append(f"Session duration: {duration/60:.1f} minutes")
        
        # Project information
        project_name = Path(session_state.project_path).name
        notes.append(f"Working on project: {project_name}")
        
        # Task information
        if session_state.active_tasks:
            notes.append(f"Active tasks: {len(session_state.active_tasks)}")
            for task in session_state.active_tasks[-3:]:  # Last 3 tasks
                task_desc = task.get("description", "Unknown task")
                task_status = task.get("status", "unknown")
                notes.append(f"  - {task_desc} ({task_status})")
        
        # Conversation insights
        if session_state.conversation_history:
            recent_topics = self._extract_recent_topics(session_state.conversation_history)
            if recent_topics:
                notes.append("Recent discussion topics:")
                for topic in recent_topics:
                    notes.append(f"  - {topic}")
        
        return notes
    
    def _extract_recent_topics(self, conversation_history: List[Dict[str, Any]]) -> List[str]:
        """Extract recent topics from conversation history"""
        
        topics = []
        
        # Simple keyword extraction from recent messages
        recent_messages = conversation_history[-10:] if conversation_history else []
        
        for message in recent_messages:
            content = message.get("content", "").lower()
            
            # Look for key topics
            if "git" in content:
                topics.append("Git operations")
            elif any(word in content for word in ["refactor", "rename", "extract"]):
                topics.append("Code refactoring")
            elif any(word in content for word in ["debug", "error", "bug", "fix"]):
                topics.append("Debugging")
            elif any(word in content for word in ["search", "find", "look"]):
                topics.append("Code search")
            elif any(word in content for word in ["file", "read", "write", "create"]):
                topics.append("File operations")
        
        # Remove duplicates while preserving order
        unique_topics = []
        for topic in topics:
            if topic not in unique_topics:
                unique_topics.append(topic)
        
        return unique_topics
    
    async def _get_modified_files(self, project_path: str) -> List[str]:
        """Get list of recently modified files"""
        
        try:
            project_dir = Path(project_path)
            modified_files = []
            
            # Look for files modified in the last hour
            cutoff_time = time.time() - 3600  # 1 hour ago
            
            for file_path in project_dir.rglob("*"):
                if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                    try:
                        if file_path.stat().st_mtime > cutoff_time:
                            relative_path = file_path.relative_to(project_dir)
                            modified_files.append(str(relative_path))
                    except (OSError, ValueError):
                        continue
            
            return modified_files[:20]  # Limit to 20 files
        
        except Exception:
            return []
    
    async def _get_git_status(self, project_path: str) -> Optional[Dict[str, Any]]:
        """Get current git status"""
        
        try:
            import subprocess
            
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse git status output
                changed_files = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        status = line[:2]
                        filename = line[3:]
                        changed_files.append({"status": status, "file": filename})
                
                # Get current branch
                branch_result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
                
                return {
                    "current_branch": current_branch,
                    "changed_files": changed_files,
                    "has_changes": len(changed_files) > 0
                }
        
        except Exception:
            pass
        
        return None
    
    async def _save_handoff_package(self, package: HandoffPackage) -> None:
        """Save handoff package to disk"""
        
        try:
            if package.format == "markdown":
                await self._save_markdown_handoff(package)
            elif package.format == "json":
                await self._save_json_handoff(package)
            else:
                # Default to JSON
                await self._save_json_handoff(package)
        
        except Exception as e:
            print(f"Warning: Could not save handoff package: {e}")
    
    async def _save_markdown_handoff(self, package: HandoffPackage) -> None:
        """Save handoff package as markdown"""
        
        handoff_file = self.handoff_dir / f"{package.id}.md"
        
        # Create markdown content
        content = f"""# Project Handoff: {package.metadata.get('project_name', 'Unknown')}

**Handoff ID:** {package.id}  
**Created:** {datetime.fromtimestamp(package.created_at).strftime('%Y-%m-%d %H:%M:%S')}  
**Project:** {package.session_state.project_path}  
**Session Duration:** {package.metadata.get('session_duration', 0)/60:.1f} minutes

## Summary

{package.summary}

## Next Steps

"""
        
        for i, step in enumerate(package.next_steps, 1):
            content += f"{i}. {step}\n"
        
        if package.context_notes:
            content += "\n## Context Notes\n\n"
            for note in package.context_notes:
                content += f"- {note}\n"
        
        if package.files_modified:
            content += "\n## Recently Modified Files\n\n"
            for file in package.files_modified:
                content += f"- `{file}`\n"
        
        if package.git_status:
            content += f"\n## Git Status\n\n"
            content += f"**Current Branch:** {package.git_status.get('current_branch', 'unknown')}\n\n"
            
            if package.git_status.get('changed_files'):
                content += "**Changed Files:**\n"
                for change in package.git_status['changed_files']:
                    content += f"- `{change['status']}` {change['file']}\n"
        
        if package.session_state.active_tasks:
            content += "\n## Active Tasks\n\n"
            for task in package.session_state.active_tasks:
                status = task.get('status', 'unknown')
                desc = task.get('description', 'Unknown task')
                content += f"- **{desc}** ({status})\n"
        
        if package.session_state.conversation_history:
            content += f"\n## Recent Conversation History\n\n"
            content += f"*Last {len(package.session_state.conversation_history)} messages*\n\n"
            
            for msg in package.session_state.conversation_history[-5:]:  # Last 5 messages
                role = msg.get('role', 'unknown')
                content_text = msg.get('content', '')[:200]  # Truncate long messages
                if len(msg.get('content', '')) > 200:
                    content_text += "..."
                content += f"**{role.title()}:** {content_text}\n\n"
        
        content += f"\n---\n*Generated by Coding Agent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        
        with open(handoff_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    async def _save_json_handoff(self, package: HandoffPackage) -> None:
        """Save handoff package as JSON"""
        
        handoff_file = self.handoff_dir / f"{package.id}.json"
        
        with open(handoff_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(package), f, indent=2, default=str)
    
    def load_handoff_package(self, handoff_id: str) -> Optional[HandoffPackage]:
        """Load handoff package from disk"""
        
        # Try different formats
        for ext in ['.json', '.md']:
            handoff_file = self.handoff_dir / f"{handoff_id}{ext}"
            
            if handoff_file.exists():
                if ext == '.json':
                    return self._load_json_handoff(handoff_file)
                # For markdown, we'd need to parse it back (complex)
                # For now, just return None for markdown files
        
        return None
    
    def _load_json_handoff(self, handoff_file: Path) -> Optional[HandoffPackage]:
        """Load JSON handoff package"""
        
        try:
            with open(handoff_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruct HandoffPackage
            session_data = data['session_state']
            session_state = SessionState(**session_data)
            
            return HandoffPackage(
                id=data['id'],
                created_at=data['created_at'],
                session_state=session_state,
                summary=data['summary'],
                next_steps=data['next_steps'],
                context_notes=data['context_notes'],
                files_modified=data['files_modified'],
                git_status=data.get('git_status'),
                format=data.get('format', 'json'),
                metadata=data.get('metadata', {})
            )
        
        except Exception as e:
            print(f"Warning: Could not load handoff package: {e}")
            return None
    
    def list_handoff_packages(self) -> List[Dict[str, Any]]:
        """List all available handoff packages"""
        
        packages = []
        
        for handoff_file in self.handoff_dir.glob("handoff_*"):
            try:
                if handoff_file.suffix == '.json':
                    with open(handoff_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    packages.append({
                        "id": data.get("id"),
                        "created_at": data.get("created_at"),
                        "project_name": data.get("metadata", {}).get("project_name"),
                        "summary": data.get("summary", "")[:100],  # Truncate
                        "format": data.get("format", "json"),
                        "file": str(handoff_file)
                    })
                
                elif handoff_file.suffix == '.md':
                    # Basic info from markdown files
                    packages.append({
                        "id": handoff_file.stem,
                        "created_at": handoff_file.stat().st_mtime,
                        "project_name": "Unknown",
                        "summary": "Markdown handoff",
                        "format": "markdown",
                        "file": str(handoff_file)
                    })
            
            except Exception:
                continue
        
        # Sort by creation time (newest first)
        packages.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return packages


# Global instances
_session_manager: Optional[SessionManager] = None
_handoff_manager: Optional[HandoffManager] = None


def get_session_manager() -> SessionManager:
    """Get global session manager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def get_handoff_manager() -> HandoffManager:
    """Get global handoff manager instance"""
    global _handoff_manager
    if _handoff_manager is None:
        _handoff_manager = HandoffManager()
    return _handoff_manager