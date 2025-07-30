#!/usr/bin/env python3
"""CLI entry point for the coding agent."""

import click
import sys
from .agent import CodingAgent


@click.group()
@click.option('--config', '-c', help='Path to configuration file')
@click.option('--model', help='Model to use for generation')
@click.option('--provider', help='Model provider (ollama)')
@click.option('--base-url', help='Provider base URL')
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.pass_context
def cli(ctx, config, model, provider, base_url, debug):
    """Coding Agent - A thin coding agent with RAG and tool execution."""
    ctx.ensure_object(dict)
    
    # Create agent with optional config overrides
    agent = CodingAgent(config_path=config)
    
    # Apply CLI overrides
    if model:
        agent.config.model.model = model
    if provider:
        agent.config.model.provider = provider
    if base_url:
        agent.config.model.base_url = base_url
    if debug:
        agent.config.debug = debug
    
    # Recreate model provider if settings changed
    if any([model, provider, base_url]):
        agent.model_provider = agent._create_model_provider()
    
    ctx.obj['agent'] = agent


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize the coding agent."""
    agent = ctx.obj['agent']
    success = agent.initialize()
    if not success:
        sys.exit(1)


@cli.command()
@click.argument('prompt', required=False)
@click.pass_context
def run(ctx, prompt):
    """Run the coding agent with a prompt."""
    agent = ctx.obj['agent']
    
    if not prompt:
        # Interactive mode
        print("Coding Agent - Interactive Mode")
        print("Type 'quit' or 'exit' to stop\n")
        
        while True:
            try:
                user_input = input("🤖 > ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                result = agent.process_request(user_input)
                print(f"\n✅ Result: {result}\n")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}\n")
    else:
        # Single prompt mode
        result = agent.process_request(prompt)
        print(result)


@cli.command()
@click.pass_context
def status(ctx):
    """Show agent status and configuration."""
    agent = ctx.obj['agent']
    config_info = agent.config_manager.get_config_info()
    
    print("🤖 Coding Agent Status")
    print(f"   Model Provider: {'✅' if agent.model_provider.is_available() else '❌'} {config_info['provider']}")
    print(f"   Model: {config_info['model']}")
    print(f"   Base URL: {config_info['base_url']}")
    print(f"   Config File: {config_info['config_path']} {'✅' if config_info['config_exists'] else '❌'}")
    print(f"   Debug Mode: {'✅' if config_info['debug'] else '❌'}")
    print(f"   Registered Tools: {len(agent.tool_registry.list_tools())}")
    print(f"   Tool Names: {', '.join(agent.tool_registry.list_tools())}")
    
    # Show recent sessions
    recent_summaries = agent.rag_db.get_recent_summaries(3)
    if recent_summaries:
        print(f"\n📚 Recent Sessions:")
        for i, summary in enumerate(recent_summaries, 1):
            print(f"   {i}. {summary}")


@cli.command()
@click.pass_context
def tools(ctx):
    """List available tools and their descriptions."""
    agent = ctx.obj['agent']
    schemas = agent.tool_registry.get_schemas()
    
    print("🔧 Available Tools:\n")
    for name, schema in schemas.items():
        destructive = "⚠️ " if schema.get('destructive', False) else ""
        print(f"{destructive}{name}")
        print(f"   {schema.get('description', 'No description')}")
        
        params = schema.get('parameters', {}).get('properties', {})
        if params:
            print("   Parameters:")
            for param_name, param_info in params.items():
                required = "required" if param_name in schema.get('parameters', {}).get('required', []) else "optional"
                print(f"     - {param_name} ({required}): {param_info.get('description', 'No description')}")
        print()


@cli.command()
@click.option('--model', prompt=True, help='Model name')
@click.option('--provider', default='ollama', help='Model provider')
@click.option('--base-url', default='http://localhost:11434', help='Provider base URL')
@click.pass_context
def config(ctx, model, provider, base_url):
    """Create or update configuration."""
    agent = ctx.obj['agent']
    
    # Update configuration
    agent.config.model.model = model
    agent.config.model.provider = provider
    agent.config.model.base_url = base_url
    
    # Save configuration
    agent.config_manager.save_config(agent.config)
    
    print(f"✅ Configuration saved to {agent.config_manager.config_path}")
    print(f"   Provider: {provider}")
    print(f"   Model: {model}")
    print(f"   Base URL: {base_url}")


@cli.command('config-show')
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    agent = ctx.obj['agent']
    config = agent.config
    
    print("🔧 Current Configuration:")
    print(f"   Config File: {agent.config_manager.config_path}")
    print()
    print("   Model Settings:")
    print(f"     Provider: {config.model.provider}")
    print(f"     Model: {config.model.model}")
    print(f"     Base URL: {config.model.base_url}")
    print(f"     Temperature: {config.model.temperature}")
    print(f"     Max Tokens: {config.model.max_tokens}")
    print()
    print("   Database Settings:")
    print(f"     DB Path: {config.database.db_path}")
    print(f"     Max Summaries: {config.database.max_summaries}")
    print(f"     Cache Enabled: {config.database.cache_enabled}")
    print()
    print("   Indexer Settings:")
    print(f"     Index File: {config.indexer.index_file}")
    print(f"     Watch Enabled: {config.indexer.watch_enabled}")
    print(f"     Ignore Patterns: {', '.join(config.indexer.ignore_patterns)}")
    print()
    print(f"   Debug: {config.debug}")


@cli.command('config-reset')
@click.confirmation_option(prompt='Reset configuration to defaults?')
@click.pass_context
def config_reset(ctx):
    """Reset configuration to defaults."""
    agent = ctx.obj['agent']
    agent.config_manager.create_default_config()
    print(f"✅ Configuration reset to defaults: {agent.config_manager.config_path}")


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()