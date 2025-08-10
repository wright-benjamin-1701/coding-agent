"""Project scaffolding tool for creating complete project structures."""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from .base import Tool
from ..types import ToolResult


class ProjectScaffoldingTool(Tool):
    """Tool for creating complete project scaffolds and structures."""
    
    @property
    def name(self) -> str:
        return "create_project"
    
    @property
    def description(self) -> str:
        return "Create complete project structures from templates (React, Vue, Node.js, Python, etc.)"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                    "enum": [
                        "vite-react-ts", "vite-react-js", "create-react-app-ts", "create-react-app-js",
                        "nextjs-ts", "nextjs-js", "vue-ts", "vue-js", 
                        "express-ts", "express-js", "fastapi-python", "flask-python",
                        "django-python", "nodejs-ts", "nodejs-js"
                    ],
                    "description": "Project template to use"
                },
                "path": {
                    "type": "string",
                    "description": "Directory path where the project should be created"
                },
                "directory": {
                    "type": "string", 
                    "description": "Directory path where the project should be created (alias for path)"
                },
                "project_name": {
                    "type": "string",
                    "description": "Project name (alias for name)"
                },
                "name": {
                    "type": "string",
                    "description": "Project name (defaults to directory name)"
                },
                "framework": {
                    "type": "string",
                    "description": "Framework for the project (legacy parameter - use template instead)",
                    "enum": ["react", "vue", "express", "fastapi", "flask", "django", "nodejs"]
                },
                "language": {
                    "type": "string", 
                    "description": "Programming language (legacy parameter - use template instead)",
                    "enum": ["javascript", "typescript", "python"]
                },
                "options": {
                    "type": "object",
                    "description": "Additional template options",
                    "properties": {
                        "with_router": {"type": "boolean", "description": "Include routing setup"},
                        "with_state_management": {"type": "boolean", "description": "Include state management (Redux, Zustand, etc.)"},
                        "with_testing": {"type": "boolean", "description": "Include testing setup"},
                        "with_linting": {"type": "boolean", "description": "Include ESLint/Prettier setup"},
                        "css_framework": {"type": "string", "enum": ["none", "tailwind", "bootstrap", "mui"], "description": "CSS framework to include"},
                        "database": {"type": "string", "enum": ["none", "sqlite", "postgres", "mongodb"], "description": "Database to configure"}
                    }
                }
            },
            "required": []
        }
    
    @property
    def is_destructive(self) -> bool:
        return False  # Creating new projects is not destructive
    
    def execute(self, **parameters) -> ToolResult:
        """Create a project scaffold."""
        template = parameters.get("template")
        
        # Handle path parameter aliases
        path = parameters.get("path") or parameters.get("directory")
        
        # Handle name parameter aliases  
        name = (parameters.get("name") or 
                parameters.get("project_name") or 
                (os.path.basename(path) if path else None))
        
        options = parameters.get("options", {})
        
        # Handle legacy parameter format (framework + language)
        if not template:
            framework = parameters.get("framework")
            language = parameters.get("language")
            template = self._map_legacy_params_to_template(framework, language)
        
        if not template or not path:
            return ToolResult(
                success=False,
                output=None,
                error="Either 'template' parameter or both 'framework' and 'language' parameters are required, along with 'path' (or 'directory'). Received parameters: " + str(list(parameters.keys()))
            )
        
        try:
            # Create project directory
            project_path = Path(path)
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Generate project based on template
            files_created = self._generate_project_scaffold(template, project_path, name, options)
            
            if not files_created:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Failed to generate project structure for template: {template}"
                )
            
            # Generate setup instructions
            setup_instructions = self._generate_setup_instructions(template, name, options)
            
            output = f"✅ **Project '{name}' created successfully!**\\n\\n"
            output += f"**Template**: {template}\\n"
            output += f"**Location**: {project_path.absolute()}\\n"
            output += f"**Files Created**: {len(files_created)}\\n\\n"
            output += "**Files:**\\n"
            for file_path in sorted(files_created)[:10]:  # Show first 10 files
                output += f"• {file_path}\\n"
            if len(files_created) > 10:
                output += f"• ... and {len(files_created) - 10} more files\\n"
            
            output += f"\\n{setup_instructions}"
            
            return ToolResult(
                success=True,
                output=output,
                action_description=f"Created {template} project at {path}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Project creation failed: {str(e)}"
            )
    
    def _map_legacy_params_to_template(self, framework: Optional[str], language: Optional[str]) -> Optional[str]:
        """Map legacy framework + language parameters to template names."""
        if not framework or not language:
            return None
        
        framework = framework.lower()
        language = language.lower()
        
        # Map framework + language combinations to template names
        mapping = {
            ("react", "typescript"): "vite-react-ts",
            ("react", "javascript"): "vite-react-js", 
            ("vue", "typescript"): "vue-ts",
            ("vue", "javascript"): "vue-js",
            ("express", "typescript"): "express-ts",
            ("express", "javascript"): "express-js",
            ("nodejs", "typescript"): "nodejs-ts", 
            ("nodejs", "javascript"): "nodejs-js",
            ("fastapi", "python"): "fastapi-python",
            ("flask", "python"): "flask-python",
            ("django", "python"): "django-python"
        }
        
        return mapping.get((framework, language))
    
    def _generate_project_scaffold(self, template: str, project_path: Path, name: str, options: Dict[str, Any]) -> List[str]:
        """Generate project files based on template."""
        files_created = []
        
        if template.startswith("vite-react"):
            files_created = self._create_vite_react_project(project_path, name, template.endswith("-ts"), options)
        elif template.startswith("create-react-app"):
            files_created = self._create_cra_project(project_path, name, template.endswith("-ts"), options)
        elif template.startswith("nextjs"):
            files_created = self._create_nextjs_project(project_path, name, template.endswith("-ts"), options)
        elif template.startswith("vue"):
            files_created = self._create_vue_project(project_path, name, template.endswith("-ts"), options)
        elif template.startswith("express"):
            files_created = self._create_express_project(project_path, name, template.endswith("-ts"), options)
        elif template.startswith("fastapi"):
            files_created = self._create_fastapi_project(project_path, name, options)
        elif template.startswith("flask"):
            files_created = self._create_flask_project(project_path, name, options)
        elif template.startswith("django"):
            files_created = self._create_django_project(project_path, name, options)
        elif template.startswith("nodejs"):
            files_created = self._create_nodejs_project(project_path, name, template.endswith("-ts"), options)
        
        return files_created
    
    def _create_vite_react_project(self, project_path: Path, name: str, is_typescript: bool, options: Dict[str, Any]) -> List[str]:
        """Create a Vite + React project."""
        files_created = []
        
        # Package.json
        package_json = {
            "name": name,
            "private": True,
            "version": "0.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0" if is_typescript else "eslint . --ext js,jsx --report-unused-disable-directives --max-warnings 0",
                "preview": "vite preview"
            },
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0"
            },
            "devDependencies": {
                "@types/react": "^18.2.43" if is_typescript else None,
                "@types/react-dom": "^18.2.17" if is_typescript else None,
                "@typescript-eslint/eslint-plugin": "^6.14.0" if is_typescript else None,
                "@typescript-eslint/parser": "^6.14.0" if is_typescript else None,
                "@vitejs/plugin-react": "^4.2.1",
                "eslint": "^8.55.0",
                "eslint-plugin-react-hooks": "^4.6.0",
                "eslint-plugin-react-refresh": "^0.4.5",
                "typescript": "^5.2.2" if is_typescript else None,
                "vite": "^5.0.8"
            }
        }
        
        # Remove None values
        package_json["devDependencies"] = {k: v for k, v in package_json["devDependencies"].items() if v is not None}
        
        # Add optional dependencies
        if options.get("with_router"):
            package_json["dependencies"]["react-router-dom"] = "^6.20.1"
        
        if options.get("css_framework") == "tailwind":
            package_json["devDependencies"]["tailwindcss"] = "^3.3.6"
            package_json["devDependencies"]["postcss"] = "^8.4.32"
            package_json["devDependencies"]["autoprefixer"] = "^10.4.16"
        
        self._write_file(project_path / "package.json", json.dumps(package_json, indent=2))
        files_created.append("package.json")
        
        # Vite config
        ext = "ts" if is_typescript else "js"
        vite_config = f"""import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({{
  plugins: [react()],
}})
"""
        self._write_file(project_path / f"vite.config.{ext}", vite_config)
        files_created.append(f"vite.config.{ext}")
        
        # HTML template
        html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.{ext}x"></script>
  </body>
