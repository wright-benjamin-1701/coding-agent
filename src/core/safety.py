"""
Safety and security features for the coding agent
"""
import re
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from .config import ConfigManager, get_config


@dataclass
class SafetyViolation:
    """Represents a safety violation"""
    type: str
    severity: str  # "low", "medium", "high", "critical"
    message: str
    details: Dict[str, Any]
    suggested_action: str


class SafetyValidator:
    """Validates operations for safety and security"""
    
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or get_config()
        self.violation_patterns = self._load_violation_patterns()
    
    def validate_file_access(self, file_path: str, operation: str = "read") -> Optional[SafetyViolation]:
        """Validate file access for safety"""
        
        path = Path(file_path).resolve()
        
        # Check if path is in restricted locations
        if not self.config.is_path_safe(str(path)):
            return SafetyViolation(
                type="restricted_path",
                severity="high",
                message=f"Access to {path} is restricted",
                details={"path": str(path), "operation": operation},
                suggested_action="Use a different file path outside restricted areas"
            )
        
        # Check file size for read operations
        if operation in ["read", "write"] and path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            max_size = self.config.config.safety.max_file_size_mb
            
            if size_mb > max_size:
                return SafetyViolation(
                    type="file_too_large",
                    severity="medium",
                    message=f"File size ({size_mb:.1f}MB) exceeds limit ({max_size}MB)",
                    details={"size_mb": size_mb, "max_size_mb": max_size, "path": str(path)},
                    suggested_action="Use a smaller file or increase the size limit in config"
                )
        
        # Check for sensitive file extensions
        if self.config.is_file_extension_sensitive(str(path)):
            return SafetyViolation(
                type="sensitive_file",
                severity="high",
                message=f"File {path.name} appears to contain sensitive information",
                details={"extension": path.suffix, "path": str(path)},
                suggested_action="Avoid accessing files that may contain secrets or credentials"
            )
        
        return None
    
    def validate_command(self, command: str) -> Optional[SafetyViolation]:
        """Validate command execution for safety"""
        
        if not self.config.is_command_safe(command):
            return SafetyViolation(
                type="dangerous_command",
                severity="critical",
                message="Command contains potentially dangerous operations",
                details={"command": command},
                suggested_action="Review the command carefully or use safer alternatives"
            )
        
        # Check for common security risks
        risk_patterns = [
            (r'eval\s*\(', "code_injection", "high", "Avoid using eval() with user input"),
            (r'exec\s*\(', "code_injection", "high", "Avoid using exec() with user input"),
            (r'__import__\s*\(', "import_injection", "medium", "Be careful with dynamic imports"),
            (r'open\s*\([^)]*["\']w', "file_overwrite", "medium", "Writing files can be destructive"),
            (r'subprocess\.(run|call|Popen)', "subprocess_call", "medium", "Subprocess calls should be validated"),
        ]
        
        for pattern, violation_type, severity, suggestion in risk_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return SafetyViolation(
                    type=violation_type,
                    severity=severity,
                    message=f"Command contains potentially risky pattern: {pattern}",
                    details={"command": command, "pattern": pattern},
                    suggested_action=suggestion
                )
        
        return None
    
    def validate_content(self, content: str, content_type: str = "code") -> List[SafetyViolation]:
        """Validate content for safety issues"""
        
        violations = []
        
        # Check for potential secrets
        secret_patterns = [
            (r'(?:password|pwd|pass)\s*[=:]\s*["\'][^"\']{8,}["\']', "password_in_code", "high"),
            (r'(?:api_?key|apikey)\s*[=:]\s*["\'][^"\']{16,}["\']', "api_key_in_code", "critical"),
            (r'(?:secret|token)\s*[=:]\s*["\'][^"\']{16,}["\']', "secret_in_code", "critical"),
            (r'-----BEGIN [A-Z ]+ KEY-----', "private_key", "critical"),
            (r'[A-Za-z0-9+/]{40,}={0,2}', "base64_encoded_secret", "medium"),
        ]
        
        for pattern, violation_type, severity in secret_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                violations.append(SafetyViolation(
                    type=violation_type,
                    severity=severity,
                    message=f"Potential {violation_type.replace('_', ' ')} detected",
                    details={"match": match.group(), "position": match.span()},
                    suggested_action="Remove or properly secure sensitive information"
                ))
        
        # Check for hardcoded URLs with credentials
        url_cred_pattern = r'https?://[^:]+:[^@]+@[^\s]+'
        if re.search(url_cred_pattern, content):
            violations.append(SafetyViolation(
                type="credentials_in_url",
                severity="high",
                message="URL with embedded credentials detected",
                details={"content_type": content_type},
                suggested_action="Use environment variables or secure credential storage"
            ))
        
        # Check for SQL injection patterns (basic)
        if content_type in ["sql", "code"]:
            sql_injection_patterns = [
                r"';?\s*drop\s+table",
                r"';?\s*delete\s+from",
                r"union\s+select",
                r"'\s*or\s+'1'\s*=\s*'1"
            ]
            
            for pattern in sql_injection_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    violations.append(SafetyViolation(
                        type="sql_injection_pattern",
                        severity="high",
                        message="Potential SQL injection pattern detected",
                        details={"pattern": pattern, "content_type": content_type},
                        suggested_action="Use parameterized queries and input validation"
                    ))
        
        return violations
    
    def validate_git_operation(self, operation: str, params: Dict[str, Any]) -> Optional[SafetyViolation]:
        """Validate git operations for safety"""
        
        # Check for potentially destructive operations
        destructive_ops = {
            "reset": "high",
            "rebase": "medium", 
            "force_push": "high",
            "clean": "medium"
        }
        
        if operation in destructive_ops:
            severity = destructive_ops[operation]
            return SafetyViolation(
                type="destructive_git_operation",
                severity=severity,
                message=f"Git {operation} can be destructive",
                details={"operation": operation, "params": params},
                suggested_action="Ensure you have backups and understand the consequences"
            )
        
        # Check commit message for sensitive information
        if operation == "commit" and "message" in params:
            message = params["message"]
            content_violations = self.validate_content(message, "commit_message")
            
            if content_violations:
                return SafetyViolation(
                    type="sensitive_commit_message",
                    severity="medium",
                    message="Commit message may contain sensitive information",
                    details={"message": message, "violations": content_violations},
                    suggested_action="Remove sensitive information from commit message"
                )
        
        return None
    
    def validate_refactor_operation(self, operation: str, file_path: str, params: Dict[str, Any]) -> Optional[SafetyViolation]:
        """Validate refactoring operations for safety"""
        
        # Check file access first
        file_violation = self.validate_file_access(file_path, "write")
        if file_violation:
            return file_violation
        
        # Check for risky refactoring patterns
        if operation == "rename" and params.get("old_name") == params.get("new_name"):
            return SafetyViolation(
                type="pointless_operation",
                severity="low",
                message="Rename operation has same source and target",
                details={"operation": operation, "params": params},
                suggested_action="Use different names for rename operation"
            )
        
        # Check for potentially problematic renames
        if operation == "rename":
            old_name = params.get("old_name", "")
            new_name = params.get("new_name", "")
            
            # Check if renaming to Python keywords
            python_keywords = {
                "and", "as", "assert", "break", "class", "continue", "def", "del", 
                "elif", "else", "except", "exec", "finally", "for", "from", "global",
                "if", "import", "in", "is", "lambda", "not", "or", "pass", "print",
                "raise", "return", "try", "while", "with", "yield"
            }
            
            if new_name.lower() in python_keywords:
                return SafetyViolation(
                    type="rename_to_keyword",
                    severity="high",
                    message=f"Renaming to Python keyword '{new_name}' will cause syntax errors",
                    details={"old_name": old_name, "new_name": new_name},
                    suggested_action="Choose a different name that is not a Python keyword"
                )
        
        return None
    
    def _load_violation_patterns(self) -> Dict[str, Any]:
        """Load violation patterns from configuration or defaults"""
        
        return {
            "dangerous_functions": [
                "eval", "exec", "__import__", "compile", "globals", "locals"
            ],
            "sensitive_keywords": [
                "password", "secret", "token", "key", "credential", "auth"
            ],
            "file_extensions_to_check": [
                ".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs"
            ]
        }
    
    def get_safety_summary(self) -> Dict[str, Any]:
        """Get summary of current safety configuration"""
        
        return {
            "path_validation_enabled": self.config.config.safety.enable_path_validation,
            "command_validation_enabled": self.config.config.safety.enable_command_validation,
            "content_scanning_enabled": self.config.config.safety.enable_content_scanning,
            "max_file_size_mb": self.config.config.safety.max_file_size_mb,
            "restricted_paths_count": len(self.config.config.safety.restricted_paths),
            "dangerous_commands_count": len(self.config.config.safety.dangerous_commands),
            "sensitive_extensions_count": len(self.config.config.safety.sensitive_extensions)
        }


