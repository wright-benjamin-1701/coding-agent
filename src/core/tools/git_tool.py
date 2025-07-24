"""
Git operations tool for version control
"""
import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from .base import BaseTool, ToolParameter, ToolResult


class GitTool(BaseTool):
    """Tool for Git version control operations"""
    
    def get_description(self) -> str:
        return "Perform Git operations like status, diff, commit, branch management"
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Git action: status, diff, add, commit, branch, log, push, pull",
                required=True
            ),
            ToolParameter(
                name="files",
                type="string",
                description="Files to operate on (space-separated, optional)",
                required=False
            ),
            ToolParameter(
                name="message",
                type="string",
                description="Commit message (for commit action)",
                required=False
            ),
            ToolParameter(
                name="branch_name",
                type="string",
                description="Branch name (for branch operations)",
                required=False
            ),
            ToolParameter(
                name="remote",
                type="string",
                description="Remote name (default: origin)",
                required=False,
                default="origin"
            )
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute Git operation"""
        if not self.validate_parameters(kwargs):
            return ToolResult(success=False, error="Invalid parameters")
        
        action = kwargs.get("action")
        
        # Check if we're in a git repository
        if not await self._is_git_repo():
            return ToolResult(success=False, error="Not in a Git repository")
        
        try:
            if action == "status":
                return await self._git_status()
            elif action == "diff":
                return await self._git_diff(kwargs.get("files"))
            elif action == "add":
                return await self._git_add(kwargs.get("files", "."))
            elif action == "commit":
                return await self._git_commit(kwargs.get("message"))
            elif action == "branch":
                return await self._git_branch(kwargs.get("branch_name"))
            elif action == "log":
                return await self._git_log()
            elif action == "push":
                return await self._git_push(kwargs.get("remote", "origin"))
            elif action == "pull":
                return await self._git_pull(kwargs.get("remote", "origin"))
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _run_git_command(self, args: List[str]) -> tuple[bool, str, str]:
        """Run git command and return success, stdout, stderr"""
        try:
            process = await asyncio.create_subprocess_exec(
                "git", *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd()
            )
            
            stdout, stderr = await process.communicate()
            
            return (
                process.returncode == 0,
                stdout.decode('utf-8').strip(),
                stderr.decode('utf-8').strip()
            )
        except Exception as e:
            return False, "", str(e)
    
    async def _is_git_repo(self) -> bool:
        """Check if current directory is a git repository"""
        success, _, _ = await self._run_git_command(["rev-parse", "--git-dir"])
        return success
    
    async def _git_status(self) -> ToolResult:
        """Get git status"""
        success, stdout, stderr = await self._run_git_command(["status", "--porcelain"])
        
        if not success:
            return ToolResult(success=False, error=stderr)
        
        # Parse status output
        files = []
        for line in stdout.split('\n'):
            if line.strip():
                status = line[:2]
                filename = line[3:].strip()
                files.append({
                    "file": filename,
                    "status": status,
                    "staged": status[0] != ' ' and status[0] != '?',
                    "modified": status[1] != ' '
                })
        
        return ToolResult(
            success=True,
            content=f"Repository status: {len(files)} changed files",
            data={"files": files}
        )
    
    async def _git_diff(self, files: Optional[str] = None) -> ToolResult:
        """Get git diff"""
        args = ["diff"]
        if files:
            args.extend(files.split())
        
        success, stdout, stderr = await self._run_git_command(args)
        
        if not success:
            return ToolResult(success=False, error=stderr)
        
        return ToolResult(
            success=True,
            content=stdout or "No differences found",
            data={"diff": stdout, "files": files}
        )
    
    async def _git_add(self, files: str) -> ToolResult:
        """Add files to staging area"""
        args = ["add"] + files.split()
        
        success, stdout, stderr = await self._run_git_command(args)
        
        if not success:
            return ToolResult(success=False, error=stderr)
        
        return ToolResult(
            success=True,
            content=f"Added files to staging: {files}",
            data={"files": files}
        )
    
    async def _git_commit(self, message: Optional[str] = None) -> ToolResult:
        """Create git commit"""
        if not message:
            return ToolResult(success=False, error="Commit message is required")
        
        args = ["commit", "-m", message]
        
        success, stdout, stderr = await self._run_git_command(args)
        
        if not success:
            return ToolResult(success=False, error=stderr)
        
        return ToolResult(
            success=True,
            content=f"Committed with message: {message}",
            data={"message": message, "output": stdout}
        )
    
    async def _git_branch(self, branch_name: Optional[str] = None) -> ToolResult:
        """List or create branches"""
        if branch_name:
            # Create new branch
            success, stdout, stderr = await self._run_git_command(["checkout", "-b", branch_name])
            
            if not success:
                return ToolResult(success=False, error=stderr)
            
            return ToolResult(
                success=True,
                content=f"Created and switched to branch: {branch_name}",
                data={"branch": branch_name}
            )
        else:
            # List branches
            success, stdout, stderr = await self._run_git_command(["branch"])
            
            if not success:
                return ToolResult(success=False, error=stderr)
            
            branches = []
            current_branch = None
            
            for line in stdout.split('\n'):
                if line.strip():
                    if line.startswith('*'):
                        current_branch = line[2:].strip()
                        branches.append({"name": current_branch, "current": True})
                    else:
                        branches.append({"name": line.strip(), "current": False})
            
            return ToolResult(
                success=True,
                content=f"Current branch: {current_branch}",
                data={"branches": branches, "current": current_branch}
            )
    
    async def _git_log(self, count: int = 10) -> ToolResult:
        """Get git log"""
        args = ["log", f"--max-count={count}", "--oneline"]
        
        success, stdout, stderr = await self._run_git_command(args)
        
        if not success:
            return ToolResult(success=False, error=stderr)
        
        commits = []
        for line in stdout.split('\n'):
            if line.strip():
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1]
                    })
        
        return ToolResult(
            success=True,
            content=f"Recent {len(commits)} commits",
            data={"commits": commits}
        )
    
    async def _git_push(self, remote: str) -> ToolResult:
        """Push to remote repository"""
        success, stdout, stderr = await self._run_git_command(["push", remote])
        
        if not success:
            return ToolResult(success=False, error=stderr)
        
        return ToolResult(
            success=True,
            content=f"Pushed to {remote}",
            data={"remote": remote, "output": stdout}
        )
    
    async def _git_pull(self, remote: str) -> ToolResult:
        """Pull from remote repository"""
        success, stdout, stderr = await self._run_git_command(["pull", remote])
        
        if not success:
            return ToolResult(success=False, error=stderr)
        
        return ToolResult(
            success=True,
            content=f"Pulled from {remote}",
            data={"remote": remote, "output": stdout}
        )
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.get_description(),
            "async": True,
            "safe": False,  # Git operations can modify repository state
            "categories": ["vcs", "git"]
        }