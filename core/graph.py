from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from config.prompts import (
    COMMUNICATION_SYSTEM_PROMPT,
    PLANNING_SYSTEM_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
    DOCUMENT_SYSTEM_PROMPT,
    PRESENTATION_SYSTEM_PROMPT,
    DATA_SYSTEM_PROMPT,
)
from core.agent import (
    agent_node_factory,
    code_execution_factory,
    memory_node_factory,
    summerizer_node,
    supervisor_node_factory,
    route_to_agent,
    work_completion,
)
from core.state import (
    State,
    internal_agent_route,
    route_after_supervisor,
    route_after_supervisor_tools,
    route_after_communication_tools,
    route_after_planning_tools,
    route_after_document_tools,
    route_after_data_tools,
    route_after_presentation_tools,
    route_start,
)
from core.llm import build_llm, build_llm_with_tools
from utils.helper import setup_logger

logger = setup_logger(__name__)


def build_graph(tool_sets, checkpointer):
    supervisor_tools = tool_sets.get("supervisor", [])
    communication_tools = tool_sets.get("communication", [])
    planning_tools = tool_sets.get("planning", [])
    content_tools = tool_sets["content"]

    document_tools = [
        t
        for t in content_tools
        if any(
            keyword in t.name.lower() for keyword in ["doc", "drive", "table", "file"]
        )
    ]

    data_tools = [
        t
        for t in content_tools
        if any(
            keyword in t.name.lower() for keyword in ["sheet", "form", "spreadsheet"]
        )
    ]

    presentation_tools = [
        t
        for t in content_tools
        if any(
            keyword in t.name.lower() for keyword in ["presentation", "page", "slide"]
        )
    ]

    logger.info(
        f"🔧 Filtered Tools -> Docs: {len(document_tools)} | Data: {len(data_tools)} | Slides: {len(presentation_tools)}"
    )

    supervisor_tools = list(supervisor_tools) + [route_to_agent]
    communication_tools = list(communication_tools) + [work_completion]
    planning_tools = list(planning_tools) + [work_completion]
    document_tools = list(document_tools) + [work_completion]
    data_tools = list(data_tools) + [work_completion]
    presentation_tools = list(presentation_tools) + [work_completion]

    communication_llm = build_llm_with_tools(communication_tools)
    planning_llm = build_llm_with_tools(planning_tools)
    supervisor_llm = build_llm_with_tools(supervisor_tools)
    code_agent_llm = build_llm()
    document_agent_llm = build_llm_with_tools(document_tools)
    presentation_agent_llm = build_llm_with_tools(presentation_tools)
    data_agent_llm = build_llm_with_tools(data_tools)

    communication_agent_node = agent_node_factory(
        communication_llm, COMMUNICATION_SYSTEM_PROMPT, agent_name="communication_agent"
    )
    planning_agent_node = agent_node_factory(
        planning_llm, PLANNING_SYSTEM_PROMPT, agent_name="planning_agent"
    )
    code_agent_node = code_execution_factory(
        llm=code_agent_llm,
        tool_sets=tool_sets,
        agent_name="code_agent",
    )

    document_agent_node = agent_node_factory(
        llm_with_tools=document_agent_llm,
        system_prompt=DOCUMENT_SYSTEM_PROMPT,
        agent_name="document_agent",
    )

    presentation_agent_node = agent_node_factory(
        llm_with_tools=presentation_agent_llm,
        system_prompt=PRESENTATION_SYSTEM_PROMPT,
        agent_name="presentation_agent",
    )

    data_agent_node = agent_node_factory(
        llm_with_tools=data_agent_llm,
        system_prompt=DATA_SYSTEM_PROMPT,
        agent_name="data_agent",
    )

    memory_update_node = memory_node_factory()

    supervisor_node = supervisor_node_factory(
        llm_with_tools=supervisor_llm,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        agent_name="supervisor",
    )

    builder = StateGraph(State)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("communication_agent", communication_agent_node)
    builder.add_node("planning_agent", planning_agent_node)
    builder.add_node("code_agent", code_agent_node)
    builder.add_node("summerizer_node", summerizer_node)
    builder.add_node("document_agent", document_agent_node)
    builder.add_node("presentation_agent", presentation_agent_node)
    builder.add_node("data_agent", data_agent_node)
    builder.add_node(
        "communication_tools",
        ToolNode(tools=communication_tools, handle_tool_errors=True),
    )
    builder.add_node(
        "planning_tools",
        ToolNode(tools=planning_tools, handle_tool_errors=True),
    )
    builder.add_node(
        "supervisor_tools",
        ToolNode(tools=supervisor_tools, handle_tool_errors=True),
    )
    builder.add_node(
        "document_tools",
        ToolNode(tools=document_tools, handle_tool_errors=True),
    )
    builder.add_node(
        "presentation_tools",
        ToolNode(tools=presentation_tools, handle_tool_errors=True),
    )
    builder.add_node(
        "data_tools",
        ToolNode(tools=data_tools, handle_tool_errors=True),
    )

    builder.add_node("memory_update_node", memory_update_node)

    builder.add_conditional_edges(
        source=START,
        path=route_start,
        path_map={
            "communication_agent": "communication_agent",
            "planning_agent": "planning_agent",
            "document_agent": "document_agent",
            "presentation_agent": "presentation_agent",
            "data_agent": "data_agent",
            "summerizer_node": "summerizer_node",
            "memory_update_node": "memory_update_node",
            "supervisor": "supervisor",
        },
    )

    builder.add_edge("summerizer_node", "supervisor")
    builder.add_edge("memory_update_node", "supervisor")

    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "communication_agent": "communication_agent",
            "planning_agent": "planning_agent",
            "document_agent": "document_agent",
            "presentation_agent": "presentation_agent",
            "data_agent": "data_agent",
            "code_agent": "code_agent",
            "supervisor_tools": "supervisor_tools",
            "supervisor": "supervisor",  # for tool fail fallback to same node and ask the LLM to re-decide
            "FINISH": END,
        },
    )

    builder.add_conditional_edges(
        "supervisor_tools",
        route_after_supervisor_tools,
        {
            "communication_agent": "communication_agent",
            "planning_agent": "planning_agent",
            "document_agent": "document_agent",
            "presentation_agent": "presentation_agent",
            "data_agent": "data_agent",
            "code_agent": "code_agent",
            "supervisor": "supervisor",
        },
    )

    builder.add_edge("code_agent", "supervisor")

    builder.add_conditional_edges(
        "communication_agent",
        internal_agent_route,
        {
            "tools": "communication_tools",
            "supervisor": "supervisor",
            "END": END,
        },
    )

    builder.add_conditional_edges(
        "communication_tools",
        route_after_communication_tools,
        {
            "communication_agent": "communication_agent",
            "supervisor": "supervisor",
        },
    )

    builder.add_conditional_edges(
        "planning_agent",
        internal_agent_route,
        {
            "tools": "planning_tools",
            "supervisor": "supervisor",
            "END": END,
        },
    )

    builder.add_conditional_edges(
        "planning_tools",
        route_after_planning_tools,
        {
            "planning_agent": "planning_agent",
            "supervisor": "supervisor",
        },
    )

    builder.add_conditional_edges(
        "document_agent",
        internal_agent_route,
        {"tools": "document_tools", "supervisor": "supervisor", "END": END},
    )

    builder.add_conditional_edges(
        "document_tools",
        route_after_document_tools,
        {
            "document_agent": "document_agent",
            "supervisor": "supervisor",
        },
    )

    builder.add_conditional_edges(
        "data_agent",
        internal_agent_route,
        {"tools": "data_tools", "supervisor": "supervisor", "END": END},
    )

    builder.add_conditional_edges(
        "data_tools",
        route_after_data_tools,
        {
            "data_agent": "data_agent",
            "supervisor": "supervisor",
        },
    )

    builder.add_conditional_edges(
        "presentation_agent",
        internal_agent_route,
        {"tools": "presentation_tools", "supervisor": "supervisor", "END": END},
    )

    builder.add_conditional_edges(
        "presentation_tools",
        route_after_presentation_tools,
        {
            "presentation_agent": "presentation_agent",
            "supervisor": "supervisor",
        },
    )

    graph = builder.compile(checkpointer=checkpointer)
    return graph
