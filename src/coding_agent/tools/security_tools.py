"""Security analysis tools for vulnerability detection and code security scanning."""

import os
import re
import json
from typing import Dict, Any, List, Set, Optional
from pathlib import Path
from .base import Tool
from ..types import ToolResult


class SecurityScanTool(Tool):
    """Tool for scanning code for common security vulnerabilities and issues."""
    
    @property
    def name(self) -> str:
        return "security_scan"
    
    @property
    def description(self) -> str:
        return "Scan code for security vulnerabilities including hardcoded secrets, SQL injection, XSS, and other common issues"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "File or directory path to scan for security issues"
                },
                "scan_type": {
                    "type": "string",
                    "enum": ["all", "secrets", "injection", "xss", "crypto", "auth", "files"],
                    "description": "Type of security scan to perform"
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Minimum severity level to report"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "description": "Output format for results"
                }
            },
            "required": ["target"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False  # Read-only scanning
    
    def execute(self, **parameters) -> ToolResult:
        """Execute security scan on target."""
        target = parameters.get("target", ".")
        scan_type = parameters.get("scan_type", "all")
        min_severity = parameters.get("severity", "low")
        output_format = parameters.get("output_format", "text")
        
        if not os.path.exists(target):
            return ToolResult(
                success=False,
                output=None,
                error=f"Target not found: {target}"
            )
        
        try:
            # Collect all files to scan
            files_to_scan = self._collect_files(target)
            
            if not files_to_scan:
                return ToolResult(
                    success=True,
                    output="No files found to scan",
                    action_description=f"Security scan of {target} - no files"
                )
            
            # Run security scans
            findings = []
            
            for file_path in files_to_scan:
                try:
                    file_findings = self._scan_file(file_path, scan_type)
                    findings.extend(file_findings)
                except Exception as e:
                    # Continue with other files if one fails
                    continue
            
            # Filter by severity
            filtered_findings = self._filter_by_severity(findings, min_severity)
            
            # Format output
            if output_format == "json":
                output = self._format_json_output(filtered_findings)
            else:
                output = self._format_text_output(filtered_findings)
            
            # Summary
            total_issues = len(filtered_findings)
            critical_count = len([f for f in filtered_findings if f['severity'] == 'critical'])
            high_count = len([f for f in filtered_findings if f['severity'] == 'high'])
            
            action_desc = f"Security scan found {total_issues} issues"
            if critical_count > 0:
                action_desc += f" ({critical_count} critical, {high_count} high)"
            
            return ToolResult(
                success=True,
                output=output,
                action_description=action_desc
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Security scan failed: {str(e)}"
            )
    
    def _collect_files(self, target: str) -> List[str]:
        """Collect files to scan."""
        files_to_scan = []
        
        if os.path.isfile(target):
            files_to_scan.append(target)
        else:
            # Scan directory
            for root, dirs, files in os.walk(target):
                # Skip common directories that shouldn't be scanned
                dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.env', 'venv', '.venv', 'build', 'dist'}]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    if self._should_scan_file(file_path):
                        files_to_scan.append(file_path)
        
        return files_to_scan[:500]  # Limit to prevent overwhelming scans
    
    def _should_scan_file(self, file_path: str) -> bool:
        """Determine if file should be scanned."""
        # Skip binary files and common non-code files
        skip_extensions = {'.pyc', '.pyo', '.exe', '.dll', '.so', '.dylib', '.jpg', '.jpeg', '.png', '.gif', '.pdf', '.zip', '.tar', '.gz'}
        
        path = Path(file_path)
        if path.suffix.lower() in skip_extensions:
            return False
        
        # Only scan text files up to reasonable size
        try:
            if os.path.getsize(file_path) > 1024 * 1024:  # 1MB limit
                return False
            
            # Try to detect if it's a text file
            with open(file_path, 'rb') as f:
                chunk = f.read(512)
                if b'\\0' in chunk:  # Binary file
                    return False
        except:
            return False
        
        return True
    
    def _scan_file(self, file_path: str, scan_type: str) -> List[Dict[str, Any]]:
        """Scan a single file for security issues."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\\n')
        except Exception:
            return findings
        
        # Run different types of scans
        if scan_type in ['all', 'secrets']:
            findings.extend(self._scan_hardcoded_secrets(file_path, content, lines))
        
        if scan_type in ['all', 'injection']:
            findings.extend(self._scan_sql_injection(file_path, content, lines))
        
        if scan_type in ['all', 'xss']:
            findings.extend(self._scan_xss_vulnerabilities(file_path, content, lines))
        
        if scan_type in ['all', 'crypto']:
            findings.extend(self._scan_crypto_issues(file_path, content, lines))
        
        if scan_type in ['all', 'auth']:
            findings.extend(self._scan_auth_issues(file_path, content, lines))
        
        if scan_type in ['all', 'files']:
            findings.extend(self._scan_file_issues(file_path, content, lines))
        
        return findings
    
    def _scan_hardcoded_secrets(self, file_path: str, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Scan for hardcoded secrets and credentials."""
        findings = []
        
        # Patterns for common secrets
        secret_patterns = {
            'API Key': [
                r'api[_-]?key["\'\s]*[=:]["\'\s]*[A-Za-z0-9_\-]{20,}',
                r'apikey["\'\s]*[=:]["\'\s]*[A-Za-z0-9_\-]{20,}',
            ],
            'AWS Key': [
                r'AKIA[0-9A-Z]{16}',
                r'aws[_-]?access[_-]?key["\'\s]*[=:]["\'\s]*[A-Za-z0-9_\-]{20,}',
            ],
            'Database Password': [
                r'password["\'\s]*[=:]["\'\s]*["\'][^"\'\n]{8,}["\']',
                r'pwd["\'\s]*[=:]["\'\s]*["\'][^"\'\n]{8,}["\']',
            ],
            'Private Key': [
                r'-----BEGIN (RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY',
            ],
            'JWT Token': [
                r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+',
            ],
            'Generic Secret': [
                r'secret["\'\s]*[=:]["\'\s]*["\'][^"\'\n]{16,}["\']',
                r'token["\'\s]*[=:]["\'\s]*["\'][^"\'\n]{16,}["\']',
            ]
        }
        
        for secret_type, patterns in secret_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    line_num = content[:match.start()].count('\\n') + 1
                    findings.append({
                        'type': 'Hardcoded Secret',
                        'severity': 'critical',
                        'category': secret_type,
                        'file': file_path,
                        'line': line_num,
                        'message': f'Potential {secret_type} found',
                        'code': lines[line_num - 1].strip() if line_num <= len(lines) else '',
                        'recommendation': f'Remove hardcoded {secret_type} and use environment variables or secure key management'
                    })
        
        return findings
    
    def _scan_sql_injection(self, file_path: str, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Scan for SQL injection vulnerabilities."""
        findings = []
        
        # Patterns for SQL injection risks
        sql_patterns = [
            r'execute\s*\(["\'].*?%s.*?["\'].*?%',  # String formatting in SQL
            r'execute\s*\([f"\'].*?\{.*?\}.*?["\']',  # f-strings in SQL
            r'query\s*=\s*["\'].*?["\']\s*[+%]',  # String concatenation in queries
            r'cursor\.execute\s*\(["\'].*?["\']\s*[+%]',  # Direct concatenation
            r'SELECT\s+.*?\+.*?FROM',  # String concatenation in SELECT
            r'WHERE\s+.*?\+.*?[=<>]',  # String concatenation in WHERE
        ]
        
        for pattern in sql_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                line_num = content[:match.start()].count('\\n') + 1
                findings.append({
                    'type': 'SQL Injection Risk',
                    'severity': 'high',
                    'category': 'Injection',
                    'file': file_path,
                    'line': line_num,
                    'message': 'Potential SQL injection vulnerability',
                    'code': lines[line_num - 1].strip() if line_num <= len(lines) else '',
                    'recommendation': 'Use parameterized queries or prepared statements'
                })
        
        return findings
    
    def _scan_xss_vulnerabilities(self, file_path: str, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Scan for XSS vulnerabilities."""
        findings = []
        
        # Patterns for XSS risks
        xss_patterns = [
            r'innerHTML\s*=\s*.*?[+]',  # innerHTML with concatenation
            r'document\.write\s*\(.*?[+]',  # document.write with concatenation
            r'\$\(.*?\)\.html\s*\(.*?[+]',  # jQuery html() with concatenation
            r'render_template_string\s*\(',  # Flask template string rendering
            r'\|safe\s*}}',  # Django safe filter
            r'\|\s*raw\s*}}',  # Jinja2 raw filter
        ]
        
        for pattern in xss_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                line_num = content[:match.start()].count('\\n') + 1
                findings.append({
                    'type': 'XSS Risk',
                    'severity': 'medium',
                    'category': 'Cross-Site Scripting',
                    'file': file_path,
                    'line': line_num,
                    'message': 'Potential XSS vulnerability',
                    'code': lines[line_num - 1].strip() if line_num <= len(lines) else '',
                    'recommendation': 'Sanitize user input and use safe template rendering'
                })
        
        return findings
    
    def _scan_crypto_issues(self, file_path: str, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Scan for cryptographic issues."""
        findings = []
        
        # Patterns for crypto issues
        crypto_patterns = {
            'Weak Hash': [r'hashlib\.(md5|sha1)\s*\(', r'MD5\s*\(', r'SHA1\s*\('],
            'Weak Random': [r'random\.(random|randint)\s*\(', r'Math\.random\s*\('],
            'Weak Cipher': [r'DES\s*\(', r'RC4\s*\('],
        }
        
        for issue_type, patterns in crypto_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    line_num = content[:match.start()].count('\\n') + 1
                    findings.append({
                        'type': 'Cryptographic Issue',
                        'severity': 'medium',
                        'category': issue_type,
                        'file': file_path,
                        'line': line_num,
                        'message': f'{issue_type} detected',
                        'code': lines[line_num - 1].strip() if line_num <= len(lines) else '',
                        'recommendation': 'Use strong cryptographic functions (SHA-256+, secure random)'
                    })
        
        return findings
    
    def _scan_auth_issues(self, file_path: str, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Scan for authentication and authorization issues."""
        findings = []
        
        # Patterns for auth issues
        auth_patterns = [
            r'auth\s*=\s*False',  # Disabled authentication
            r'verify\s*=\s*False',  # Disabled SSL verification
            r'check_hostname\s*=\s*False',  # Disabled hostname check
            r'CSRF_DISABLED\s*=\s*True',  # CSRF disabled
        ]
        
        for pattern in auth_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\\n') + 1
                findings.append({
                    'type': 'Authentication Issue',
                    'severity': 'medium',
                    'category': 'Authentication',
                    'file': file_path,
                    'line': line_num,
                    'message': 'Authentication or security check disabled',
                    'code': lines[line_num - 1].strip() if line_num <= len(lines) else '',
                    'recommendation': 'Enable proper authentication and security checks'
                })
        
        return findings
    
    def _scan_file_issues(self, file_path: str, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Scan for file handling security issues."""
        findings = []
        
        # Patterns for file issues
        file_patterns = [
            r'open\s*\(.*?user_input',  # Opening files with user input
            r'os\.system\s*\(',  # OS command execution
            r'subprocess\.call\s*\(',  # Subprocess without shell=False
            r'eval\s*\(',  # Using eval()
            r'exec\s*\(',  # Using exec()
            r'pickle\.loads\s*\(',  # Unpickling untrusted data
        ]
        
        severity_map = {
            'eval': 'critical',
            'exec': 'critical',
            'pickle.loads': 'high',
            'os.system': 'high',
            'subprocess': 'medium',
            'open': 'low'
        }
        
        for pattern in file_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\\n') + 1
                issue_type = match.group().split('(')[0].split('.')[-1]
                severity = severity_map.get(issue_type, 'medium')
                
                findings.append({
                    'type': 'Unsafe Operation',
                    'severity': severity,
                    'category': 'File/Command Execution',
                    'file': file_path,
                    'line': line_num,
                    'message': f'Potentially unsafe operation: {issue_type}',
                    'code': lines[line_num - 1].strip() if line_num <= len(lines) else '',
                    'recommendation': 'Validate inputs and use safe alternatives'
                })
        
        return findings
    
    def _filter_by_severity(self, findings: List[Dict[str, Any]], min_severity: str) -> List[Dict[str, Any]]:
        """Filter findings by minimum severity level."""
        severity_levels = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
        min_level = severity_levels.get(min_severity, 0)
        
        return [f for f in findings if severity_levels.get(f['severity'], 0) >= min_level]
    
    def _format_text_output(self, findings: List[Dict[str, Any]]) -> str:
        """Format findings as human-readable text."""
        if not findings:
            return "✅ No security issues found"
        
        output = f"🔍 Security Scan Results ({len(findings)} issues found)\\n\\n"
        
        # Group by severity
        by_severity = {}
        for finding in findings:
            severity = finding['severity']
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(finding)
        
        severity_order = ['critical', 'high', 'medium', 'low']
        severity_icons = {
            'critical': '🔥',
            'high': '⚠️',
            'medium': '⚡',
            'low': 'ℹ️'
        }
        
        for severity in severity_order:
            if severity not in by_severity:
                continue
                
            issues = by_severity[severity]
            output += f"{severity_icons[severity]} {severity.upper()} ({len(issues)} issues)\\n"
            output += "=" * 50 + "\\n\\n"
            
            for issue in issues:
                output += f"📁 {issue['file']}:{issue['line']}\\n"
                output += f"🔍 {issue['type']}: {issue['message']}\\n"
                output += f"💡 {issue['recommendation']}\\n"
                if issue.get('code'):
                    output += f"📝 Code: {issue['code']}\\n"
                output += "\\n"
        
        return output
    
    def _format_json_output(self, findings: List[Dict[str, Any]]) -> str:
        """Format findings as JSON."""
        return json.dumps({
            'scan_results': {
                'total_issues': len(findings),
                'issues_by_severity': {
                    'critical': len([f for f in findings if f['severity'] == 'critical']),
                    'high': len([f for f in findings if f['severity'] == 'high']),
                    'medium': len([f for f in findings if f['severity'] == 'medium']),
                    'low': len([f for f in findings if f['severity'] == 'low']),
                },
                'findings': findings
            }
        }, indent=2)