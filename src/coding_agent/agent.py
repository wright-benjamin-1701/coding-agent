"""Main coding agent that coordinates all components."""

import subprocess
from typing import List, Dict, Any
from .types import Context
from .config import ConfigManager, AgentConfig
from .providers.ollama import OllamaProvider
from .prompt_manager import PromptManager
from .tools.registry import ToolRegistry
from .tools.file_tools import ReadFileTool, WriteFileTool, SearchFilesTool
from .tools.git_tools import GitStatusTool, GitDiffTool, GitCommitHashTool
from .tools.brainstorm_tool import BrainstormSearchTermsTool
from .tools.test_tools import RunTestsTool, LintCodeTool
from .orchestrator import PlanOrchestrator
from .executor import PlanExecutor
from .database.rag_db import RAGDatabase
from .indexer.file_indexer import FileIndexer


class CodingAgent:
    """Main coding agent that coordinates all components."""
    
    def __init__(self, config_path: str = None):
        # Load configuration
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config()
        
        # Initialize components based on config
        self.model_provider = self._create_model_provider()
        self.prompt_manager = PromptManager()
        self.tool_registry = ToolRegistry()
        self.rag_db = RAGDatabase(self.config.database.db_path)
        self.file_indexer = FileIndexer(
            index_file=self.config.indexer.index_file
        )
        
        # Register core tools
        self._register_tools()
        
        # Initialize orchestrator and executor
        self.orchestrator = PlanOrchestrator(
            self.model_provider,
            self.prompt_manager,
            self.tool_registry
        )
        self.executor = PlanExecutor(self.tool_registry)
    
    def _create_model_provider(self):
        """Create model provider based on configuration."""
        if self.config.model.provider == "ollama":
            return OllamaProvider(
                model=self.config.model.model,
                base_url=self.config.model.base_url
            )
        else:
            raise ValueError(f"Unknown model provider: {self.config.model.provider}")
    
    def _register_tools(self):
        """Register all available tools."""
        # File tools
        self.tool_registry.register(ReadFileTool())
        self.tool_registry.register(WriteFileTool())
        self.tool_registry.register(SearchFilesTool())
        
        # Git tools
        self.tool_registry.register(GitStatusTool())
        self.tool_registry.register(GitDiffTool())
        self.tool_registry.register(GitCommitHashTool())
        
        # Brainstorming and analysis tools
        self.tool_registry.register(BrainstormSearchTermsTool())
        
        # Testing tools
        self.tool_registry.register(RunTestsTool())
        self.tool_registry.register(LintCodeTool())
    
    def process_request(self, user_prompt: str) -> str:
        """Process a user request and return the result."""
        try:
            # Build context
            context = self._build_context(user_prompt)
            
            # Generate plan
            print("🔄 Generating execution plan...")
            plan = self.orchestrator.generate_plan(context)
            
            if not plan.actions:
                return "No actions generated for this request."
            
            # Show plan to user
            print(f"\n📋 Plan ({len(plan.actions)} actions):")
            for i, action in enumerate(plan.actions, 1):
                if hasattr(action, 'tool_name'):
                    print(f"  {i}. {action.tool_name}: {action.parameters}")
                else:
                    print(f"  {i}. Confirmation: {action.message}")
            
            # Execute plan
            print("\n⚡ Executing plan...")
            results = self.executor.execute_plan(plan)
            
            # Generate summary
            summary = self._generate_summary(user_prompt, results)
            
            # Store session
            self.rag_db.store_session(
                user_prompt=user_prompt,
                commit_hash=context.current_commit,
                modified_files=context.modified_files,
                summary=summary,
                execution_log=self.executor.execution_log
            )
            
            return summary
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def _build_context(self, user_prompt: str) -> Context:
        """Build context for the request."""
        # Get current commit
        try:
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"], 
                capture_output=True, text=True
            )
            current_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unknown"
        except:
            current_commit = "unknown"
        
        # Get modified files
        try:
            status_result = subprocess.run(
                ["git", "status", "--porcelain"], 
                capture_output=True, text=True
            )
            modified_files = []
            if status_result.returncode == 0:
                for line in status_result.stdout.split('\n'):
                    if line.strip():
                        # Extract filename from git status output
                        filename = line[3:].strip()
                        modified_files.append(filename)
        except:
            modified_files = []
        
        # Get recent summaries
        recent_summaries = self.rag_db.get_recent_summaries(self.config.database.max_summaries)
        
        return Context(
            user_prompt=user_prompt,
            current_commit=current_commit,
            modified_files=modified_files,
            recent_summaries=recent_summaries
        )
    
    def _generate_summary(self, user_prompt: str, results: List) -> str:
        """Generate a 1-2 sentence summary of what was accomplished."""
        successful_actions = sum(1 for r in results if hasattr(r, 'success') and r.success)
        total_actions = len(results)
        
        if successful_actions == 0:
            return f"Failed to complete request: {user_prompt}"
        elif successful_actions == total_actions:
            return f"Successfully completed: {user_prompt}"
        else:
            return f"Partially completed ({successful_actions}/{total_actions} actions): {user_prompt}"
    
    def initialize(self):
        """Initialize the agent (build initial index, check dependencies)."""
        print("🚀 Initializing coding agent...")
        
        # Check if Ollama is available
        if not self.model_provider.is_available():
            print("⚠️  Warning: Ollama not available at configured URL")
            return False
        
        # Build initial file index
        print("📁 Building file index...")
        updated_files = self.file_indexer.build_full_index()
        print(f"   Indexed {len(updated_files)} files")
        
        print("✅ Agent initialized successfully!")
        return True