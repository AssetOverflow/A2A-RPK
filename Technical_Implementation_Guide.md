<!-- @format -->

# Agentic RAG Technical Implementation Guide

## Technical Deep Dive: Emulating Leading Patterns

This document provides detailed technical implementation based on proven patterns from `pdichone/knowledge-graph-rag` and `mlvanguards/agentic-graph-rag-evaluation-cometml`, adapted for A2A-RPK and pgvectorscale.

## Core Implementation Patterns

### 1. Hybrid Retrieval Pattern (from pdichone)

The pdichone project demonstrates a powerful pattern of combining structured graph queries with unstructured vector search. Here's how we adapt it:

#### 1.1 Entity-First Retrieval Strategy

```python
class BiblicalHybridRetriever:
    """Hybrid retrieval combining graph and vector search"""

    def __init__(self, knowledge_graph: BiblicalKnowledgeGraph,
                 vector_store: PgvectorscaleBiblicalRetriever,
                 llm: ChatOpenAI):
        self.kg = knowledge_graph
        self.vector_store = vector_store
        self.llm = llm
        self.entity_extractor = self._create_entity_extractor()

    def _create_entity_extractor(self):
        """Create entity extraction chain following pdichone pattern"""
        from pydantic import BaseModel, Field

        class BiblicalEntities(BaseModel):
            """Extracted biblical entities from query"""
            persons: List[str] = Field(description="Biblical persons mentioned")
            places: List[str] = Field(description="Biblical places mentioned")
            events: List[str] = Field(description="Biblical events mentioned")
            concepts: List[str] = Field(description="Theological concepts")

        extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are extracting biblical entities from text.
            Focus on persons, places, events, and theological concepts.
            Be precise and use standard biblical names."""),
            ("human", "Extract entities from: {text}")
        ])

        return extraction_prompt | self.llm.with_structured_output(BiblicalEntities)

    async def hybrid_retrieve(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """Hybrid retrieval following pdichone's structured+unstructured pattern"""

        # Step 1: Extract entities from query (structured approach)
        entities = await self.entity_extractor.ainvoke({"text": query})
        structured_results = await self._structured_retrieval(entities)

        # Step 2: Vector similarity search (unstructured approach)
        vector_results = await self.vector_store.semantic_search(query, k=top_k)

        # Step 3: Combine and rank results
        final_context = self._combine_retrieval_results(
            structured_results, vector_results, query
        )

        return {
            "structured_data": structured_results,
            "unstructured_data": vector_results,
            "final_context": final_context,
            "query": query
        }

    async def _structured_retrieval(self, entities: 'BiblicalEntities') -> List[Dict]:
        """Structured retrieval using knowledge graph"""
        all_results = []

        # For each entity type, query the knowledge graph
        for entity_list, entity_type in [
            (entities.persons, BiblicalEntityType.PERSON),
            (entities.places, BiblicalEntityType.PLACE),
            (entities.events, BiblicalEntityType.EVENT),
            (entities.concepts, BiblicalEntityType.CONCEPT)
        ]:
            for entity_name in entity_list:
                # Find entity using full-text search (pdichone pattern)
                found_entities = await self.kg.find_entities_fulltext(entity_name, limit=2)

                for found_entity in found_entities:
                    # Get neighborhood for multi-hop reasoning
                    neighborhood = await self.kg.get_entity_neighborhood(
                        found_entity.id, max_depth=2
                    )

                    result = {
                        "entity": found_entity,
                        "neighborhood": neighborhood["relationships"],
                        "entity_type": entity_type.value,
                        "search_term": entity_name
                    }
                    all_results.append(result)

        return all_results

    def _combine_retrieval_results(self, structured: List[Dict],
                                 unstructured: List[Tuple[str, float]],
                                 query: str) -> str:
        """Combine results following pdichone's context assembly pattern"""

        # Format structured data
        structured_context = "Structured Knowledge:\n"
        for result in structured[:5]:  # Limit for context size
            entity = result["entity"]
            structured_context += f"- {entity.name} ({entity.entity_type.value}): {entity.description}\n"

            # Add key relationships
            for rel in result["neighborhood"][:3]:
                structured_context += f"  * {rel}\n"

        # Format unstructured data
        unstructured_context = "\nRelevant Passages:\n"
        for text, score in unstructured[:7]:
            unstructured_context += f"- (Score: {score:.3f}) {text}\n"

        return f"""Context for Query: "{query}"

{structured_context}

{unstructured_context}"""
```

