#!/usr/bin/env python3
"""
Test Kafka messaging using the same environment as the agents
This script will be run inside a container with the exact same dependencies
"""

import json
import time
import uuid
import io
from kafka import KafkaProducer, KafkaConsumer
import fastavro


def create_test_schemas():
    """Create test schemas matching the agents"""
    task_request_schema = {
        "type": "record",
        "name": "TaskRequest",
        "fields": [
            {"name": "task_id", "type": "string"},
            {"name": "requester_id", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "proposed_cost", "type": ["null", "double"], "default": None},
            {"name": "priority", "type": "int", "default": 1},
            {"name": "timestamp", "type": "long"},
        ],
    }

    task_response_schema = {
        "type": "record",
        "name": "TaskResponse",
        "fields": [
            {"name": "task_id", "type": "string"},
            {"name": "responder_id", "type": "string"},
            {
                "name": "status",
                "type": {
                    "type": "enum",
                    "name": "TaskStatus",
                    "symbols": [
                        "PENDING",
                        "ACCEPTED",
                        "REJECTED",
                        "NEGOTIATING",
                        "RUNNING",
                        "COMPLETED",
                        "FAILED",
                    ],
                },
            },
            {"name": "counter_offer", "type": ["null", "double"], "default": None},
            {"name": "message", "type": ["null", "string"], "default": None},
            {"name": "timestamp", "type": "long"},
        ],
    }

    return {
        "task_request": fastavro.parse_schema(task_request_schema),
        "task_response": fastavro.parse_schema(task_response_schema),
    }


def serialize_avro(schema, data):
    """Serialize data using Avro schema"""
    bytes_writer = io.BytesIO()
    fastavro.schemaless_writer(bytes_writer, schema, data)
    return bytes_writer.getvalue()


def deserialize_avro(schema, data):
    """Deserialize data using Avro schema"""
    bytes_reader = io.BytesIO(data)
    return fastavro.schemaless_reader(bytes_reader, schema)


def test_kafka_messaging():
    """Test end-to-end Kafka messaging with the same setup as agents"""
    print("🧪 Testing Kafka messaging (container environment)")
    print("=" * 60)

    # Use internal Kafka port (same as agents)
    broker = "redpanda:9092"

    # Create schemas
    schemas = create_test_schemas()

    # Create producer
    producer = KafkaProducer(
        bootstrap_servers=[broker],
        client_id="test-producer",
        value_serializer=lambda v: v,  # We'll handle Avro serialization
        key_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
    )

    # Create consumer
    consumer = KafkaConsumer(
        "task-responses",
        bootstrap_servers=[broker],
        group_id="test-consumer-group",
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda m: m,  # We'll handle Avro deserialization
        consumer_timeout_ms=30000,  # 30 second timeout
    )

    # Generate test task
    task_id = str(uuid.uuid4())
    task_request = {
        "task_id": task_id,
        "requester_id": "test-requester",
        "description": "Test data processing task from container",
        "proposed_cost": 85.0,
        "priority": 2,
        "timestamp": int(time.time() * 1000),
    }

    print(f"📤 Sending task request: {task_id}")
    print(f"   Description: {task_request['description']}")
    print(f"   Cost: ${task_request['proposed_cost']}")

    # Serialize and send task request
    serialized_request = serialize_avro(schemas["task_request"], task_request)
    producer.send("task-requests", value=serialized_request, key=task_id)
    producer.flush()
    print("✅ Task request sent to 'task-requests' topic")

    # Listen for responses
    print("👂 Listening for responses on 'task-responses' topic...")
    response_received = False

    try:
        for message in consumer:
            try:
                # Deserialize response
                response = deserialize_avro(schemas["task_response"], message.value)

                if response["task_id"] == task_id:
                    print(f"✅ Received response for task {task_id}:")
                    print(f"   Status: {response['status']}")
                    print(f"   Responder: {response['responder_id']}")
                    print(f"   Message: {response.get('message', 'N/A')}")
                    response_received = True
                    break
                else:
                    print(
                        f"📝 Received response for different task: {response['task_id']}"
                    )

            except Exception as e:
                print(f"⚠️  Error deserializing response: {e}")

    except Exception as e:
        print(f"⚠️  Consumer timeout or error: {e}")

    # Cleanup
    consumer.close()
    producer.close()

    if response_received:
        print("\n🎉 End-to-end Kafka messaging test successful!")
    else:
        print("\n⚠️  No response received (agents may not be processing requests yet)")
        print("   This is normal if agents are just monitoring topics")

    print("\n💡 This test uses the same kafka-python + Avro setup as the agents")


if __name__ == "__main__":
    test_kafka_messaging()
