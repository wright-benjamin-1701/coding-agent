"""Enhanced UI utilities for the coding agent."""

import os
from typing import List, Dict, Any


class UIHelper:
    """Helper class for UI formatting and user interaction."""
    
    @staticmethod
    def print_header():
        """Print a nice header."""
        print("=" * 60)
        print("🤖 CODING AGENT")
        print("A thin coding agent with RAG and tool execution")
        print("=" * 60)
        print()
    
    @staticmethod
    def print_section(title: str, items: List[str] = None):
        """Print a formatted section."""
        print(f"\n{title}")
        print("-" * len(title))
        if items:
            for item in items:
                print(f"  {item}")
        print()
    
    @staticmethod
    def get_input_with_suggestions(prompt: str, suggestions: List[str] = None, default: str = "") -> str:
        """Get input with optional suggestions."""
        if suggestions:
            print(f"Popular options: {', '.join(suggestions[:3])}")
        
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            return user_input if user_input else default
        else:
            return input(f"{prompt}: ").strip()
    
    @staticmethod
    def format_status(status_info: Dict[str, Any]) -> str:
        """Format status information nicely."""
        lines = []
        lines.append("🤖 Agent Status:")
        
        provider_status = "✅" if status_info.get('provider_available') else "❌"
        lines.append(f"   Provider: {provider_status} {status_info.get('provider', 'unknown')}")
        lines.append(f"   Model: {status_info.get('model', 'unknown')}")
        lines.append(f"   Base URL: {status_info.get('base_url', 'unknown')}")
        lines.append(f"   Debug: {'✅' if status_info.get('debug') else '❌'}")
        lines.append(f"   Tools: {status_info.get('tool_count', 0)} registered")
        
        if status_info.get('recent_summaries'):
            lines.append("\n📚 Recent Sessions:")
            for i, summary in enumerate(status_info['recent_summaries'], 1):
                lines.append(f"   {i}. {summary}")
        
        return "\n".join(lines) + "\n"
    
    @staticmethod
    def format_config(config_data: Dict[str, Any]) -> str:
        """Format configuration nicely."""
        lines = []
        lines.append("🔧 Configuration:")
        lines.append(f"   Config File: {config_data.get('config_path', 'unknown')}")
        lines.append("")
        
        model = config_data.get('model', {})
        lines.append("   Model Settings:")
        lines.append(f"     Provider: {model.get('provider', 'unknown')}")
        lines.append(f"     Model: {model.get('model', 'unknown')}")
        lines.append(f"     Base URL: {model.get('base_url', 'unknown')}")
        lines.append(f"     Temperature: {model.get('temperature', 'unknown')}")
        lines.append("")
        
        database = config_data.get('database', {})
        lines.append("   Database:")
        lines.append(f"     Path: {database.get('db_path', 'unknown')}")
        lines.append(f"     Max Summaries: {database.get('max_summaries', 'unknown')}")
        lines.append("")
        
        indexer = config_data.get('indexer', {})
        lines.append("   File Indexer:")
        lines.append(f"     Index File: {indexer.get('index_file', 'unknown')}")
        lines.append(f"     Watch Enabled: {indexer.get('watch_enabled', 'unknown')}")
        
        return "\n".join(lines) + "\n"
    
    @staticmethod
    def format_tools(tools_data: Dict[str, Any]) -> str:
        """Format tools list nicely."""
        lines = []
        lines.append("🔧 Available Tools:")
        
        for name, schema in tools_data.items():
            destructive = "⚠️ " if schema.get('destructive', False) else "  "
            description = schema.get('description', 'No description')
            lines.append(f"{destructive}{name} - {description}")
        
        return "\n".join(lines) + "\n"
    
    @staticmethod
    def format_help() -> str:
        """Format help message."""
        lines = []
        lines.append("📚 Available Commands:")
        lines.append("  help       - Show this help message")
        lines.append("  status     - Show agent status and configuration")
        lines.append("  config     - Show detailed configuration")
        lines.append("  tools      - List available tools")
        lines.append("  clear      - Clear screen")
        lines.append("  debug on   - Enable debug mode (shows full prompts/responses)")
        lines.append("  debug off  - Disable debug mode")
        lines.append("  quit/exit  - Exit the program")
        lines.append("")
        lines.append("💡 Tip: Just type your coding request and I'll help!")
        lines.append("   Examples:")
        lines.append("   - 'add error handling to main.py'")
        lines.append("   - 'find all TODO comments'")
        lines.append("   - 'run the tests'")
        
        return "\n".join(lines) + "\n"
    
    @staticmethod
    def clear_screen():
        """Clear the screen."""
        os.system('clear' if os.name == 'posix' else 'cls')