#### 1.2 Multi-hop Graph Traversal (pdichone pattern)

```python
class BiblicalGraphTraversal:
    """Multi-hop graph traversal for complex biblical relationships"""

    def __init__(self, knowledge_graph: BiblicalKnowledgeGraph):
        self.kg = knowledge_graph

    async def find_connection_paths(self, entity1_name: str, entity2_name: str,
                                  max_depth: int = 3) -> List[Dict]:
        """Find connection paths between biblical entities"""

        # Find entities by name
        entities1 = await self.kg.find_entities_fulltext(entity1_name, limit=1)
        entities2 = await self.kg.find_entities_fulltext(entity2_name, limit=1)

        if not entities1 or not entities2:
            return []

        entity1_id = entities1[0].id
        entity2_id = entities2[0].id

        # Use Neo4j's shortest path algorithm
        with self.kg.driver.session() as session:
            result = session.run("""
                MATCH (start:Entity {id: $start_id}), (end:Entity {id: $end_id})
                CALL apoc.algo.dijkstra(start, end, 'RELATIONSHIP', 'weight')
                YIELD path, weight
                RETURN path, weight
                ORDER BY weight
                LIMIT 5
            """, {"start_id": entity1_id, "end_id": entity2_id})

            paths = []
            for record in result:
                path_info = self._extract_path_information(record["path"])
                paths.append({
                    "path": path_info,
                    "weight": record["weight"],
                    "connection_strength": 1.0 / (record["weight"] + 1)
                })

            return paths

    async def find_biblical_themes(self, entity_id: str, theme_types: List[str] = None) -> Dict:
        """Find thematic connections following pdichone's pattern"""

        theme_types = theme_types or ["theological", "prophetic", "historical"]

        with self.kg.driver.session() as session:
            # Complex Cypher query for thematic analysis
            result = session.run("""
                MATCH (entity:Entity {id: $entity_id})
                CALL {
                    WITH entity
                    MATCH (entity)-[r*1..3]-(theme:Entity)
                    WHERE theme.type = 'CONCEPT'
                    AND any(prop IN keys(theme.properties) WHERE prop IN $theme_types)
                    RETURN theme, length(r) as distance, type(r[0]) as first_relation
                }
                RETURN theme, distance, first_relation,
                       theme.properties as theme_props
                ORDER BY distance, theme.confidence_score DESC
                LIMIT 20
            """, {"entity_id": entity_id, "theme_types": theme_types})

            themes = {}
            for record in result:
                theme_name = record["theme"]["name"]
                if theme_name not in themes:
                    themes[theme_name] = {
                        "entity": record["theme"],
                        "distance": record["distance"],
                        "connections": [],
                        "properties": record["theme_props"]
                    }

                themes[theme_name]["connections"].append({
                    "relation": record["first_relation"],
                    "distance": record["distance"]
                })

            return themes
```

### 2. Agentic Decision Making Pattern (from mlvanguards)

The mlvanguards project demonstrates sophisticated agent decision-making and tool selection. Here's our adaptation:

#### 2.1 Strategic Research Planning

