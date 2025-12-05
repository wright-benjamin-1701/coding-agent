"""Prompt enhancement system for adding business context and extensibility guidance."""

import re
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from .types import Context


class PromptEnhancer:
    """Enhances user prompts with business context and extensibility considerations."""
    
    def __init__(self, rag_db=None, cache_service=None, file_indexer=None):
        self.rag_db = rag_db
        self.cache_service = cache_service
        self.file_indexer = file_indexer
        self.business_patterns = self._load_business_patterns()
        self.extensibility_patterns = self._load_extensibility_patterns()
        self.enhancement_templates = self._load_enhancement_templates()
    
    def _load_business_patterns(self) -> Dict[str, List[str]]:
        """Load patterns that indicate business use cases."""
        return {
            'data_analysis': [
                'analyze', 'report', 'dashboard', 'metrics', 'kpi', 'performance',
                'insights', 'trends', 'statistics', 'visualization', 'chart'
            ],
            'development': [
                'build', 'create', 'implement', 'develop', 'code', 'function',
                'class', 'api', 'service', 'module', 'component'
            ],
            'automation': [
                'automate', 'script', 'batch', 'process', 'workflow', 'pipeline',
                'schedule', 'trigger', 'monitor'
            ],
            'testing': [
                'test', 'validate', 'verify', 'check', 'quality', 'coverage',
                'unit test', 'integration', 'mock'
            ],
            'deployment': [
                'deploy', 'production', 'release', 'publish', 'distribute',
                'configuration', 'environment', 'docker', 'container'
            ],
            'maintenance': [
                'refactor', 'optimize', 'improve', 'fix', 'debug', 'performance',
                'security', 'update', 'migrate'
            ]
        }
    
    def _load_extensibility_patterns(self) -> List[str]:
        """Load patterns that suggest need for extensibility."""
        return [
            'plugin', 'extension', 'modular', 'flexible', 'configurable',
            'customizable', 'scalable', 'reusable', 'generic', 'template',
            'framework', 'library', 'interface', 'abstract', 'base class'
        ]
    
    def _load_enhancement_templates(self) -> Dict[str, str]:
        """Load enhancement templates for different contexts."""
        return {
            'business_data_analysis': """
Consider business requirements:
- Ensure outputs are stakeholder-friendly and actionable
- Include executive summary and key metrics
- Focus on business impact and ROI implications
- Make visualizations presentation-ready
- Consider regulatory and compliance requirements""",
            
            'business_development': """
Consider business requirements:
- Follow enterprise coding standards and best practices
- Include comprehensive error handling and logging
- Design for maintainability and team collaboration
- Consider security implications and data protection
- Document for non-technical stakeholders""",
            
            'business_automation': """
Consider business requirements:
- Design for reliability and fault tolerance
- Include monitoring and alerting capabilities
- Consider business continuity and disaster recovery
- Make processes auditable and compliant
- Design for different user roles and permissions""",
            
            'extensible_architecture': """
Consider extensibility requirements:
- Design modular, loosely-coupled components
- Use interfaces and dependency injection
- Follow SOLID principles and design patterns
- Create plugin/extension points for future needs
- Include comprehensive configuration options
- Design for easy testing and mocking""",
            
            'extensible_data': """
Consider extensibility requirements:
- Design schema that can evolve over time
- Create flexible data pipelines and transformations
- Support multiple data sources and formats
- Include versioning and migration strategies
- Design for different deployment environments""",
            
            'extensible_ui': """
Consider extensibility requirements:
- Create reusable, composable components
- Support theming and customization
- Design responsive, accessible interfaces
- Include internationalization support
- Create extension points for custom features"""
        }
    
    def enhance_prompt(self, user_prompt: str, context: Context) -> str:
        """Enhance user prompt with business context and extensibility guidance."""
        if not user_prompt or not user_prompt.strip():
            return user_prompt
        
        # Detect business context
        business_context = self._detect_business_context(user_prompt)
        
        # Detect extensibility needs  
        needs_extensibility = self._detect_extensibility_needs(user_prompt, context)
        
        # Analyze codebase for RAG-based architecture considerations
        architecture_considerations = self._get_architecture_considerations(user_prompt, context)
        
        # Build enhancement
        enhancements = []
        
        # Add business context enhancements
        if business_context:
            for context_type in business_context:
                enhancement_key = f"business_{context_type}"
                if enhancement_key in self.enhancement_templates:
                    enhancements.append(self.enhancement_templates[enhancement_key])
        
        # Add extensibility enhancements
        if needs_extensibility:
            extensibility_type = self._determine_extensibility_type(user_prompt)
            enhancement_key = f"extensible_{extensibility_type}"
            if enhancement_key in self.enhancement_templates:
                enhancements.append(self.enhancement_templates[enhancement_key])
        
        # Add RAG-based architecture considerations
        if architecture_considerations:
            enhancements.append(architecture_considerations)
        
        # Combine original prompt with enhancements
        if enhancements:
            enhanced_prompt = f"{user_prompt}\n\n" + "\n\n".join(enhancements)
            return enhanced_prompt
        
        return user_prompt
    
    def _detect_business_context(self, user_prompt: str) -> List[str]:
        """Detect business context indicators in the prompt."""
        prompt_lower = user_prompt.lower()
        detected_contexts = []
        
        for context_type, patterns in self.business_patterns.items():
            if any(pattern in prompt_lower for pattern in patterns):
                detected_contexts.append(context_type)
        
        return detected_contexts
    
    def _detect_extensibility_needs(self, user_prompt: str, context: Context) -> bool:
        """Detect if the request would benefit from extensibility considerations."""
        prompt_lower = user_prompt.lower()
        
        # Check for explicit extensibility keywords
        if any(pattern in prompt_lower for pattern in self.extensibility_patterns):
            return True
        
        # Check for complex development requests
        complex_indicators = [
            'system', 'platform', 'framework', 'architecture', 'enterprise',
            'multi-', 'large scale', 'production', 'team', 'organization'
        ]
        
        if any(indicator in prompt_lower for indicator in complex_indicators):
            return True
        
        # Check context for indicators
        if context.modified_files and len(context.modified_files) > 5:
            return True  # Large changes suggest need for extensibility
        
        # Check for file types that suggest system-level work
        if context.modified_files:
            system_files = [f for f in context.modified_files 
                          if any(ext in f.lower() for ext in ['.config', '.json', '.yaml', '.toml', 'setup.py', 'requirements.txt'])]
            if system_files:
                return True
        
        return False
    
    def _determine_extensibility_type(self, user_prompt: str) -> str:
        """Determine the type of extensibility enhancement needed."""
        prompt_lower = user_prompt.lower()
        
        # Data-related extensibility
        if any(keyword in prompt_lower for keyword in ['data', 'database', 'analytics', 'etl', 'pipeline']):
            return 'data'
        
        # UI-related extensibility
        if any(keyword in prompt_lower for keyword in ['ui', 'interface', 'frontend', 'web', 'component', 'react', 'vue']):
            return 'ui'
        
        # Default to architecture extensibility
        return 'architecture'
    
    def get_enhancement_summary(self, original_prompt: str, enhanced_prompt: str) -> str:
        """Get a summary of the enhancements made."""
        if original_prompt == enhanced_prompt:
            return "No enhancements applied"
        
        enhancement_length = len(enhanced_prompt) - len(original_prompt)
        
        # Count enhancement types
        business_enhancements = enhanced_prompt.count("Consider business requirements:")
        extensibility_enhancements = enhanced_prompt.count("Consider extensibility requirements:")
        architecture_enhancements = enhanced_prompt.count("Consider architecture requirements based on your codebase:")
        
        summary_parts = []
        if business_enhancements > 0:
            summary_parts.append(f"{business_enhancements} business context enhancement(s)")
        if extensibility_enhancements > 0:
            summary_parts.append(f"{extensibility_enhancements} extensibility enhancement(s)")
        if architecture_enhancements > 0:
            summary_parts.append(f"{architecture_enhancements} architecture enhancement(s)")
        
        return f"Enhanced prompt with {', '.join(summary_parts)} (+{enhancement_length} characters)"
    
    def _get_architecture_considerations(self, user_prompt: str, context: Context) -> Optional[str]:
        """Generate architecture considerations based on RAG knowledge of the codebase."""
        # Always try to provide architecture considerations based on available information
        # Even without RAG DB or file indexer, we can analyze the filesystem
        
        try:
            # Analyze current project structure
            project_analysis = self._analyze_project_structure()
            
            # Get relevant historical context
            historical_context = self._get_historical_context(user_prompt, context)
            
            # Detect existing patterns and frameworks
            existing_patterns = self._detect_existing_patterns()
            
            # Generate architecture-specific guidance
            guidance = self._generate_architecture_guidance(
                user_prompt, project_analysis, historical_context, existing_patterns
            )
            
            # Only return guidance if it has meaningful content beyond the header
            if guidance and len(guidance.split('\n')) > 1:
                return guidance
            return None
            
        except Exception as e:
            # Don't fail the enhancement if RAG analysis fails
            return None
    
    def _analyze_project_structure(self) -> Dict[str, Any]:
        """Analyze the project structure from file indexer or filesystem."""
        analysis = {
            'languages': set(),
            'frameworks': set(), 
            'patterns': set(),
            'file_structure': {},
            'dependencies': set()
        }
        
        try:
            # Use file indexer if available
            if self.file_indexer and hasattr(self.file_indexer, 'index'):
                index = self.file_indexer.index
                for file_path, file_info in index.items():
                    # Detect languages
                    ext = Path(file_path).suffix.lower()
                    if ext == '.py':
                        analysis['languages'].add('Python')
                    elif ext in ['.js', '.jsx']:
                        analysis['languages'].add('JavaScript')
                    elif ext in ['.ts', '.tsx']:
                        analysis['languages'].add('TypeScript')
                    elif ext == '.java':
                        analysis['languages'].add('Java')
                    elif ext in ['.cs']:
                        analysis['languages'].add('C#')
                    elif ext in ['.go']:
                        analysis['languages'].add('Go')
            else:
                # Fallback to filesystem analysis
                analysis = self._analyze_filesystem()
                
            # Detect frameworks and patterns
            analysis.update(self._detect_frameworks_and_patterns(analysis))
            
        except Exception:
            pass  # Return basic analysis if detailed analysis fails
            
        return analysis
    
    def _analyze_filesystem(self) -> Dict[str, Any]:
        """Analyze filesystem when file indexer is not available."""
        analysis = {
            'languages': set(),
            'frameworks': set(),
            'patterns': set(), 
            'file_structure': {},
            'dependencies': set()
        }
        
        try:
            # Get current working directory files
            for root, dirs, files in os.walk('.'):
                # Skip common ignored directories
                dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.env']]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    ext = Path(file).suffix.lower()
                    
                    # Detect languages
                    if ext == '.py':
                        analysis['languages'].add('Python')
                    elif ext in ['.js', '.jsx']:
                        analysis['languages'].add('JavaScript')
                    elif ext in ['.ts', '.tsx']:
                        analysis['languages'].add('TypeScript')
                    elif ext == '.java':
                        analysis['languages'].add('Java')
                    
                    # Check for specific files
                    if file in ['package.json', 'requirements.txt', 'Pipfile', 'pyproject.toml']:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                analysis['dependencies'].update(self._extract_dependencies(file, content))
                        except Exception:
                            continue
                            
        except Exception:
            pass
            
        return analysis
    
    def _detect_frameworks_and_patterns(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Detect frameworks and architectural patterns from project analysis."""
        frameworks = set()
        patterns = set()
        
        # Framework detection based on dependencies
        deps = ' '.join(analysis.get('dependencies', []))
        
        if 'react' in deps.lower():
            frameworks.add('React')
        if 'vue' in deps.lower():
            frameworks.add('Vue')
        if 'angular' in deps.lower():
            frameworks.add('Angular')
        if 'express' in deps.lower():
            frameworks.add('Express')
        if 'flask' in deps.lower():
            frameworks.add('Flask')
        if 'django' in deps.lower():
            frameworks.add('Django')
        if 'fastapi' in deps.lower():
            frameworks.add('FastAPI')
        if 'spring' in deps.lower():
            frameworks.add('Spring')
        
        # Pattern detection based on project structure and files
        if 'Python' in analysis.get('languages', []):
            if any('test' in dep for dep in analysis.get('dependencies', [])):
                patterns.add('Test-Driven Development')
        
        # Directory structure patterns
        try:
            if os.path.exists('src') or os.path.exists('lib'):
                patterns.add('Source Organization')
            if os.path.exists('tests') or os.path.exists('test'):
                patterns.add('Test Structure')
            if os.path.exists('docs'):
                patterns.add('Documentation')
            if os.path.exists('config') or os.path.exists('configs'):
                patterns.add('Configuration Management')
        except Exception:
            pass
        
        return {
            'frameworks': frameworks,
            'patterns': patterns
        }
    
    def _extract_dependencies(self, filename: str, content: str) -> List[str]:
        """Extract dependencies from package files."""
        deps = []
        try:
            if filename == 'package.json':
                import json
                data = json.loads(content)
                deps.extend(data.get('dependencies', {}).keys())
                deps.extend(data.get('devDependencies', {}).keys())
            elif filename == 'requirements.txt':
                for line in content.split('\n'):
                    if line.strip() and not line.strip().startswith('#'):
                        dep = line.strip().split('==')[0].split('>=')[0].split('<=')[0]
                        deps.append(dep)
            elif filename in ['Pipfile', 'pyproject.toml']:
                # Basic extraction for Python files
                for line in content.split('\n'):
                    if '=' in line and not line.strip().startswith('#'):
                        parts = line.split('=')
                        if len(parts) >= 2:
                            dep = parts[0].strip().strip('"\'')
                            if dep and not dep.startswith('['):
                                deps.append(dep)
        except Exception:
            pass
        return deps
    
    def _get_historical_context(self, user_prompt: str, context: Context) -> Dict[str, Any]:
        """Get relevant historical context from RAG database."""
        if not self.rag_db:
            return {}
        
        try:
            # Get recent summaries related to architecture or development
            relevant_summaries = []
            for summary in context.recent_summaries:
                if any(keyword in summary.lower() for keyword in [
                    'architecture', 'design', 'pattern', 'framework', 'structure',
                    'refactor', 'implement', 'create', 'build'
                ]):
                    relevant_summaries.append(summary)
            
            return {
                'relevant_summaries': relevant_summaries[-3:],  # Last 3 relevant summaries
                'modified_files': context.modified_files
            }
            
        except Exception:
            return {}
    
    def _detect_existing_patterns(self) -> List[str]:
        """Detect existing architectural patterns in the codebase."""
        patterns = []
        
        try:
            # Check for common architectural patterns
            if os.path.exists('src'):
                # Check for MVC pattern
                mvc_dirs = ['models', 'views', 'controllers', 'model', 'view', 'controller']
                if any(os.path.exists(os.path.join('src', d)) for d in mvc_dirs):
                    patterns.append('MVC Architecture')
                
                # Check for layered architecture
                layer_dirs = ['api', 'services', 'repositories', 'data', 'business', 'presentation']
                if any(os.path.exists(os.path.join('src', d)) for d in layer_dirs):
                    patterns.append('Layered Architecture')
                
                # Check for microservices indicators
                if os.path.exists('docker-compose.yml') or os.path.exists('Dockerfile'):
                    patterns.append('Containerized Services')
            
            # Check for configuration patterns
            config_files = ['config.json', '.env', 'settings.py', 'application.properties']
            if any(os.path.exists(f) for f in config_files):
                patterns.append('Configuration-Based Design')
                
        except Exception:
            pass
            
        return patterns
    
    def _generate_architecture_guidance(self, user_prompt: str, project_analysis: Dict[str, Any], 
                                      historical_context: Dict[str, Any], existing_patterns: List[str]) -> str:
        """Generate architecture-specific guidance based on project analysis."""
        guidance_parts = ["Consider architecture requirements based on your codebase:"]
        
        # Language-specific guidance
        languages = project_analysis.get('languages', set())
        if languages:
            guidance_parts.append(f"- Language stack: {', '.join(languages)}")
            
            # Python-specific guidance
            if 'Python' in languages:
                guidance_parts.append("- Follow Python conventions: PEP 8, type hints, docstrings")
                if 'Django' in project_analysis.get('frameworks', set()):
                    guidance_parts.append("- Django patterns: MVT architecture, model relationships, admin integration")
                elif 'Flask' in project_analysis.get('frameworks', set()):
                    guidance_parts.append("- Flask patterns: blueprint organization, factory pattern, configuration management")
            
            # JavaScript/TypeScript guidance  
            if 'JavaScript' in languages or 'TypeScript' in languages:
                guidance_parts.append("- Follow modern JS/TS practices: ES6+, proper async/await, error handling")
                if 'React' in project_analysis.get('frameworks', set()):
                    guidance_parts.append("- React patterns: component composition, hooks, state management, performance optimization")
                elif 'Vue' in project_analysis.get('frameworks', set()):
                    guidance_parts.append("- Vue patterns: component structure, reactivity, Vuex/Pinia for state management")
        
        # Framework-specific guidance
        frameworks = project_analysis.get('frameworks', set())
        if frameworks:
            guidance_parts.append(f"- Detected frameworks: {', '.join(frameworks)}")
            guidance_parts.append("- Follow framework conventions and best practices")
        
        # Existing patterns guidance
        if existing_patterns:
            guidance_parts.append(f"- Existing architectural patterns: {', '.join(existing_patterns)}")
            guidance_parts.append("- Maintain consistency with established patterns")
        
        # Historical context guidance
        if historical_context.get('relevant_summaries'):
            guidance_parts.append("- Recent architectural decisions:")
            for summary in historical_context['relevant_summaries']:
                # Extract key points from summary
                summary_short = summary[:100] + "..." if len(summary) > 100 else summary
                guidance_parts.append(f"  • {summary_short}")
        
        # Modified files guidance
        if historical_context.get('modified_files'):
            guidance_parts.append(f"- Consider impact on modified files: {', '.join(historical_context['modified_files'][:5])}")
        
        # Request-specific guidance
        prompt_lower = user_prompt.lower()
        if 'database' in prompt_lower or 'data' in prompt_lower:
            guidance_parts.append("- Database considerations: migrations, relationships, indexing, caching")
        if 'api' in prompt_lower:
            guidance_parts.append("- API considerations: versioning, authentication, rate limiting, documentation")
        if 'test' in prompt_lower:
            guidance_parts.append("- Testing considerations: unit/integration/e2e tests, mocking, coverage")
        if 'security' in prompt_lower:
            guidance_parts.append("- Security considerations: input validation, authentication, authorization, encryption")
        
        return "\n".join(guidance_parts)


class PromptEnhancementConfig:
    """Configuration for prompt enhancement behavior."""
    
    def __init__(self, 
                 enabled: bool = True,
                 business_context: bool = True,
                 extensibility_context: bool = True,
                 show_enhancements: bool = False):
        self.enabled = enabled
        self.business_context = business_context  
        self.extensibility_context = extensibility_context
        self.show_enhancements = show_enhancements  # Whether to show enhancement summary