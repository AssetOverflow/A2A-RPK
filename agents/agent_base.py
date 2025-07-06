import os
import json
import asyncio
import logging
import io
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import fastavro
import requests
import httpx

logger = logging.getLogger(__name__)


class AvroSchemaManager:
    """Manages Avro schemas and serialization/deserialization"""

    def __init__(self, schema_registry_url: str):
        self.schema_registry_url = schema_registry_url
        self.schemas = {}
        self.compiled_schemas = {}

    def register_schema(self, schema_name: str, schema_json: str):
        """Register an Avro schema"""
        try:
            schema = fastavro.parse_schema(json.loads(schema_json))
            self.schemas[schema_name] = schema_json
            self.compiled_schemas[schema_name] = schema
            logger.info(f"Registered schema: {schema_name}")
        except Exception as e:
            logger.error(f"Failed to register schema {schema_name}: {e}")
            raise

    def serialize(self, schema_name: str, data: Dict[str, Any]) -> bytes:
        """Serialize data using the specified schema"""
        if schema_name not in self.compiled_schemas:
            raise ValueError(f"Schema {schema_name} not registered")

        schema = self.compiled_schemas[schema_name]
        bytes_writer = io.BytesIO()
        fastavro.schemaless_writer(bytes_writer, schema, data)
        return bytes_writer.getvalue()

    def deserialize(self, schema_name: str, data: bytes) -> Dict[str, Any]:
        """Deserialize data using the specified schema"""
        if schema_name not in self.compiled_schemas:
            raise ValueError(f"Schema {schema_name} not registered")

        schema = self.compiled_schemas[schema_name]
        bytes_reader = io.BytesIO(data)
        return fastavro.schemaless_reader(bytes_reader, schema)


class AgentBase(ABC):
    """Base class for all A2A agents with Kafka and MCP support"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.kafka_broker = os.getenv("KAFKA_BROKER", "localhost:19092")
        self.schema_registry_url = os.getenv(
            "SCHEMA_REGISTRY_URL", "http://localhost:18081"
        )

        # Kafka components
        self.producer: Optional[KafkaProducer] = None
        self.consumer: Optional[KafkaConsumer] = None
        self.schema_manager: Optional[AvroSchemaManager] = None

        # Agent state
        self.is_running = False
        self.tasks: Dict[str, Dict] = {}

        logger.info(f"Agent {agent_id} initialized")

    async def initialize(self):
        """Initialize Kafka connections and schema registry"""
        try:
            # Initialize Schema Manager
            self.schema_manager = AvroSchemaManager(self.schema_registry_url)

            # Initialize Kafka producer
            self.producer = KafkaProducer(
                bootstrap_servers=[self.kafka_broker],
                client_id=f"{self.agent_id}-producer",
                value_serializer=lambda v: v,  # We'll handle serialization manually
                key_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
            )

            # Initialize Kafka consumer
            self.consumer = KafkaConsumer(
                bootstrap_servers=[self.kafka_broker],
                group_id=f"{self.agent_id}-group",
                client_id=f"{self.agent_id}-consumer",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: m,  # We'll handle deserialization manually
            )

            # Register schemas
            await self._setup_schemas()

            # Subscribe to relevant topics
            await self._subscribe_to_topics()

            # Start background tasks
            self.is_running = True
            asyncio.create_task(self._message_consumer_loop())

            logger.info(f"Agent {self.agent_id} initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize agent {self.agent_id}: {e}")
            raise

    async def shutdown(self):
        """Shutdown agent and cleanup resources"""
        self.is_running = False

        if self.consumer:
            self.consumer.close()

        if self.producer:
            self.producer.flush()
            self.producer.close()

        logger.info(f"Agent {self.agent_id} shutdown complete")

    async def _setup_schemas(self):
        """Setup Avro schemas for message serialization"""
        try:
            # Task Request Schema
            task_request_schema = """
            {
                "type": "record",
                "name": "TaskRequest",
                "fields": [
                    {"name": "task_id", "type": "string"},
                    {"name": "requester_id", "type": "string"},
                    {"name": "description", "type": "string"},
                    {"name": "proposed_cost", "type": ["null", "double"], "default": null},
                    {"name": "priority", "type": "int", "default": 1},
                    {"name": "timestamp", "type": "long"}
                ]
            }
            """

            # Task Response Schema
            task_response_schema = """
            {
                "type": "record",
                "name": "TaskResponse",
                "fields": [
                    {"name": "task_id", "type": "string"},
                    {"name": "responder_id", "type": "string"},
                    {"name": "status", "type": {"type": "enum", "name": "TaskStatus", "symbols": ["PENDING", "ACCEPTED", "REJECTED", "NEGOTIATING", "RUNNING", "COMPLETED", "FAILED"]}},
                    {"name": "counter_offer", "type": ["null", "double"], "default": null},
                    {"name": "message", "type": ["null", "string"], "default": null},
                    {"name": "timestamp", "type": "long"}
                ]
            }
            """

            # Negotiation Message Schema
            negotiation_schema = """
            {
                "type": "record",
                "name": "NegotiationMessage",
                "fields": [
                    {"name": "task_id", "type": "string"},
                    {"name": "sender_id", "type": "string"},
                    {"name": "receiver_id", "type": "string"},
                    {"name": "negotiation_round", "type": "int"},
                    {"name": "offer", "type": ["null", "double"], "default": null},
                    {"name": "approved", "type": "boolean"},
                    {"name": "message", "type": ["null", "string"], "default": null},
                    {"name": "timestamp", "type": "long"}
                ]
            }
            """

            # Register schemas with our manager
            self.schema_manager.register_schema("task_request", task_request_schema)
            self.schema_manager.register_schema("task_response", task_response_schema)
            self.schema_manager.register_schema("negotiation", negotiation_schema)

            logger.info("Schemas setup complete")

        except Exception as e:
            logger.error(f"Failed to setup schemas: {e}")
            raise

    async def _message_consumer_loop(self):
        """Background task to consume messages from Kafka"""
        while self.is_running:
            try:
                # Poll for messages with timeout
                msg_batch = self.consumer.poll(timeout_ms=1000, max_records=1)

                if not msg_batch:
                    await asyncio.sleep(0.1)
                    continue

                for topic_partition, messages in msg_batch.items():
                    for msg in messages:
                        try:
                            # Process the message
                            await self._process_message(msg)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")

            except Exception as e:
                logger.error(f"Error in message consumer loop: {e}")
                await asyncio.sleep(1)

    async def send_message(self, topic: str, message_type: str, data: Dict[str, Any]):
        """Send a message to Kafka topic with schema validation"""
        try:
            # Serialize the message using our schema manager
            serialized_data = self.schema_manager.serialize(message_type, data)

            # Send to Kafka
            self.producer.send(
                topic, value=serialized_data, key=data.get("task_id", self.agent_id)
            )

            self.producer.flush()
            logger.info(f"Sent {message_type} message to {topic}")

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            "agent_id": self.agent_id,
            "is_running": self.is_running,
            "active_tasks": len(self.tasks),
            "kafka_broker": self.kafka_broker,
            "schema_registry": self.schema_registry_url,
        }

    def deserialize_message(self, message_type: str, data: bytes) -> Dict[str, Any]:
        """Helper method to deserialize Kafka messages"""
        return self.schema_manager.deserialize(message_type, data)

    @abstractmethod
    async def _subscribe_to_topics(self):
        """Subscribe to relevant Kafka topics (implemented by subclasses)"""
        pass

    @abstractmethod
    async def _process_message(self, msg):
        """Process incoming Kafka messages (implemented by subclasses)"""
        pass