```python
from typing import Protocol, List, Dict, Any
import asyncio
from dataclasses import dataclass
from enum import Enum

class ResearchStrategy(Enum):
    BROAD_EXPLORATION = "broad_exploration"
    FOCUSED_ANALYSIS = "focused_analysis"
    COMPARATIVE_STUDY = "comparative_study"
    HISTORICAL_INVESTIGATION = "historical_investigation"

@dataclass
class ResearchPlan:
    """Research plan generated by agentic reasoning"""
    strategy: ResearchStrategy
    investigation_steps: List[str]
    required_tools: List[str]
    expected_domains: List[str]
    confidence_threshold: float
    max_iterations: int

class BiblicalResearchPlanner:
    """Agentic research planner following mlvanguards patterns"""

    def __init__(self, llm: ChatOpenAI, knowledge_graph: BiblicalKnowledgeGraph):
        self.llm = llm
        self.kg = knowledge_graph
        self.planning_chain = self._create_planning_chain()

    def _create_planning_chain(self):
        """Create research planning chain"""
        planning_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a biblical research strategist. Given a research query,
            create a strategic plan for investigation.

            Consider:
            1. What type of investigation is needed?
            2. What sequence of research steps would be most effective?
            3. What biblical domains need to be consulted?
            4. What confidence level should we aim for?

            Respond with a structured research plan."""),
            ("human", """Research Query: {query}

            Available Knowledge: {available_knowledge}
            Available Tools: {available_tools}

            Create a research plan.""")
        ])

        return planning_prompt | self.llm.with_structured_output(ResearchPlan)

    async def create_research_plan(self, query: str, context: Dict = None) -> ResearchPlan:
        """Create strategic research plan"""

        # Analyze available knowledge
        available_knowledge = await self._assess_available_knowledge(query)
        available_tools = ["linguistic_analysis", "chronological_analysis",
                          "geographical_analysis", "theological_synthesis"]

        plan = await self.planning_chain.ainvoke({
            "query": query,
            "available_knowledge": available_knowledge,
            "available_tools": available_tools
        })

        return plan

    async def _assess_available_knowledge(self, query: str) -> Dict:
        """Assess what knowledge is available for the query"""

        # Quick entity extraction
        entities = await self._extract_key_entities(query)

        knowledge_assessment = {
            "entities_found": len(entities),
            "domains_covered": [],
            "knowledge_gaps": [],
            "confidence_indicators": []
        }

        # Check knowledge graph coverage
        for entity in entities:
            found_entities = await self.kg.find_entities_fulltext(entity, limit=1)
            if found_entities:
                entity_obj = found_entities[0]
                knowledge_assessment["domains_covered"].append(entity_obj.entity_type.value)
                knowledge_assessment["confidence_indicators"].append(entity_obj.confidence_score)
            else:
                knowledge_assessment["knowledge_gaps"].append(entity)

        return knowledge_assessment

class AgenticResearchExecutor:
    """Execute research following agentic patterns from mlvanguards"""

    def __init__(self,
                 planner: BiblicalResearchPlanner,
                 retriever: BiblicalHybridRetriever,
                 agents: Dict[str, 'BiblicalAgent']):
        self.planner = planner
        self.retriever = retriever
        self.agents = agents
        self.execution_state = {}

    async def execute_research(self, query: str) -> Dict[str, Any]:
        """Execute agentic research following mlvanguards pattern"""

        # Step 1: Create research plan
        plan = await self.planner.create_research_plan(query)

        # Step 2: Initialize execution state
        execution_state = {
            "query": query,
            "plan": plan,
            "completed_steps": [],
            "gathered_evidence": [],
            "current_confidence": 0.0,
            "iteration": 0
        }

        # Step 3: Execute plan iteratively
        for step in plan.investigation_steps:
            if execution_state["iteration"] >= plan.max_iterations:
                break

            # Execute step based on type
            step_result = await self._execute_research_step(step, execution_state)

            # Update state
            execution_state["completed_steps"].append(step)
            execution_state["gathered_evidence"].extend(step_result.get("evidence", []))
            execution_state["current_confidence"] = max(
                execution_state["current_confidence"],
                step_result.get("confidence", 0.0)
            )
            execution_state["iteration"] += 1

            # Check if we've reached confidence threshold
            if execution_state["current_confidence"] >= plan.confidence_threshold:
                break

        # Step 4: Synthesize final result
        final_result = await self._synthesize_research_result(execution_state)

        return final_result

    async def _execute_research_step(self, step: str, state: Dict) -> Dict[str, Any]:
        """Execute individual research step"""

        if "linguistic" in step.lower():
            return await self._execute_linguistic_step(step, state)
        elif "historical" in step.lower():
            return await self._execute_historical_step(step, state)
        elif "comparative" in step.lower():
            return await self._execute_comparative_step(step, state)
        else:
            return await self._execute_general_step(step, state)

    async def _execute_linguistic_step(self, step: str, state: Dict) -> Dict[str, Any]:
        """Execute linguistic analysis step"""

        query = state["query"]

        # Use hybrid retrieval for linguistic context
        retrieval_result = await self.retriever.hybrid_retrieve(
            f"Hebrew Greek linguistic {query}", top_k=15
        )

        # Apply linguistic agent if available
        if "linguistics" in self.agents:
            agent_result = await self.agents["linguistics"].analyze(
                query, retrieval_result["final_context"]
            )

            return {
                "evidence": agent_result.get("findings", []),
                "confidence": agent_result.get("confidence_score", 0.5),
                "methodology": "linguistic_analysis",
                "sources": retrieval_result["structured_data"]
            }

        return {"evidence": [], "confidence": 0.0}

    async def _synthesize_research_result(self, state: Dict) -> Dict[str, Any]:
        """Synthesize final research result using all gathered evidence"""

        synthesis_prompt = f"""
        Research Query: {state['query']}

        Execution Plan: {state['plan'].strategy.value}
        Completed Steps: {', '.join(state['completed_steps'])}

        Gathered Evidence:
        {json.dumps(state['gathered_evidence'], indent=2)}

        Current Confidence: {state['current_confidence']}

        Synthesize this research into a comprehensive, scholarly response that:
        1. Directly addresses the research question
        2. Integrates evidence from multiple steps
        3. Provides clear reasoning and support
        4. Acknowledges uncertainty where appropriate
        5. Suggests areas for further investigation
        """

        synthesis_result = await self.planner.llm.ainvoke(synthesis_prompt)

        return {
            "query": state["query"],
            "synthesis": synthesis_result.content,
            "confidence_score": state["current_confidence"],
            "evidence_sources": len(state["gathered_evidence"]),
            "methodology": state["plan"].strategy.value,
            "completed_steps": state["completed_steps"]
        }
```

