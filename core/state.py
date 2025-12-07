from typing import Annotated, Literal, Optional

from langgraph.graph import END
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


class State(TypedDict):
    messages: Annotated[list, add_messages]

    next: Optional[str]


class Route(BaseModel):
    """
    Supervisor's decision.
    - If 'next' is chosen, we route to a worker.
    - If 'direct_reply' is chosen, we answer the user direclty when no tools are needed.
    """

    step: Optional[Literal["communication_agent", "productivity_agent"]] = None
    direct_reply: Optional[str] = None


def route_after_supervisor(state: State):
    next_dest = state.get("next")

    # If Supervisor chose to reply directly, we exit the graph
    if next_dest == "__end__":
        return END

    if next_dest:
        return next_dest

    return END
