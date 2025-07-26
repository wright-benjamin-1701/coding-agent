"""
Summary tool for generating natural language summaries from collected data
"""
from typing import Dict, List, Optional, Any
from .base import BaseTool, ToolParameter, ToolResult


class SummaryTool(BaseTool):
    """Tool for generating comprehensive summaries using LLM without JSON constraints"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, llm_provider=None):
        super().__init__(config)
        self.llm_provider = llm_provider
        self.name = "summary"
    
    def set_llm_provider(self, provider):
        """Set the LLM provider for summary generation"""
        self.llm_provider = provider
    
    def get_description(self) -> str:
        return "Generate comprehensive natural language summaries from collected data and context"
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="task_description", 
                type="string", 
                description="Original task description"
            ),
            ToolParameter(
                name="collected_data", 
                type="object", 
                description="All data collected from previous steps"
            ),
            ToolParameter(
                name="context", 
                type="object", 
                description="Project and conversation context", 
                required=False
            ),
            ToolParameter(
                name="focus", 
                type="string", 
                description="Specific focus for the summary (e.g., 'architecture', 'functionality', 'overview')", 
                required=False,
                default="overview"
            )
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Generate a comprehensive summary"""
        
        try:
            task_description = kwargs.get("task_description", "")
            collected_data = kwargs.get("collected_data", {})
            context = kwargs.get("context", {})
            focus = kwargs.get("focus", "overview")
            
            if not self.llm_provider:
                return ToolResult(
                    success=False,
                    error="No LLM provider available for summary generation"
                )
            
            # Build comprehensive prompt
            summary_prompt = self._build_summary_prompt(
                task_description, collected_data, context, focus
            )
            
            # Call LLM without JSON constraints
            from ..providers.base import ChatMessage, ModelConfig
            
            messages = [
                ChatMessage(
                    role="system",
                    content="You are a helpful assistant that provides clear, comprehensive summaries. Use natural language and organize information logically. Be thorough but concise."
                ),
                ChatMessage(role="user", content=summary_prompt)
            ]
            
            model_config = ModelConfig(
                model_name=self._select_best_model(),
                temperature=0.3,  # Slightly creative for better prose
                max_tokens=2000   # Allow for detailed summaries
            )
            
            response = await self.llm_provider.chat_completion(messages, model_config)
            
            return ToolResult(
                success=True,
                content=response.content,
                data={
                    "summary": response.content,
                    "focus": focus,
                    "data_sources": list(collected_data.keys()) if isinstance(collected_data, dict) else [],
                    "task": task_description
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Summary generation failed: {str(e)}"
            )
    
    def _build_summary_prompt(self, task_description: str, collected_data: Dict[str, Any], 
                             context: Dict[str, Any], focus: str) -> str:
        """Build comprehensive prompt for summary generation"""
        
        prompt_parts = []
        
        # Task context
        if task_description:
            prompt_parts.append(f"**Original Task:** {task_description}")
        
        # Project context
        if context:
            prompt_parts.append("**Project Context:**")
            if isinstance(context, dict):
                for key, value in context.items():
                    if value and str(value).strip():
                        prompt_parts.append(f"- {key}: {value}")
            else:
                prompt_parts.append(f"- {context}")
        
        # Collected data
        if collected_data:
            prompt_parts.append("**Collected Information:**")
            
            for source, data in collected_data.items():
                prompt_parts.append(f"\n**From {source}:**")
                
                if isinstance(data, dict):
                    if "results" in data:
                        results = data["results"]
                        if isinstance(results, list) and results:
                            prompt_parts.append(f"- Found {len(results)} items")
                            for item in results[:5]:  # Show first 5 items
                                if isinstance(item, dict):
                                    prompt_parts.append(f"  • {item}")
                                else:
                                    prompt_parts.append(f"  • {str(item)[:100]}...")
                            if len(results) > 5:
                                prompt_parts.append(f"  • ... and {len(results) - 5} more items")
                        else:
                            prompt_parts.append("- No results found")
                    
                    if "files" in data:
                        files = data["files"]
                        if isinstance(files, list) and files:
                            prompt_parts.append(f"- Found {len(files)} files")
                            for file_info in files[:10]:  # Show first 10 files
                                if isinstance(file_info, dict):
                                    file_name = file_info.get("file", file_info.get("name", str(file_info)))
                                    prompt_parts.append(f"  • {file_name}")
                                else:
                                    prompt_parts.append(f"  • {str(file_info)}")
                            if len(files) > 10:
                                prompt_parts.append(f"  • ... and {len(files) - 10} more files")
                    
                    # Handle other data types
                    for key, value in data.items():
                        if key not in ["results", "files"] and value:
                            if isinstance(value, (list, dict)):
                                prompt_parts.append(f"- {key}: {len(value)} items" if isinstance(value, list) else f"- {key}: {len(value)} entries")
                            else:
                                preview = str(value)[:200] + "..." if len(str(value)) > 200 else str(value)
                                prompt_parts.append(f"- {key}: {preview}")
                
                elif isinstance(data, list):
                    prompt_parts.append(f"- {len(data)} items found")
                    for item in data[:3]:
                        prompt_parts.append(f"  • {str(item)[:100]}...")
                else:
                    preview = str(data)[:300] + "..." if len(str(data)) > 300 else str(data)
                    prompt_parts.append(f"- {preview}")
        
        # Summary instructions
        prompt_parts.append(f"\n**Please provide a comprehensive {focus} summary that:**")
        
        if focus == "architecture":
            prompt_parts.extend([
                "- Describes the overall code structure and organization",
                "- Identifies key components and their relationships", 
                "- Explains the architectural patterns used",
                "- Highlights important files and directories"
            ])
        elif focus == "functionality":
            prompt_parts.extend([
                "- Explains what this codebase does",
                "- Describes the main features and capabilities",
                "- Identifies entry points and core functionality",
                "- Summarizes the purpose and use cases"
            ])
        else:  # overview
            prompt_parts.extend([
                "- Provides a clear overview of what this codebase is",
                "- Describes its main purpose and functionality", 
                "- Explains the structure and key components",
                "- Identifies important files and entry points",
                "- Summarizes findings in an organized, readable format"
            ])
        
        prompt_parts.append("\nUse clear headings, bullet points, and organize the information logically for easy reading.")
        
        return "\n".join(prompt_parts)
    
    def _select_best_model(self) -> str:
        """Select the best available model for summary generation"""
        if not self.llm_provider:
            return "default"
        
        available_models = self.llm_provider.list_models()
        if not available_models:
            return "default"
        
        # Prefer models good for reasoning and text generation
        preferred_models = [
            "deepseek-reasoner", "deepseek-chat", "qwen", "llama", "claude", "gpt"
        ]
        
        for preferred in preferred_models:
            for model in available_models:
                if preferred in model.lower():
                    return model
        
        # Fallback to first available
        return available_models[0]