#### 2.2 Tool Selection and Orchestration

```python
from typing import Protocol, Callable, Dict, Any
from abc import ABC, abstractmethod

class BiblicalTool(Protocol):
    """Protocol for biblical research tools"""

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool with given query and context"""
        ...

    def get_capability_description(self) -> str:
        """Get description of tool capabilities"""
        ...

class LinguisticAnalysisTool:
    """Linguistic analysis tool following mlvanguards tool pattern"""

    def __init__(self, llm: ChatOpenAI, hebrew_lexicon_db, greek_lexicon_db):
        self.llm = llm
        self.hebrew_lexicon = hebrew_lexicon_db
        self.greek_lexicon = greek_lexicon_db

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute linguistic analysis"""

        # Extract Hebrew/Greek terms from context
        linguistic_terms = self._extract_linguistic_terms(context)

        analysis_results = []
        for term in linguistic_terms:
            # Morphological analysis
            morphology = await self._analyze_morphology(term)

            # Semantic analysis
            semantics = await self._analyze_semantics(term, context)

            # Cross-reference analysis
            cross_refs = await self._find_cross_references(term)

            analysis_results.append({
                "term": term,
                "morphology": morphology,
                "semantics": semantics,
                "cross_references": cross_refs
            })

        return {
            "tool": "linguistic_analysis",
            "results": analysis_results,
            "confidence": self._calculate_linguistic_confidence(analysis_results),
            "methodology": "morphological_semantic_analysis"
        }

    def get_capability_description(self) -> str:
        return "Analyzes Hebrew and Greek biblical terms for morphology, semantics, and cross-references"

class ToolOrchestrator:
    """Tool orchestration following mlvanguards coordination pattern"""

    def __init__(self):
        self.tools: Dict[str, BiblicalTool] = {}
        self.tool_selection_chain = None

    def register_tool(self, name: str, tool: BiblicalTool):
        """Register a tool for use"""
        self.tools[name] = tool

    async def select_and_execute_tools(self, query: str, context: Dict[str, Any],
                                     max_tools: int = 3) -> List[Dict[str, Any]]:
        """Select and execute appropriate tools for the query"""

        # Select tools based on query analysis
        selected_tools = await self._select_tools(query, context, max_tools)

        # Execute tools in parallel
        tool_tasks = []
        for tool_name in selected_tools:
            if tool_name in self.tools:
                task = self.tools[tool_name].execute(query, context)
                tool_tasks.append((tool_name, task))

        # Gather results
        results = []
        for tool_name, task in tool_tasks:
            try:
                result = await task
                result["tool_name"] = tool_name
                results.append(result)
            except Exception as e:
                print(f"Tool {tool_name} failed: {e}")

        return results

    async def _select_tools(self, query: str, context: Dict[str, Any],
                          max_tools: int) -> List[str]:
        """Select appropriate tools based on query analysis"""

        # Analyze query for domain indicators
        domain_indicators = {
            "linguistic": ["hebrew", "greek", "word", "language", "translation"],
            "chronological": ["date", "time", "year", "period", "chronology"],
            "geographical": ["place", "location", "geography", "map", "region"],
            "theological": ["theology", "doctrine", "belief", "teaching"]
        }

        query_lower = query.lower()
        relevant_domains = []

        for domain, indicators in domain_indicators.items():
            if any(indicator in query_lower for indicator in indicators):
                relevant_domains.append(domain)

        # Map domains to tools
        domain_tool_mapping = {
            "linguistic": "linguistic_analysis",
            "chronological": "chronological_analysis",
            "geographical": "geographical_analysis",
            "theological": "theological_analysis"
        }

        selected_tools = []
        for domain in relevant_domains[:max_tools]:
            if domain in domain_tool_mapping:
                tool_name = domain_tool_mapping[domain]
                if tool_name in self.tools:
                    selected_tools.append(tool_name)

        # Always include general biblical analysis if space
        if len(selected_tools) < max_tools and "general_biblical" in self.tools:
            selected_tools.append("general_biblical")

        return selected_tools
```

