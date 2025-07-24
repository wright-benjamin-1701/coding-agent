"""
Main entry point for the coding agent
"""
import asyncio
import argparse
import os
from pathlib import Path

from core.providers.ollama_provider import OllamaProvider
from core.tools.file_tool import FileTool
from core.tools.git_tool import GitTool
from core.tools.search_tool import SearchTool
from core.tools.refactor_tool import RefactorTool
from core.tools.debug_tool import DebugTool
from core.orchestrator import AgentOrchestrator
from core.config import init_config


async def create_agent() -> AgentOrchestrator:
    """Create and configure the coding agent"""
    
    # Initialize configuration
    config = init_config()
    
    # Initialize Ollama provider with config
    provider_config = {
        "base_url": config.config.ollama.base_url,
        "timeout": config.config.ollama.timeout
    }
    
    provider = OllamaProvider(provider_config)
    
    # Validate provider configuration
    if not provider.validate_config():
        print("❌ Error: Cannot connect to Ollama. Make sure Ollama is running.")
        print("   Start Ollama with: ollama serve")
        exit(1)
    
    # Get available models
    models = provider.list_models()
    if not models:
        print("❌ Error: No models found. Pull a model first:")
        print("   ollama pull qwen2.5-coder:7b")
        exit(1)
    
    print(f"✅ Connected to Ollama. Available models: {', '.join(models)}")
    
    # Show intelligent model selection
    selected_models = {
        "high_reasoning": config.get_model_for_task("high_reasoning", models),
        "fast_completion": config.get_model_for_task("fast_completion", models),  
        "analysis": config.get_model_for_task("analysis", models)
    }
    
    print("🧠 Model Selection:")
    for task_type, model in selected_models.items():
        if model:
            print(f"   {task_type}: {model}")
        else:
            print(f"   {task_type}: no suitable model found")
    
    # Initialize tools based on configuration
    tools = []
    
    if config.is_tool_enabled("file"):
        tools.append(FileTool())
    if config.is_tool_enabled("git"):
        tools.append(GitTool())
    if config.is_tool_enabled("search"):
        tools.append(SearchTool())
    if config.is_tool_enabled("refactor"):
        tools.append(RefactorTool())
    if config.is_tool_enabled("debug"):
        tools.append(DebugTool())
    
    print(f"🔧 Enabled tools: {', '.join(tool.__class__.__name__ for tool in tools)}")
    
    # Create orchestrator with config
    orchestrator = AgentOrchestrator(provider, tools, config)
    
    # Set project path to current directory and build context
    await orchestrator.set_project_path(os.getcwd())
    
    return orchestrator


