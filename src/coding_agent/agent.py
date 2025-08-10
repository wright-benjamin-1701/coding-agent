"""Main coding agent that coordinates all components."""

import subprocess
from typing import List, Dict, Any
from .types import Context
from .config import ConfigManager, AgentConfig
from .providers.ollama import OllamaProvider
from .prompt_manager import PromptManager
from .tools.registry import ToolRegistry
from .tools.file_tools import ReadFileTool, WriteFileTool, SearchFilesTool
from .tools.smart_write_tool import SmartWriteTool
from .tools.file_move_tool import FileMoverTool
from .tools.git_tools import GitStatusTool, GitDiffTool, GitCommitHashTool
from .tools.brainstorm_tool import BrainstormSearchTermsTool
from .tools.test_tools import RunTestsTool, LintCodeTool
from .tools.analysis_tools import SummarizeCodeTool, AnalyzeCodeTool
from .tools.directive_tools import DirectiveManagementTool
from .tools.code_generation_tools import CodeGeneratorTool
from .tools.refactoring_tools import RefactoringTool
from .tools.security_tools import SecurityScanTool
from .tools.architecture_tools import ArchitectureAnalysisTool
from .tools.test_generator_tool import TestGeneratorTool
from .orchestrator import PlanOrchestrator
from .executor import PlanExecutor
from .database.rag_db import RAGDatabase
from .indexer.file_indexer import FileIndexer
from .cache_service import CacheService