### 3. Evaluation and Monitoring (mlvanguards pattern)

```python
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import time
import json

@dataclass
class ResearchMetrics:
    """Research performance metrics"""
    query_id: str
    processing_time: float
    knowledge_graph_queries: int
    vector_searches: int
    agent_invocations: int
    confidence_score: float
    evidence_count: int
    tool_usage: Dict[str, int]
    success: bool
    error_details: Optional[str] = None

class BiblicalResearchMonitor:
    """Research monitoring following mlvanguards evaluation patterns"""

    def __init__(self, experiment_tracker=None):
        self.experiment_tracker = experiment_tracker
        self.metrics_history = []
        self.performance_baselines = self._load_baselines()

    def start_research_tracking(self, query: str) -> str:
        """Start tracking a research session"""
        query_id = f"research_{int(time.time())}_{hash(query) % 10000}"

        if self.experiment_tracker:
            self.experiment_tracker.log_parameter("query", query)
            self.experiment_tracker.log_parameter("query_id", query_id)
            self.experiment_tracker.log_parameter("start_time", time.time())

        return query_id

    def track_knowledge_graph_query(self, query_id: str, cypher_query: str,
                                   execution_time: float, result_count: int):
        """Track knowledge graph query performance"""

        if self.experiment_tracker:
            self.experiment_tracker.log_metrics({
                f"kg_query_time_{query_id}": execution_time,
                f"kg_result_count_{query_id}": result_count,
                "total_kg_queries": 1
            })

    def track_vector_search(self, query_id: str, search_query: str,
                           execution_time: float, result_count: int, top_similarity: float):
        """Track vector search performance"""

        if self.experiment_tracker:
            self.experiment_tracker.log_metrics({
                f"vector_search_time_{query_id}": execution_time,
                f"vector_result_count_{query_id}": result_count,
                f"vector_top_similarity_{query_id}": top_similarity,
                "total_vector_searches": 1
            })

    def track_agent_performance(self, query_id: str, agent_name: str,
                              processing_time: float, confidence_score: float):
        """Track individual agent performance"""

        if self.experiment_tracker:
            self.experiment_tracker.log_metrics({
                f"agent_{agent_name}_time_{query_id}": processing_time,
                f"agent_{agent_name}_confidence_{query_id}": confidence_score,
                f"total_{agent_name}_invocations": 1
            })

    def finalize_research_tracking(self, query_id: str, final_result: Dict[str, Any]) -> ResearchMetrics:
        """Finalize research tracking and generate metrics"""

        end_time = time.time()

        # Create comprehensive metrics
        metrics = ResearchMetrics(
            query_id=query_id,
            processing_time=final_result.get("total_processing_time", 0.0),
            knowledge_graph_queries=final_result.get("kg_queries_count", 0),
            vector_searches=final_result.get("vector_searches_count", 0),
            agent_invocations=len(final_result.get("agent_results", {})),
            confidence_score=final_result.get("confidence_score", 0.0),
            evidence_count=len(final_result.get("evidence_sources", [])),
            tool_usage=final_result.get("tool_usage", {}),
            success=final_result.get("success", True)
        )

        # Log final metrics
        if self.experiment_tracker:
            self.experiment_tracker.log_metrics({
                "final_confidence": metrics.confidence_score,
                "total_processing_time": metrics.processing_time,
                "evidence_count": metrics.evidence_count,
                "success": int(metrics.success)
            })

        # Store for analysis
        self.metrics_history.append(metrics)

        # Performance analysis
        self._analyze_performance(metrics)

        return metrics

    def _analyze_performance(self, metrics: ResearchMetrics):
        """Analyze performance against baselines"""

        performance_analysis = {
            "processing_time_percentile": self._calculate_percentile(
                metrics.processing_time,
                [m.processing_time for m in self.metrics_history[-100:]]
            ),
            "confidence_comparison": metrics.confidence_score - self.performance_baselines.get("avg_confidence", 0.7),
            "efficiency_score": metrics.evidence_count / max(metrics.processing_time, 0.1)
        }

        if self.experiment_tracker:
            self.experiment_tracker.log_metrics(performance_analysis)

    def _calculate_percentile(self, value: float, historical_values: List[float]) -> float:
        """Calculate percentile of current value"""
        if not historical_values:
            return 50.0

        sorted_values = sorted(historical_values)
        position = sum(1 for v in sorted_values if v <= value)
        return (position / len(sorted_values)) * 100

    def _load_baselines(self) -> Dict[str, float]:
        """Load performance baselines"""
        return {
            "avg_confidence": 0.75,
            "avg_processing_time": 5.0,
            "avg_evidence_count": 12
        }

class QualityAssessment:
    """Quality assessment following mlvanguards evaluation patterns"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.assessment_criteria = self._define_assessment_criteria()

    async def assess_research_quality(self, query: str, result: Dict[str, Any]) -> Dict[str, float]:
        """Assess quality of research result"""

        assessments = {}

        # Factual accuracy assessment
        accuracy_score = await self._assess_factual_accuracy(query, result)
        assessments["factual_accuracy"] = accuracy_score

        # Completeness assessment
        completeness_score = await self._assess_completeness(query, result)
        assessments["completeness"] = completeness_score

        # Biblical scholarship standards
        scholarship_score = await self._assess_scholarship_standards(result)
        assessments["scholarship_quality"] = scholarship_score

        # Evidence quality
        evidence_score = await self._assess_evidence_quality(result)
        assessments["evidence_quality"] = evidence_score

        # Overall quality score
        assessments["overall_quality"] = sum(assessments.values()) / len(assessments)

        return assessments

    async def _assess_factual_accuracy(self, query: str, result: Dict[str, Any]) -> float:
        """Assess factual accuracy of research result"""

        accuracy_prompt = f"""
        Assess the factual accuracy of this biblical research result.

        Query: {query}
        Result: {result.get('synthesis', '')}
        Evidence: {json.dumps(result.get('evidence_sources', []), indent=2)}

        Rate factual accuracy from 0.0 to 1.0 based on:
        1. Consistency with established biblical scholarship
        2. Accuracy of biblical references and quotes
        3. Correctness of historical and theological claims
        4. Proper use of original language insights

        Provide only a numeric score.
        """

        response = await self.llm.ainvoke(accuracy_prompt)

        try:
            score = float(response.content.strip())
            return max(0.0, min(1.0, score))
        except ValueError:
            return 0.5  # Default if parsing fails

    def _define_assessment_criteria(self) -> Dict[str, str]:
        """Define quality assessment criteria"""
        return {
            "factual_accuracy": "Consistency with established biblical scholarship",
            "completeness": "Comprehensive coverage of relevant aspects",
            "scholarship_quality": "Adherence to academic biblical scholarship standards",
            "evidence_quality": "Quality and relevance of supporting evidence"
        }
```

