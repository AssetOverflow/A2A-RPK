<!-- @format -->

# Implementation Starter Kit: Biblical Agentic RAG System

## Quick Start Implementation Guide

This document provides immediate, actionable steps to begin implementing the biblical agentic RAG + knowledge graph system based on proven patterns from leading repositories.

## Phase 1: Foundation Setup (Week 1-2)

### 1.1 Environment Setup

```bash
# Create project structure
mkdir biblical-agentic-rag
cd biblical-agentic-rag

# Core directories
mkdir -p {src/{agents,rag,knowledge_graph,tools,evaluation},data/{biblical_texts,commentaries},config,tests}

# Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### requirements.txt

```txt
# Core dependencies
langchain==0.3.3
langchain-community==0.3.2
langchain-openai==0.2.2
langgraph==0.2.39
pydantic>=2.0.0
neo4j==5.21.0
psycopg2-binary>=2.9.0
pgvector>=0.2.0

# Kafka for A2A-RPK
kafka-python>=2.0.0
avro-python3>=1.11.0

# Biblical text processing
python-biblical-text>=1.0.0
hebrew-transliteration>=1.0.0
greek-text-processor>=0.5.0

# ML and embeddings
openai>=1.0.0
sentence-transformers>=3.2.0
torch>=2.0.0
numpy>=1.24.0

# Monitoring and evaluation
comet-ml>=3.47.0
streamlit>=1.39.0
plotly>=5.0.0

# Development
pytest>=7.0.0
black>=23.0.0
mypy>=1.0.0
```

### 1.2 Basic Configuration

#### config/settings.py

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""

    # Database connections
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str

    postgres_uri: str = "postgresql://user:password@localhost:5432/biblical_rag"

    # AI Services
    openai_api_key: str

    # Kafka (A2A-RPK)
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_prefix: str = "biblical_study"

    # Monitoring
    comet_api_key: Optional[str] = None
    experiment_project_name: str = "biblical-agentic-rag"

    # Application
    debug: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

# Global settings instance
settings = Settings()
```

### 1.3 Knowledge Graph Foundation

#### src/knowledge_graph/entities.py

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import uuid

class BiblicalEntityType(Enum):
    PERSON = "Person"
    PLACE = "Place"
    EVENT = "Event"
    CONCEPT = "Concept"
    BOOK = "Book"
    PROPHECY = "Prophecy"
    THEME = "Theme"

class RelationshipType(Enum):
    AUTHORED = "AUTHORED"
    LOCATED_IN = "LOCATED_IN"
    OCCURRED_AT = "OCCURRED_AT"
    DESCENDANT_OF = "DESCENDANT_OF"
    CONTEMPORARY_OF = "CONTEMPORARY_OF"
    REFERENCES = "REFERENCES"
    FULFILLS = "FULFILLS"
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"

@dataclass
class BiblicalEntity:
    """Core biblical entity"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    entity_type: BiblicalEntityType = BiblicalEntityType.CONCEPT
    properties: Dict[str, str] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    source_references: List[str] = field(default_factory=list)
    confidence_score: float = 1.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "properties": self.properties,
            "aliases": self.aliases,
            "description": self.description,
            "source_references": self.source_references,
            "confidence_score": self.confidence_score
        }

@dataclass
class BiblicalRelationship:
    """Relationship between biblical entities"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    relationship_type: RelationshipType = RelationshipType.RELATED_TO
    properties: Dict[str, str] = field(default_factory=dict)
    confidence_score: float = 1.0
    source_references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type.value,
            "properties": self.properties,
            "confidence_score": self.confidence_score,
            "source_references": self.source_references
        }
```

#### src/knowledge_graph/graph_client.py

```python
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .entities import BiblicalEntity, BiblicalRelationship, BiblicalEntityType, RelationshipType
from config.settings import settings

