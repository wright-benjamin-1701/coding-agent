"""Intelligent debugging assistant with stack trace analysis and root cause suggestions."""

import ast
import re
import os
import sys
import traceback
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict
from .base import Tool
from ..types import ToolResult
from ..providers.base import ModelProvider


class StackTraceAnalyzer:
    """Analyze stack traces to extract meaningful debugging information."""
    
    def __init__(self):
        self.common_error_patterns = {
            'NameError': 'Variable or function name not defined',
            'AttributeError': 'Object does not have the specified attribute',
            'TypeError': 'Operation applied to wrong type',
            'ValueError': 'Function received correct type but inappropriate value',
            'KeyError': 'Key not found in dictionary',
            'IndexError': 'List index out of range',
            'ImportError': 'Module could not be imported',
            'ModuleNotFoundError': 'Module not found',
            'FileNotFoundError': 'File or directory not found',
            'PermissionError': 'Insufficient permissions',
            'ConnectionError': 'Network connection issue',
            'TimeoutError': 'Operation timed out',
            'RecursionError': 'Maximum recursion depth exceeded'
        }
    
    def analyze_stack_trace(self, stack_trace: str) -> Dict[str, Any]:
        """Analyze a stack trace and extract debugging information."""
        analysis = {
            'error_type': None,
            'error_message': None,
            'root_cause_line': None,
            'affected_files': [],
            'call_chain': [],
            'potential_causes': [],
            'suggestions': []
        }
        
        lines = stack_trace.strip().split('\n')
        
        # Find the error type and message
        if lines:
            last_line = lines[-1].strip()
            if ':' in last_line:
                parts = last_line.split(':', 1)
                analysis['error_type'] = parts[0].strip()
                analysis['error_message'] = parts[1].strip() if len(parts) > 1 else ''
        
        # Extract call chain and affected files
        current_frame = {}
        for line in lines:
            line = line.strip()
            
            # File and line number
            if line.startswith('File "'):
                file_match = re.match(r'File "([^"]+)", line (\d+), in (.+)', line)
                if file_match:
                    current_frame = {
                        'file': file_match.group(1),
                        'line': int(file_match.group(2)),
                        'function': file_match.group(3)
                    }
                    if current_frame['file'] not in analysis['affected_files']:
                        analysis['affected_files'].append(current_frame['file'])
            
            # Code line
            elif line and not line.startswith('Traceback') and current_frame:
                current_frame['code'] = line
                analysis['call_chain'].append(current_frame.copy())
                current_frame = {}
        
        # Identify root cause (last frame in user code)
        if analysis['call_chain']:
            # Find the last frame that's not in system/library code
            for frame in reversed(analysis['call_chain']):
                if not self._is_system_code(frame['file']):
                    analysis['root_cause_line'] = frame
                    break
        
        # Generate suggestions based on error type
        if analysis['error_type']:
            analysis['potential_causes'] = self._identify_potential_causes(analysis)
            analysis['suggestions'] = self._generate_suggestions(analysis)
        
        return analysis
    
    def _is_system_code(self, file_path: str) -> bool:
        """Check if the file is system/library code."""
        system_patterns = ['/usr/lib/', '/usr/local/lib/', 'site-packages/', 'dist-packages/', '<built-in>']
        return any(pattern in file_path for pattern in system_patterns)
    
    def _identify_potential_causes(self, analysis: Dict[str, Any]) -> List[str]:
        """Identify potential causes based on error type and context."""
        causes = []
        error_type = analysis['error_type']
        error_message = analysis['error_message']
        
        if error_type == 'NameError':
            if "is not defined" in error_message:
                var_name = re.search(r"name '(\w+)' is not defined", error_message)
                if var_name:
                    causes.extend([
                        f"Variable '{var_name.group(1)}' was never initialized",
                        f"Typo in variable name '{var_name.group(1)}'",
                        f"Variable '{var_name.group(1)}' is out of scope",
                        f"Missing import for '{var_name.group(1)}'"
                    ])
        
        elif error_type == 'AttributeError':
            if "has no attribute" in error_message:
                attr_match = re.search(r"'(\w+)' object has no attribute '(\w+)'", error_message)
                if attr_match:
                    obj_type, attr_name = attr_match.groups()
                    causes.extend([
                        f"'{attr_name}' method/attribute doesn't exist on {obj_type} objects",
                        f"Typo in attribute name '{attr_name}'",
                        f"Object is None when you expected a {obj_type}",
                        f"Wrong object type - expected different class"
                    ])
        
        elif error_type == 'KeyError':
            key_match = re.search(r"KeyError: ['\"]([^'\"]+)['\"]", error_message)
            if key_match:
                key = key_match.group(1)
                causes.extend([
                    f"Key '{key}' doesn't exist in dictionary",
                    f"Typo in key name '{key}'",
                    f"Dictionary structure changed",
                    f"Key '{key}' was removed or never added"
                ])
        
        elif error_type == 'IndexError':
            causes.extend([
                "List/array is shorter than expected",
                "Using wrong index value",
                "Off-by-one error in loop or indexing",
                "Empty list when expecting items"
            ])
        
        elif error_type == 'TypeError':
            if "unsupported operand" in error_message:
                causes.append("Trying to perform operation on incompatible types")
            elif "argument" in error_message:
                causes.extend([
                    "Wrong number of arguments passed to function",
                    "Passing wrong type of argument",
                    "Missing required argument"
                ])
        
        elif error_type in ['ImportError', 'ModuleNotFoundError']:
            module_match = re.search(r"No module named '([^']+)'", error_message)
            if module_match:
                module = module_match.group(1)
                causes.extend([
                    f"Module '{module}' not installed",
                    f"Typo in module name '{module}'",
                    f"Module '{module}' not in Python path",
                    f"Virtual environment not activated"
                ])
        
        return causes
    
    def _generate_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable debugging suggestions."""
        suggestions = []
        error_type = analysis['error_type']
        
        # General suggestions
        suggestions.extend([
            "Add print statements to trace variable values",
            "Use debugger (pdb) to step through code",
            "Check variable types with type() function"
        ])
        
        # Error-specific suggestions
        if error_type == 'NameError':
            suggestions.extend([
                "Check for typos in variable names",
                "Verify variable is initialized before use",
                "Check variable scope and indentation",
                "Add missing imports"
            ])
        
        elif error_type == 'AttributeError':
            suggestions.extend([
                "Check object type with type() or isinstance()",
                "Verify object is not None",
                "Check available attributes with dir()",
                "Review class definition for correct method names"
            ])
        
        elif error_type == 'KeyError':
            suggestions.extend([
                "Use dict.get() with default value instead of direct access",
                "Check if key exists with 'key in dict'",
                "Print dictionary keys to verify structure",
                "Use try/except to handle missing keys"
            ])
        
        elif error_type == 'IndexError':
            suggestions.extend([
                "Check list length before accessing elements",
                "Use enumerate() to avoid index errors",
                "Add bounds checking in loops",
                "Handle empty lists explicitly"
            ])
        
        elif error_type in ['ImportError', 'ModuleNotFoundError']:
            suggestions.extend([
                "Install missing package with pip install",
                "Check virtual environment is activated",
                "Verify module name spelling",
                "Check PYTHONPATH environment variable"
            ])
        
        return suggestions


class VariableFlowTracker(ast.NodeVisitor):
    """Track variable flow and dependencies in code."""
    
    def __init__(self, target_variable: str):
        self.target_variable = target_variable
        self.assignments = []
        self.usages = []
        self.current_function = None
        self.current_line = 0
    
    def track_variable_flow(self, tree: ast.AST, source: str) -> Dict[str, Any]:
        """Track how a variable flows through code."""
        self.source_lines = source.split('\n')
        self.visit(tree)
        
        return {
            'assignments': self.assignments,
            'usages': self.usages,
            'flow_analysis': self._analyze_flow()
        }
    
    def visit_Assign(self, node):
        """Track variable assignments."""
        self.current_line = node.lineno
        
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == self.target_variable:
                self.assignments.append({
                    'line': node.lineno,
                    'function': self.current_function,
                    'value': self._get_source_line(node.lineno),
                    'type': 'assignment'
                })
        
        self.generic_visit(node)
    
    def visit_Name(self, node):
        """Track variable usage."""
        if node.id == self.target_variable and isinstance(node.ctx, ast.Load):
            self.usages.append({
                'line': getattr(node, 'lineno', self.current_line),
                'function': self.current_function,
                'context': 'load'
            })
        
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        """Track function context."""
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
    
    def _get_source_line(self, line_no: int) -> str:
        """Get source code line."""
        if 1 <= line_no <= len(self.source_lines):
            return self.source_lines[line_no - 1].strip()
        return ""
    
    def _analyze_flow(self) -> Dict[str, Any]:
        """Analyze variable flow patterns."""
        analysis = {
            'first_assignment': None,
            'last_usage': None,
            'potential_issues': []
        }
        
        if self.assignments:
            analysis['first_assignment'] = min(self.assignments, key=lambda x: x['line'])
        
        if self.usages:
            analysis['last_usage'] = max(self.usages, key=lambda x: x['line'])
        
        # Check for potential issues
        if self.usages and not self.assignments:
            analysis['potential_issues'].append(f"Variable '{self.target_variable}' used but never assigned")
        
        if self.assignments and not self.usages:
            analysis['potential_issues'].append(f"Variable '{self.target_variable}' assigned but never used")
        
        # Check for usage before assignment
        if self.assignments and self.usages:
            first_assign_line = analysis['first_assignment']['line']
            early_usages = [u for u in self.usages if u['line'] < first_assign_line]
            if early_usages:
                analysis['potential_issues'].append(f"Variable '{self.target_variable}' used before assignment")
        
        return analysis


class IntelligentDebuggingTool(Tool):
    """Intelligent debugging assistant with advanced analysis capabilities."""
    
    def __init__(self, model_provider: Optional[ModelProvider] = None):
        self.model_provider = model_provider
    
    @property
    def name(self) -> str:
        return "intelligent_debugging"
    
    @property
    def description(self) -> str:
        return "Advanced debugging assistant with stack trace analysis, variable flow tracking, and AI-powered root cause suggestions"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "debug_type": {
                    "type": "string",
                    "enum": ["stack_trace", "variable_flow", "code_analysis", "error_reproduction", "performance_debug"],
                    "description": "Type of debugging analysis to perform"
                },
                "stack_trace": {
                    "type": "string",
                    "description": "Stack trace text to analyze"
                },
                "error_log": {
                    "type": "string",
                    "description": "Path to error log file"
                },
                "code_file": {
                    "type": "string",
                    "description": "Path to code file to debug"
                },
                "variable_name": {
                    "type": "string",
                    "description": "Variable name to track flow for"
                },
                "error_description": {
                    "type": "string",
                    "description": "Description of the bug or issue"
                },
                "reproduction_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Steps to reproduce the issue"
                },
                "context_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related files that might provide context"
                },
                "ai_analysis": {
                    "type": "boolean",
                    "default": True,
                    "description": "Use AI for advanced analysis and suggestions"
                },
                "run_tests": {
                    "type": "boolean",
                    "default": False,
                    "description": "Run tests to help identify issues"
                }
            },
            "required": ["debug_type"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def _analyze_stack_trace(self, stack_trace: str) -> Dict[str, Any]:
        """Analyze stack trace with detailed debugging information."""
        analyzer = StackTraceAnalyzer()
        analysis = analyzer.analyze_stack_trace(stack_trace)
        
        # Add file content analysis for root cause
        if analysis['root_cause_line']:
            root_file = analysis['root_cause_line']['file']
            if Path(root_file).exists():
                try:
                    with open(root_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Analyze the problematic line and surrounding context
                    lines = content.split('\n')
                    error_line_num = analysis['root_cause_line']['line']
                    
                    # Get context around the error
                    start_line = max(0, error_line_num - 5)
                    end_line = min(len(lines), error_line_num + 5)
                    context = lines[start_line:end_line]
                    
                    analysis['code_context'] = {
                        'start_line': start_line + 1,
                        'context_lines': context,
                        'error_line_index': error_line_num - start_line - 1
                    }
                    
                except Exception:
                    pass
        
        return analysis
    
    def _track_variable_flow(self, code_file: str, variable_name: str) -> Dict[str, Any]:
        """Track variable flow through code."""
        if not Path(code_file).exists():
            return {'error': f"File {code_file} not found"}
        
        try:
            with open(code_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            tracker = VariableFlowTracker(variable_name)
            flow_data = tracker.track_variable_flow(tree, content)
            
            return flow_data
        
        except Exception as e:
            return {'error': f"Failed to analyze variable flow: {str(e)}"}
    
    def _run_code_analysis(self, code_file: str) -> Dict[str, Any]:
        """Perform static code analysis for potential issues."""
        if not Path(code_file).exists():
            return {'error': f"File {code_file} not found"}
        
        analysis = {
            'syntax_errors': [],
            'potential_issues': [],
            'code_smells': []
        }
        
        try:
            with open(code_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for syntax errors
            try:
                ast.parse(content)
            except SyntaxError as e:
                analysis['syntax_errors'].append({
                    'line': e.lineno,
                    'message': e.msg,
                    'text': e.text.strip() if e.text else ''
                })
            
            # Look for common issues with regex patterns
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                # Potential issues
                if re.search(r'^\s*except:\s*$', line):
                    analysis['potential_issues'].append({
                        'line': i,
                        'issue': 'Bare except clause',
                        'suggestion': 'Specify exception type'
                    })
                
                if 'print(' in line and 'debug' not in line.lower():
                    analysis['code_smells'].append({
                        'line': i,
                        'issue': 'Debug print statement',
                        'suggestion': 'Remove or use logging'
                    })
                
                if re.search(r'TODO|FIXME|HACK', line, re.IGNORECASE):
                    analysis['potential_issues'].append({
                        'line': i,
                        'issue': 'TODO/FIXME comment',
                        'suggestion': 'Address pending work'
                    })
        
        except Exception as e:
            analysis['error'] = str(e)
        
        return analysis
    
    def _run_tests_for_debugging(self, context_files: List[str]) -> Dict[str, Any]:
        """Run tests to help identify issues."""
        test_results = {
            'tests_run': False,
            'results': {},
            'suggestions': []
        }
        
        try:
            # Try to run pytest if available
            result = subprocess.run(['python', '-m', 'pytest', '--tb=short', '-v'], 
                                  capture_output=True, text=True, timeout=30)
            
            test_results['tests_run'] = True
            test_results['results'] = {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
            # Analyze test output for debugging insights
            if result.returncode != 0:
                if 'FAILED' in result.stdout:
                    test_results['suggestions'].append("Some tests are failing - check test output for clues")
                if 'ERROR' in result.stdout:
                    test_results['suggestions'].append("Test execution errors - check test setup")
            else:
                test_results['suggestions'].append("All tests pass - bug might be in untested code")
        
        except subprocess.TimeoutExpired:
            test_results['suggestions'].append("Tests timed out - might indicate performance issue")
        except FileNotFoundError:
            test_results['suggestions'].append("pytest not available - install with 'pip install pytest'")
        except Exception as e:
            test_results['error'] = str(e)
        
        return test_results
    
    def _get_ai_analysis(self, debug_data: Dict[str, Any], error_description: str) -> str:
        """Get AI-powered analysis and suggestions."""
        if not self.model_provider:
            return "AI analysis not available - no model provider configured"
        
        # Prepare context for AI analysis
        prompt_parts = [
            "Analyze this debugging information and provide detailed insights:",
            f"\nError Description: {error_description}",
        ]
        
        if debug_data.get('error_type'):
            prompt_parts.append(f"Error Type: {debug_data['error_type']}")
            prompt_parts.append(f"Error Message: {debug_data.get('error_message', '')}")
        
        if debug_data.get('root_cause_line'):
            root = debug_data['root_cause_line']
            prompt_parts.append(f"\nRoot Cause Location:")
            prompt_parts.append(f"File: {root['file']}")
            prompt_parts.append(f"Line: {root['line']}")
            prompt_parts.append(f"Function: {root['function']}")
            prompt_parts.append(f"Code: {root.get('code', '')}")
        
        if debug_data.get('code_context'):
            ctx = debug_data['code_context']
            prompt_parts.append(f"\nCode Context (around line {ctx['start_line']}):")
            for i, line in enumerate(ctx['context_lines']):
                marker = " --> " if i == ctx.get('error_line_index', -1) else "     "
                prompt_parts.append(f"{ctx['start_line'] + i:3d}{marker}{line}")
        
        if debug_data.get('potential_causes'):
            prompt_parts.append(f"\nPotential Causes:")
            for cause in debug_data['potential_causes'][:5]:
                prompt_parts.append(f"- {cause}")
        
        prompt_parts.extend([
            "\nPlease provide:",
            "1. Root cause analysis",
            "2. Step-by-step debugging approach",
            "3. Specific code fixes",
            "4. Prevention strategies",
            "5. Alternative approaches"
        ])
        
        try:
            response = self.model_provider.generate("\n".join(prompt_parts), max_tokens=1000)
            return response.content if response else "AI analysis failed"
        except Exception as e:
            return f"AI analysis error: {str(e)}"
    
    def execute(self, **parameters) -> ToolResult:
        """Execute intelligent debugging analysis."""
        try:
            debug_type = parameters.get("debug_type")
            stack_trace = parameters.get("stack_trace", "")
            error_log = parameters.get("error_log", "")
            code_file = parameters.get("code_file", "")
            variable_name = parameters.get("variable_name", "")
            error_description = parameters.get("error_description", "")
            reproduction_steps = parameters.get("reproduction_steps", [])
            context_files = parameters.get("context_files", [])
            ai_analysis = parameters.get("ai_analysis", True)
            run_tests = parameters.get("run_tests", False)
            
            result_parts = ["🔍 Intelligent Debugging Analysis\n"]
            debug_data = {}
            
            # Stack trace analysis
            if debug_type == "stack_trace":
                if not stack_trace and error_log:
                    try:
                        with open(error_log, 'r', encoding='utf-8') as f:
                            stack_trace = f.read()
                    except Exception as e:
                        return ToolResult(
                            success=False,
                            error=f"Could not read error log: {str(e)}"
                        )
                
                if not stack_trace:
                    return ToolResult(
                        success=False,
                        error="No stack trace provided"
                    )
                
                debug_data = self._analyze_stack_trace(stack_trace)
                
                result_parts.append("📊 **Stack Trace Analysis:**")
                result_parts.append(f"   • Error Type: {debug_data.get('error_type', 'Unknown')}")
                result_parts.append(f"   • Error Message: {debug_data.get('error_message', 'N/A')}")
                
                if debug_data.get('root_cause_line'):
                    root = debug_data['root_cause_line']
                    result_parts.append(f"   • Root Cause: {root['file']}:{root['line']} in {root['function']}")
                
                result_parts.append(f"   • Affected Files: {len(debug_data.get('affected_files', []))}")
                
                if debug_data.get('code_context'):
                    result_parts.append(f"\n💻 **Code Context:**")
                    ctx = debug_data['code_context']
                    for i, line in enumerate(ctx['context_lines']):
                        line_num = ctx['start_line'] + i
                        marker = " ❌ " if i == ctx.get('error_line_index', -1) else "    "
                        result_parts.append(f"{line_num:3d}{marker}{line}")
                
                if debug_data.get('potential_causes'):
                    result_parts.append(f"\n🔍 **Potential Causes:**")
                    for cause in debug_data['potential_causes'][:5]:
                        result_parts.append(f"   • {cause}")
                
                if debug_data.get('suggestions'):
                    result_parts.append(f"\n💡 **Debugging Suggestions:**")
                    for suggestion in debug_data['suggestions'][:5]:
                        result_parts.append(f"   • {suggestion}")
            
            # Variable flow analysis
            elif debug_type == "variable_flow":
                if not code_file or not variable_name:
                    return ToolResult(
                        success=False,
                        error="code_file and variable_name required for variable flow analysis"
                    )
                
                flow_data = self._track_variable_flow(code_file, variable_name)
                
                if flow_data.get('error'):
                    return ToolResult(success=False, error=flow_data['error'])
                
                result_parts.append(f"📈 **Variable Flow Analysis for '{variable_name}':**")
                
                assignments = flow_data.get('assignments', [])
                usages = flow_data.get('usages', [])
                
                result_parts.append(f"   • Assignments: {len(assignments)}")
                result_parts.append(f"   • Usages: {len(usages)}")
                
                if assignments:
                    result_parts.append(f"\n📝 **Assignments:**")
                    for assign in assignments[:5]:
                        func = f" in {assign['function']}" if assign['function'] else ""
                        result_parts.append(f"   • Line {assign['line']}{func}: {assign['value']}")
                
                if usages:
                    result_parts.append(f"\n👁️ **Usages:**")
                    for usage in usages[:5]:
                        func = f" in {usage['function']}" if usage['function'] else ""
                        result_parts.append(f"   • Line {usage['line']}{func}")
                
                flow_analysis = flow_data.get('flow_analysis', {})
                if flow_analysis.get('potential_issues'):
                    result_parts.append(f"\n⚠️ **Flow Issues:**")
                    for issue in flow_analysis['potential_issues']:
                        result_parts.append(f"   • {issue}")
                
                debug_data = flow_data
            
            # Code analysis
            elif debug_type == "code_analysis":
                if not code_file:
                    return ToolResult(
                        success=False,
                        error="code_file required for code analysis"
                    )
                
                analysis = self._run_code_analysis(code_file)
                
                if analysis.get('error'):
                    return ToolResult(success=False, error=analysis['error'])
                
                result_parts.append(f"🔬 **Code Analysis for {Path(code_file).name}:**")
                
                if analysis['syntax_errors']:
                    result_parts.append(f"\n❌ **Syntax Errors ({len(analysis['syntax_errors'])}):**")
                    for error in analysis['syntax_errors']:
                        result_parts.append(f"   • Line {error['line']}: {error['message']}")
                        if error['text']:
                            result_parts.append(f"     Code: {error['text']}")
                
                if analysis['potential_issues']:
                    result_parts.append(f"\n⚠️ **Potential Issues ({len(analysis['potential_issues'])}):**")
                    for issue in analysis['potential_issues']:
                        result_parts.append(f"   • Line {issue['line']}: {issue['issue']}")
                        result_parts.append(f"     Suggestion: {issue['suggestion']}")
                
                if analysis['code_smells']:
                    result_parts.append(f"\n👃 **Code Smells ({len(analysis['code_smells'])}):**")
                    for smell in analysis['code_smells']:
                        result_parts.append(f"   • Line {smell['line']}: {smell['issue']}")
                
                debug_data = analysis
            
            # Run tests for debugging insights
            if run_tests:
                result_parts.append(f"\n🧪 **Test Results:**")
                test_results = self._run_tests_for_debugging(context_files)
                
                if test_results['tests_run']:
                    if test_results['results']['returncode'] == 0:
                        result_parts.append("   ✅ All tests passed")
                    else:
                        result_parts.append("   ❌ Some tests failed")
                        if test_results['results']['stderr']:
                            result_parts.append(f"   Error output: {test_results['results']['stderr'][:200]}...")
                
                if test_results['suggestions']:
                    result_parts.append(f"\n💡 **Test-Based Suggestions:**")
                    for suggestion in test_results['suggestions']:
                        result_parts.append(f"   • {suggestion}")
            
            # AI-powered analysis
            if ai_analysis and self.model_provider and debug_data:
                result_parts.append(f"\n🤖 **AI Analysis:**")
                ai_insights = self._get_ai_analysis(debug_data, error_description)
                result_parts.append(ai_insights)
            
            # Reproduction steps
            if reproduction_steps:
                result_parts.append(f"\n🔄 **Reproduction Steps:**")
                for i, step in enumerate(reproduction_steps, 1):
                    result_parts.append(f"   {i}. {step}")
            
            # Summary and next steps
            result_parts.append(f"\n📋 **Next Steps:**")
            result_parts.append("   1. Fix the identified issues")
            result_parts.append("   2. Add logging/debugging statements")
            result_parts.append("   3. Write tests to prevent regression")
            result_parts.append("   4. Review related code for similar issues")
            
            return ToolResult(
                success=True,
                output="\n".join(result_parts),
                action_description=f"Debugging analysis: {debug_type}"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Debugging analysis error: {str(e)}"
            )