## Integration with A2A-RPK Infrastructure

### Kafka Message Schemas for Agentic RAG

```python
# Update existing Avro schemas for agentic RAG support

AGENTIC_RESEARCH_REQUEST_SCHEMA = {
    "type": "record",
    "name": "AgenticResearchRequest",
    "fields": [
        {"name": "request_id", "type": "string"},
        {"name": "query", "type": "string"},
        {"name": "research_strategy", "type": ["null", "string"], "default": None},
        {"name": "max_iterations", "type": "int", "default": 3},
        {"name": "confidence_threshold", "type": "float", "default": 0.8},
        {"name": "required_domains", "type": {"type": "array", "items": "string"}},
        {"name": "context", "type": ["null", "string"], "default": None},
        {"name": "timestamp", "type": "long"}
    ]
}

KNOWLEDGE_GRAPH_UPDATE_SCHEMA = {
    "type": "record",
    "name": "KnowledgeGraphUpdate",
    "fields": [
        {"name": "update_id", "type": "string"},
        {"name": "update_type", "type": {"type": "enum", "name": "UpdateType",
                                       "symbols": ["ADD_ENTITY", "ADD_RELATIONSHIP", "UPDATE_ENTITY"]}},
        {"name": "entity_data", "type": ["null", "string"], "default": None},
        {"name": "relationship_data", "type": ["null", "string"], "default": None},
        {"name": "confidence_score", "type": "float"},
        {"name": "source_agent", "type": "string"},
        {"name": "timestamp", "type": "long"}
    ]
}

RESEARCH_RESULT_SCHEMA = {
    "type": "record",
    "name": "AgenticResearchResult",
    "fields": [
        {"name": "request_id", "type": "string"},
        {"name": "synthesis", "type": "string"},
        {"name": "confidence_score", "type": "float"},
        {"name": "evidence_sources", "type": {"type": "array", "items": "string"}},
        {"name": "methodology", "type": "string"},
        {"name": "contributing_agents", "type": {"type": "array", "items": "string"}},
        {"name": "quality_metrics", "type": "string"},  # JSON encoded
        {"name": "processing_time", "type": "float"},
        {"name": "timestamp", "type": "long"}
    ]
}
```

This technical implementation guide provides the concrete patterns and code structures needed to build the agentic RAG + knowledge graph system for biblical studies, directly emulating the proven approaches from the reference projects while adapting them for the A2A-RPK infrastructure.
