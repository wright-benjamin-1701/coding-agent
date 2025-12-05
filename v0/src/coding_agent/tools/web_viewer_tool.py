"""Web viewer tool for examining AI model interactions."""

import sqlite3
import json
import threading
import webbrowser
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

from .base import Tool
from ..types import ToolResult


class WebViewerHandler(BaseHTTPRequestHandler):
    """HTTP handler for the web viewer."""
    
    def __init__(self, *args, db_path: str = None, **kwargs):
        self.db_path = db_path or ".coding_agent.db"
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/" or self.path == "/index.html":
            self.serve_index()
        elif self.path.startswith("/api/sessions"):
            self.serve_sessions()
        elif self.path.startswith("/api/session/"):
            session_id = self.path.split("/")[-1]
            self.serve_session_details(session_id)
        elif self.path.startswith("/api/files"):
            self.serve_files()
        elif self.path.startswith("/api/interactions/"):
            session_id = self.path.split("/")[-1]
            self.serve_model_interactions(session_id)
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests."""
        self.send_error(404)
    
    def serve_index(self):
        """Serve the main HTML page."""
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Coding Agent Model Interactions</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        .session { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
        .session:hover { background: #f9f9f9; cursor: pointer; }
        .timestamp { color: #666; font-size: 0.9em; }
        .prompt { font-weight: bold; margin: 10px 0; }
        .summary { color: #444; margin: 10px 0; }
        .execution-log { background: #f8f8f8; padding: 10px; border-radius: 3px; font-family: monospace; }
        .model-interaction { background: #e8f4fd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .model-prompt { background: #fff3cd; padding: 10px; border-radius: 3px; margin: 5px 0; }
        .model-response { background: #d4edda; padding: 10px; border-radius: 3px; margin: 5px 0; }
        .file-cache { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }
        pre { white-space: pre-wrap; word-wrap: break-word; }
        .nav { margin: 20px 0; }
        .nav button { padding: 10px 20px; margin: 5px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
        .nav button:hover { background: #0056b3; }
        .details { display: none; }
        h1, h2 { color: #333; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Coding Agent Model Interactions</h1>
        
        <div class="nav">
            <button onclick="showSessions()">📋 Sessions</button>
            <button onclick="showFiles()">📁 File Cache</button>
            <button onclick="refreshData()">🔄 Refresh</button>
        </div>
        
        <div id="sessions-view">
            <h2>Recent Sessions</h2>
            <div id="sessions-list">Loading sessions...</div>
        </div>
        
        <div id="files-view" style="display: none;">
            <h2>Cached Files</h2>
            <div id="files-list">Loading files...</div>
        </div>
        
        <div id="session-details" class="details">
            <button onclick="showSessions()">← Back to Sessions</button>
            <div id="session-content"></div>
        </div>
    </div>

    <script>
        function showSessions() {
            document.getElementById('sessions-view').style.display = 'block';
            document.getElementById('files-view').style.display = 'none';
            document.getElementById('session-details').style.display = 'none';
            loadSessions();
        }
        
        function showFiles() {
            document.getElementById('sessions-view').style.display = 'none';
            document.getElementById('files-view').style.display = 'block';
            document.getElementById('session-details').style.display = 'none';
            loadFiles();
        }
        
        function showSessionDetails(sessionId) {
            document.getElementById('sessions-view').style.display = 'none';
            document.getElementById('files-view').style.display = 'none';
            document.getElementById('session-details').style.display = 'block';
            loadSessionDetails(sessionId);
        }
        
        async function loadSessions() {
            try {
                const response = await fetch('/api/sessions');
                const sessions = await response.json();
                
                const html = sessions.map(session => `
                    <div class="session" onclick="showSessionDetails(${session.id})">
                        <div class="timestamp">${new Date(session.timestamp).toLocaleString()}</div>
                        <div class="prompt">${escapeHtml(session.user_prompt)}</div>
                        <div class="summary">${escapeHtml(session.summary)}</div>
                    </div>
                `).join('');
                
                document.getElementById('sessions-list').innerHTML = html || 'No sessions found.';
            } catch (error) {
                document.getElementById('sessions-list').innerHTML = 'Error loading sessions: ' + error.message;
            }
        }
        
        async function loadFiles() {
            try {
                const response = await fetch('/api/files');
                const files = await response.json();
                
                const html = files.map(file => `
                    <div class="file-cache">
                        <strong>${escapeHtml(file.file_path)}</strong>
                        <div class="timestamp">Commit: ${file.commit_hash} | Updated: ${new Date(file.last_updated).toLocaleString()}</div>
                        ${file.summary ? `<div class="summary">${escapeHtml(file.summary)}</div>` : ''}
                        <details>
                            <summary>View Content</summary>
                            <pre>${escapeHtml(file.content)}</pre>
                        </details>
                    </div>
                `).join('');
                
                document.getElementById('files-list').innerHTML = html || 'No cached files found.';
            } catch (error) {
                document.getElementById('files-list').innerHTML = 'Error loading files: ' + error.message;
            }
        }
        
        async function loadSessionDetails(sessionId) {
            try {
                const [sessionResponse, interactionsResponse] = await Promise.all([
                    fetch(`/api/session/${sessionId}`),
                    fetch(`/api/interactions/${sessionId}`)
                ]);
                
                const session = await sessionResponse.json();
                const interactions = await interactionsResponse.json();
                
                let interactionsHtml = '';
                if (interactions.length > 0) {
                    interactionsHtml = `
                        <div class="model-interaction">
                            <h3>🧠 Model Interactions</h3>
                            ${interactions.map(interaction => `
                                <div style="border: 1px solid #ddd; margin: 10px 0; padding: 10px; border-radius: 5px;">
                                    <h4>Step ${interaction.step_number} - ${new Date(interaction.timestamp).toLocaleTimeString()}</h4>
                                    <div class="model-prompt">
                                        <strong>Prompt:</strong>
                                        <pre style="max-height: 300px; overflow-y: auto;">${escapeHtml(interaction.prompt)}</pre>
                                    </div>
                                    <div class="model-response">
                                        <strong>Response:</strong>
                                        <pre style="max-height: 300px; overflow-y: auto;">${escapeHtml(interaction.response)}</pre>
                                    </div>
                                    ${interaction.metadata ? `<div><strong>Metadata:</strong> ${escapeHtml(interaction.metadata)}</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    `;
                } else if (session.execution_log) {
                    const log = JSON.parse(session.execution_log);
                    interactionsHtml = `
                        <div class="model-interaction">
                            <h3>📋 Execution Log</h3>
                            <pre style="max-height: 400px; overflow-y: auto;">${escapeHtml(JSON.stringify(log, null, 2))}</pre>
                        </div>
                    `;
                }
                
                const html = `
                    <h2>Session Details</h2>
                    <div class="timestamp">${new Date(session.timestamp).toLocaleString()}</div>
                    <div class="prompt"><strong>User Prompt:</strong><br><pre>${escapeHtml(session.user_prompt)}</pre></div>
                    <div class="summary"><strong>Summary:</strong><br>${escapeHtml(session.summary)}</div>
                    <div><strong>Commit Hash:</strong> ${session.commit_hash}</div>
                    <div><strong>Modified Files:</strong> ${JSON.parse(session.modified_files).join(', ')}</div>
                    ${interactionsHtml}
                `;
                
                document.getElementById('session-content').innerHTML = html;
            } catch (error) {
                document.getElementById('session-content').innerHTML = 'Error loading session: ' + error.message;
            }
        }
        
        function refreshData() {
            if (document.getElementById('sessions-view').style.display !== 'none') {
                loadSessions();
            } else if (document.getElementById('files-view').style.display !== 'none') {
                loadFiles();
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Load sessions on page load
        loadSessions();
    </script>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def serve_sessions(self):
        """Serve sessions data as JSON."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT id, timestamp, user_prompt, commit_hash, modified_files, summary
                    FROM sessions 
                    ORDER BY timestamp DESC 
                    LIMIT 50
                """)
                
                sessions = [dict(row) for row in cursor.fetchall()]
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(sessions, ensure_ascii=False).encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Database error: {str(e)}")
    
    def serve_session_details(self, session_id: str):
        """Serve detailed session data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM sessions WHERE id = ?
                """, (session_id,))
                
                session = cursor.fetchone()
                if not session:
                    self.send_error(404, "Session not found")
                    return
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(dict(session), ensure_ascii=False).encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Database error: {str(e)}")
    
    def serve_files(self):
        """Serve file cache data as JSON."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT file_path, commit_hash, content, summary, last_updated
                    FROM file_cache 
                    ORDER BY last_updated DESC 
                    LIMIT 100
                """)
                
                files = [dict(row) for row in cursor.fetchall()]
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(files, ensure_ascii=False).encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Database error: {str(e)}")
    
    def serve_model_interactions(self, session_id: str):
        """Serve model interactions for a session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT step_number, timestamp, prompt, response, metadata
                    FROM model_interactions 
                    WHERE session_id = ?
                    ORDER BY step_number ASC
                """, (session_id,))
                
                interactions = [dict(row) for row in cursor.fetchall()]
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(interactions, ensure_ascii=False).encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Database error: {str(e)}")
    
    
    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


class WebViewerTool(Tool):
    """Tool for launching a web interface to view AI model interactions."""
    
    def __init__(self):
        self.server = None
        self.server_thread = None
    
    @property
    def name(self) -> str:
        return "web_viewer"
    
    @property
    def description(self) -> str:
        return "Launch a web interface to view AI model interactions and database contents"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "port": {
                    "type": "integer",
                    "description": "Port to run the web server on (default: 8080)",
                    "default": 8080
                },
                "open_browser": {
                    "type": "boolean", 
                    "description": "Whether to automatically open browser (default: true)",
                    "default": True
                }
            },
            "required": []
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, **parameters) -> ToolResult:
        """Launch the web viewer."""
        port = parameters.get("port", 8080)
        open_browser = parameters.get("open_browser", True)
        
        try:
            # Stop existing server if running
            if self.server:
                self.stop_server()
            
            # Find database path
            db_path = ".coding_agent.db"
            if not Path(db_path).exists():
                return ToolResult(
                    success=False, 
                    output=None, 
                    error=f"Database not found at {db_path}. Run some coding agent commands first."
                )
            
            # Create handler with database path
            def handler_factory(*args, **kwargs):
                return WebViewerHandler(*args, db_path=db_path, **kwargs)
            
            # Start server
            self.server = HTTPServer(('localhost', port), handler_factory)
            
            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True
            )
            self.server_thread.start()
            
            url = f"http://localhost:{port}"
            
            # Open browser if requested
            if open_browser:
                webbrowser.open(url)
                browser_msg = " and opened in browser"
            else:
                browser_msg = ""
            
            return ToolResult(
                success=True,
                output=f"Web viewer started at {url}{browser_msg}",
                action_description=f"Started web viewer on port {port}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Failed to start web viewer: {str(e)}"
            )
    
    def stop_server(self):
        """Stop the web server."""
        if self.server:
            self.server.shutdown()
            self.server = None
        if self.server_thread:
            self.server_thread.join(timeout=1)
            self.server_thread = None