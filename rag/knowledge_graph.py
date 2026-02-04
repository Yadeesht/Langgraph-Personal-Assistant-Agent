import kuzu
from pathlib import Path
import json
from sentence_transformers import SentenceTransformer
from yfiles_jupyter_graphs_for_kuzu import KuzuGraphWidget
import sys
import pandas
import networkx as nx
import matplotlib.pyplot as plt

root = Path(__file__).parent.parent
sys.path.append(str(root))

from config.settings import KNOWLEDGE_GRAPH_DB
from utils.helper import setup_logger

logger = setup_logger(__name__)


class KnowledgeGraph:
    def __init__(self, db_path: str = KNOWLEDGE_GRAPH_DB):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(str(self.path))
        self.conn = kuzu.Connection(self.db)
        self.model = SentenceTransformer("BAAI/bge-small-en-v1.5")
        self._create_generic_schema()

    def _create_generic_schema(self):
        try:
            try:
                self.conn.execute("MATCH (n:Entity) RETURN n LIMIT 1")
                logger.info("Entity table already exists.")
            except Exception:
                self.conn.execute("""
                    CREATE NODE TABLE Entity(
                        id STRING, 
                        type STRING, 
                        search_keywords STRING, 
                        full_description STRING, 
                        embedding FLOAT[384], 
                        PRIMARY KEY(id)
                    )
                """)
                logger.info("Entity table created successfully.")
            try:
                self.conn.execute(
                    "CALL create_hnsw_index('Entity', 'embedding', 'cosine')"
                )
                logger.info("HNSW vector index created successfully.")
            except Exception as e:
                pass

            try:
                self.conn.execute("MATCH ()-[r:RELATED_TO]->() RETURN r LIMIT 1")
                logger.info("RELATED_TO table already exists.")
            except Exception:
                self.conn.execute("""
                    CREATE REL TABLE RELATED_TO(
                        FROM Entity TO Entity, 
                        rel_type STRING, 
                        confidence DOUBLE
                    )
                """)
                logger.info("RELATED_TO table created successfully.")
        except Exception as e:
            logger.info(f"Error creating schema: {e}")

    def execute_query(self, query: str):
        try:
            return self.conn.execute(query)
        except Exception as e:
            logger.info(f"Error executing query: {e}")
            return None

    def clear_database(self):
        try:
            self.execute_query("MATCH (n) DETACH DELETE n")
            logger.info("Database cleared successfully.")
        except Exception as e:
            logger.info(f"Error clearing database: {e}")

    def _compute_embedding(self, text: str):
        try:
            embedding = self.model.encode(text)
            if hasattr(embedding, "tolist"):
                return embedding.tolist()
            return list(embedding)
        except Exception as e:
            logger.info(f"Error computing embedding: {e}")
            return None

    def close(self):
        self.conn.close()

    def add_node(
        self, node_id: str, node_type: str, search_keywords: str, full_description: str
    ):
        try:
            existing_node_query = f"MATCH (n:Entity) WHERE n.id = '{node_id}' RETURN n"
            result = self.execute_query(existing_node_query)
            if result and result.has_next():
                logger.info(
                    f"Node with id '{node_id}' already exists. Skipping insertion."
                )
                return
            text = f"{node_id} {node_type} {search_keywords}"

            embedding = self._compute_embedding(text)

            query = f"""
            MERGE (n:Entity {{id: '{node_id}'}})
            SET n.type = '{node_type}', 
                n.search_keywords = '{search_keywords}',
                n.full_description = '{full_description}', 
                n.embedding = {embedding}
            """

            self.execute_query(query)
            logger.info(f"Node '{node_id}' upserted with keyword-dense embedding.")

        except Exception as e:
            logger.info(f"Error adding node: {e}")

    def add_relationship(
        self, source: str, target: str, rel_type: str, confidence: float = 1.0
    ):
        try:
            query = f"""
            MATCH (a:Entity), (b:Entity)
            WHERE a.id = '{source}' AND b.id = '{target}'
            CREATE (a)-[:RELATED_TO {{ rel_type: '{rel_type}', confidence: {confidence} }}]->(b)
            """
            self.execute_query(query)
        except Exception as e:
            logger.info(f"Error adding relationship: {e}")
            return

    def modify_node_attributes(self, node_id: str, attributes: dict):
        try:
            set_clauses = ", ".join(
                [f"n.{key} = '{value}'" for key, value in attributes.items()]
            )
            query = f"""
            MATCH (n:Entity) 
            WHERE n.id = '{node_id}' 
            SET {set_clauses}
            """
            self.execute_query(query)
            logger.info(f"Node '{node_id}' attributes updated successfully.")
        except Exception as e:
            logger.info(f"Error modifying node attributes: {e}")
            return

    def modify_relationship(
        self, source: str, target: str, rel_type: str, confidence: float = 1.0
    ):
        try:
            query = f"""
            MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)
            WHERE a.id = '{source}' AND b.id = '{target}'
            SET r.rel_type = '{rel_type}', r.confidence = {confidence}
            """
            self.execute_query(query)
            logger.info(
                f"Relationship from '{source}' to '{target}' updated successfully."
            )
        except Exception as e:
            logger.info(f"Error modifying relationship: {e}")
            return

    def delete_node(self, node_id: str):
        try:
            query = f"""
            MATCH (n:Entity) 
            WHERE n.id = '{node_id}' 
            DETACH DELETE n
            """
            self.execute_query(query)
            logger.info(f"Node '{node_id}' deleted successfully.")
        except Exception as e:
            logger.info(f"Error deleting node: {e}")
            return

    def delete_relationship(self, source: str, target: str):
        try:
            query = f"""
            MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)
            WHERE a.id = '{source}' AND b.id = '{target}'
            DELETE r
            """
            self.execute_query(query)
            logger.info(
                f"Relationship from '{source}' to '{target}' deleted successfully."
            )
        except Exception as e:
            logger.info(f"Error deleting relationship: {e}")
            return

    def find_similar_nodes(self, keywords: str, top_k: int = 5):
        try:
            query_embedding = self._compute_embedding(keywords)
            query = f"""
            MATCH (n:Entity) 
            WHERE n.embedding IS NOT NULL
            RETURN n.id, n.type, n.full_description, 
                   array_cosine_similarity(n.embedding, CAST({query_embedding}, 'FLOAT[384]')) AS score
            ORDER BY score DESC
            LIMIT {top_k}
            """

            result = self.execute_query(query)

            if not result:
                return []

            nodes_with_scores = []
            while result.has_next():
                row = result.get_next()
                nodes_with_scores.append(
                    {
                        "id": row[0],
                        "type": row[1],
                        "full_description": row[2],
                        "score": row[3],
                    }
                )

            return nodes_with_scores

        except Exception as e:
            logger.info(f"Error finding similar nodes: {e}")
            return []

    def find_similar_with_expansion(
        self, keywords: str, top_k: int = 5, expansion_factor: float = 0.5
    ):
        """
        Find similar nodes + their neighbors using standard Cypher matches.
        Independent of internal index names.
        """
        query_embedding = self._compute_embedding(keywords)

        query = """
            /* 1. Direct Matches (Hop 0) */
            MATCH (n:Entity)
            WHERE n.embedding IS NOT NULL
            WITH n, array_cosine_similarity(n.embedding, CAST($query_embedding, 'FLOAT[384]')) AS score
            ORDER BY score DESC
            LIMIT $top_k
            RETURN 
                n.id AS id,
                n.type AS type,
                n.full_description AS description,
                score AS base_score,
                0 AS hops,
                score AS relevance_score
            
            UNION
            
            /* 2. Direct Neighbors (Hop 1) */
            MATCH (n:Entity)
            WHERE n.embedding IS NOT NULL
            WITH n, array_cosine_similarity(n.embedding, CAST($query_embedding, 'FLOAT[384]')) AS score
            ORDER BY score DESC
            LIMIT $top_k
            MATCH (n)-[r]-(neighbor)
            RETURN 
                neighbor.id AS id,
                neighbor.type AS type,
                neighbor.full_description AS description,
                score AS base_score,
                1 AS hops,
                CAST(score * $expansion_factor, 'FLOAT') AS relevance_score
            """

        result = self.conn.execute(
            query,
            parameters={
                "query_embedding": query_embedding,
                "top_k": top_k,
                "expansion_factor": expansion_factor,
            },
        )

        df = result.get_as_df()

        if not df.empty:
            df = df.sort_values(by="relevance_score", ascending=False)
            df = df.drop_duplicates(subset=["id"], keep="first")

        return df

    def preprocess_graph(self):
        try:
            query = (
                "MATCH (n:Entity) WHERE n.embedding IS NULL RETURN n.id, n.description"
            )
            result = self.execute_query(query)

            while result.has_next():
                row = result.get_next()
                node_id, description = row[0], row[1]
                embedding = self._compute_embedding(description)
                update_query = f"MATCH (n:Entity) WHERE n.id = '{node_id}' SET n.embedding = {embedding}"
                self.execute_query(update_query)

            logger.info("Graph preprocessing complete: All nodes have embeddings.")
        except Exception as e:
            logger.info(f"Error during graph preprocessing: {e}")

    def generate_prompt(self, question: str, context: list):
        context_str = "\n".join(
            [
                f"Node: {c['node']}, Subgraph: {json.dumps(c['subgraph'], indent=2)}"
                for c in context
            ]
        )
        prompt = f"""
        You are an AI assistant. Answer the following question based on the provided graph data.

        Question: {question}

        Graph Data:
        {context_str}

        Answer:
        """
        return prompt

    def visualize(self, output_path: str = "docs/knowledge_graph.png"):
        try:
            nodes_res = self.conn.execute("MATCH (n:Entity) RETURN n.id, n.type")
            rels_res = self.conn.execute(
                "MATCH (a)-[r]->(b) RETURN a.id, b.id, r.rel_type"
            )

            G = nx.DiGraph()
            node_colors = []

            color_map = {
                "Project": "#2ecc71",
                "Organization": "#3498db",
                "Tool": "#f1c40f",
                "Person": "#e67e22",
            }

            while nodes_res.has_next():
                node_id, n_type = nodes_res.get_next()
                G.add_node(node_id, type=n_type)
                node_colors.append(color_map.get(n_type, "#95a5a6"))

            while rels_res.has_next():
                u, v, rel_type = rels_res.get_next()
                G.add_edge(u, v, label=rel_type)

            plt.figure(figsize=(16, 10))

            pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)

            nx.draw_networkx_nodes(
                G, pos, node_size=3000, node_color=node_colors, alpha=0.9
            )
            nx.draw_networkx_labels(G, pos, font_size=10, font_weight="bold")

            nx.draw_networkx_edges(
                G,
                pos,
                edgelist=G.edges(),
                edge_color="#bdc3c7",
                arrowsize=20,
                connectionstyle="arc3, rad=0.1",
            )

            edge_labels = nx.get_edge_attributes(G, "label")
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

            plt.title("Knowledge Graph", fontsize=15)
            plt.axis("off")
            plt.tight_layout()
            plt.savefig(output_path, dpi=300)
            print(f"✅ Visualization saved with improved spacing: {output_path}")

        except Exception as e:
            print(f"Error during visualization: {e}")
