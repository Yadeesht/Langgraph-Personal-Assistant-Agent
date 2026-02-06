from rag.knowledge_graph import KnowledgeGraph
import sys
from pathlib import Path

from app_mcp.core.server_init import supervisor_server
from utils.helper import setup_logger

logger = setup_logger(__name__)


@supervisor_server.tool()
def retrieve_from_knowledge_graph(query: str):
    """Perform a search through the knowledge graph using the provided query and return relevant results."""
    kg = KnowledgeGraph()
    results = kg.find_similar_with_expansion(query)
    return results


@supervisor_server.tool()
def add_information_to_knowledge_graph(Details: str):
    """Add new entities and with appropriate relationships to the knowledge graph."""

    kg = KnowledgeGraph()
    kg.add_entity(
        node_id=node_id,
        node_type=node_type,
        search_keywords=search_keywords,
        description=description,
    )
    return f"Entity '{node_id}' added to the knowledge graph."