</html>
"""
        self._write_file(project_path / "index.html", html_content)
        files_created.append("index.html")
        
        # Source files
        src_path = project_path / "src"
        src_path.mkdir(exist_ok=True)
        
        # Main entry file
        if is_typescript:
            main_content = """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""
        else:
            main_content = """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""
        
        self._write_file(src_path / f"main.{ext}x", main_content)
        files_created.append(f"src/main.{ext}x")
        
        # App component
        if is_typescript:
            app_content = """import { useState } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <div>
        <h1>{name}</h1>
      </div>
      <h1>Vite + React</h1>
      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          count is {count}
        </button>
        <p>
          Edit <code>src/App.tsx</code> and save to test HMR
        </p>
      </div>
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default App
""".replace("{name}", name)
        else:
            app_content = """import { useState } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <div>
        <h1>{name}</h1>
      </div>
      <h1>Vite + React</h1>
      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          count is {count}
        </button>
        <p>
          Edit <code>src/App.jsx</code> and save to test HMR
        </p>
      </div>
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default App
""".replace("{name}", name)
        
        self._write_file(src_path / f"App.{ext}x", app_content)
        files_created.append(f"src/App.{ext}x")
        
        # CSS files
        app_css = """#root {
  max-width: 1280px;
  margin: 0 auto;
  padding: 2rem;
  text-align: center;
}