class SafetyEnforcer:
    """Enforces safety policies and handles violations"""
    
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or get_config()
        self.validator = SafetyValidator(config)
        self.violation_log: List[SafetyViolation] = []
    
    def check_and_enforce(self, operation_type: str, **kwargs) -> Tuple[bool, Optional[SafetyViolation]]:
        """Check operation for safety and enforce policies"""
        
        violation = None
        
        if operation_type == "file_access":
            violation = self.validator.validate_file_access(
                kwargs.get("file_path", ""),
                kwargs.get("operation", "read")
            )
        elif operation_type == "command":
            violation = self.validator.validate_command(kwargs.get("command", ""))
        elif operation_type == "git":
            violation = self.validator.validate_git_operation(
                kwargs.get("operation", ""),
                kwargs.get("params", {})
            )
        elif operation_type == "refactor":
            violation = self.validator.validate_refactor_operation(
                kwargs.get("operation", ""),
                kwargs.get("file_path", ""),
                kwargs.get("params", {})
            )
        
        if violation:
            self.violation_log.append(violation)
            
            # Enforce based on severity
            if violation.severity == "critical":
                return False, violation  # Block operation
            elif violation.severity == "high":
                # Could implement user confirmation here
                return True, violation  # Allow with warning
            else:
                return True, violation  # Allow with minor warning
        
        return True, None
    
    def get_violation_history(self) -> List[SafetyViolation]:
        """Get history of safety violations"""
        return self.violation_log.copy()
    
    def clear_violation_history(self) -> None:
        """Clear violation history"""
        self.violation_log.clear()


# Global safety enforcer instance
_safety_enforcer: Optional[SafetyEnforcer] = None


def get_safety_enforcer() -> SafetyEnforcer:
    """Get global safety enforcer instance"""
    global _safety_enforcer
    if _safety_enforcer is None:
        _safety_enforcer = SafetyEnforcer()
    return _safety_enforcer