class CodingAgent:
    """Main coding agent that coordinates all components."""
    
    def __init__(self, config_path: str = None):
        # Load configuration
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config()
        
        # Initialize components based on config
        self.model_provider = self._create_model_provider()
        self.prompt_manager = PromptManager(self.config)
        self.tool_registry = ToolRegistry()
        self.rag_db = RAGDatabase(self.config.database.db_path)
        self.cache_service = CacheService(self.rag_db)
        self.file_indexer = FileIndexer(
            root_path=".",
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
        self.executor = PlanExecutor(self.tool_registry, self.config)
    
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
        # File tools (with cache service)
        read_tool = ReadFileTool(self.cache_service)
        search_tool = SearchFilesTool()
        self.tool_registry.register(read_tool)
        self.tool_registry.register(WriteFileTool())
        self.tool_registry.register(search_tool)
        self.tool_registry.register(SmartWriteTool(self.cache_service, search_tool, read_tool))
        self.tool_registry.register(FileMoverTool(self.cache_service, read_tool, search_tool))
        
        # Git tools
        self.tool_registry.register(GitStatusTool())
        self.tool_registry.register(GitDiffTool())
        self.tool_registry.register(GitCommitHashTool())
        
        # Brainstorming and analysis tools
        self.tool_registry.register(BrainstormSearchTermsTool())
        
        # Testing tools
        self.tool_registry.register(RunTestsTool())
        self.tool_registry.register(LintCodeTool())
        
        # Analysis tools (pass model provider for LLM analysis)
        self.tool_registry.register(SummarizeCodeTool(self.model_provider))
        self.tool_registry.register(AnalyzeCodeTool(self.model_provider))
        
        # Directive management tool
        self.tool_registry.register(DirectiveManagementTool(self.config_manager))
        
        # Code generation and development tools
        self.tool_registry.register(CodeGeneratorTool(self.model_provider))
        self.tool_registry.register(RefactoringTool())
        self.tool_registry.register(SecurityScanTool())
        self.tool_registry.register(ArchitectureAnalysisTool())
        self.tool_registry.register(TestGeneratorTool(self.model_provider, self.cache_service, read_tool, search_tool))
        
        # Web viewer tool for debugging AI interactions
        from .tools.web_viewer_tool import WebViewerTool
        self.tool_registry.register(WebViewerTool(agent_instance=self))
    
    def process_request(self, user_prompt: str) -> str:
        """Process a user request with multi-step planning and execution."""
        try:
            # Build context
            context = self._build_context(user_prompt)
            
            # Multi-step execution loop with intelligent stopping
            all_results = []
            step = 1
            max_steps = self._calculate_max_steps(context)
            
            while step <= max_steps:
                print(f"🔄 Generating execution plan (step {step})...")
                
                # Generate plan with step information
                filtered_results = self._filter_results_for_context(all_results, step)
                plan = self.orchestrator.generate_plan(context, filtered_results, step)
                
                # Handle empty plans
                if not plan.actions:
                    if step == 1 and not self.model_provider.is_available():
                        return "❌ Model provider (Ollama) is not available. Please:\n1. Install and start Ollama\n2. Pull a model: 'ollama pull llama2'\n3. Verify it's running: 'ollama list'"
                    elif step == 1:
                        return "❌ No actions could be generated for this request. Try rephrasing or check if the model is responding properly."
                    else:
                        print("✅ No additional actions needed, task appears complete.")
                        break
                
                # Show plan with metadata to user
                self._display_plan(plan, step)
                
                # Check intelligent stopping conditions
                if plan.metadata and plan.metadata.is_final:
                    print(f"🎯 Plan indicates final step: {plan.metadata.reasoning}")
                
                # Execute plan
                print(f"\n⚡ Executing plan step {step}...")
                results = self.executor.execute_plan(plan)
                all_results.extend(results)
                
                # Show immediate results for successful actions
                self._display_step_results(results)
                
                # Check for execution failures
                if results and not results[-1].success:
                    failure_reason = results[-1].error if hasattr(results[-1], 'error') else "Unknown failure"
                    if failure_reason and "cancelled" in failure_reason.lower():
                        print(f"⏹️  Execution stopped: {failure_reason}")
                    else:
                        print(f"❌ Execution failed: {failure_reason}")
                    break
                
                # Intelligent stopping based on plan metadata
                if plan.metadata and plan.metadata.is_final:
                    print("✅ Task marked as complete by plan analysis")
                    break
                
                # Traditional stopping conditions
                tool_actions = [a for a in plan.actions if hasattr(a, 'tool_name')]
                if not tool_actions:
                    print("✅ Plan completed (no more tool actions)")
                    break
                
                # Check if we should stop based on follow-up expectations
                if plan.metadata and not plan.metadata.expected_follow_up and step > 2:
                    print(f"✅ No follow-up expected (confidence: {plan.metadata.confidence:.2f})")
                    break
                
                step += 1
            
            if step > max_steps:
                print(f"⚠️  Maximum steps ({max_steps}) reached, stopping execution")
            
            # Generate summary
            summary = self._generate_summary(user_prompt, all_results)
            
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
            import traceback
            error_msg = f"Error processing request: {str(e)}"
            if self.config.debug:
                print(f"Full traceback: {traceback.format_exc()}")
            print(f"❌ {error_msg}")
            return error_msg
    
    def _build_context(self, user_prompt: str) -> Context:
        """Build context for the request."""
        # Ensure user_prompt is not None
        if not user_prompt:
            user_prompt = ""
        
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
            recent_summaries=recent_summaries,
            debug=self.config.debug
        )
    
    def _calculate_max_steps(self, context: Context) -> int:
        """Calculate adaptive maximum steps based on task complexity."""
        base_steps = 5
        
        # Increase steps for complex requests
        complexity_keywords = ['refactor', 'implement', 'create', 'build', 'design', 'test', 'debug']
        if context.user_prompt and any(keyword in context.user_prompt.lower() for keyword in complexity_keywords):
            base_steps += 2
        
        # Increase steps if many files are modified
        if len(context.modified_files) > 5:
            base_steps += 1
        
        # Reduce steps for simple requests
        simple_keywords = ['read', 'show', 'display', 'list', 'status']
        if context.user_prompt and any(keyword in context.user_prompt.lower() for keyword in simple_keywords):
            base_steps = max(3, base_steps - 2)
        
        return min(10, max(3, base_steps))  # Between 3 and 10 steps
    
    def _filter_results_for_context(self, all_results: List, current_step: int) -> List:
        """Filter results to keep only the most relevant ones for context."""
        if not all_results:
            return None
        
        # Keep all results for early steps
        if current_step <= 3:
            return all_results
        
        # For later steps, keep more recent results and important ones
        recent_results = all_results[-6:]  # Last 6 results
        
        # Also keep any results that had errors (they might be relevant)
        error_results = [r for r in all_results[:-6] if hasattr(r, 'success') and not r.success]
        
        # Combine and deduplicate
        filtered = recent_results + error_results
        return filtered if filtered else all_results
    
    def _display_plan(self, plan, step: int):
        """Display plan with metadata information."""
        print(f"\n📋 Plan Step {step} ({len(plan.actions)} actions)")
        
        if plan.metadata:
            confidence_emoji = "🟢" if plan.metadata.confidence > 0.8 else "🟡" if plan.metadata.confidence > 0.5 else "🔴"
            print(f"   {confidence_emoji} Confidence: {plan.metadata.confidence:.1f} | Final: {plan.metadata.is_final} | Follow-up: {plan.metadata.expected_follow_up}")
            if plan.metadata.reasoning:
                print(f"   💭 {plan.metadata.reasoning}")
        
        for i, action in enumerate(plan.actions, 1):
            if hasattr(action, 'tool_name'):
                print(f"  {i}. {action.tool_name}: {action.parameters}")
            else:
                print(f"  {i}. Confirmation: {action.message}")
    
    def _display_step_results(self, results: List):
        """Display immediate results from executed actions."""
        if not results:
            return
        
        successful_count = sum(1 for r in results if hasattr(r, 'success') and r.success)
        total_count = len(results)
        
        if successful_count == total_count:
            print(f"✅ Step completed successfully ({successful_count}/{total_count})")
        elif successful_count > 0:
            print(f"⚠️  Step partially completed ({successful_count}/{total_count})")
        else:
            print(f"❌ Step failed ({successful_count}/{total_count})")
        
        # Show preview of successful results
        for i, result in enumerate(results):
            if hasattr(result, 'success') and result.success and hasattr(result, 'output') and result.output:
                action_desc = getattr(result, 'action_description', f'Action {i+1}')
                
                # Skip confirmation actions in immediate results
                if "Confirmation:" in action_desc:
                    continue
                    
                # For search results, show more lines and better formatting
                if 'search' in action_desc.lower() and '\n' in result.output:
                    lines = result.output.split('\n')[:10]  # Show first 10 lines
                    output_preview = '\n      '.join(lines)
                    total_lines = len(result.output.split('\n'))
                    if total_lines > 10:
                        output_preview += f"\n      ... and {total_lines - 10} more lines"
                else:
                    # For other outputs, be more generous with length
                    output_preview = result.output[:500] + "..." if len(result.output) > 500 else result.output
                
                print(f"   📄 {action_desc}")
                if output_preview.strip():
                    print(f"      {output_preview}")
                
                if i >= 2:  # Show max 3 results per step
                    break
    
    def _generate_summary(self, user_prompt: str, results: List) -> str:
        """Generate a meaningful summary of what was accomplished."""
        successful_actions = sum(1 for r in results if hasattr(r, 'success') and r.success)
        total_actions = len(results)
        
        # Build detailed summary with actual results
        summary_parts = []
        
        # Add completion status
        if successful_actions == 0:
            summary_parts.append("❌ No actions completed successfully")
        elif successful_actions == total_actions:
            summary_parts.append(f"✅ All {total_actions} actions completed successfully")
        else:
            summary_parts.append(f"⚠️  {successful_actions}/{total_actions} actions completed")
        
        # Add key results from successful actions (excluding confirmations)
        key_outputs = []
        for result in results:
            if hasattr(result, 'success') and result.success and hasattr(result, 'output') and result.output:
                action_desc = getattr(result, 'action_description', '')
                
                # Skip confirmation actions in summary
                if "Confirmation:" in action_desc:
                    continue
                
                # For search results, provide more meaningful summary with better truncation
                if 'search' in action_desc.lower() and '\n' in result.output:
                    lines = result.output.split('\n')
                    # Show first few meaningful results
                    meaningful_lines = [line for line in lines[:15] if line.strip() and not line.endswith(':')]
                    if meaningful_lines:
                        output_preview = '\n    '.join(meaningful_lines[:8])  # Show up to 8 results
                        if len(meaningful_lines) > 8:
                            output_preview += f"\n    ... and {len(meaningful_lines) - 8} more matches"
                    else:
                        output_preview = result.output[:600] + "..." if len(result.output) > 600 else result.output
                else:
                    output_preview = result.output[:600] + "..." if len(result.output) > 600 else result.output
                
                if action_desc:
                    key_outputs.append(f"  • {action_desc}:\n    {output_preview}")
                else:
                    key_outputs.append(f"  • {output_preview}")
        
        if key_outputs:
            summary_parts.append("\nKey Results:")
            summary_parts.extend(key_outputs[:3])  # Show max 3 results
            if len(key_outputs) > 3:
                summary_parts.append(f"  • ... and {len(key_outputs) - 3} more results")
        
        # Add request context
        summary_parts.append(f"\nRequest: {user_prompt}")
        
        return "\n".join(summary_parts)
    
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
        
        # Clean up old cache entries
        print("🗄️  Cleaning up cache...")
        self.cache_service.cleanup_old_cache()
        
        print("✅ Agent initialized successfully!")
        return True