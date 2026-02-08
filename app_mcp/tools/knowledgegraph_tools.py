from rag.knowledge_graph import KnowledgeGraph
import sys
from pathlib import Path
import asyncio

from app_mcp.core.server_init import supervisor_server
from utils.helper import setup_logger
import logging

logger = setup_logger(__name__)

_kg_instance = None


def get_kg_instance():
    global _kg_instance
    if _kg_instance is None:
        try:
            _kg_instance = KnowledgeGraph()
        except Exception as e:
            logger.error(f"Failed to initialize KnowledgeGraph: {e}")
            raise
    return _kg_instance


@supervisor_server.tool()
async def retrieve_from_knowledge_graph(query: str):
    """
    Query the internal Knowledge Graph to retrieve context about specific entities (Person, Project, Organization, Tool, Concept, Event, Resource).

    Args:
        query: Search string or entity reference used to locate related knowledge graph nodes.
    """
    try:
        kg = get_kg_instance()
        results = await asyncio.to_thread(kg.find_similar_with_expansion, query)
        await asyncio.to_thread(kg.visualize)
        return results
    except Exception as e:
        logger.error(f"Error retrieving from knowledge graph: {e}")
        return f"Error retrieving from knowledge graph: {e}"


@supervisor_server.tool()
async def add_information_to_knowledge_graph(details: str):
    """
    Persist new information as structured knowledge within the internal Knowledge Graph for long-term contextual retrieval.

    Args:
        details: Text description containing facts, relationships, or updates to be stored.
    """
    try:
        kg = get_kg_instance()

        explicitly_request_prompt = """
            "Extract all entities and relationships from the following text as a structured Knowledge Graph. "
            "The user is explicitly providing this information for storage. "
            "Return the output strictly in the requested JSON format."

            ### ONE-SHOT EXAMPLE
            "Yadeesh: Hey, I want to add some information about my friend Raajan. He is a collaborator of mine in a college club. His email is raanjan@gmail.com"

            **Output JSON:**
            {
            "candidates": {
                "entities": [
                {
                    "id": "Raajan",
                    "type": "Person",
                    "description": "Collaborator of Yadeesh in a college club; email: raanjan@gmail.com",
                    "search_keywords": ["raanjan", "raanjan@gmail.com", "college club"]
                }
                ],
                "relationships": [
                {
                    "source": "Yadeesh",
                    "target": "Raajan",
                    "relation_type": "WORKS_WITH"
                }
                ]
            }
            }     
        """

        candidates_json = await asyncio.to_thread(
            kg.generate_entity_relation, details, explicitly_request_prompt
        )

        entities = candidates_json.get("candidates", {}).get("entities", [])

        if not entities:
            logger.info("No entities extracted from the provided details.")
            return "No entities extracted from the provided details."

        types_df = await asyncio.to_thread(kg.search_similar_node, entities)

        final_update_json = kg.validate_entity_relation(types_df, candidates_json)
        resolution = final_update_json.get("resolution", {})

        if not resolution.get("entities") and not resolution.get("relationships"):
            logger.info("No valid entities to add after validation.")
            return "No valid entities to add after validation. so this information is already exist in knowledge graph."

        for entity in resolution.get("entities", []):
            action = entity.get("action", "DISCARD").upper()

            if action == "CREATE":
                await asyncio.to_thread(
                    kg.add_entity,
                    node_id=entity["id"],
                    node_type=entity.get("type", "unknown"),
                    search_keywords=", ".join(entity.get("keywords", [])),
                    description=entity.get("description", ""),
                )
            elif action == "UPDATE":
                await asyncio.to_thread(
                    kg.add_entity,
                    node_id=entity["id"],
                    node_type=entity.get("type", "unknown"),
                    search_keywords=", ".join(entity.get("keywords", [])),
                    description=entity.get("description", ""),
                )

        for rel in resolution.get("relationships", []):
            action = rel.get("action", "DISCARD").upper()

            if action == "CREATE":
                await asyncio.to_thread(
                    kg.add_relationship,
                    source=rel["source"],
                    target=rel["target"],
                    relation_type=rel.get("relation_type", "unknown"),
                )
            elif action == "UPDATE":
                await asyncio.to_thread(
                    kg.modify_relationship,
                    source=rel["source"],
                    target=rel["target"],
                    relation_type=rel.get("relation_type", "unknown"),
                )
        await asyncio.to_thread(kg.visualize)
        return "Information added/updated successfully in the knowledge graph."
    except Exception as e:
        logger.error(f"Error adding information to knowledge graph: {e}")
        return f"Error adding information to knowledge graph: {e}"
