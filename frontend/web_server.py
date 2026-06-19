import sys
import os
import ast
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import aiosqlite

# Append root directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import StructuredTool

from app_tools.core.server_init import (
    communication_server,
    planning_server,
    content_server,
    supervisor_server,
)

# Import tools so they register to local registries
import app_tools.tools.google.gmail_tools
import app_tools.tools.google.calendar_tools
import app_tools.tools.google.gdrive_tools
import app_tools.tools.google.gslide_tools
import app_tools.tools.google.gsheet_tools
import app_tools.tools.google.gform_tools
import app_tools.tools.google.gdocs_tools
import app_tools.tools.google.gtask_tools
import app_tools.tools.google.gsearch_tools
import app_tools.tools.rag_tools

from config.settings import CHECKPOINT_DB
from core.graph import build_graph
from utils.helper import AsyncSqliteSaver, request_counter, setup_logger
from utils.memory_manager import log_event

from contextlib import asynccontextmanager

logger = setup_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start sandbox server on port 9000
    sandbox_script = root_dir / "core" / "sandbox_server.py"
    logger.info(f"Starting sandbox server on port 9000: {sandbox_script}")
    sandbox_process = None
    try:
        sandbox_process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(sandbox_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        logger.error(f"Failed to start sandbox server: {e}")

    # Start runtime in the background
    asyncio.create_task(runtime.initialize())
    yield
    # Shutdown: Close connection and cleanup
    await runtime.close()
    if sandbox_process:
        try:
            sandbox_process.terminate()
            await sandbox_process.wait()
            logger.info("Sandbox server stopped.")
        except Exception as e:
            logger.error(f"Error stopping sandbox server: {e}")

app = FastAPI(title="JARVIS Agent Dashboard API", lifespan=lifespan)

# Configuration and Database Paths
ENABLED_TOOLS_FILE = root_dir / "data" / "enabled_tools.json"
ENV_FILE = root_dir / ".env"

# Ensure data directory exists
(root_dir / "data").mkdir(parents=True, exist_ok=True)

# Helper: Load and Save enabled tools config
def load_enabled_tools_config() -> Dict[str, bool]:
    if ENABLED_TOOLS_FILE.exists():
        try:
            with open(ENABLED_TOOLS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading enabled tools: {e}")
    return {}

def save_enabled_tools_config(config: Dict[str, bool]):
    try:
        with open(ENABLED_TOOLS_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving enabled tools: {e}")

# Helper: Read and update .env file
def load_env_config() -> Dict[str, str]:
    config = {}
    if ENV_FILE.exists():
        try:
            lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    config[key.strip()] = val.strip()
        except Exception as e:
            logger.error(f"Error reading .env config: {e}")
    return config

def save_env_config(new_config: Dict[str, str]):
    lines = []
    updated_keys = set()
    if ENV_FILE.exists():
        try:
            current_lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
            for line in current_lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key, val = stripped.split("=", 1)
                    key = key.strip()
                    if key in new_config:
                        lines.append(f"{key}={new_config[key]}")
                        updated_keys.add(key)
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
        except Exception as e:
            logger.error(f"Error parsing .env file: {e}")
            
    # Add any new keys that weren't already in the file
    for key, val in new_config.items():
        if key not in updated_keys:
            lines.append(f"{key}={val}")
            
    try:
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # Update process environment variables as well
        for key, val in new_config.items():
            os.environ[key] = val
    except Exception as e:
        logger.error(f"Error writing .env file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to write .env file: {e}")

# Helper: AST parser to find tools in tools
def parse_registered_tools() -> List[Dict[str, Any]]:
    tools_dir = root_dir / "app_tools" / "tools"
        
    if not tools_dir.exists():
        logger.warning("No tools folder found (checked tools)")
        return []

    tools = []
    for py_file in tools_dir.rglob("*.py"):
        if "helper" in py_file.parts:
            continue
        if py_file.name == "__init__.py" or py_file.name == "workspace_comment_base.py":
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check decorators for server registrations
                    is_tool = False
                    category = "Other"
                    for decorator in node.decorator_list:
                        dec_str = ""
                        if isinstance(decorator, ast.Call):
                            func = decorator.func
                            if isinstance(func, ast.Attribute):
                                dec_str = f"{func.value.id if isinstance(func.value, ast.Name) else ''}.{func.attr}"
                            elif isinstance(func, ast.Name):
                                dec_str = func.id
                        elif isinstance(decorator, ast.Attribute):
                            dec_str = f"{decorator.value.id if isinstance(decorator.value, ast.Name) else ''}.{decorator.attr}"
                        elif isinstance(decorator, ast.Name):
                            dec_str = decorator.id
                            
                        if "tool" in dec_str:
                            is_tool = True
                            if "communication" in dec_str:
                                category = "Communication"
                            elif "planning" in dec_str:
                                category = "Planning"
                            elif "content" in dec_str:
                                category = "Content"
                            elif "supervisor" in dec_str:
                                category = "Supervisor"
                            break
                            
                    if is_tool:
                        docstring = ast.get_docstring(node) or "No description available."
                        # Use first line of docstring as short description
                        short_desc = docstring.strip().split("\n")[0] if docstring else "No description available."
                        tools.append({
                            "name": node.name,
                            "description": short_desc,
                            "category": category,
                            "file": py_file.name
                        })
        except Exception as e:
            logger.error(f"Error parsing AST of file {py_file}: {e}")
            
    return tools

# Unified Runtime class managing tools and LangGraph
class AgentRuntime:
    def __init__(self):
        self.graph = None
        self._connection = None
        self._cached_tools = {}
        self.all_tools_map = {}
        self.is_loaded = False

    def _get_langchain_tools(self, server) -> List[StructuredTool]:
        return server.list_tools()

    async def initialize(self):
        logger.info("Initializing Agent Runtime...")
        try:
            # 1. Retrieve and convert tools in-process
            self._cached_tools["communication"] = self._get_langchain_tools(communication_server)
            self._cached_tools["planning"] = self._get_langchain_tools(planning_server)
            self._cached_tools["content"] = self._get_langchain_tools(content_server)
            self._cached_tools["supervisor"] = self._get_langchain_tools(supervisor_server)
            
            # 2. Cache flat tools map
            self.all_tools_map = {}
            for category, tools in self._cached_tools.items():
                for t in tools:
                    self.all_tools_map[t.name] = t
            
            # 3. Compile the Graph
            await self.compile_graph()
            self.is_loaded = True
            logger.info("Agent Runtime initialized successfully.")
        except Exception as e:
            logger.exception(f"Error during Agent Runtime initialization: {e}")

    async def compile_graph(self):
        logger.info("Compiling LangGraph with filtered tools...")
        
        # Load enabled tools mapping
        enabled_map = load_enabled_tools_config()
        
        # Filter tool sets
        tool_sets = {}
        for key, tools in self._cached_tools.items():
            ui_category = key.capitalize()
            category_enabled = enabled_map.get(key, True) and enabled_map.get(ui_category, True)
            
            filtered = []
            for t in tools:
                if category_enabled and enabled_map.get(t.name, True):
                    filtered.append(t)
            tool_sets[key] = filtered
            logger.info(f"Loaded {len(filtered)} / {len(tools)} tools for server: {key}")

        # Setup persistence connection
        if self._connection is not None:
            await self._connection.close()
            
        self._connection = await aiosqlite.connect(str(CHECKPOINT_DB))
        checkpointer = AsyncSqliteSaver(self._connection)
        
        # Build graph
        self.graph = build_graph(tool_sets, checkpointer)
        logger.info("LangGraph compiled.")

    async def chat(self, query: str, thread_id: str) -> Dict[str, Any]:
        if not self.is_loaded:
            raise HTTPException(status_code=503, detail="Agent runtime is not fully initialized.")

        config = {"configurable": {"thread_id": thread_id}}
        
        # Audit human message
        try:
            await log_event(
                thread_id=thread_id,
                actor="Human_node",
                message=query,
                metadata={"source": "web_dashboard"},
            )
        except Exception as exc:
            logger.warning("Failed to log Human_node audit event: %s", exc)

        # Get state snapshot
        snapshot = await self.graph.aget_state(config)
        current_agent = "supervisor"
        if snapshot and snapshot.values:
            current_agent = snapshot.values.get("current_agent", "supervisor")

        AGENT_MESSAGE_KEY = {
            "supervisor": "supervisor_messages",
            "communication_agent": "communication_messages",
            "planning_agent": "planning_messages",
            "document_agent": "document_messages",
            "presentation_agent": "presentation_messages",
            "data_agent": "data_messages",
            "code_agent": "code_messages",
        }
        
        context_key = AGENT_MESSAGE_KEY.get(current_agent, "supervisor_messages")
        human_message = HumanMessage(content=query)

        request_counter.start_turn(query)
        state = await self.graph.ainvoke(
            {"messages": [human_message], context_key: [human_message]},
            config=config,
        )
        request_counter.end_turn()

        # Extract final answer
        response = self._extract_last_ai_message(state)
        
        # Extract thoughts
        thought_logs = self._extract_thought_logs(state)

        return {"response": response, "thought_logs": thought_logs}

    def _extract_last_ai_message(self, state: dict[str, Any]) -> str:
        AGENT_MESSAGE_KEY = {
            "supervisor": "supervisor_messages",
            "communication_agent": "communication_messages",
            "planning_agent": "planning_messages",
            "document_agent": "document_messages",
            "presentation_agent": "presentation_messages",
            "data_agent": "data_messages",
            "code_agent": "code_messages",
        }
        active_agent = state.get("current_agent", "supervisor")
        response_key = AGENT_MESSAGE_KEY.get(active_agent, "supervisor_messages")
        messages = state.get(response_key) or state.get("messages", [])
        
        for message in reversed(messages):
            msg_type = getattr(message, "type", "")
            content = getattr(message, "content", "")
            if msg_type == "ai" and content:
                return str(content)

        if messages:
            fallback = messages[-1]
            content = getattr(fallback, "content", "")
            if content:
                return str(content)

        return "I could not generate a response for that request."

    def _extract_thought_logs(self, state: dict[str, Any]) -> str:
        logs = []
        all_messages = []
        
        keys = [
            "messages", "supervisor_messages", "communication_messages",
            "planning_messages", "document_messages", "presentation_messages",
            "data_messages", "code_messages"
        ]
        
        for key in keys:
            if key in state and state[key]:
                for msg in state[key]:
                    if msg not in all_messages:
                        all_messages.append(msg)
                        
        for msg in all_messages:
            msg_type = getattr(msg, "type", "")
            content = getattr(msg, "content", "")
            name = getattr(msg, "name", "")
            tool_calls = getattr(msg, "tool_calls", None)
            
            if msg_type == "ai":
                actor = name or "JARVIS Agent"
                if content:
                    logs.append(f"🤖 [{actor} Reasoning]\n{content}\n")
                if tool_calls:
                    for tc in tool_calls:
                        logs.append(f"⚙️ [{actor} Action] Calling tool '{tc.get('name')}' with parameters:\n{json.dumps(tc.get('args'), indent=2)}\n")
            elif msg_type == "tool":
                actor = name or "System Tool"
                logs.append(f"📥 [Tool Response from '{actor}']\n{content}\n")
                
        return "\n".join(logs)

    async def close(self):
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception as e:
                logger.error(f"Error closing DB connection: {e}")
            self._connection = None
            
        self._cached_tools = {}
        self.all_tools_map = {}

    async def reload(self):
        logger.info("Reloading Agent Runtime (in-process tools refresh)...")
        try:
            self.is_loaded = False
            await self.close()
            await self.initialize()
            logger.info("Agent Runtime reloaded successfully.")
        except Exception as e:
            logger.exception(f"Error during Agent Runtime reload: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to reload agent: {e}")

# Global Runtime Instance
runtime = AgentRuntime()

# Pydantic Schema
class ChatRequest(BaseModel):
    query: str
    thread_id: str

class ToolToggleRequest(BaseModel):
    name: str
    enabled: bool

class ConfigUpdateRequest(BaseModel):
    config: Dict[str, str]

# API Endpoints
@app.get("/api/tools")
def get_tools():
    all_tools = parse_registered_tools()
    enabled_config = load_enabled_tools_config()
    
    # Map enabled state
    for t in all_tools:
        t["enabled"] = enabled_config.get(t["name"], True)
        
    # Map category enabled states
    categories = {
        "Communication": enabled_config.get("Communication", True),
        "Planning": enabled_config.get("Planning", True),
        "Content": enabled_config.get("Content", True),
        "Supervisor": enabled_config.get("Supervisor", True)
    }
        
    return {"tools": all_tools, "categories": categories}

@app.post("/api/tools/toggle")
def toggle_tool(req: ToolToggleRequest):
    config = load_enabled_tools_config()
    config[req.name] = req.enabled
    save_enabled_tools_config(config)
    return {"status": "ok"}

@app.get("/api/config")
def get_config():
    config = load_env_config()
    return {"config": config}

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    save_env_config(req.config)
    return {"status": "ok"}

@app.post("/api/agent/reload")
async def reload_agent():
    if not runtime.is_loaded:
        raise HTTPException(status_code=503, detail="Agent runtime is not loaded yet.")
    await runtime.reload()
    return {"status": "ok"}

class SandboxToolExecutionRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]

@app.post("/api/sandbox/execute_tool")
async def sandbox_execute_tool(req: SandboxToolExecutionRequest):
    if not runtime.is_loaded:
        raise HTTPException(status_code=503, detail="Agent runtime is not fully initialized.")
        
    tool = getattr(runtime, "all_tools_map", {}).get(req.tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {req.tool_name} not found")
        
    try:
        result = await tool.ainvoke(req.arguments)
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {"success": True, "data": result}
        return result
    except Exception as e:
        logger.error(f"Sandbox tool execution failed: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    return await runtime.chat(req.query, req.thread_id)

# Serve static dashboard files
app.mount("/", StaticFiles(directory=str(root_dir / "frontend" / "static"), html=True), name="static")

if __name__ == "__main__":
    # Use port 8080 to avoid Windows socket bind conflicts with default port 8000
    uvicorn.run(app, host="127.0.0.1", port=8080)