class BiblicalKnowledgeGraph:
    """Biblical knowledge graph client following pdichone patterns"""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._setup_constraints_and_indexes()

    def close(self):
        """Close the driver"""
        if self.driver:
            self.driver.close()

    def _setup_constraints_and_indexes(self):
        """Setup Neo4j constraints and indexes"""
        with self.driver.session() as session:
            # Constraints
            session.run("""
                CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.id IS UNIQUE
            """)

            session.run("""
                CREATE CONSTRAINT relationship_id_unique IF NOT EXISTS
                FOR (r:Relationship) REQUIRE r.id IS UNIQUE
            """)

            # Full-text index for entity search
            session.run("""
                CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
                FOR (e:Entity) ON EACH [e.name, e.aliases, e.description]
            """)

            # Property indexes
            session.run("""
                CREATE INDEX entity_type_index IF NOT EXISTS
                FOR (e:Entity) ON (e.entity_type)
            """)

    async def add_entity(self, entity: BiblicalEntity) -> bool:
        """Add entity to knowledge graph"""
        def _add_entity_sync(tx, entity_data):
            tx.run("""
                MERGE (e:Entity {id: $id})
                SET e.name = $name,
                    e.entity_type = $entity_type,
                    e.aliases = $aliases,
                    e.description = $description,
                    e.properties = $properties,
                    e.confidence_score = $confidence_score,
                    e.source_references = $source_references
            """, entity_data)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                lambda: self.driver.session().execute_write(_add_entity_sync, entity.to_dict())
            )
            return True
        except Exception as e:
            print(f"Error adding entity: {e}")
            return False

    async def add_relationship(self, relationship: BiblicalRelationship) -> bool:
        """Add relationship to knowledge graph"""
        def _add_relationship_sync(tx, rel_data):
            tx.run("""
                MATCH (source:Entity {id: $source_id})
                MATCH (target:Entity {id: $target_id})
                MERGE (source)-[r:RELATIONSHIP {id: $id}]->(target)
                SET r.relationship_type = $relationship_type,
                    r.properties = $properties,
                    r.confidence_score = $confidence_score,
                    r.source_references = $source_references
            """, rel_data)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                lambda: self.driver.session().execute_write(_add_relationship_sync, relationship.to_dict())
            )
            return True
        except Exception as e:
            print(f"Error adding relationship: {e}")
            return False

    async def find_entities_fulltext(self, query: str, limit: int = 10) -> List[BiblicalEntity]:
        """Find entities using full-text search (pdichone pattern)"""
        def _search_entities_sync(tx, search_query, limit):
            # Generate fuzzy search query
            words = search_query.lower().strip().split()
            fuzzy_query = " AND ".join([f"{word}~2" for word in words if word])

            result = tx.run("""
                CALL db.index.fulltext.queryNodes('entity_fulltext', $query)
                YIELD node, score
                RETURN node, score
                ORDER BY score DESC
                LIMIT $limit
            """, {"query": fuzzy_query, "limit": limit})

            entities = []
            for record in result:
                node = record["node"]
                entity = BiblicalEntity(
                    id=node["id"],
                    name=node["name"],
                    entity_type=BiblicalEntityType(node["entity_type"]),
                    properties=node.get("properties", {}),
                    aliases=node.get("aliases", []),
                    description=node.get("description", ""),
                    confidence_score=node.get("confidence_score", 1.0),
                    source_references=node.get("source_references", [])
                )
                entities.append(entity)

            return entities

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                lambda: self.driver.session().execute_read(_search_entities_sync, query, limit)
            )
        except Exception as e:
            print(f"Error searching entities: {e}")
            return []

    async def get_entity_neighborhood(self, entity_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """Get entity neighborhood for multi-hop reasoning (pdichone pattern)"""
        def _get_neighborhood_sync(tx, entity_id, max_depth):
            result = tx.run("""
                MATCH (start:Entity {id: $entity_id})
                CALL {
                    WITH start
                    MATCH (start)-[r:RELATIONSHIP]-(neighbor:Entity)
                    RETURN start.name + ' - ' + r.relationship_type + ' -> ' + neighbor.name AS output,
                           neighbor.id AS neighbor_id,
                           r.relationship_type AS relation_type
                    UNION ALL
                    WITH start
                    MATCH (start)<-[r:RELATIONSHIP]-(neighbor:Entity)
                    RETURN neighbor.name + ' - ' + r.relationship_type + ' -> ' + start.name AS output,
                           neighbor.id AS neighbor_id,
                           r.relationship_type AS relation_type
                }
                RETURN output, neighbor_id, relation_type
                LIMIT 50
            """, {"entity_id": entity_id})

            relationships = []
            neighbors = []

            for record in result:
                relationships.append(record["output"])
                neighbors.append({
                    "id": record["neighbor_id"],
                    "relation_type": record["relation_type"]
                })

            return {
                "entity_id": entity_id,
                "relationships": relationships,
                "neighbors": neighbors,
                "depth": max_depth
            }

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                lambda: self.driver.session().execute_read(_get_neighborhood_sync, entity_id, max_depth)
            )
        except Exception as e:
            print(f"Error getting neighborhood: {e}")
            return {"entity_id": entity_id, "relationships": [], "neighbors": []}
