"""Anti-pattern parser tool for detecting code patterns in files."""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from .base import Tool
from ..types import ToolResult


class AntiPatternRule:
    """Represents a single anti-pattern detection rule."""
    
    def __init__(self, name: str, patterns: List[str], description: str = "", case_sensitive: bool = False):
        self.name = name
        self.patterns = patterns
        self.description = description
        self.case_sensitive = case_sensitive
        
    def check_file(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Check if file content matches this rule's patterns."""
        issues = []
        
        # Convert content to lowercase if case insensitive
        search_content = content if self.case_sensitive else content.lower()
        
        # Check if all patterns appear in the same file
        pattern_matches = []
        for pattern in self.patterns:
            search_pattern = pattern if self.case_sensitive else pattern.lower()
            if search_pattern in search_content:
                # Find all line numbers where pattern appears
                lines = content.split('\n')
                line_numbers = []
                for i, line in enumerate(lines, 1):
                    line_to_search = line if self.case_sensitive else line.lower()
                    if search_pattern in line_to_search:
                        line_numbers.append(i)
                pattern_matches.append({
                    'pattern': pattern,
                    'lines': line_numbers
                })
        
        # If all patterns were found, report the issue
        if len(pattern_matches) == len(self.patterns):
            issues.append({
                'rule': self.name,
                'description': self.description,
                'file': file_path,
                'patterns_found': pattern_matches
            })
        
        return issues


class AntiPatternParser(Tool):
    """Tool for detecting custom anti-patterns in code."""
    
    def __init__(self, config_file: str = ".anti_patterns.json"):
        self.config_file = config_file
        self.rules: List[AntiPatternRule] = []
        self._load_rules()
    
    @property
    def name(self) -> str:
        return "anti_pattern_parser"
    
    @property
    def description(self) -> str:
        return "Detects custom anti-patterns in code based on configurable rules"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["scan", "add_rule", "remove_rule", "list_rules"],
                    "description": "Action to perform"
                },
                "path": {
                    "type": "string",
                    "description": "Path to scan (for scan action)"
                },
                "rule_name": {
                    "type": "string",
                    "description": "Name of the rule (for add/remove actions)"
                },
                "patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of patterns that must all appear in the same file"
                },
                "description": {
                    "type": "string",
                    "description": "Description of the anti-pattern"
                },
                "case_sensitive": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether pattern matching is case sensitive"
                }
            },
            "required": ["action"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def _load_rules(self):
        """Load rules from config file."""
        config_path = Path(self.config_file)
        if not config_path.exists():
            # Create empty config file
            default_config = {"rules": []}
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.rules = [
                    AntiPatternRule(
                        name=rule['name'],
                        patterns=rule['patterns'],
                        description=rule.get('description', ''),
                        case_sensitive=rule.get('case_sensitive', False)
                    )
                    for rule in config.get('rules', [])
                ]
        except Exception as e:
            print(f"Warning: Could not load anti-pattern rules: {e}")
            self.rules = []
    
    def _save_rules(self):
        """Save rules to config file."""
        config = {
            "rules": [
                {
                    "name": rule.name,
                    "patterns": rule.patterns,
                    "description": rule.description,
                    "case_sensitive": rule.case_sensitive
                }
                for rule in self.rules
            ]
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def _scan_path(self, path: str) -> List[Dict[str, Any]]:
        """Scan path for anti-patterns."""
        all_issues = []
        scan_path = Path(path)
        
        if not scan_path.exists():
            return []
        
        # Define file extensions to scan
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.php', '.rb', '.rs', '.kt', '.swift'}
        
        if scan_path.is_file():
            files_to_scan = [scan_path]
        else:
            files_to_scan = [
                f for f in scan_path.rglob('*') 
                if f.is_file() and f.suffix in code_extensions
                and not any(ignore in f.parts for ignore in {'.git', '__pycache__', 'node_modules'})
            ]
        
        for file_path in files_to_scan:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for rule in self.rules:
                    issues = rule.check_file(str(file_path), content)
                    all_issues.extend(issues)
            except Exception as e:
                print(f"Warning: Could not scan {file_path}: {e}")
        
        return all_issues
    
    def execute(self, **parameters) -> ToolResult:
        """Execute the anti-pattern parser tool."""
        action = parameters.get('action')
        
        try:
            if action == "scan":
                path = parameters.get('path', '.')
                issues = self._scan_path(path)
                
                if not issues:
                    return ToolResult(
                        success=True,
                        output="No anti-patterns detected.",
                        action_description=f"Scanned {path} for anti-patterns"
                    )
                
                # Format output
                output_lines = [f"Found {len(issues)} anti-pattern issue(s):"]
                for issue in issues:
                    output_lines.append(f"\n📋 Rule: {issue['rule']}")
                    if issue['description']:
                        output_lines.append(f"   Description: {issue['description']}")
                    output_lines.append(f"   File: {issue['file']}")
                    for pattern_info in issue['patterns_found']:
                        lines_str = ", ".join(map(str, pattern_info['lines']))
                        output_lines.append(f"   Pattern '{pattern_info['pattern']}' found at lines: {lines_str}")
                
                return ToolResult(
                    success=True,
                    output="\n".join(output_lines),
                    action_description=f"Found {len(issues)} anti-pattern issues"
                )
            
            elif action == "add_rule":
                rule_name = parameters.get('rule_name')
                patterns = parameters.get('patterns', [])
                description = parameters.get('description', '')
                case_sensitive = parameters.get('case_sensitive', False)
                
                if not rule_name or not patterns:
                    return ToolResult(
                        success=False,
                        error="Rule name and patterns are required"
                    )
                
                # Remove existing rule with same name
                self.rules = [r for r in self.rules if r.name != rule_name]
                
                # Add new rule
                new_rule = AntiPatternRule(rule_name, patterns, description, case_sensitive)
                self.rules.append(new_rule)
                self._save_rules()
                
                return ToolResult(
                    success=True,
                    output=f"Added anti-pattern rule '{rule_name}' with patterns: {', '.join(patterns)}",
                    action_description=f"Added anti-pattern rule '{rule_name}'"
                )
            
            elif action == "remove_rule":
                rule_name = parameters.get('rule_name')
                if not rule_name:
                    return ToolResult(
                        success=False,
                        error="Rule name is required"
                    )
                
                original_count = len(self.rules)
                self.rules = [r for r in self.rules if r.name != rule_name]
                
                if len(self.rules) < original_count:
                    self._save_rules()
                    return ToolResult(
                        success=True,
                        output=f"Removed anti-pattern rule '{rule_name}'",
                        action_description=f"Removed anti-pattern rule '{rule_name}'"
                    )
                else:
                    return ToolResult(
                        success=False,
                        error=f"Rule '{rule_name}' not found"
                    )
            
            elif action == "list_rules":
                if not self.rules:
                    return ToolResult(
                        success=True,
                        output="No anti-pattern rules configured.",
                        action_description="Listed anti-pattern rules"
                    )
                
                output_lines = ["Anti-pattern rules:"]
                for rule in self.rules:
                    output_lines.append(f"\n📋 {rule.name}")
                    output_lines.append(f"   Patterns: {', '.join(rule.patterns)}")
                    if rule.description:
                        output_lines.append(f"   Description: {rule.description}")
                    output_lines.append(f"   Case sensitive: {rule.case_sensitive}")
                
                return ToolResult(
                    success=True,
                    output="\n".join(output_lines),
                    action_description="Listed anti-pattern rules"
                )
            
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Anti-pattern parser error: {str(e)}"
            )