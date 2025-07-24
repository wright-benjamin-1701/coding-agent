"""
Intelligent model routing and chaining system
"""
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .config import ConfigManager, get_config
from .providers.base import BaseLLMProvider, ChatMessage, ModelConfig


class ModelType(Enum):
    REASONING = "reasoning"
    FAST_COMPLETION = "fast_completion"
    CHAT = "chat"
    ANALYSIS = "analysis"
    CODE_GENERATION = "code_generation"


@dataclass
class ModelCapability:
    model_name: str
    type: ModelType
    reasoning_score: int  # 1-10, higher is better for complex reasoning
    speed_score: int      # 1-10, higher is faster
    context_window: int
    specializations: List[str]  # e.g., ["python", "javascript", "debugging"]


@dataclass
class TaskComplexity:
    complexity_score: int  # 1-10, higher is more complex
    requires_reasoning: bool
    requires_speed: bool
    estimated_tokens: int
    task_type: str
    context_needs: List[str]


class ModelRouter:
    """Routes requests to optimal models and manages model chaining"""
    
    def __init__(self, provider: BaseLLMProvider, config: Optional[ConfigManager] = None):
        self.provider = provider
        self.config = config or get_config()
        self.model_capabilities = self._initialize_model_capabilities()
        self.performance_history: Dict[str, List[float]] = {}
        self.model_chain_cache: Dict[str, Any] = {}
    
    def _initialize_model_capabilities(self) -> Dict[str, ModelCapability]:
        """Initialize model capabilities based on available models"""
        
        available_models = self.provider.list_models()
        capabilities = {}
        
        for model in available_models:
            model_lower = model.lower()
            
            # Determine model type and capabilities
            if any(term in model_lower for term in ["coder", "code"]):
                if "32b" in model_lower or "33b" in model_lower:
                    capabilities[model] = ModelCapability(
                        model_name=model,
                        type=ModelType.REASONING,
                        reasoning_score=9,
                        speed_score=4,
                        context_window=32768,
                        specializations=["python", "javascript", "debugging", "refactoring"]
                    )
                elif "14b" in model_lower:
                    capabilities[model] = ModelCapability(
                        model_name=model,
                        type=ModelType.ANALYSIS,
                        reasoning_score=8,
                        speed_score=6,
                        context_window=16384,
                        specializations=["python", "javascript", "analysis"]
                    )
                elif "7b" in model_lower:
                    capabilities[model] = ModelCapability(
                        model_name=model,
                        type=ModelType.FAST_COMPLETION,
                        reasoning_score=7,
                        speed_score=8,
                        context_window=8192,
                        specializations=["python", "javascript", "quick_tasks"]
                    )
                elif "1.5b" in model_lower or "2b" in model_lower:
                    capabilities[model] = ModelCapability(
                        model_name=model,
                        type=ModelType.FAST_COMPLETION,
                        reasoning_score=5,
                        speed_score=10,
                        context_window=4096,
                        specializations=["simple_tasks", "quick_responses"]
                    )
            
            elif "llama" in model_lower:
                if "70b" in model_lower or "72b" in model_lower:
                    capabilities[model] = ModelCapability(
                        model_name=model,
                        type=ModelType.REASONING,
                        reasoning_score=9,
                        speed_score=3,
                        context_window=32768,
                        specializations=["reasoning", "analysis", "complex_tasks"]
                    )
                elif any(size in model_lower for size in ["8b", "7b"]):
                    capabilities[model] = ModelCapability(
                        model_name=model,
                        type=ModelType.CHAT,
                        reasoning_score=6,
                        speed_score=7,
                        context_window=8192,
                        specializations=["conversation", "general_tasks"]
                    )
            
            elif "deepseek" in model_lower:
                capabilities[model] = ModelCapability(
                    model_name=model,
                    type=ModelType.CODE_GENERATION,
                    reasoning_score=8,
                    speed_score=6,
                    context_window=16384,
                    specializations=["code_generation", "debugging", "optimization"]
                )
            
            else:
                # Default capabilities for unknown models
                capabilities[model] = ModelCapability(
                    model_name=model,
                    type=ModelType.CHAT,
                    reasoning_score=6,
                    speed_score=6,
                    context_window=4096,
                    specializations=["general"]
                )
        
        return capabilities
    
    def analyze_task_complexity(self, user_input: str, context: Dict[str, Any]) -> TaskComplexity:
        """Analyze task to determine complexity and requirements"""
        
        input_lower = user_input.lower()
        estimated_tokens = len(user_input.split()) * 4  # Rough estimate
        
        # Base complexity scoring
        complexity_score = 5
        requires_reasoning = False
        requires_speed = False
        task_type = "general"
        context_needs = []
        
        # High complexity indicators
        high_complexity_terms = [
            "refactor", "analyze", "debug", "optimize", "implement", "design",
            "architecture", "complex", "multiple", "across", "entire", "system"
        ]
        
        # Fast completion indicators  
        fast_completion_terms = [
            "show", "list", "display", "status", "quick", "simple", "what is",
            "help", "summary"
        ]
        
        # Reasoning indicators
        reasoning_terms = [
            "why", "how", "explain", "analyze", "compare", "evaluate", "decide",
            "recommend", "strategy", "approach", "best", "optimize"
        ]
        
        # Code generation indicators
        code_generation_terms = [
            "write", "create", "generate", "implement", "build", "develop",
            "function", "class", "method"
        ]
        
        # Adjust complexity based on terms
        if any(term in input_lower for term in high_complexity_terms):
            complexity_score += 3
            requires_reasoning = True
            task_type = "complex_analysis"
        
        if any(term in input_lower for term in reasoning_terms):
            complexity_score += 2
            requires_reasoning = True
            task_type = "reasoning"
        
        if any(term in input_lower for term in fast_completion_terms):
            complexity_score -= 2
            requires_speed = True
            task_type = "quick_response"
        
        if any(term in input_lower for term in code_generation_terms):
            complexity_score += 1
            task_type = "code_generation"
            context_needs.append("code_context")
        
        # Adjust based on context
        if context.get("project_context"):
            estimated_tokens += 1000  # Additional context
            context_needs.append("project_understanding")
        
        if context.get("conversation_history"):
            history_length = len(context["conversation_history"])
            if history_length > 10:
                complexity_score += 1
                context_needs.append("conversation_continuity")
        
        # Clamp complexity score
        complexity_score = max(1, min(10, complexity_score))
        
        return TaskComplexity(
            complexity_score=complexity_score,
            requires_reasoning=requires_reasoning,
            requires_speed=requires_speed,
            estimated_tokens=estimated_tokens,
            task_type=task_type,
            context_needs=context_needs
        )
    
    def select_optimal_model(self, task_complexity: TaskComplexity) -> Tuple[str, bool]:
        """Select optimal model for task, returns (model_name, should_chain)"""
        
        if not self.model_capabilities:
            available_models = self.provider.list_models()
            return available_models[0] if available_models else "default", False
        
        # Score each model for this task
        model_scores = {}
        
        for model_name, capability in self.model_capabilities.items():
            score = 0
            
            # Base scoring
            if task_complexity.requires_reasoning:
                score += capability.reasoning_score * 2
            
            if task_complexity.requires_speed:
                score += capability.speed_score * 2
            
            # Complexity matching
            if task_complexity.complexity_score >= 8:
                # High complexity - prefer reasoning models
                if capability.type == ModelType.REASONING:
                    score += 5
                elif capability.reasoning_score >= 8:
                    score += 3
            elif task_complexity.complexity_score <= 3:
                # Low complexity - prefer fast models
                if capability.type == ModelType.FAST_COMPLETION:
                    score += 5
                elif capability.speed_score >= 8:
                    score += 3
            else:
                # Medium complexity - balanced approach
                score += (capability.reasoning_score + capability.speed_score) / 2
            
            # Task type matching
            if task_complexity.task_type == "code_generation":
                if capability.type == ModelType.CODE_GENERATION:
                    score += 4
                elif "python" in capability.specializations:
                    score += 2
            
            # Context window requirements
            if task_complexity.estimated_tokens > capability.context_window:
                score -= 10  # Heavy penalty for insufficient context
            
            # Performance history adjustment
            if model_name in self.performance_history:
                avg_response_time = sum(self.performance_history[model_name]) / len(self.performance_history[model_name])
                if avg_response_time < 5.0:  # Fast responses
                    score += 1
                elif avg_response_time > 15.0:  # Slow responses
                    score -= 1
            
            model_scores[model_name] = score
        
        # Select best model
        best_model = max(model_scores.items(), key=lambda x: x[1])
        best_model_name = best_model[0]
        best_score = best_model[1]
        
        # Determine if we should chain models
        should_chain = self._should_chain_models(task_complexity, best_model_name)
        
        return best_model_name, should_chain
    
    def _should_chain_models(self, task_complexity: TaskComplexity, selected_model: str) -> bool:
        """Determine if we should chain models for better performance"""
        
        if selected_model not in self.model_capabilities:
            return False
        
        # Check if we have enough models for chaining
        available_models = self.provider.list_models()
        if len(available_models) < 2:
            return False  # Can't chain with only one model
        
        # Check if we have both reasoning and fast models available
        reasoning_model = self._get_best_reasoning_model()
        fast_model = self._get_best_fast_model()
        
        if not reasoning_model or not fast_model or reasoning_model == fast_model:
            return False  # Can't chain effectively
        
        selected_capability = self.model_capabilities[selected_model]
        
        # Chain if:
        # 1. High complexity task but selected a fast model
        # 2. Task requires both reasoning and speed
        # 3. Task has multiple phases (analysis + generation)
        
        if (task_complexity.complexity_score >= 7 and 
            selected_capability.reasoning_score < 7):
            return True
        
        if (task_complexity.requires_reasoning and 
            task_complexity.requires_speed and
            selected_capability.type == ModelType.FAST_COMPLETION):
            return True
        
        if task_complexity.task_type in ["complex_analysis", "code_generation"] and len(task_complexity.context_needs) > 2:
            return True
        
        return False
    
    async def execute_with_routing(
        self, 
        messages: List[ChatMessage], 
        task_complexity: TaskComplexity,
        model_config: Optional[ModelConfig] = None
    ) -> str:
        """Execute request with intelligent model routing"""
        
        # Check available models
        available_models = self.provider.list_models()
        if not available_models:
            raise Exception("No models available. Please ensure Ollama is running with at least one model loaded.")
        
        # Select optimal model
        selected_model, should_chain = self.select_optimal_model(task_complexity)
        
        # Log model selection for user awareness
        if len(available_models) == 1:
            print(f"🤖 Using single model: {selected_model}")
        elif should_chain:
            reasoning_model = self._get_best_reasoning_model()
            fast_model = self._get_best_fast_model()
            print(f"🔗 Chaining models: {reasoning_model} → {fast_model}")
        else:
            print(f"🎯 Selected model: {selected_model}")
        
        if not should_chain:
            # Simple single-model execution
            return await self._execute_single_model(messages, selected_model, model_config)
        else:
            # Chain models for optimal performance
            return await self._execute_model_chain(messages, task_complexity, model_config)
    
    async def _execute_single_model(
        self, 
        messages: List[ChatMessage], 
        model_name: str,
        model_config: Optional[ModelConfig] = None
    ) -> str:
        """Execute with single model"""
        
        start_time = time.time()
        
        # Use provided config or create default
        if not model_config:
            model_config = ModelConfig(model_name=model_name)
        else:
            model_config.model_name = model_name
        
        try:
            response = await self.provider.chat_completion(messages, model_config)
            
            # Record performance
            response_time = time.time() - start_time
            self._record_performance(model_name, response_time)
            
            return response.content
        
        except Exception as e:
            # Fallback to any available model
            available_models = self.provider.list_models()
            if available_models and model_name != available_models[0]:
                fallback_config = ModelConfig(model_name=available_models[0])
                response = await self.provider.chat_completion(messages, fallback_config)
                return f"⚠️ Fallback model used due to error: {str(e)}\n\n{response.content}"
            else:
                raise e
    
    async def _execute_model_chain(
        self, 
        messages: List[ChatMessage], 
        task_complexity: TaskComplexity,
        model_config: Optional[ModelConfig] = None
    ) -> str:
        """Execute with model chaining for optimal performance"""
        
        # Phase 1: Use reasoning model for analysis/planning
        reasoning_model = self._get_best_reasoning_model()
        
        if reasoning_model:
            # Create analysis prompt
            analysis_messages = messages + [
                ChatMessage(
                    role="system", 
                    content=f"""You are the reasoning phase of a multi-model system. 
                    Analyze this request and provide:
                    1. Key insights and approach
                    2. Specific requirements 
                    3. Implementation steps if applicable
                    4. Any code generation needs
                    
                    Task complexity: {task_complexity.complexity_score}/10
                    Task type: {task_complexity.task_type}
                    
                    Be concise but thorough. Your analysis will guide the next model."""
                )
            ]
            
            try:
                reasoning_config = ModelConfig(model_name=reasoning_model)
                reasoning_response = await self.provider.chat_completion(analysis_messages, reasoning_config)
                
                # Phase 2: Use fast completion model for implementation
                fast_model = self._get_best_fast_model()
                
                if fast_model and fast_model != reasoning_model and task_complexity.task_type in ["code_generation", "quick_response"]:
                    try:
                        # Create implementation prompt  
                        implementation_messages = [
                            ChatMessage(role="system", content="You are the implementation phase. Use the analysis below to provide a fast, accurate response."),
                            ChatMessage(role="assistant", content=f"Analysis: {reasoning_response.content}"),
                            messages[-1]  # Original user request
                        ]
                        
                        fast_config = ModelConfig(model_name=fast_model)
                        implementation_response = await self.provider.chat_completion(implementation_messages, fast_config)
                        
                        return f"🧠 **Analysis:** {reasoning_response.content}\n\n⚡ **Implementation:** {implementation_response.content}"
                    except Exception as e:
                        # If fast model fails, just return reasoning response
                        print(f"⚠️ Fast model {fast_model} failed, using reasoning model result only")
                        return f"🧠 **Analysis:** {reasoning_response.content}"
                else:
                    return reasoning_response.content
            
            except Exception as e:
                # If reasoning model fails, fallback to single model with any available model
                print(f"⚠️ Reasoning model {reasoning_model} failed, falling back to single model")
                available_models = self.provider.list_models()
                if available_models:
                    return await self._execute_single_model(messages, available_models[0], model_config)
                else:
                    raise Exception("No models available for fallback")
        else:
            # Fallback to single model
            return await self._execute_single_model(messages, self.provider.list_models()[0], model_config)
    
    def _get_best_reasoning_model(self) -> Optional[str]:
        """Get the best available reasoning model"""
        reasoning_models = [
            (name, cap) for name, cap in self.model_capabilities.items()
            if cap.type == ModelType.REASONING or cap.reasoning_score >= 8
        ]
        
        if reasoning_models:
            # Sort by reasoning score, then by speed as tiebreaker
            reasoning_models.sort(key=lambda x: (x[1].reasoning_score, x[1].speed_score), reverse=True)
            return reasoning_models[0][0]
        
        return None
    
    def _get_best_fast_model(self) -> Optional[str]:
        """Get the best available fast completion model"""
        fast_models = [
            (name, cap) for name, cap in self.model_capabilities.items()
            if cap.type == ModelType.FAST_COMPLETION or cap.speed_score >= 8
        ]
        
        if fast_models:
            # Sort by speed score, then by reasoning as tiebreaker  
            fast_models.sort(key=lambda x: (x[1].speed_score, x[1].reasoning_score), reverse=True)
            return fast_models[0][0]
        
        return None
    
    def _record_performance(self, model_name: str, response_time: float) -> None:
        """Record model performance for future routing decisions"""
        if model_name not in self.performance_history:
            self.performance_history[model_name] = []
        
        self.performance_history[model_name].append(response_time)
        
        # Keep only recent history (last 20 requests)
        if len(self.performance_history[model_name]) > 20:
            self.performance_history[model_name] = self.performance_history[model_name][-20:]
    
    def get_model_recommendations(self, task_description: str) -> Dict[str, Any]:
        """Get model recommendations for a given task"""
        
        task_complexity = self.analyze_task_complexity(task_description, {})
        selected_model, should_chain = self.select_optimal_model(task_complexity)
        
        recommendations = {
            "primary_model": selected_model,
            "should_chain": should_chain,
            "task_complexity": task_complexity.complexity_score,
            "reasoning_needed": task_complexity.requires_reasoning,
            "speed_priority": task_complexity.requires_speed,
            "task_type": task_complexity.task_type
        }
        
        if should_chain:
            recommendations["reasoning_model"] = self._get_best_reasoning_model()
            recommendations["fast_model"] = self._get_best_fast_model()
        
        return recommendations
    
    def get_available_models_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all available models"""
        
        models_info = {}
        
        for model_name, capability in self.model_capabilities.items():
            models_info[model_name] = {
                "type": capability.type.value,
                "reasoning_score": capability.reasoning_score,
                "speed_score": capability.speed_score,
                "context_window": capability.context_window,
                "specializations": capability.specializations,
                "avg_response_time": None
            }
            
            # Add performance data if available
            if model_name in self.performance_history:
                avg_time = sum(self.performance_history[model_name]) / len(self.performance_history[model_name])
                models_info[model_name]["avg_response_time"] = round(avg_time, 2)
        
        return models_info
    
    def suggest_model_for_task_type(self, task_type: str) -> Optional[str]:
        """Suggest best model for specific task type"""
        
        task_type_preferences = {
            "reasoning": ModelType.REASONING,
            "analysis": ModelType.ANALYSIS,
            "code_generation": ModelType.CODE_GENERATION,
            "fast_response": ModelType.FAST_COMPLETION,
            "chat": ModelType.CHAT
        }
        
        preferred_type = task_type_preferences.get(task_type)
        if not preferred_type:
            return None
        
        # Find best model of preferred type
        matching_models = [
            (name, cap) for name, cap in self.model_capabilities.items()
            if cap.type == preferred_type
        ]
        
        if matching_models:
            # Sort by combined score
            matching_models.sort(
                key=lambda x: x[1].reasoning_score + x[1].speed_score, 
                reverse=True
            )
            return matching_models[0][0]
        
        return None