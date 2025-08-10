"""Task evaluator tool for testing and analyzing agent performance on complex tasks."""

import os
import ast
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from .base import Tool
from .file_tools import ReadFileTool, SearchFilesTool
from ..types import ToolResult
from ..cache_service import CacheService


class TaskEvaluatorTool(Tool):
    """Tool for executing complex tasks and evaluating the agent's performance."""
    
    def __init__(self, agent_instance=None, cache_service: Optional[CacheService] = None,
                 read_tool: Optional[ReadFileTool] = None,
                 search_tool: Optional[SearchFilesTool] = None):
        self.agent_instance = agent_instance
        self.cache_service = cache_service
        self.read_tool = read_tool or ReadFileTool(cache_service)
        self.search_tool = search_tool or SearchFilesTool()
    
    @property
    def name(self) -> str:
        return "evaluate_task"
    
    @property
    def description(self) -> str:
        return "Execute complex tasks and evaluate the agent's performance, code quality, and tool effectiveness"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Complex task for the agent to complete"
                },
                "output_directory": {
                    "type": "string",
                    "description": "Directory where the agent should create output files",
                    "default": "./task_output"
                },
                "evaluation_criteria": {
                    "type": "array",
                    "description": "Criteria to evaluate the task completion",
                    "items": {
                        "type": "string",
                        "enum": [
                            "completeness", "code_quality", "functionality", 
                            "best_practices", "documentation", "error_handling",
                            "performance", "user_experience", "maintainability"
                        ]
                    },
                    "default": ["completeness", "code_quality", "functionality"]
                },
                "expected_files": {
                    "type": "array",
                    "description": "Expected files/patterns that should be created",
                    "items": {"type": "string"},
                    "default": []
                },
                "timeout_minutes": {
                    "type": "integer",
                    "description": "Maximum time to spend on the task (in minutes)",
                    "default": 30
                }
            },
            "required": ["task_description"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, **parameters) -> ToolResult:
        """Execute and evaluate a complex task."""
        task_description = parameters.get("task_description")
        output_directory = parameters.get("output_directory", "./task_output")
        evaluation_criteria = parameters.get("evaluation_criteria", ["completeness", "code_quality", "functionality"])
        expected_files = parameters.get("expected_files", [])
        timeout_minutes = parameters.get("timeout_minutes", 30)
        
        if not task_description:
            return ToolResult(
                success=False,
                output=None,
                error="Missing task_description parameter"
            )
        
        if not self.agent_instance:
            return ToolResult(
                success=False,
                output=None,
                error="Agent instance not available for task execution"
            )
        
        try:
            # Create output directory
            os.makedirs(output_directory, exist_ok=True)
            
            # Record initial state
            initial_state = self._capture_directory_state(output_directory)
            
            # Execute the task
            execution_result = self._execute_complex_task(
                task_description, output_directory, timeout_minutes
            )
            
            # Capture final state
            final_state = self._capture_directory_state(output_directory)
            
            # Analyze the results
            analysis = self._analyze_task_completion(
                task_description, output_directory, initial_state, 
                final_state, execution_result, evaluation_criteria, expected_files
            )
            
            # Generate evaluation report
            report = self._generate_evaluation_report(analysis)
            
            return ToolResult(
                success=True,
                output=report,
                action_description=f"Evaluated task: {task_description[:50]}..."
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Task evaluation failed: {str(e)}"
            )
    
    def _capture_directory_state(self, directory: str) -> Dict[str, Any]:
        """Capture the current state of a directory."""
        state = {
            "files": [],
            "file_count": 0,
            "total_size": 0,
            "file_types": {},
            "timestamp": time.time()
        }
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, directory)
                    file_ext = Path(file_path).suffix.lower()
                    file_size = os.path.getsize(file_path)
                    
                    state["files"].append({
                        "path": relative_path,
                        "size": file_size,
                        "extension": file_ext,
                        "modified": os.path.getmtime(file_path)
                    })
                    
                    state["total_size"] += file_size
                    state["file_types"][file_ext] = state["file_types"].get(file_ext, 0) + 1
            
            state["file_count"] = len(state["files"])
            
        except Exception:
            pass  # Return empty state if directory doesn't exist
        
        return state
    
    def _execute_complex_task(self, task_description: str, output_directory: str, 
                            timeout_minutes: int) -> Dict[str, Any]:
        """Execute the complex task using the agent."""
        start_time = time.time()
        
        # Modify the task to include output directory context
        enhanced_task = f"""
{task_description}

IMPORTANT: Create all files in the directory: {output_directory}
Make sure to create a complete, working implementation with proper error handling, documentation, and best practices.
"""
        
        execution_result = {
            "success": False,
            "output": "",
            "error": None,
            "execution_time": 0,
            "steps_completed": 0
        }
        
        try:
            # Execute the task through the agent
            result = self.agent_instance.process_request(enhanced_task)
            execution_time = time.time() - start_time
            
            execution_result.update({
                "success": True,
                "output": result,
                "execution_time": execution_time,
                "timed_out": execution_time > (timeout_minutes * 60)
            })
            
        except Exception as e:
            execution_result.update({
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            })
        
        return execution_result
    
    def _analyze_task_completion(self, task_description: str, output_directory: str,
                               initial_state: Dict[str, Any], final_state: Dict[str, Any],
                               execution_result: Dict[str, Any], evaluation_criteria: List[str],
                               expected_files: List[str]) -> Dict[str, Any]:
        """Analyze how well the task was completed."""
        analysis = {
            "task_description": task_description,
            "execution_success": execution_result["success"],
            "execution_time": execution_result["execution_time"],
            "files_created": final_state["file_count"] - initial_state["file_count"],
            "evaluation_scores": {},
            "created_files": [],
            "missing_files": [],
            "code_analysis": {},
            "improvement_suggestions": []
        }
        
        # Identify new files
        initial_files = {f["path"] for f in initial_state["files"]}
        final_files = {f["path"] for f in final_state["files"]}
        new_files = final_files - initial_files
        analysis["created_files"] = list(new_files)
        
        # Check expected files
        if expected_files:
            for expected in expected_files:
                found = any(expected in created_file for created_file in new_files)
                if not found:
                    analysis["missing_files"].append(expected)
        
        # Evaluate based on criteria
        for criterion in evaluation_criteria:
            score = self._evaluate_criterion(criterion, output_directory, new_files, execution_result)
            analysis["evaluation_scores"][criterion] = score
        
        # Analyze created code
        if new_files:
            analysis["code_analysis"] = self._analyze_created_code(output_directory, new_files)
        
        # Generate improvement suggestions
        analysis["improvement_suggestions"] = self._generate_improvement_suggestions(analysis)
        
        return analysis
    
    def _evaluate_criterion(self, criterion: str, output_directory: str, 
                          created_files: set, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a specific criterion."""
        score_data = {
            "score": 0.0,  # 0-1 scale
            "details": "",
            "issues": []
        }
        
        if criterion == "completeness":
            # Did it create files? Is there substantial content?
            if created_files:
                total_size = sum(self._get_file_size(output_directory, f) for f in created_files)
                if total_size > 1000:  # More than 1KB of code
                    score_data["score"] = 0.8
                    score_data["details"] = f"Created {len(created_files)} files with {total_size} bytes"
                else:
                    score_data["score"] = 0.4
                    score_data["details"] = "Created files but with minimal content"
            else:
                score_data["score"] = 0.0
                score_data["issues"].append("No files were created")
        
        elif criterion == "code_quality":
            score_data = self._evaluate_code_quality(output_directory, created_files)
        
        elif criterion == "functionality":
            score_data = self._evaluate_functionality(output_directory, created_files)
        
        elif criterion == "best_practices":
            score_data = self._evaluate_best_practices(output_directory, created_files)
        
        elif criterion == "documentation":
            score_data = self._evaluate_documentation(output_directory, created_files)
        
        elif criterion == "error_handling":
            score_data = self._evaluate_error_handling(output_directory, created_files)
        
        return score_data
    
    def _get_file_size(self, directory: str, filename: str) -> int:
        """Get size of a file."""
        try:
            return os.path.getsize(os.path.join(directory, filename))
        except:
            return 0
    
    def _evaluate_code_quality(self, output_directory: str, created_files: set) -> Dict[str, Any]:
        """Evaluate code quality aspects."""
        score_data = {
            "score": 0.5,  # Default middle score
            "details": "Code quality assessment",
            "issues": []
        }
        
        python_files = [f for f in created_files if f.endswith('.py')]
        js_files = [f for f in created_files if f.endswith(('.js', '.ts', '.jsx', '.tsx'))]
        
        quality_score = 0.5
        total_files = len(python_files) + len(js_files)
        
        if total_files == 0:
            score_data["details"] = "No code files to evaluate"
            return score_data
        
        # Check Python files
        for py_file in python_files:
            file_path = os.path.join(output_directory, py_file)
            try:
                read_result = self.read_tool.execute(file_path=file_path)
                if read_result.success:
                    content = read_result.output
                    
                    # Basic syntax check
                    try:
                        ast.parse(content)
                        quality_score += 0.1  # Valid syntax
                    except SyntaxError:
                        score_data["issues"].append(f"Syntax error in {py_file}")
                        quality_score -= 0.2
                    
                    # Check for basic quality indicators
                    if 'def ' in content:
                        quality_score += 0.1  # Has functions
                    if 'class ' in content:
                        quality_score += 0.1  # Has classes
                    if '"""' in content or "'''" in content:
                        quality_score += 0.1  # Has docstrings
                    if 'import ' in content:
                        quality_score += 0.05  # Uses imports
                    
            except Exception as e:
                score_data["issues"].append(f"Error reading {py_file}: {str(e)}")
        
        score_data["score"] = max(0.0, min(1.0, quality_score))
        score_data["details"] = f"Evaluated {total_files} code files"
        
        return score_data
    
    def _evaluate_functionality(self, output_directory: str, created_files: set) -> Dict[str, Any]:
        """Evaluate if the code appears functional."""
        score_data = {
            "score": 0.3,  # Conservative default
            "details": "Functionality assessment",
            "issues": []
        }
        
        # Look for main execution files
        has_main = any(
            'main' in f.lower() or 'app' in f.lower() or 'index' in f.lower()
            for f in created_files
        )
        
        if has_main:
            score_data["score"] += 0.3
            score_data["details"] = "Found main execution files"
        
        # Check for configuration files
        has_config = any(
            f.endswith(('.json', '.yaml', '.yml', '.toml', '.ini'))
            for f in created_files
        )
        
        if has_config:
            score_data["score"] += 0.2
            score_data["details"] += ", configuration files"
        
        # Check for web app indicators
        has_web = any(
            f.endswith(('.html', '.css', '.js')) or 'template' in f.lower()
            for f in created_files
        )
        
        if has_web:
            score_data["score"] += 0.2
            score_data["details"] += ", web files"
        
        score_data["score"] = min(1.0, score_data["score"])
        
        return score_data
    
    def _evaluate_best_practices(self, output_directory: str, created_files: set) -> Dict[str, Any]:
        """Evaluate adherence to best practices."""
        score_data = {
            "score": 0.4,  # Default
            "details": "Best practices assessment",
            "issues": []
        }
        
        # Check for proper file organization
        has_structure = len(created_files) > 3  # Multiple files indicate structure
        if has_structure:
            score_data["score"] += 0.2
        
        # Check for requirements/dependencies file
        has_deps = any(
            f in created_files for f in [
                'requirements.txt', 'package.json', 'pyproject.toml', 'Pipfile'
            ]
        )
        if has_deps:
            score_data["score"] += 0.2
        
        # Check for README
        has_readme = any('readme' in f.lower() for f in created_files)
        if has_readme:
            score_data["score"] += 0.2
        
        score_data["score"] = min(1.0, score_data["score"])
        return score_data
    
    def _evaluate_documentation(self, output_directory: str, created_files: set) -> Dict[str, Any]:
        """Evaluate documentation quality."""
        score_data = {
            "score": 0.2,  # Conservative start
            "details": "Documentation assessment",
            "issues": []
        }
        
        # Check for README files
        readme_files = [f for f in created_files if 'readme' in f.lower()]
        if readme_files:
            score_data["score"] += 0.4
            score_data["details"] = f"Found README: {readme_files[0]}"
        
        # Check for markdown files
        md_files = [f for f in created_files if f.endswith('.md')]
        if md_files:
            score_data["score"] += 0.2
            score_data["details"] += f", {len(md_files)} markdown files"
        
        # Check for inline documentation in Python files
        python_files = [f for f in created_files if f.endswith('.py')]
        for py_file in python_files:
            file_path = os.path.join(output_directory, py_file)
            try:
                read_result = self.read_tool.execute(file_path=file_path)
                if read_result.success and ('"""' in read_result.output or "'''" in read_result.output):
                    score_data["score"] += 0.1
                    break
            except:
                continue
        
        score_data["score"] = min(1.0, score_data["score"])
        return score_data
    
    def _evaluate_error_handling(self, output_directory: str, created_files: set) -> Dict[str, Any]:
        """Evaluate error handling implementation."""
        score_data = {
            "score": 0.1,  # Low default
            "details": "Error handling assessment",
            "issues": []
        }
        
        # Check Python files for try/except blocks
        python_files = [f for f in created_files if f.endswith('.py')]
        error_handling_count = 0
        
        for py_file in python_files:
            file_path = os.path.join(output_directory, py_file)
            try:
                read_result = self.read_tool.execute(file_path=file_path)
                if read_result.success:
                    content = read_result.output
                    if 'try:' in content and 'except' in content:
                        error_handling_count += 1
                    if 'raise ' in content:
                        error_handling_count += 0.5
            except:
                continue
        
        if error_handling_count > 0:
            score_data["score"] = min(1.0, 0.3 + (error_handling_count * 0.2))
            score_data["details"] = f"Found error handling in {error_handling_count} locations"
        else:
            score_data["issues"].append("No error handling found")
        
        return score_data
    
    def _analyze_created_code(self, output_directory: str, created_files: set) -> Dict[str, Any]:
        """Analyze the created code for patterns and quality."""
        analysis = {
            "file_types": {},
            "total_lines": 0,
            "functions_count": 0,
            "classes_count": 0,
            "imports_count": 0,
            "comments_ratio": 0.0
        }
        
        for file_name in created_files:
            file_path = os.path.join(output_directory, file_name)
            file_ext = Path(file_name).suffix.lower()
            
            analysis["file_types"][file_ext] = analysis["file_types"].get(file_ext, 0) + 1
            
            if file_ext == '.py':
                try:
                    read_result = self.read_tool.execute(file_path=file_path)
                    if read_result.success:
                        content = read_result.output
                        lines = content.split('\n')
                        analysis["total_lines"] += len(lines)
                        
                        # Count functions and classes
                        analysis["functions_count"] += content.count('def ')
                        analysis["classes_count"] += content.count('class ')
                        analysis["imports_count"] += content.count('import ')
                        
                        # Count comments
                        comment_lines = [line for line in lines if line.strip().startswith('#')]
                        if lines:
                            analysis["comments_ratio"] = len(comment_lines) / len(lines)
                        
                except:
                    continue
        
        return analysis
    
    def _generate_improvement_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate suggestions for improving the agent's performance."""
        suggestions = []
        
        # Check completeness
        if analysis["files_created"] == 0:
            suggestions.append("CRITICAL: No files were created. The agent may need better file creation tools or prompts.")
        
        # Check code quality
        code_quality_score = analysis["evaluation_scores"].get("code_quality", {}).get("score", 0)
        if code_quality_score < 0.5:
            suggestions.append("LOW CODE QUALITY: Consider improving code generation templates and best practices.")
        
        # Check functionality
        functionality_score = analysis["evaluation_scores"].get("functionality", {}).get("score", 0)
        if functionality_score < 0.5:
            suggestions.append("FUNCTIONALITY ISSUES: The agent may need better understanding of application structure.")
        
        # Check documentation
        doc_score = analysis["evaluation_scores"].get("documentation", {}).get("score", 0)
        if doc_score < 0.3:
            suggestions.append("POOR DOCUMENTATION: Add tools or prompts to automatically generate README and documentation.")
        
        # Check error handling
        error_score = analysis["evaluation_scores"].get("error_handling", {}).get("score", 0)
        if error_score < 0.3:
            suggestions.append("WEAK ERROR HANDLING: Improve code generation to include proper try/except blocks.")
        
        # Check execution issues
        if not analysis["execution_success"]:
            suggestions.append("EXECUTION FAILED: Debug the agent's execution process and error handling.")
        
        return suggestions
    
    def _generate_evaluation_report(self, analysis: Dict[str, Any]) -> str:
        """Generate a comprehensive evaluation report."""
        report = f"""
# TASK EVALUATION REPORT

## Task Overview
**Description:** {analysis['task_description'][:100]}...
**Execution Success:** {'✅ Yes' if analysis['execution_success'] else '❌ No'}
**Execution Time:** {analysis['execution_time']:.2f} seconds
**Files Created:** {analysis['files_created']}

## Evaluation Scores
"""
        
        for criterion, score_data in analysis["evaluation_scores"].items():
            score = score_data["score"]
            emoji = "🟢" if score >= 0.7 else "🟡" if score >= 0.4 else "🔴"
            report += f"**{criterion.title()}:** {emoji} {score:.2f}/1.0 - {score_data['details']}\n"
            
            if score_data["issues"]:
                for issue in score_data["issues"]:
                    report += f"   ⚠️ {issue}\n"
        
        report += f"\n## Files Created\n"
        if analysis["created_files"]:
            for file_name in analysis["created_files"]:
                report += f"- {file_name}\n"
        else:
            report += "❌ No files were created\n"
        
        if analysis["missing_files"]:
            report += f"\n## Missing Expected Files\n"
            for missing in analysis["missing_files"]:
                report += f"❌ {missing}\n"
        
        if analysis["code_analysis"]:
            ca = analysis["code_analysis"]
            report += f"""
## Code Analysis
- **Total Lines:** {ca['total_lines']}
- **Functions:** {ca['functions_count']}
- **Classes:** {ca['classes_count']}
- **Imports:** {ca['imports_count']}
- **Comments Ratio:** {ca['comments_ratio']:.2%}
- **File Types:** {', '.join(f"{ext}({count})" for ext, count in ca['file_types'].items())}
"""
        
        if analysis["improvement_suggestions"]:
            report += f"\n## 🚀 Improvement Suggestions\n"
            for i, suggestion in enumerate(analysis["improvement_suggestions"], 1):
                report += f"{i}. {suggestion}\n"
        
        # Overall assessment
        avg_score = sum(s["score"] for s in analysis["evaluation_scores"].values()) / len(analysis["evaluation_scores"])
        if avg_score >= 0.7:
            report += f"\n## 🎉 Overall Assessment: EXCELLENT ({avg_score:.2f}/1.0)"
        elif avg_score >= 0.5:
            report += f"\n## 👍 Overall Assessment: GOOD ({avg_score:.2f}/1.0)"
        elif avg_score >= 0.3:
            report += f"\n## 👎 Overall Assessment: NEEDS IMPROVEMENT ({avg_score:.2f}/1.0)"
        else:
            report += f"\n## ❌ Overall Assessment: POOR ({avg_score:.2f}/1.0)"
        
        return report