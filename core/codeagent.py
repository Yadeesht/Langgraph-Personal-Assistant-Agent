"""
Code Execution Agent - For complex multi-tool workflows
Uses code generation to orchestrate MCP tools efficiently
"""

from pathlib import Path

import asyncio
import tempfile
import subprocess
from typing import Dict, Any, List
from utils.helper import setup_logger

logger = setup_logger(__name__)


class CodeExecutionAgent:
    """
    Agent that generates and executes code to orchestrate MCP tools
    Use for complex workflows that would otherwise require many supervisor iterations
    """

    def __init__(self, llm_client, mcp_clients: Dict[str, Any]):
        self.llm = llm_client
        self.mcp_clients = mcp_clients
        self.sandbox_path = Path(tempfile.gettempdir()) / "mcp_sandbox"
        self.sandbox_path.mkdir(exist_ok=True)

    async def execute_workflow(
        self, task: str, required_tools: List[str]
    ) -> Dict[str, Any]:
        """
        Generate and execute code for complex multi-tool workflows

        Args:
            task: Natural language description of the workflow
            required_tools: List of tool types needed (e.g., ['gmail', 'gdrive', 'sheets'])

        Returns:
            Dict with execution results and summary
        """
        logger.info(f"Code execution workflow requested: {task}")

        # Step 1: Load only required tool schemas
        tool_schemas = await self._load_tool_schemas(required_tools)

        # Step 2: Generate code with LLM
        code_prompt = self._build_code_generation_prompt(task, tool_schemas)
        generated_code = await self._generate_code(code_prompt)

        # Step 3: Execute in sandbox
        execution_result = await self._execute_in_sandbox(generated_code)

        # Step 4: Summarize results (only return essentials to model)
        summary = await self._summarize_results(execution_result)

        return {
            "status": "success",
            "summary": summary,
            "full_output": execution_result,
            "tokens_saved": self._estimate_token_savings(execution_result, summary),
        }

    async def _load_tool_schemas(self, tool_types: List[str]) -> Dict[str, Any]:
        """Load only the schemas for required tool types"""
        schemas = {}
        for tool_type in tool_types:
            if tool_type in self.mcp_clients:
                client = self.mcp_clients[tool_type]
                tools = await client.get_tools()
                schemas[tool_type] = [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.inputSchema,
                    }
                    for t in tools
                ]
        return schemas

    def _build_code_generation_prompt(self, task: str, schemas: Dict) -> str:
        """Build prompt for code generation"""
        return f"""
            Generate Python code to accomplish this task: {task}

            Available MCP tools:
            {self._format_schemas(schemas)}

            Requirements:
            1. Import necessary MCP clients
            2. Call tools in the correct sequence
            3. Handle errors gracefully
            4. Return a structured result dict with:
            - 'summary': Brief summary of what was accomplished
            - 'details': Key metrics/data points
            - 'artifacts': List of created resources (IDs, links)

            Use this template:
            ```python
            import asyncio
            from typing import Dict, Any

            async def execute_workflow() -> Dict[str, Any]:
                # Your code here
                return {{
                    "summary": "...",
                    "details": {{}},
                    "artifacts": []
                }}

            if __name__ == "__main__":
                result = asyncio.run(execute_workflow())
                print(result)
            ```

            Generate only the code, no explanations.
            """

    async def _generate_code(self, prompt: str) -> str:
        """Generate code using LLM"""
        # Use your LLM client to generate code
        response = await self.llm.generate(prompt)
        # Extract code from response
        code = self._extract_code_block(response)
        return code

    async def _execute_in_sandbox(self, code: str) -> Dict[str, Any]:
        """Execute generated code in a sandboxed environment"""
        script_path = self.sandbox_path / "workflow_script.py"

        try:
            # Write code to file
            script_path.write_text(code)

            # Execute with timeout and resource limits
            result = subprocess.run(
                ["python", str(script_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=str(self.sandbox_path),
            )

            if result.returncode == 0:
                # Parse output
                import json

                output = json.loads(result.stdout)
                return output
            else:
                logger.error(f"Code execution failed: {result.stderr}")
                return {"error": result.stderr}

        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return {"error": str(e)}
        finally:
            # Cleanup
            if script_path.exists():
                script_path.unlink()

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

    def _estimate_token_savings(self, full_output: Dict, summary: str) -> int:
        """Estimate tokens saved by using code execution"""
        # Rough estimate: 4 chars per token
        full_tokens = len(str(full_output)) // 4
        summary_tokens = len(summary) // 4
        return full_tokens - summary_tokens

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
