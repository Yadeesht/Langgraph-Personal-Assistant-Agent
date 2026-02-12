import json
import re
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Callable
from utils.helper import setup_logger
from langchain_core.messages import BaseMessage
from core.state import TaskSpec

logger = setup_logger(__name__)


class CodeExecutionAgent:
    def __init__(self, llm_client, tool_sets: Dict[str, Any]):
        self.llm = llm_client
        self.tool_sets = tool_sets
        self.sandbox_path = Path("D:/Agentic AI/core/sandbox")
        self.sandbox_path.mkdir(exist_ok=True)

    async def execute_workflow(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        task_spec = await self._resolve_intent(messages)

        logger.info(f"Task Specs: {task_spec}")

        tool_map = self._create_tool_map(task_spec.required_tools_hint)

        tool_schemas = await self._load_tool_schemas(task_spec.required_tools_hint)

        code_prompt = self._build_code_generation_prompt(task_spec, tool_schemas)

        generated_code = await self._generate_code(code_prompt)

        result = await self._execute_in_sandbox(generated_code, tool_map)

        result["generated_code"] = generated_code
        result["task_goal"] = task_spec.primary_goal

        return result

    def _create_tool_map(self, required_hints: List[str]) -> Dict[str, Callable]:
        tool_map = {}
        active_tools = []
        for category, tools in self.tool_sets.items():
            if not required_hints or category in required_hints:
                active_tools.extend(tools)

        for tool in active_tools:

            def make_wrapper(t):
                async def wrapper(**kwargs):
                    logger.info(f"⚙️ Executing Tool: {t.name}")
                    logger.info(f"   Parameters: {kwargs}")
                    try:
                        if hasattr(t, "ainvoke"):
                            result = await t.ainvoke(kwargs)
                        elif hasattr(t, "arun"):
                            result = await t.arun(kwargs)
                        elif hasattr(t, "run"):
                            result = t.run(kwargs)
                        else:
                            result = t(kwargs)

                        logger.info(f"   Raw result type: {type(result)}")
                        logger.info(f"   Raw result: {str(result)}")

                        # Parse string results into dict
                        if isinstance(result, str):
                            import json

                            try:
                                result = json.loads(result)
                            except json.JSONDecodeError:
                                logger.warning(
                                    "Could not parse as JSON, wrapping in dict"
                                )
                                result = {
                                    "success": True,
                                    "data": result,
                                    "raw_output": result,
                                }

                        return result

                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"Tool {t.name} failed: {error_msg}")

                        return {
                            "error": error_msg,
                            "success": False,
                            "count": 0,
                            "emails": [],
                            "message": f"Tool execution failed: {error_msg[:200]}",
                        }

                return wrapper

            tool_map[tool.name] = make_wrapper(tool)

        logger.info(f"🔧 Created tool map with {len(tool_map)} tools")
        return tool_map

    async def _execute_locally(
        self, code: str, tool_map: Dict[str, Callable]
    ) -> Dict[str, Any]:
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
                return {
                    "status": "error",
                    "error": "Function 'execute_workflow' missing in generated code",
                    "summary": "Code generation failed",
                }

            func = global_scope["execute_workflow"]

            if asyncio.iscoroutinefunction(func):
                result = await func()
            else:
                logger.warning("execute_workflow is not async, running synchronously")
                result = func()

            if not isinstance(result, dict):
                return {
                    "status": "error",
                    "error": f"execute_workflow returned {type(result)}, expected dict",
                    "summary": "Invalid return type",
                }

            if "status" not in result:
                result["status"] = "success"

            return result

        except Exception as e:
            logger.error(f"Execution error: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "summary": f"Execution failed: {str(e)[:100]}",
            }

    async def _resolve_intent(self, messages: List[BaseMessage]) -> TaskSpec:
        system_prompt = """
            You are a task analyzer. Your job is to extract structured intent from the conversation
            and determine which tools are STRICTLY REQUIRED to complete the user's LATEST request.

            Return a JSON object with EXACTLY this structure:
            {
            "primary_goal": "Clear, concise description of what the user wants to accomplish",
            "required_tools_hint": ["communication", "planning", "content"],
            "context_variables": {"key": "string value only"},
            "last_error": null
            }

            ### TOOL SELECTION RULES (CRITICAL)

            You MUST include a tool in "required_tools_hint" ONLY if the user's request
            CANNOT be completed without that tool.

            #### Tool eligibility rules:

            1. "communication"
            Include ONLY IF the user explicitly asks to:
            - communicate with a person via email or chat

            2. "planning"
            Include ONLY IF the user explicitly asks to:
            - create, update, delete, or view calendar events
            - schedule or reschedule meetings
            - manage tasks or reminders (Google Tasks)

            3. "content"
            Include ONLY IF the user explicitly asks to:
            - create, edit, read, search, or share files
            - work with Google Docs, Sheets, Slides, Forms
            - access Google Drive content

            4. If NONE of the above conditions are met:
            - "required_tools_hint" MUST be an empty list []

            ### IMPORTANT CONSTRAINTS

            - Base your decision ONLY on the LATEST user request
            - Ignore earlier intent unless it is unfinished or caused an error
            - If the request can be answered by reasoning alone, return an empty tool list
            - Never infer tools from intent like "prepare", "think", "draft", or "explain"
            - If the user asks for advice or explanation ONLY, no tools are required

            ### CONTEXT VARIABLES

            - Include only values that are REQUIRED for downstream execution
            - ALL values MUST be strings (no numbers, booleans, objects, or arrays)
            """

        recent_messages = messages
        conversation = "\n".join([f"{m.type}: {m.content}" for m in recent_messages])

        prompt = f"{system_prompt}\n\nConversation:\n{conversation}"

        response = await self.llm.ainvoke([{"role": "user", "content": prompt}])

        json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))

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

                ctx = data.get("context_variables", {})
                if isinstance(ctx, dict):
                    sanitized["context_variables"] = {k: str(v) for k, v in ctx.items()}

                return TaskSpec(**sanitized)
            except Exception as e:
                logger.error(f"TaskSpec creation failed: {e}")

        return TaskSpec(
            primary_goal=recent_messages[-1].content if recent_messages else "No goal",
            required_tools_hint=["communication"],
            context_variables={},
            last_error=None,
        )

    async def _load_tool_schemas(self, tool_types: List[str]) -> Dict[str, Any]:
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
        
        AVAILABLE TOOLS (ALL ARE ASYNC):
        {self._format_schemas(schemas)}

        Requirements:
        1. You CANNOT use `input()` or interactive commands.
        2. You MUST use the provided MCP tools for external actions.
        3. ALL TOOL CALLS MUST BE AWAITED: `result = await tool_name(**params)`
        4. ALWAYS CHECK FOR ERRORS in tool results before processing.
        5. Return a dictionary with 'summary', 'details', 'artifacts'.
        
        Example error handling:
        ```python
        result = await get_unread_emails(date=0)
        
        # ✅ Always check for errors
        if result.get("error") or not result.get("success", True):
            return {{
                "summary": f"Failed: {{result.get('error', 'Unknown error')}}",
                "details": {{"error": result.get("error")}},
                "artifacts": []
            }}
        
        # Now safe to use result
        emails = result.get("emails", [])
        ```
        
        Follow this template strictly:
        ```python
        import asyncio
        from typing import Dict, Any, List

        async def execute_workflow() -> Dict[str, Any]:
            # Step 1: Call tool with await
            result = await tool_name(param1="value")
            
            # Step 2: Check for errors
            if result.get("error"):
                return {{
                    "summary": f"Tool failed: {{result['error']}}",
                    "details": {{"error": result["error"]}},
                    "artifacts": []
                }}
            
            # Step 3: Process successful results
            data = result.get("data", [])
            
            return {{
                "summary": f"Successfully processed {{len(data)}} items", 
                "details": {{"count": len(data), "items": data}},
                "artifacts": []
            }}
        
        if __name__ == "__main__":
            result = asyncio.run(execute_workflow())
            print(result)
        ```
        """

    async def _generate_code(self, prompt: str) -> str:
        response = await self.llm.ainvoke([{"role": "user", "content": prompt}])
        code = self._extract_code_block(response.content)

        logger.info(f"Generated code:\n{code}")
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

    def _format_schemas(
        self, schemas: Dict
    ) -> str:  # need to check if they really better than the basic json transfer
        formatted = []
        for tool_type, tools in schemas.items():
            formatted.append(f"\n# --- {tool_type.upper()} TOOLS ---")

            for tool in tools:
                name = tool["name"]
                desc = tool["description"]
                params = tool.get("parameters", {})
                props = params.get("properties", {})
                required = params.get("required", [])

                args_list = []
                for prop_name, prop_info in props.items():
                    prop_type = prop_info.get("type", "any")
                    if prop_name not in required:
                        args_list.append(
                            f"{prop_name}: {prop_type} = None"
                        )  # handle llm to know is it required or not
                    else:
                        args_list.append(f"{prop_name}: {prop_type}")

                args_str = ", ".join(args_list)
                signature = f'async def {name}({args_str}):\n    """{desc}"""'

                formatted.append(signature)

        return "\n".join(formatted)

    def _extract_code_block(self, response: str) -> str:
        """Extract code from markdown code blocks"""
        import re

        pattern = r"```python\n(.*?)\n```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1)
        return response
