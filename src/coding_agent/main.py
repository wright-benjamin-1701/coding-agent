#!/usr/bin/env python3
"""Main text-based interface for the coding agent."""

import sys
from pathlib import Path
from typing import Optional
from .agent import CodingAgent
from .config import ConfigManager
from .ui import UIHelper


class CodingAgentUI:
    """Text-based user interface for the coding agent."""
    
    def __init__(self):
        self.agent: Optional[CodingAgent] = None
        self.config_manager: Optional[ConfigManager] = None
        self.running = True
    
    def start(self):
        """Start the main program."""
        self.print_header()
        
        # Initialize agent
        if not self.initialize_agent():
            return
        
        # Main interaction loop
        self.main_loop()
    
    def print_header(self):
        """Print program header."""
        UIHelper.print_header()
    
    def initialize_agent(self) -> bool:
        """Initialize the agent with configuration."""
        try:
            # Load configuration
            self.config_manager = ConfigManager()
            print(f"📄 Loading config from: {self.config_manager.config_path}")
            
            # Check if config exists, if not create one
            if not Path(self.config_manager.config_path).exists():
                print("No configuration found. Let's set one up!")
                if not self.setup_initial_config():
                    return False
            
            # Create agent with the same config manager and pass it directly
            self.agent = CodingAgent(config_path=str(self.config_manager.config_path))
            # Share the same config manager instance to avoid reload
            self.agent.config_manager = self.config_manager
            self.agent.config = self.config_manager.load_config()
            
            # Initialize agent
            print("🚀 Initializing agent...")
            if not self.agent.initialize():
                print("❌ Failed to initialize agent. Check your configuration.")
                return False
            
            print("✅ Agent ready!\n")
            return True
            
        except Exception as e:
            print(f"❌ Error initializing agent: {e}")
            return False
    
    def setup_initial_config(self) -> bool:
        """Set up initial configuration interactively.""" 
        UIHelper.print_section("📝 Configuration Setup")
        
        try:
            # Get model provider
            provider = UIHelper.get_input_with_suggestions("Model provider", ["ollama"], "ollama")
            
            # Get model name
            model_suggestions = {
                "ollama": ["llama2", "codellama", "mistral", "qwen", "deepseek-coder"]
            }
            suggestions = model_suggestions.get(provider, [])
            model = UIHelper.get_input_with_suggestions("Model name", suggestions, suggestions[0] if suggestions else "llama2")
            
            # Get base URL
            base_url = UIHelper.get_input_with_suggestions("Base URL", [], "http://localhost:11434")
            
            # Create and save config
            config = self.config_manager.load_config()
            config.model.provider = provider
            config.model.model = model
            config.model.base_url = base_url
            
            self.config_manager.save_config(config)
            print(f"\n✅ Configuration saved to: {self.config_manager.config_path}")
            return True
            
        except KeyboardInterrupt:
            print("\n❌ Setup cancelled.")
            return False
    
    def get_input(self, prompt: str, default: str = "") -> str:
        """Get input from user with default value."""
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            return user_input if user_input else default
        else:
            return input(f"{prompt}: ").strip()
    
    def main_loop(self):
        """Main interaction loop."""
        print("Type your request, or use commands:")
        print("  'help' - Show available commands")
        print("  'status' - Show agent status")
        print("  'config' - Show configuration")
        print("  'quit' or 'exit' - Exit program")
        print()
        
        while self.running:
            try:
                user_input = input("🤖 > ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    self.handle_quit()
                elif user_input.lower() == 'help':
                    self.handle_help()
                elif user_input.lower() == 'status':
                    self.handle_status()
                elif user_input.lower() == 'config':
                    self.handle_config()
                elif user_input.lower() == 'tools':
                    self.handle_tools()
                elif user_input.lower() == 'clear':
                    self.handle_clear()
                elif user_input.lower() in ['debug on', 'debug enable']:
                    self.handle_debug(True)
                elif user_input.lower() in ['debug off', 'debug disable']:
                    self.handle_debug(False)
                else:
                    # Process as agent request
                    self.handle_request(user_input)
                
            except KeyboardInterrupt:
                print("\n")
                self.handle_quit()
            except Exception as e:
                print(f"❌ Error: {e}\n")
    
    def handle_quit(self):
        """Handle quit command."""
        print("👋 Goodbye!")
        self.running = False
    
    def handle_help(self):
        """Handle help command."""
        print(UIHelper.format_help())
    
    def handle_status(self):
        """Handle status command."""
        config_info = self.agent.config_manager.get_config_info()
        recent_summaries = self.agent.rag_db.get_recent_summaries(3)
        
        status_info = {
            'provider_available': self.agent.model_provider.is_available(),
            'provider': config_info['provider'],
            'model': config_info['model'],
            'base_url': config_info['base_url'],
            'debug': config_info['debug'],
            'tool_count': len(self.agent.tool_registry.list_tools()),
            'recent_summaries': recent_summaries
        }
        
        print(UIHelper.format_status(status_info))
    
    def handle_config(self):
        """Handle config command."""
        config = self.agent.config
        
        config_data = {
            'config_path': str(self.agent.config_manager.config_path),
            'model': config.model.dict(),
            'database': config.database.dict(),
            'indexer': config.indexer.dict()
        }
        
        print(UIHelper.format_config(config_data))
    
    def handle_tools(self):
        """Handle tools command."""
        schemas = self.agent.tool_registry.get_schemas()
        print(UIHelper.format_tools(schemas))
    
    def handle_clear(self):
        """Handle clear command."""
        UIHelper.clear_screen()
        self.print_header()
    
    def handle_debug(self, enable: bool):
        """Handle debug mode toggle."""
        self.agent.config.debug = enable
        status = "enabled" if enable else "disabled"
        print(f"🐛 Debug mode {status}")
        if enable:
            print("   Debug will show full prompts and responses when no actions are generated")
        print()
    
    def handle_request(self, user_input: str):
        """Handle user request."""
        print()
        print("🔄 Processing request...")
        
        try:
            result = self.agent.process_request(user_input)
            print(f"\n✅ Result:")
            print(f"{result}")
            print()
        except Exception as e:
            print(f"\n❌ Error processing request: {e}")
            print()


def main():
    """Main entry point."""
    try:
        ui = CodingAgentUI()
        ui.start()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
    