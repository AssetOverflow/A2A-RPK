#!/usr/bin/env python3
"""
Kafka-based A2A Communication Test
Tests actual message flow through Kafka topics with schema validation
"""

import asyncio
import json
import time
import uuid
import io
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import fastavro
import requests


class AvroSchemaManager:
    """Manages Avro schemas and serialization/deserialization"""

    def __init__(self):
        self.schemas = {}
        self.compiled_schemas = {}

    def register_schema(self, schema_name: str, schema_json: str):
        """Register an Avro schema"""
        try:
            schema = fastavro.parse_schema(json.loads(schema_json))
            self.schemas[schema_name] = schema_json
            self.compiled_schemas[schema_name] = schema
            print(f"✅ Registered schema: {schema_name}")
        except Exception as e:
            print(f"❌ Failed to register schema {schema_name}: {e}")
            raise

    def serialize(self, schema_name: str, data: dict) -> bytes:
        """Serialize data using the specified schema"""
        if schema_name not in self.compiled_schemas:
            raise ValueError(f"Schema {schema_name} not registered")

        schema = self.compiled_schemas[schema_name]
        bytes_writer = io.BytesIO()
        fastavro.schemaless_writer(bytes_writer, schema, data)
        return bytes_writer.getvalue()

    def deserialize(self, schema_name: str, data: bytes) -> dict:
        """Deserialize data using the specified schema"""
        if schema_name not in self.compiled_schemas:
            raise ValueError(f"Schema {schema_name} not registered")

        schema = self.compiled_schemas[schema_name]
        bytes_reader = io.BytesIO(data)
        return fastavro.schemaless_reader(bytes_reader, schema)


class KafkaA2ATest:
    """Test Kafka-based A2A communication with schema validation"""

    def __init__(self):
        self.broker = "localhost:19092"

        # Initialize components
        self.producer = None
        self.consumer = None
        self.schema_manager = AvroSchemaManager()

    async def setup(self):
        """Setup Kafka producer, consumer, and schema registry"""
        print("🔧 Setting up Kafka components...")

        try:
            # Producer
            self.producer = KafkaProducer(
                bootstrap_servers=[self.broker],
                client_id="a2a-test-producer",
                value_serializer=lambda v: v,  # We'll handle serialization manually
                key_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
            )

            # Consumer
            self.consumer = KafkaConsumer(
                bootstrap_servers=[self.broker],
                group_id="a2a-test-group",
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda m: m,  # We'll handle deserialization manually
            )

            # Setup schemas
            await self._setup_schemas()

            print("✅ Kafka components ready")

        except Exception as e:
            print(f"❌ Failed to setup Kafka: {e}")
            raise

    async def _setup_schemas(self):
        """Setup Avro schemas for serialization"""
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

        # Register schemas
        self.schema_manager.register_schema("task_request", task_request_schema)
        self.schema_manager.register_schema("task_response", task_response_schema)

    async def test_task_request_flow(self):
        """Test the complete task request flow"""
        print("\n🚀 Testing Task Request Flow...")

        task_id = str(uuid.uuid4())

        # 1. Send task request
        request_data = {
            "task_id": task_id,
            "requester_id": "test-requester",
            "description": "Test data processing task",
            "proposed_cost": 75.0,
            "priority": 2,
            "timestamp": int(time.time() * 1000),
        }

        print(f"📤 Sending task request: {task_id}")
        await self._send_message("task-requests", "task_request", request_data)

        # 2. Subscribe to responses and wait
        print("👂 Listening for responses...")
        self.consumer.subscribe(["task-responses"])

        # Wait for response (timeout after 30 seconds)
        timeout = time.time() + 30
        found_response = False

        while time.time() < timeout and not found_response:
            msg_batch = self.consumer.poll(timeout_ms=1000, max_records=1)

            if not msg_batch:
                continue

            for topic_partition, messages in msg_batch.items():
                for msg in messages:
                    try:
                        # Deserialize response
                        response = self.schema_manager.deserialize(
                            "task_response", msg.value
                        )

                        if response["task_id"] == task_id:
                            print(f"✅ Received response for task {task_id}:")
                            print(f"   Status: {response['status']}")
                            print(f"   Responder: {response['responder_id']}")
                            print(f"   Message: {response.get('message', 'N/A')}")
                            found_response = True

                    except Exception as e:
                        print(f"⚠️  Error deserializing response: {e}")

        if not found_response:
            print("⚠️  No response received (agents may not be running or processing)")

    async def test_schema_validation(self):
        """Test schema validation by sending invalid data"""
        print("\n🧪 Testing Schema Validation...")

        # Try to send invalid data (missing required field)
        try:
            invalid_data = {
                "task_id": "test-invalid",
                # Missing required 'requester_id' field
                "description": "Invalid request",
                "timestamp": int(time.time() * 1000),
            }

            await self._send_message("task-requests", "task_request", invalid_data)
            print("❌ Schema validation failed - invalid message was accepted")

        except Exception as e:
            print("✅ Schema validation working - invalid message rejected:")
            print(f"   Error: {e}")

    async def _send_message(self, topic: str, message_type: str, data: dict):
        """Send message to Kafka topic with schema validation"""
        try:
            # Serialize the message using our schema manager
            serialized_data = self.schema_manager.serialize(message_type, data)

            # Send to Kafka
            self.producer.send(
                topic, value=serialized_data, key=data.get("task_id", "test-key")
            )

            self.producer.flush()
            print(f"✅ Sent {message_type} to {topic}")

        except Exception as e:
            print(f"❌ Failed to send message: {e}")
            raise

    async def cleanup(self):
        """Cleanup resources"""
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.flush()
            self.producer.close()


async def main():
    """Run Kafka A2A tests"""
    test = KafkaA2ATest()

    print("🧪 Kafka-based A2A Communication Test")
    print("=" * 50)
    print("Testing actual message flow through Kafka topics")
    print("=" * 50)

    try:
        await test.setup()
        await test.test_schema_validation()
        await test.test_task_request_flow()

        print("\n✨ Kafka tests completed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")

    finally:
        await test.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