.card {
  padding: 2em;
}

.read-the-docs {
  color: #888;
}
"""
        self._write_file(src_path / "App.css", app_css)
        files_created.append("src/App.css")
        
        index_css = """:root {
  font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
  line-height: 1.5;
  font-weight: 400;

  color-scheme: light dark;
  color: rgba(255, 255, 255, 0.87);
  background-color: #242424;

  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  -webkit-text-size-adjust: 100%;
}

body {
  margin: 0;
  display: flex;
  place-items: center;
  min-width: 320px;
  min-height: 100vh;
}

h1 {
  font-size: 3.2em;
  line-height: 1.1;
}

button {
  border-radius: 8px;
  border: 1px solid transparent;
  padding: 0.6em 1.2em;
  font-size: 1em;
  font-weight: 500;
  font-family: inherit;
  background-color: #1a1a1a;
  color: white;
  cursor: pointer;
  transition: border-color 0.25s;
}

button:hover {
  border-color: #646cff;
}

button:focus,
button:focus-visible {
  outline: 4px auto -webkit-focus-ring-color;
}

@media (prefers-color-scheme: light) {
  :root {
    color: #213547;
    background-color: #ffffff;
  }
  button {
    background-color: #f9f9f9;
    color: #213547;
  }
}
"""
        self._write_file(src_path / "index.css", index_css)
        files_created.append("src/index.css")
        
        # TypeScript config if needed
        if is_typescript:
            tsconfig = {
                "compilerOptions": {
                    "target": "ES2020",
                    "useDefineForClassFields": True,
                    "lib": ["ES2020", "DOM", "DOM.Iterable"],
                    "module": "ESNext",
                    "skipLibCheck": True,
                    "moduleResolution": "bundler",
                    "allowImportingTsExtensions": True,
                    "resolveJsonModule": True,
                    "isolatedModules": True,
                    "noEmit": True,
                    "jsx": "react-jsx",
                    "strict": True,
                    "noUnusedLocals": True,
                    "noUnusedParameters": True,
                    "noFallthroughCasesInSwitch": True
                },
                "include": ["src"],
                "references": [{"path": "./tsconfig.node.json"}]
            }
            
            self._write_file(project_path / "tsconfig.json", json.dumps(tsconfig, indent=2))
            files_created.append("tsconfig.json")
            
            tsconfig_node = {
                "compilerOptions": {
                    "composite": True,
                    "skipLibCheck": True,
                    "module": "ESNext",
                    "moduleResolution": "bundler",
                    "allowSyntheticDefaultImports": True
                },
                "include": ["vite.config.ts"]
            }
            
            self._write_file(project_path / "tsconfig.node.json", json.dumps(tsconfig_node, indent=2))
            files_created.append("tsconfig.node.json")
        
        # ESLint config
        eslint_config = {
            "root": True,
            "env": {"browser": True, "es2020": True},
            "extends": [
                "eslint:recommended",
                "@typescript-eslint/recommended" if is_typescript else None,
                "plugin:react-hooks/recommended"
            ],
            "ignorePatterns": ["dist", ".eslintrc.cjs"],
            "parser": "@typescript-eslint/parser" if is_typescript else None,
            "plugins": ["react-refresh"],
            "rules": {
                "react-refresh/only-export-components": [
                    "warn",
                    {"allowConstantExport": True}
                ]
            }
        }
        
        # Remove None values
        eslint_config["extends"] = [ext for ext in eslint_config["extends"] if ext is not None]
        if not is_typescript:
            del eslint_config["parser"]
        
        self._write_file(project_path / ".eslintrc.cjs", f"module.exports = {json.dumps(eslint_config, indent=2)}")
        files_created.append(".eslintrc.cjs")
        
        # README
        readme_content = f"""# {name}