async def interactive_mode(orchestrator: AgentOrchestrator):
    """Run interactive chat mode"""
    
    print("\n🤖 Coding Agent Ready!")
    print("Type 'exit' to quit, 'help' for available commands")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\n💬 You: ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == 'help':
                print_help()
                continue
            
            if user_input.lower() == 'config':
                await show_config(orchestrator)
                continue
            
            if user_input.lower() == 'session':
                await show_session_info(orchestrator)
                continue
            
            if user_input.lower() == 'tasks':  
                await show_active_tasks(orchestrator)
                continue
            
            if user_input.lower() == 'safety':
                await show_safety_status(orchestrator)
                continue
            
            if user_input.lower() == 'models':
                await show_model_info(orchestrator)
                continue
            
            if user_input.lower().startswith('suggest '):
                task_description = user_input[8:]  # Remove 'suggest '
                await show_model_suggestion(orchestrator, task_description)
                continue
            
            if user_input.lower() == 'learning':
                await show_learning_info(orchestrator)
                continue
            
            if user_input.lower().startswith('feedback '):
                feedback_text = user_input[9:]  # Remove 'feedback '
                response = await orchestrator.process_user_feedback(feedback_text)
                print(f"\n💡 {response}")
                continue
            
            if not user_input:
                continue
            
            print("\n🤔 Agent: Thinking...")
            
            # Process request
            response = await orchestrator.process_request(user_input)
            
            print(f"\n🤖 Agent: {response}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


def print_help():
    """Print help information"""
    help_text = """
Available Commands:
  help          - Show this help message
  exit/quit     - Exit the agent
  config        - Show current configuration
  session       - Show session information
  tasks         - Show active task plans
  safety        - Show safety status
  models        - Show available models and capabilities
  suggest <task> - Get model recommendations for a task
  learning      - Show learning progress and user preferences
  feedback <text> - Provide feedback on the last response

Example Requests:
  "Show me the project structure"
  "What files are in the src directory?"
  "Create a new Python file called utils.py"
  "Show git status"
  "What's the difference in the last commit?"
  "Commit my changes with message 'Add new feature'"
  "Search for all TODO comments"
  "Rename variable 'data' to 'user_data' in auth.py"
  "Check for syntax errors in Python files"

The agent can:
  ✅ Context awareness and project understanding
  ✅ Intelligent codebase navigation and search
  ✅ Code refactoring and modification
  ✅ Git operations with safety checks
  ✅ Error diagnosis and debugging
  ✅ Task planning and decomposition
  ✅ Safety validation and collaboration features
"""
    print(help_text)


async def show_config(orchestrator: AgentOrchestrator):
    """Show current configuration"""
    config = orchestrator.config
    
    print("\n🔧 Current Configuration:")
    print(f"   Ollama URL: {config.config.ollama.base_url}")
    print(f"   Max iterations: {config.config.agent.max_iterations}")
    print(f"   Context window: {config.config.agent.context_window}")
    print(f"   Auto-save sessions: {config.config.agent.auto_save_session}")
    print(f"   Safety validation: {config.config.safety.enable_path_validation}")
    
    # Show model preferences
    print("\n🧠 Model Preferences:")
    print(f"   High reasoning: {', '.join(config.config.models.high_reasoning[:3])}")
    print(f"   Fast completion: {', '.join(config.config.models.fast_completion[:3])}")
    
    # Show enabled tools
    enabled_tools = [name for name in orchestrator.tools.keys()]
    print(f"\n🔧 Enabled Tools: {', '.join(enabled_tools)}")


async def show_session_info(orchestrator: AgentOrchestrator):
    """Show session information"""
    session = orchestrator.session_manager.get_current_session()
    
    if not session:
        print("\n📊 No active session")
        return
    
    import time
    duration = time.time() - session.started_at
    
    print(f"\n📊 Session Information:")
    print(f"   Session ID: {session.session_id}")
    print(f"   Duration: {duration/60:.1f} minutes")
    print(f"   Project: {session.project_path}")
    print(f"   Messages: {len(session.conversation_history)}")
    print(f"   Active tasks: {len(session.active_tasks)}")


async def show_active_tasks(orchestrator: AgentOrchestrator):
    """Show active task plans"""
    planner = orchestrator.task_planner
    active_plans = planner.get_active_plans()
    
    if not active_plans:
        print("\n📋 No active task plans")
        return
    
    print(f"\n📋 Active Task Plans ({len(active_plans)}):")
    
    for plan in active_plans:
        progress = planner.get_plan_progress(plan.id)
        print(f"\n   🎯 {plan.title} ({plan.id})")
        print(f"      Status: {plan.status.value}")
        print(f"      Progress: {progress['progress_percentage']:.1f}%")
        print(f"      Steps: {progress['completed_steps']}/{progress['total_steps']}")
        
        if progress.get('estimated_remaining_time'):
            print(f"      Est. remaining: {progress['estimated_remaining_time']/60:.1f} min")
        
        # Show current/next step
        next_step = planner.get_next_executable_step(plan.id)
        if next_step:
            print(f"      Next: {next_step.description}")


async def show_safety_status(orchestrator: AgentOrchestrator):
    """Show safety status"""
    safety = orchestrator.safety_enforcer
    summary = safety.validator.get_safety_summary()
    
    print(f"\n🛡️ Safety Status:")
    print(f"   Path validation: {'✅' if summary['path_validation_enabled'] else '❌'}")
    print(f"   Command validation: {'✅' if summary['command_validation_enabled'] else '❌'}")  
    print(f"   Content scanning: {'✅' if summary['content_scanning_enabled'] else '❌'}")
    print(f"   Max file size: {summary['max_file_size_mb']}MB")
    print(f"   Restricted paths: {summary['restricted_paths_count']}")
    print(f"   Dangerous commands: {summary['dangerous_commands_count']}")
    
    # Show recent violations
    violations = safety.get_violation_history()
    if violations:
        recent_violations = violations[-5:]  # Last 5
        print(f"\n⚠️ Recent Violations ({len(violations)} total):")
        for v in recent_violations:
            print(f"   - {v.type}: {v.message} ({v.severity})")
    else:
        print(f"\n✅ No safety violations recorded")


async def show_model_info(orchestrator: AgentOrchestrator):
    """Show available models and their capabilities"""
    router = orchestrator.model_router
    models_info = router.get_available_models_info()
    
    if not models_info:
        print("\n🤖 No model information available")
        return
    
    print(f"\n🤖 Available Models ({len(models_info)}):")
    
    # Group by type
    model_types = {}
    for model_name, info in models_info.items():
        model_type = info["type"]
        if model_type not in model_types:
            model_types[model_type] = []
        model_types[model_type].append((model_name, info))
    
    for model_type, models in model_types.items():
        print(f"\n   📋 {model_type.replace('_', ' ').title()}:")
        
        # Sort by reasoning score descending
        models.sort(key=lambda x: x[1]["reasoning_score"], reverse=True)
        
        for model_name, info in models:
            reasoning = info["reasoning_score"]
            speed = info["speed_score"]
            context = info["context_window"]
            specializations = ", ".join(info["specializations"][:3])  # First 3
            
            status = ""
            if info["avg_response_time"]:
                response_time = info["avg_response_time"]
                if response_time < 5:
                    status = "⚡ Fast"
                elif response_time < 15:
                    status = "⏱️ Normal"
                else:
                    status = "🐌 Slow"
                status += f" ({response_time}s avg)"
            
            print(f"      • {model_name}")
            print(f"        Reasoning: {reasoning}/10, Speed: {speed}/10, Context: {context:,}")
            print(f"        Specializations: {specializations}")
            if status:
                print(f"        Performance: {status}")


async def show_model_suggestion(orchestrator: AgentOrchestrator, task_description: str):
    """Show model recommendations for a specific task"""
    router = orchestrator.model_router
    recommendations = router.get_model_recommendations(task_description)
    
    complexity = recommendations["task_complexity"]
    primary_model = recommendations["primary_model"]
    should_chain = recommendations["should_chain"]
    task_type = recommendations["task_type"]
    
    print(f"\n🎯 Model Recommendations for: '{task_description}'")
    print(f"   Task complexity: {complexity}/10")
    print(f"   Task type: {task_type}")
    print(f"   Reasoning needed: {'✅' if recommendations['reasoning_needed'] else '❌'}")
    print(f"   Speed priority: {'✅' if recommendations['speed_priority'] else '❌'}")
    
    print(f"\n🤖 Recommended approach:")
    
    if should_chain:
        reasoning_model = recommendations.get("reasoning_model")
        fast_model = recommendations.get("fast_model")
        
        print(f"   📋 Model chaining recommended")
        print(f"   🧠 Reasoning phase: {reasoning_model or 'None available'}")
        print(f"   ⚡ Implementation phase: {fast_model or 'None available'}")
        print(f"   💡 The reasoning model will analyze your request, then the fast model will implement the solution")
    else:
        print(f"   🎯 Single model: {primary_model}")
        
        # Get model info
        models_info = router.get_available_models_info()
        if primary_model in models_info:
            info = models_info[primary_model]
            print(f"   📊 Model stats: Reasoning {info['reasoning_score']}/10, Speed {info['speed_score']}/10")
            print(f"   🔧 Best for: {', '.join(info['specializations'][:3])}")
    
    # Show alternative models
    available_models = list(router.get_available_models_info().keys())
    if len(available_models) > 1:
        print(f"\n💡 Alternative models:")
        for model in available_models[:3]:  # Show top 3 alternatives
            if model != primary_model:
                task_specific_rec = router.suggest_model_for_task_type(task_type)
                marker = "⭐" if model == task_specific_rec else "•"
                print(f"   {marker} {model}")


async def show_learning_info(orchestrator: AgentOrchestrator):
    """Show learning progress and user preferences"""
    learning_summary = orchestrator.get_learning_summary()
    preferences = orchestrator.get_user_preferences()
    metrics = orchestrator.get_performance_metrics()
    
    print(f"\n🧠 Learning & Adaptation Status:")
    print(f"   Patterns learned: {learning_summary.get('patterns_learned', 0)}")
    print(f"   User preferences: {learning_summary.get('user_preferences', 0)}")
    print(f"   Recent interactions: {learning_summary.get('recent_interactions', 0)}")
    print(f"   Data path: {learning_summary.get('learning_data_path', 'Not set')}")
    
    if preferences:
        print(f"\n👤 User Preferences:")
        for key, value in preferences.items():
            print(f"   • {key.replace('_', ' ').title()}: {value}")
    else:
        print(f"\n👤 No user preferences learned yet")
    
    if metrics:
        print(f"\n📊 Performance Metrics:")
        for metric_name, metric_data in metrics.items():
            avg = metric_data.get('average', 0)
            trend = metric_data.get('trend', 'unknown')
            count = metric_data.get('count', 0)
            print(f"   • {metric_name}: {avg:.2f} avg ({trend}, {count} samples)")
    else:
        print(f"\n📊 No performance metrics recorded yet")
    
    top_patterns = learning_summary.get('top_patterns', [])
    if top_patterns:
        print(f"\n🔍 Top Learned Patterns:")
        for i, pattern in enumerate(top_patterns[:3], 1):
            pattern_type = pattern.get('type', 'unknown').replace('_', ' ').title()
            confidence = pattern.get('confidence', 0)
            usage = pattern.get('usage', 0)
            success_rate = pattern.get('success_rate', 0)
            print(f"   {i}. {pattern_type} (confidence: {confidence:.2f}, used: {usage}x, success: {success_rate:.1%})")


async def batch_mode(orchestrator: AgentOrchestrator, commands: list[str]):
    """Run batch commands"""
    
    print(f"🚀 Running {len(commands)} commands in batch mode")
    
    for i, command in enumerate(commands, 1):
        print(f"\n[{i}/{len(commands)}] Executing: {command}")
        print("-" * 40)
        
        try:
            response = await orchestrator.process_request(command)
            print(f"Response: {response}")
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description="Open Source Coding Agent")
    parser.add_argument(
        "--batch", 
        nargs="+", 
        help="Run commands in batch mode"
    )
    parser.add_argument(
        "--project-path",
        type=str,
        default=".",
        help="Project directory path (default: current directory)"
    )
    
    args = parser.parse_args()
    
    # Change to project directory
    if args.project_path != ".":
        if not Path(args.project_path).exists():
            print(f"❌ Error: Project path does not exist: {args.project_path}")
            exit(1)
        os.chdir(args.project_path)
    
    print(f"📁 Working directory: {os.getcwd()}")
    
    async def run():
        orchestrator = await create_agent()
        
        if args.batch:
            await batch_mode(orchestrator, args.batch)
        else:
            await interactive_mode(orchestrator)
    
    # Run the async main function
    asyncio.run(run())


if __name__ == "__main__":
    main()