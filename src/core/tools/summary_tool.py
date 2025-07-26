"""
Summary tool for generating natural language summaries from collected data
"""
from typing import Dict, List, Optional, Any
from .base import BaseTool, ToolParameter, ToolResult
from ..debug import debug_print


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
            
            # Clean the response to remove thinking tags and artifacts
            from ..response_cleaner import clean_llm_response
            cleaned_content = clean_llm_response(response.content)
            
            return ToolResult(
                success=True,
                content=cleaned_content,
                data={
                    "summary": cleaned_content,
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
        
        # Check if this is a file analysis task (define before collected_data section)
        file_analysis_keywords = ["functions", "methods", "classes", "summarize", "analyze", "list", "content", "refactor", "improve", "restructure"]
        is_file_analysis = any(keyword in task_description.lower() for keyword in file_analysis_keywords)
        
        debug_print(f"Task description: {task_description}")
        debug_print(f"Is file analysis: {is_file_analysis}")
        debug_print(f"Collected data keys: {list(collected_data.keys()) if collected_data else []}")
        
        # Collected data
        if collected_data:
            prompt_parts.append("**Collected Information:**")
            
            for source, data in collected_data.items():
                prompt_parts.append(f"\n**From {source}:**")
                
                if isinstance(data, dict):
                    debug_print(f"Processing data from {source}: {list(data.keys())}")
                    
                    # Special handling for file tool results
                    if source.startswith("file_") and is_file_analysis:
                        debug_print(f"File tool result detected for {source}")
                        # For file analysis, include the full file content
                        if "content" in data:
                            file_content = data["content"]
                            file_path = data.get("path", "unknown file")
                            debug_print(f"Found file content ({len(str(file_content))} chars) from {file_path}")
                            prompt_parts.append(f"**File Content from {file_path}:**")
                            prompt_parts.append("```")
                            prompt_parts.append(str(file_content))
                            prompt_parts.append("```")
                            continue
                        elif "data" in data and isinstance(data["data"], str):
                            # Alternative location for file content
                            file_content = data["data"]
                            file_path = data.get("path", "unknown file")
                            debug_print(f"Found file content in data field ({len(str(file_content))} chars) from {file_path}")
                            prompt_parts.append(f"**File Content from {file_path}:**")
                            prompt_parts.append("```")
                            prompt_parts.append(str(file_content))
                            prompt_parts.append("```")
                            continue
                        else:
                            debug_print(f"No file content found in file tool result: {list(data.keys())}")
                    elif is_file_analysis:
                        debug_print(f"File analysis task but {source} doesn't start with 'file_'")
                    
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
                        if key not in ["results", "files", "content"] and value:  # Skip content since we handle it specially above
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
                    # Check if this is raw file content
                    if is_file_analysis and len(str(data)) > 1000:
                        prompt_parts.append("**File Content:**")
                        prompt_parts.append("```")
                        prompt_parts.append(str(data))
                        prompt_parts.append("```")
                    else:
                        preview = str(data)[:300] + "..." if len(str(data)) > 300 else str(data)
                        prompt_parts.append(f"- {preview}")
        
        # Summary instructions
        prompt_parts.append(f"\n**Please provide a comprehensive {focus} summary that:**")
        
        # Special instructions for file analysis tasks
        if is_file_analysis and any("file content" in part.lower() for part in prompt_parts):
            prompt_parts.extend([
                "- Analyzes the ACTUAL code provided above",
                "- Lists the specific functions, classes, and methods found in the code",
                "- Explains what each major component does based on the actual implementation", 
                "- Describes the real structure and patterns used in this specific file",
                "- Does NOT make generic assumptions - only describes what is actually in the code",
                "- Focuses on the concrete implementation details, not theoretical possibilities"
            ])
        elif focus == "architecture":
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