```

### 1.4 Vector Store with pgvectorscale

#### src/rag/vector_store.py

```python
import psycopg2
from pgvector.psycopg2 import register_vector
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
import asyncio
import aiopg
from langchain_openai import OpenAIEmbeddings

from config.settings import settings

class PgvectorscaleBiblicalStore:
    """Biblical text vector store using pgvectorscale"""

    def __init__(self, connection_string: str = None):
        self.conn_str = connection_string or settings.postgres_uri
        self.embedding_model = OpenAIEmbeddings(openai_api_key=settings.openai_api_key)
        self._setup_database()

    def _setup_database(self):
        """Setup pgvectorscale database and tables"""
        with psycopg2.connect(self.conn_str) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                # Create extensions
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE")

                # Biblical texts table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS biblical_texts (
                        id SERIAL PRIMARY KEY,
                        book VARCHAR(50) NOT NULL,
                        chapter INTEGER NOT NULL,
                        verse INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        translation VARCHAR(20) NOT NULL DEFAULT 'ESV',
                        language VARCHAR(10) NOT NULL DEFAULT 'en',
                        embedding vector(1536),
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Vectorscale index for similarity search
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS biblical_texts_embedding_idx
                    ON biblical_texts USING vectorscale (embedding)
                    WITH (quantization_type = 'fp16')
                """)

                # Commentary and cross-references table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS biblical_commentaries (
                        id SERIAL PRIMARY KEY,
                        reference VARCHAR(100) NOT NULL,
                        author VARCHAR(100),
                        title VARCHAR(200),
                        content TEXT NOT NULL,
                        commentary_type VARCHAR(50) DEFAULT 'exegetical',
                        embedding vector(1536),
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS commentaries_embedding_idx
                    ON biblical_commentaries USING vectorscale (embedding)
                    WITH (quantization_type = 'fp16')
                """)

    async def add_biblical_text(self, book: str, chapter: int, verse: int,
                               text: str, translation: str = "ESV",
                               language: str = "en", metadata: Dict = None):
        """Add biblical text with embedding"""
        # Generate embedding
        embedding = await self.embedding_model.aembed_query(text)

        # Use connection pool for async operations
        async with aiopg.connect(self.conn_str) as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO biblical_texts
                    (book, chapter, verse, text, translation, language, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (book, chapter, verse, text, translation, language,
                      embedding, metadata or {}))

    async def semantic_search(self, query: str, k: int = 10,
                            filters: Dict[str, Any] = None) -> List[Tuple[str, float]]:
        """Semantic search using pgvectorscale"""
        # Generate query embedding
        query_embedding = await self.embedding_model.aembed_query(query)

        # Build filter conditions
        where_conditions = []
        params = [query_embedding, k]

        if filters:
            if 'book' in filters:
                where_conditions.append("book = %s")
                params.insert(-1, filters['book'])

            if 'translation' in filters:
                where_conditions.append("translation = %s")
                params.insert(-1, filters['translation'])

            if 'chapter_range' in filters:
                where_conditions.append("chapter BETWEEN %s AND %s")
                params.insert(-2, filters['chapter_range'][0])
                params.insert(-1, filters['chapter_range'][1])

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Execute search
        async with aiopg.connect(self.conn_str) as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    SELECT
                        book || ' ' || chapter || ':' || verse AS reference,
                        text,
                        translation,
                        1 - (embedding <=> %s) AS similarity,
                        metadata
                    FROM biblical_texts
                    {where_clause}
                    ORDER BY embedding <=> %s
                    LIMIT %s
                """, params)

                results = []
                async for row in cur:
                    reference, text, translation, similarity, metadata = row
                    formatted_result = f"{reference} ({translation}): {text}"
                    results.append((formatted_result, similarity))

                return results

    async def hybrid_search(self, query: str, k: int = 10) -> List[Tuple[str, float, str]]:
        """Hybrid search across biblical texts and commentaries"""
        # Search biblical texts
        biblical_results = await self.semantic_search(query, k=k//2)

        # Search commentaries
        query_embedding = await self.embedding_model.aembed_query(query)

        async with aiopg.connect(self.conn_str) as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT
                        reference,
                        author,
                        title,
                        content,
                        1 - (embedding <=> %s) AS similarity,
                        commentary_type
                    FROM biblical_commentaries
                    ORDER BY embedding <=> %s
                    LIMIT %s
                """, (query_embedding, query_embedding, k//2))

                commentary_results = []
                async for row in cur:
                    reference, author, title, content, similarity, comm_type = row
                    formatted_result = f"Commentary on {reference} by {author}: {content[:200]}..."
                    commentary_results.append((formatted_result, similarity, "commentary"))

        # Combine results
        all_results = [(text, score, "biblical") for text, score in biblical_results]
        all_results.extend(commentary_results)

        # Sort by similarity
        all_results.sort(key=lambda x: x[1], reverse=True)

        return all_results[:k]
```

### 1.5 Simple Agentic RAG Implementation

#### src/rag/agentic_rag.py

```python
from typing import Dict, List, Any, Optional
import asyncio
import time
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .vector_store import PgvectorscaleBiblicalStore
from ..knowledge_graph.graph_client import BiblicalKnowledgeGraph
from config.settings import settings

@dataclass
class ResearchContext:
    """Context for agentic research process"""
    query: str
    structured_results: List[Dict] = field(default_factory=list)
    vector_results: List[tuple] = field(default_factory=list)
    reasoning_steps: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    iteration: int = 0

class SimpleAgenticRAG:
    """Simple agentic RAG following mlvanguards patterns"""

    def __init__(self,
                 vector_store: PgvectorscaleBiblicalStore,
                 knowledge_graph: BiblicalKnowledgeGraph,
                 max_iterations: int = 3):
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph
        self.max_iterations = max_iterations
        self.llm = ChatOpenAI(
            openai_api_key=settings.openai_api_key,
            temperature=0.1,
            model="gpt-4o-mini"
        )

        # Create analysis chain
        self.analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a biblical research assistant. Analyze the current research context
            and determine if more information is needed to answer the query comprehensively.

            Respond with:
            - needs_more_info: true/false
            - missing_info_types: list of information types needed
            - confidence: current confidence in answering the query (0-1)
            - reasoning: brief explanation of your assessment"""),
            ("human", """Query: {query}

            Current Context:
            Structured Knowledge: {structured_context}
            Vector Search Results: {vector_context}

            Assess if we need more information.""")
        ])

    async def autonomous_research(self, query: str) -> ResearchContext:
        """Autonomous research process"""
        context = ResearchContext(query=query)

        # Initial context building
        context = await self._build_initial_context(context)

        # Iterative refinement
        for iteration in range(self.max_iterations):
            context.iteration = iteration + 1

            # Analyze current context
            analysis = await self._analyze_context(context)

            # Update confidence
            context.confidence_score = analysis.get("confidence", 0.5)

            # Check if we need more information
            if not analysis.get("needs_more_info", True) or context.confidence_score >= 0.8:
                context.reasoning_steps.append(f"Iteration {iteration + 1}: Sufficient information gathered")
                break

            # Gather additional information
            additional_context = await self._strategic_retrieval(
                analysis.get("missing_info_types", []), context
            )

            # Merge contexts
            context = self._merge_contexts(context, additional_context)
            context.reasoning_steps.append(f"Iteration {iteration + 1}: {analysis.get('reasoning', 'No reasoning provided')}")

        return context

    async def _build_initial_context(self, context: ResearchContext) -> ResearchContext:
        """Build initial research context"""
        start_time = time.time()

        # Parallel retrieval
        vector_task = self.vector_store.semantic_search(context.query, k=10)
        graph_task = self._graph_entity_search(context.query)

        vector_results, graph_results = await asyncio.gather(vector_task, graph_task)

        context.vector_results = vector_results
        context.structured_results = graph_results

        processing_time = time.time() - start_time
        context.reasoning_steps.append(f"Initial context built in {processing_time:.2f}s")

        return context

    async def _graph_entity_search(self, query: str) -> List[Dict]:
        """Search knowledge graph for relevant entities"""
        # Simple entity extraction - in production, use more sophisticated NER
        potential_entities = self._extract_potential_entities(query)

        graph_results = []
        for entity_name in potential_entities:
            entities = await self.knowledge_graph.find_entities_fulltext(entity_name, limit=2)

            for entity in entities:
                neighborhood = await self.knowledge_graph.get_entity_neighborhood(entity.id)

                graph_results.append({
                    "entity": entity,
                    "neighborhood": neighborhood,
                    "search_term": entity_name
                })

        return graph_results

    def _extract_potential_entities(self, query: str) -> List[str]:
        """Extract potential biblical entities from query"""
        # Simple keyword extraction - improve with NER in production
        biblical_keywords = []

        # Common biblical names and places
        known_entities = {
            "jesus", "christ", "david", "solomon", "moses", "abraham", "isaac", "jacob",
            "jerusalem", "bethlehem", "nazareth", "galilee", "judah", "israel",
            "genesis", "exodus", "psalms", "matthew", "john", "revelation"
        }

        words = query.lower().split()
        for word in words:
            # Remove punctuation
            clean_word = ''.join(c for c in word if c.isalpha())
            if clean_word in known_entities:
                biblical_keywords.append(clean_word.title())

        # If no known entities, return query words that might be entities
        if not biblical_keywords:
            biblical_keywords = [word.title() for word in words if len(word) > 3 and word.isalpha()]

        return biblical_keywords[:5]  # Limit to 5 entities

    async def _analyze_context(self, context: ResearchContext) -> Dict[str, Any]:
        """Analyze current context to determine next steps"""

        structured_summary = f"Found {len(context.structured_results)} knowledge graph entities"
        vector_summary = f"Found {len(context.vector_results)} relevant passages"

        response = await self.llm.ainvoke(
            self.analysis_prompt.format(
                query=context.query,
                structured_context=structured_summary,
                vector_context=vector_summary
            )
        )

        # Parse response - in production, use structured output
        content = response.content.lower()

        needs_more_info = "needs_more_info: true" in content or len(context.vector_results) < 5
        confidence = 0.7 if len(context.vector_results) >= 8 else 0.4

        return {
            "needs_more_info": needs_more_info,
            "missing_info_types": ["cross_references", "historical_context"],
            "confidence": confidence,
            "reasoning": "Basic analysis of available information"
        }

    async def _strategic_retrieval(self, missing_info_types: List[str],
                                 context: ResearchContext) -> ResearchContext:
        """Strategically retrieve additional information"""
        additional_context = ResearchContext(query=context.query)

        for info_type in missing_info_types:
            if info_type == "cross_references":
                # Search for cross-references
                cross_ref_query = f"cross references {context.query}"
                cross_refs = await self.vector_store.semantic_search(cross_ref_query, k=5)
                additional_context.vector_results.extend(cross_refs)

            elif info_type == "historical_context":
                # Search for historical context
                historical_query = f"historical context {context.query}"
                historical_results = await self.vector_store.semantic_search(historical_query, k=5)
                additional_context.vector_results.extend(historical_results)

        return additional_context

    def _merge_contexts(self, main_context: ResearchContext,
                       additional_context: ResearchContext) -> ResearchContext:
        """Merge additional context into main context"""
        main_context.vector_results.extend(additional_context.vector_results)
        main_context.structured_results.extend(additional_context.structured_results)

        # Remove duplicates and sort by relevance
        unique_vector_results = {}
        for text, score in main_context.vector_results:
            if text not in unique_vector_results or unique_vector_results[text] < score:
                unique_vector_results[text] = score

        main_context.vector_results = list(unique_vector_results.items())
        main_context.vector_results.sort(key=lambda x: x[1], reverse=True)

        return main_context

    async def generate_response(self, context: ResearchContext) -> str:
        """Generate final response from research context"""

        # Format context for response generation
        context_text = "Biblical Knowledge:\n"

        # Add structured knowledge
        for result in context.structured_results[:5]:
            entity = result["entity"]
            context_text += f"- {entity.name}: {entity.description}\n"

        # Add relevant passages
        context_text += "\nRelevant Biblical Passages:\n"
        for text, score in context.vector_results[:7]:
            context_text += f"- {text}\n"

        # Generate response
        response_prompt = f"""
        Based on the following biblical knowledge and passages, provide a comprehensive answer to the query.

        Query: {context.query}

        {context_text}

        Provide a scholarly, well-reasoned response that:
        1. Directly addresses the query
        2. References relevant biblical passages
        3. Provides appropriate context
        4. Acknowledges any limitations in the available information
        """

        response = await self.llm.ainvoke(response_prompt)
        return response.content
```

### 1.6 Basic Testing Framework

#### tests/test_basic_functionality.py

```python
import pytest
import asyncio
from unittest.mock import Mock, patch

from src.knowledge_graph.entities import BiblicalEntity, BiblicalEntityType
from src.knowledge_graph.graph_client import BiblicalKnowledgeGraph
from src.rag.agentic_rag import SimpleAgenticRAG

class TestBasicFunctionality:
    """Basic tests for core functionality"""

    @pytest.fixture
    def sample_entity(self):
        return BiblicalEntity(
            name="David",
            entity_type=BiblicalEntityType.PERSON,
            description="King of Israel, author of many Psalms",
            properties={"reign_period": "c. 1010-970 BCE"}
        )

    def test_entity_creation(self, sample_entity):
        """Test basic entity creation"""
        assert sample_entity.name == "David"
        assert sample_entity.entity_type == BiblicalEntityType.PERSON
        assert "reign_period" in sample_entity.properties

    def test_entity_to_dict(self, sample_entity):
        """Test entity serialization"""
        entity_dict = sample_entity.to_dict()
        assert entity_dict["name"] == "David"
        assert entity_dict["entity_type"] == "Person"

    @pytest.mark.asyncio
    @patch('src.knowledge_graph.graph_client.GraphDatabase')
    async def test_knowledge_graph_connection(self, mock_driver):
        """Test knowledge graph connection"""
        mock_driver.driver.return_value = Mock()
        kg = BiblicalKnowledgeGraph()

        # Test that driver is created
        assert kg.driver is not None
        kg.close()

    @pytest.mark.asyncio
    async def test_agentic_rag_initialization(self):
        """Test agentic RAG initialization"""
        with patch('src.rag.agentic_rag.PgvectorscaleBiblicalStore') as mock_vector_store, \
             patch('src.rag.agentic_rag.BiblicalKnowledgeGraph') as mock_kg:

            rag = SimpleAgenticRAG(mock_vector_store, mock_kg)
            assert rag.max_iterations == 3
            assert rag.llm is not None

if __name__ == "__main__":
    pytest.main([__file__])
```

### 1.7 Basic Data Loading Script

#### scripts/load_initial_data.py

```python
#!/usr/bin/env python3
"""
Load initial biblical data into the system
"""
import asyncio
import json
from pathlib import Path

from src.knowledge_graph.graph_client import BiblicalKnowledgeGraph
from src.knowledge_graph.entities import BiblicalEntity, BiblicalEntityType, BiblicalRelationship, RelationshipType
from src.rag.vector_store import PgvectorscaleBiblicalStore

async def load_basic_biblical_entities():
    """Load basic biblical entities"""
    kg = BiblicalKnowledgeGraph()

    # Basic biblical figures
    entities = [
        BiblicalEntity(
            name="Jesus Christ",
            entity_type=BiblicalEntityType.PERSON,
            description="Central figure of Christianity, Son of God",
            aliases=["Jesus", "Christ", "Messiah", "Lord"],
            properties={"birth_location": "Bethlehem", "ministry_region": "Galilee and Judea"}
        ),
        BiblicalEntity(
            name="David",
            entity_type=BiblicalEntityType.PERSON,
            description="Second king of Israel, author of many Psalms",
            properties={"reign_period": "c. 1010-970 BCE", "capital": "Jerusalem"}
        ),
        BiblicalEntity(
            name="Jerusalem",
            entity_type=BiblicalEntityType.PLACE,
            description="Holy city, capital of ancient Israel",
            aliases=["City of David", "Zion"],
            properties={"modern_location": "Israel/Palestine", "significance": "Temple location"}
        ),
        BiblicalEntity(
            name="Creation",
            entity_type=BiblicalEntityType.EVENT,
            description="Biblical account of the creation of the world",
            properties={"biblical_reference": "Genesis 1-2", "duration": "Six days"}
        )
    ]

    # Add entities
    for entity in entities:
        success = await kg.add_entity(entity)
        print(f"Added entity {entity.name}: {success}")

    kg.close()

async def load_sample_biblical_texts():
    """Load sample biblical texts"""
    vector_store = PgvectorscaleBiblicalStore()

    # Sample verses
    verses = [
        {
            "book": "John", "chapter": 3, "verse": 16,
            "text": "For God so loved the world that he gave his one and only Son, that whoever believes in him shall not perish but have eternal life."
        },
        {
            "book": "Psalm", "chapter": 23, "verse": 1,
            "text": "The Lord is my shepherd, I lack nothing."
        },
        {
            "book": "Genesis", "chapter": 1, "verse": 1,
            "text": "In the beginning God created the heavens and the earth."
        },
        {
            "book": "Matthew", "chapter": 5, "verse": 3,
            "text": "Blessed are the poor in spirit, for theirs is the kingdom of heaven."
        }
    ]

    # Add verses
    for verse in verses:
        await vector_store.add_biblical_text(
            book=verse["book"],
            chapter=verse["chapter"],
            verse=verse["verse"],
            text=verse["text"],
            translation="ESV"
        )
        print(f"Added {verse['book']} {verse['chapter']}:{verse['verse']}")

async def main():
    """Main loading function"""
    print("Loading initial biblical data...")

    try:
        await load_basic_biblical_entities()
        await load_sample_biblical_texts()
        print("Data loading completed successfully!")
    except Exception as e:
        print(f"Error loading data: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 1.8 Simple Test Script

#### scripts/test_system.py

```python
#!/usr/bin/env python3
"""
Simple test script for the biblical agentic RAG system
"""
import asyncio
from src.rag.agentic_rag import SimpleAgenticRAG
from src.rag.vector_store import PgvectorscaleBiblicalStore
from src.knowledge_graph.graph_client import BiblicalKnowledgeGraph

async def test_basic_query():
    """Test basic query functionality"""
    print("Initializing system...")

    # Initialize components
    vector_store = PgvectorscaleBiblicalStore()
    knowledge_graph = BiblicalKnowledgeGraph()
    rag_system = SimpleAgenticRAG(vector_store, knowledge_graph)

    # Test query
    test_queries = [
        "Who was David in the Bible?",
        "What is the significance of Jerusalem?",
        "Tell me about the creation story"
    ]

    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print(f"{'='*50}")

        try:
            # Run autonomous research
            context = await rag_system.autonomous_research(query)

            # Generate response
            response = await rag_system.generate_response(context)

            print(f"\nResponse: {response}")
            print(f"\nConfidence Score: {context.confidence_score:.2f}")
            print(f"Reasoning Steps: {len(context.reasoning_steps)}")

        except Exception as e:
            print(f"Error processing query: {e}")

    # Cleanup
    knowledge_graph.close()

async def main():
    await test_basic_query()

if __name__ == "__main__":
    asyncio.run(main())
```

## Quick Start Instructions

1. **Setup Environment**:

   ```bash
   # Clone or create project directory
   mkdir biblical-agentic-rag && cd biblical-agentic-rag

   # Create virtual environment
   python -m venv venv
   source venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Configure Services**:

   ```bash
   # Start Neo4j (Docker)
   docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/password neo4j:5.21

   # Start PostgreSQL with pgvector (Docker)
   docker run -d --name postgres-vector -p 5432:5432 \
     -e POSTGRES_PASSWORD=password \
     timescale/timescaledb-ha:pg15-all
   ```

3. **Set Environment Variables**:

   ```bash
   # Create .env file
   cat > .env << EOF
   NEO4J_PASSWORD=password
   POSTGRES_URI=postgresql://postgres:password@localhost:5432/postgres
   OPENAI_API_KEY=your_openai_api_key_here
   EOF
   ```

4. **Load Initial Data**:

   ```bash
   python scripts/load_initial_data.py
   ```

5. **Test System**:
   ```bash
   python scripts/test_system.py
   ```

This starter kit provides a working foundation that implements the core patterns from the reference repositories while being adapted for biblical studies and the A2A-RPK infrastructure. The system can be expanded incrementally by adding more sophisticated agents, better entity extraction, and integration with Kafka messaging.
