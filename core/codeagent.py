import asyncio
import tempfile
from pathlib import Path
import subprocess
from typing import Dict, Any, List, Callable
from utils.helper import setup_logger
from langchain_core.messages import BaseMessage, SystemMessage
from core.state import TaskSpec

logger = setup_logger(__name__)


class CodeExecutionAgent:
    def __init__(self, llm_client, tool_sets: Dict[str, Any]):
        self.llm = llm_client
        self.tool_sets = tool_sets
        self.sandbox_path = Path("D:/Agentic AI/core/sandbox")
        self.sandbox_path.mkdir(exist_ok=True)

    async def execute_workflow(
        self, messages: List[BaseMessage], available_tools: List[str]
    ) -> Dict[str, Any]:
        """
        1. Parse History -> TaskSpec (Structured)
        2. TaskSpec -> Python Code (Executable)
        """

        task_spec = await self._resolve_intent(
            messages, available_tools=available_tools
        )

        # 1. Create the Tool Map (Injects your real tools)
        tool_map = self._create_tool_map(task_spec.required_tools_hint)

        tool_schemas = await self._load_tool_schemas(task_spec.required_tools_hint)
        code_prompt = self._build_code_generation_prompt(task_spec, tool_schemas)

        generated_code = await self._generate_code(code_prompt)

        # 2. Run with exec()
        return await self._execute_locally(generated_code, tool_map)

    def _create_tool_map(self, required_hints: List[str]) -> Dict[str, Callable]:
        tool_map = {}
        active_tools = []
        for category, tools in self.tool_sets.items():
            if not required_hints or category in required_hints:
                active_tools.extend(tools)

        for tool in active_tools:
            # Create a simple wrapper for the tool
            def make_wrapper(t):
                def wrapper(**kwargs):
                    logger.info(f"⚙️ Executing Tool: {t.name}")
                    if hasattr(t, "run"):
                        return t.run(kwargs)
                    return t(kwargs)

                return wrapper

            tool_map[tool.name] = make_wrapper(tool)
        return tool_map

    async def _execute_locally(
        self, code: str, tool_map: Dict[str, Callable]
    ) -> Dict[str, Any]:
        # Inject tools into the script's global scope
        global_scope = {
            "Dict": Dict,
            "Any": Any,
            "List": List,
            "asyncio": asyncio,
            **tool_map,
        }

        try:
            logger.info("⚡ Running code...")
            exec(code, global_scope)

            if "execute_workflow" not in global_scope:
                return {"error": "Function 'execute_workflow' missing."}

            func = global_scope["execute_workflow"]

            if asyncio.iscoroutinefunction(func):
                return await func()
            return func()

        except Exception as e:
            return {"error": str(e)}

    async def _resolve_intent(
        self, messages: List[BaseMessage], available_tools: List[str]
    ) -> TaskSpec:
        """Extract task specification from conversation history"""

        system_prompt = f"""
        You are a task analyzer. Extract structured information from this conversation.
        
        Return a JSON object with:
        {{
            "primary_goal": "What the user wants to accomplish",
            "required_tools_hint": ["communication", "planning", "content"],
            "context_variables": {{"key": "string value only"}},
            "last_error": null
        }}
        the available tool types are: {available_tools} only use these.
        
        IMPORTANT: All values in context_variables MUST be strings, not booleans or numbers.
        Example: {{"handled": "true"}} NOT {{"handled": true}}
        
        Focus on the LATEST user request and any errors.
        """

        # Get last 5 messages for context
        recent_messages = messages[-5:]
        conversation = "\n".join([f"{m.type}: {m.content}" for m in recent_messages])

        prompt = f"{system_prompt}\n\nConversation:\n{conversation}"

        response = await self.llm.ainvoke([{"role": "user", "content": prompt}])

        # Parse JSON from response
        import json
        import re

        json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))

                # ✅ Ensure all required fields exist with defaults
                sanitized = {
                    "primary_goal": data.get("primary_goal", "Unknown goal"),
                    "required_tools_hint": data.get(
                        "required_tools_hint", ["communication"]
                    ),
                    "context_variables": {},
                    "last_error": data.get("last_error")
                    if data.get("last_error")
                    else None,
                }

                # ✅ Sanitize context_variables - convert all values to strings
                ctx = data.get("context_variables", {})
                if isinstance(ctx, dict):
                    sanitized["context_variables"] = {k: str(v) for k, v in ctx.items()}

                return TaskSpec(**sanitized)
            except Exception as e:
                logger.error(f"TaskSpec creation failed: {e}")

        # Fallback if parsing fails
        return TaskSpec(
            primary_goal=recent_messages[-1].content if recent_messages else "No goal",
            required_tools_hint=["communication"],
            context_variables={},
            last_error=None,
        )

    async def _load_tool_schemas(self, tool_types: List[str]) -> Dict[str, Any]:
        """Load only the schemas for required tool types"""
        schemas = {}
        for tool_type in tool_types:
            if tool_type in self.tool_sets:
                tools = self.tool_sets[tool_type]

                tool_schemas = []
                for t in tools:
                    # Debug: See what attributes the tool has
                    logger.debug(f"Tool: {t.name}, Type: {type(t).__name__}")
                    logger.debug(
                        f"  Attributes: {[a for a in dir(t) if not a.startswith('_')]}"
                    )

                    schema = {
                        "name": t.name,
                        "description": t.description,
                    }

                    # Handle different tool types
                    if hasattr(t, "inputSchema"):
                        schema["parameters"] = t.inputSchema
                    elif hasattr(t, "args_schema") and t.args_schema:
                        # ✅ Check if it's already a dict or a Pydantic model
                        if isinstance(t.args_schema, dict):
                            schema["parameters"] = t.args_schema
                        else:
                            # It's a Pydantic model, call .schema()
                            schema["parameters"] = t.args_schema.schema()
                    elif hasattr(t, "args"):
                        schema["parameters"] = t.args
                    else:
                        schema["parameters"] = {}
                        logger.warning(f"Tool {t.name} has no schema attribute")

                    tool_schemas.append(schema)  # ✅ Add this line - it was missing!

                schemas[tool_type] = tool_schemas  # ✅ This was indented wrong

        logger.info(f"📦 Loaded schemas for {len(schemas)} tool types")
        for tool_type, tools in schemas.items():
            logger.info(f"   {tool_type}: {len(tools)} tools")

        return schemas

    def _build_code_generation_prompt(self, spec: TaskSpec, schemas: Dict) -> str:
        """
        Builds the prompt using the Clean Spec.
        """
        return f"""
        You are an expert Python developer.
        
        GOAL: {spec.primary_goal}
        
        CONTEXT VARIABLES:
        {spec.context_variables}
        
        PREVIOUS ERROR (Fix this if present):
        {spec.last_error or "None"}
        
        AVAILABLE TOOLS:
        {self._format_schemas(schemas)}

            Requirements:
            1. You CANNOT use `input()` or interactive commands.
            2. You MUST use the provided MCP tools for external actions.
            3. DO NOT HALLUCINATE OR SIMULATE DATA. You must call the tool functions to get real data.
            4. If you need to search, call the search tool. Do not return hardcoded examples.
            5. Return a dictionary with 'summary', 'details', 'artifacts'.
            
            follow this template strictly:
            ```python
            import asyncio
            from typing import Dict, Any

            async def execute_workflow() -> Dict[str, Any]:
                # Step 1: Initialize clients
                # Step 2: Perform logic based on PREVIOUS CONTEXT and CURRENT TASK
                
                return {{
                    "summary": "...", 
                    "details": {{}},
                    "artifacts": []
                }}
            
            if __name__ == "__main__":
                result = asyncio.run(execute_workflow())
                print(result)
            ```
            """

    async def _generate_code(self, prompt: str) -> str:
        """Generate code using LLM"""
        response = await self.llm.ainvoke([{"role": "user", "content": prompt}])

        # Extract code block
        code = self._extract_code_block(response.content)

        logger.info(f"Generated code:\n{code[:]}...")
        return code

    async def _execute_in_sandbox(self, code: str) -> Dict[str, Any]:
        """Execute in Docker container for safety"""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "run",
                "--rm",
                "-i",
                "--memory=512m",
                "--cpus=1",
                "--network=none",
                "python-sandbox",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(code.encode()), timeout=300
            )

            if process.returncode == 0:
                import json

                result = json.loads(stdout.decode())
                return {
                    "status": "success",
                    "summary": result.get("summary", "Completed"),
                    "full_output": result,
                }
            else:
                error_msg = stderr.decode()
                logger.error(f"Execution failed: {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg,
                    "summary": f"Failed: {error_msg[:200]}",
                }

        except asyncio.TimeoutError:
            return {
                "status": "error",
                "error": "Execution timeout (5 min)",
                "summary": "Task took too long",
            }
        except Exception as e:
            logger.error(f"Docker execution error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "summary": f"Execution error: {e}",
            }

    async def _summarize_results(self, execution_result: Dict) -> str:
        """Extract only essential information to return to model"""
        if "error" in execution_result:
            return f"Execution failed: {execution_result['error']}"

        # Return only the summary and key metrics, not full data
        summary_parts = [execution_result.get("summary", "Task completed")]

        if "details" in execution_result:
            details = execution_result["details"]
            summary_parts.append(f"Key metrics: {details}")

        if "artifacts" in execution_result:
            artifacts = execution_result["artifacts"]
            summary_parts.append(f"Created: {len(artifacts)} artifacts")

        return " | ".join(summary_parts)

    # def _estimate_token_savings(self, full_output: Dict, summary: str) -> int:
    #     """Estimate tokens saved by using code execution"""
    #     # Rough estimate: 4 chars per token
    #     full_tokens = len(str(full_output)) // 4
    #     summary_tokens = len(summary) // 4
    #     return full_tokens - summary_tokens

    def _format_schemas(self, schemas: Dict) -> str:
        """Format tool schemas for prompt"""
        formatted = []
        for tool_type, tools in schemas.items():
            formatted.append(f"\n{tool_type.upper()} Tools:")
            for tool in tools:
                formatted.append(f"  - {tool['name']}: {tool['description']}")
        return "\n".join(formatted)

    def _extract_code_block(self, response: str) -> str:
        """Extract code from markdown code blocks"""
        import re

        pattern = r"```python\n(.*?)\n```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1)
        return response