This is a React application built with Vite{'and TypeScript' if is_typescript else ''}.

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Open [http://localhost:5173](http://localhost:5173) in your browser.

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run lint` - Run ESLint
- `npm run preview` - Preview production build

## Project Structure

```
{name}/
├── src/
│   ├── App.{ext}x
│   ├── main.{ext}x
│   ├── App.css
│   └── index.css
├── index.html
├── package.json
├── vite.config.{ext}
└── README.md
```
"""
        
        self._write_file(project_path / "README.md", readme_content)
        files_created.append("README.md")
        
        return files_created
    
    def _create_express_project(self, project_path: Path, name: str, is_typescript: bool, options: Dict[str, Any]) -> List[str]:
        """Create an Express.js project."""
        files_created = []
        
        # Package.json
        package_json = {
            "name": name,
            "version": "1.0.0",
            "description": "",
            "main": f"src/index.{'ts' if is_typescript else 'js'}",
            "scripts": {
                "start": f"node {'dist/index.js' if is_typescript else 'src/index.js'}",
                "dev": f"{'ts-node-dev' if is_typescript else 'nodemon'} src/index.{'ts' if is_typescript else 'js'}",
                "build": "tsc" if is_typescript else None
            },
            "dependencies": {
                "express": "^4.18.2",
                "cors": "^2.8.5",
                "dotenv": "^16.3.1"
            },
            "devDependencies": {
                "@types/express": "^4.17.21" if is_typescript else None,
                "@types/cors": "^2.8.17" if is_typescript else None,
                "@types/node": "^20.10.4" if is_typescript else None,
                "typescript": "^5.3.3" if is_typescript else None,
                "ts-node-dev": "^2.0.0" if is_typescript else None,
                "nodemon": "^3.0.2" if not is_typescript else None
            }
        }
        
        # Remove None values and scripts
        package_json["devDependencies"] = {k: v for k, v in package_json["devDependencies"].items() if v is not None}
        package_json["scripts"] = {k: v for k, v in package_json["scripts"].items() if v is not None}
        
        self._write_file(project_path / "package.json", json.dumps(package_json, indent=2))
        files_created.append("package.json")
        
        # Source directory
        src_path = project_path / "src"
        src_path.mkdir(exist_ok=True)
        
        # Main server file
        ext = "ts" if is_typescript else "js"
        server_content = f"""import express{', { Request, Response }' if is_typescript else ''} from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({{ extended: true }}));

// Routes
app.get('/', (req{': Request' if is_typescript else ''}, res{': Response' if is_typescript else ''}) => {{
  res.json({{ message: 'Hello from {name}!' }});
}});

app.get('/health', (req{': Request' if is_typescript else ''}, res{': Response' if is_typescript else ''}) => {{
  res.json({{ status: 'OK', timestamp: new Date().toISOString() }});
}});

// Start server
app.listen(PORT, () => {{
  console.log(`Server is running on port ${{PORT}}`);
}});
"""
        
        self._write_file(src_path / f"index.{ext}", server_content)
        files_created.append(f"src/index.{ext}")
        
        # TypeScript config
        if is_typescript:
            tsconfig = {
                "compilerOptions": {
                    "target": "ES2020",
                    "module": "CommonJS",
                    "lib": ["ES2020"],
                    "outDir": "./dist",
                    "rootDir": "./src",
                    "strict": True,
                    "esModuleInterop": True,
                    "skipLibCheck": True,
                    "forceConsistentCasingInFileNames": True,
                    "resolveJsonModule": True
                },
                "include": ["src/**/*"],
                "exclude": ["node_modules", "dist"]
            }
            
            self._write_file(project_path / "tsconfig.json", json.dumps(tsconfig, indent=2))
            files_created.append("tsconfig.json")
        
        # Environment file
        env_content = """PORT=3000
NODE_ENV=development
"""
        self._write_file(project_path / ".env", env_content)
        files_created.append(".env")
        
        # Gitignore
        gitignore = """node_modules/
dist/
.env
*.log
.DS_Store
"""
        self._write_file(project_path / ".gitignore", gitignore)
        files_created.append(".gitignore")
        
        return files_created
    
    def _create_fastapi_project(self, project_path: Path, name: str, options: Dict[str, Any]) -> List[str]:
        """Create a FastAPI Python project."""
        files_created = []
        
        # Requirements.txt
        requirements = """fastapi==0.104.1
uvicorn[standard]==0.24.0
python-dotenv==1.0.0
pydantic==2.5.0
"""
        
        if options.get("database") == "postgres":
            requirements += "psycopg2-binary==2.9.7\nsqlalchemy==2.0.23\n"
        elif options.get("database") == "sqlite":
            requirements += "sqlalchemy==2.0.23\n"
        
        self._write_file(project_path / "requirements.txt", requirements)
        files_created.append("requirements.txt")
        
        # Main FastAPI app
        main_content = f'''"""
{name} - FastAPI Application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="{name}",
    description="A FastAPI application",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {{"message": "Hello from {name}!"}}

@app.get("/health")
async def health_check():
    return {{"status": "OK", "service": "{name}"}}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
'''
        
        self._write_file(project_path / "main.py", main_content)
        files_created.append("main.py")
        
        # Environment file
        env_content = """PORT=8000
ENVIRONMENT=development
"""
        self._write_file(project_path / ".env", env_content)
        files_created.append(".env")
        
        return files_created
    
    def _write_file(self, file_path: Path, content: str):
        """Write content to a file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_setup_instructions(self, template: str, name: str, options: Dict[str, Any]) -> str:
        """Generate setup instructions for the project."""
        instructions = "## 🚀 Next Steps:\\n\\n"
        
        if template.startswith(("vite-react", "create-react-app", "nextjs", "vue")):
            instructions += f"1. **Navigate to your project:**\\n   ```bash\\n   cd {name}\\n   ```\\n\\n"
            instructions += "2. **Install dependencies:**\\n   ```bash\\n   npm install\\n   ```\\n\\n"
            instructions += "3. **Start development server:**\\n   ```bash\\n   npm run dev\\n   ```\\n\\n"
            if template.startswith("nextjs"):
                instructions += "4. **Open your browser:** [http://localhost:3000](http://localhost:3000)\\n"
            else:
                instructions += "4. **Open your browser:** [http://localhost:5173](http://localhost:5173)\\n"
        
        elif template.startswith(("express", "nodejs")):
            instructions += f"1. **Navigate to your project:**\\n   ```bash\\n   cd {name}\\n   ```\\n\\n"
            instructions += "2. **Install dependencies:**\\n   ```bash\\n   npm install\\n   ```\\n\\n"
            instructions += "3. **Start development server:**\\n   ```bash\\n   npm run dev\\n   ```\\n\\n"
            instructions += "4. **Test the API:** [http://localhost:3000](http://localhost:3000)\\n"
        
        elif template.startswith(("fastapi", "flask", "django")):
            instructions += f"1. **Navigate to your project:**\\n   ```bash\\n   cd {name}\\n   ```\\n\\n"
            instructions += "2. **Create virtual environment:**\\n   ```bash\\n   python -m venv venv\\n   ```\\n\\n"
            instructions += "3. **Activate virtual environment:**\\n   ```bash\\n   # Windows\\n   venv\\Scripts\\activate\\n   # macOS/Linux\\n   source venv/bin/activate\\n   ```\\n\\n"
            instructions += "4. **Install dependencies:**\\n   ```bash\\n   pip install -r requirements.txt\\n   ```\\n\\n"
            if template.startswith("fastapi"):
                instructions += "5. **Start development server:**\\n   ```bash\\n   python main.py\\n   ```\\n\\n"
                instructions += "6. **Open your browser:** [http://localhost:8000](http://localhost:8000)\\n"
            elif template.startswith("flask"):
                instructions += "5. **Start development server:**\\n   ```bash\\n   python app.py\\n   ```\\n\\n"
                instructions += "6. **Open your browser:** [http://localhost:5000](http://localhost:5000)\\n"
        
        return instructions
    
    # Placeholder methods for other project types
    def _create_cra_project(self, project_path: Path, name: str, is_typescript: bool, options: Dict[str, Any]) -> List[str]:
        # Would implement Create React App template
        return []
    
    def _create_nextjs_project(self, project_path: Path, name: str, is_typescript: bool, options: Dict[str, Any]) -> List[str]:
        # Would implement Next.js template  
        return []
    
    def _create_vue_project(self, project_path: Path, name: str, is_typescript: bool, options: Dict[str, Any]) -> List[str]:
        # Would implement Vue.js template
        return []
    
    def _create_flask_project(self, project_path: Path, name: str, options: Dict[str, Any]) -> List[str]:
        # Would implement Flask template
        return []
    
    def _create_django_project(self, project_path: Path, name: str, options: Dict[str, Any]) -> List[str]:
        # Would implement Django template
        return []
    
    def _create_nodejs_project(self, project_path: Path, name: str, is_typescript: bool, options: Dict[str, Any]) -> List[str]:
        # Would implement basic Node.js template
        return []