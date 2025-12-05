from typing import Literal
from pydantic import BaseModel
from langchain_core.messages import SystemMessage
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from core.agent import agent_node_factory
from core.llm import build_llm_with_tools
from core.state import State


class Route(BaseModel):
    """Route decision for supervisor"""

    step: Literal["communication_agent", "calendar_agent", "productivity_agent"]


def build_graph(tool_sets, checkpointer):
    comm_tools = tool_sets["communication"]
    prod_tools = tool_sets["productivity"]

    comm_llm = build_llm_with_tools(comm_tools)
    prod_llm = build_llm_with_tools(prod_tools)
    supervisor_llm = build_llm_with_tools([])

    comm_agent_node = agent_node_factory(comm_llm)
    prod_agent_node = agent_node_factory(prod_llm)

    def supervisor_node(State):
        messages = State["messages"]

        system_prompt = (
            "You are a supervisor managing three specialized workers:\n\n"
            "1. **Communication Agent**: Handles emails all forms of communication.\n"
            "   - Use when: sending messages, checking emails, reaching out to people, communication tasks\n\n"
            "3. **Productivity Agent**: Handles tasks, todos, project management (calender).\n"
            "   - Use when: creating tasks, managing todos, project tracking, productivity queries\n\n"
            "Analyze the user's request and decide which agent is most appropriate to handle it.\n"
            "Consider the intent and context, not just keywords."
        )

        router = supervisor_llm.with_structured_output(Route)

        response = router.invoke([SystemMessage(content=system_prompt)] + messages)

        return {"next": response.step}

    def route_after_supervisor(state: State):
        return state.get("next", "communication_agent")

    builder = StateGraph(State)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("communication_agent", comm_agent_node)
    builder.add_node("productivity_agent", prod_agent_node)

    builder.add_node("comm_tools", ToolNode(tools=comm_tools))
    builder.add_node("prod_tools", ToolNode(tools=prod_tools))

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", route_after_supervisor)

    builder.add_conditional_edges(
        "communication_agent", tools_condition, {"tools": "comm_tools", END: END}
    )
    builder.add_edge("comm_tools", "communication_agent")

    builder.add_conditional_edges(
        "productivity_agent", tools_condition, {"tools": "prod_tools", END: END}
    )
    builder.add_edge("prod_tools", "productivity_agent")

    graph = builder.compile(checkpointer=checkpointer)
    return graph
