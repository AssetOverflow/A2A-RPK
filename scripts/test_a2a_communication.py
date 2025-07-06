#!/usr/bin/env python3
"""
Test script for A2A communication system
Demonstrates end-to-end task request, negotiation, and execution
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any


class A2ATestClient:
    """Test client for A2A system"""

    def __init__(self):
        self.requester_url = "http://localhost:8001"
        self.provider_url = "http://localhost:8002"
        self.executor_url = "http://localhost:8003"
        self.console_url = "http://localhost:8080"

    async def test_agent_health(self):
        """Test that all agents are healthy (monitoring endpoints only)"""
        print("🔍 Testing agent health (monitoring endpoints)...")

        async with httpx.AsyncClient() as client:
            agents = [
                ("Requester", self.requester_url),
                ("Provider", self.provider_url),
                ("Executor", self.executor_url),
            ]

            for name, url in agents:
                try:
                    response = await client.get(f"{url}/health", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        print(
                            f"✅ {name} Agent ({data['agent_id']}): {data['status']} - {data['communication']}"
                        )
                    else:
                        print(f"❌ {name} Agent: HTTP {response.status_code}")
                except Exception as e:
                    print(f"❌ {name} Agent: {e}")

    async def test_agent_status(self):
        """Get detailed status from all agents (for monitoring, not messaging)"""
        print(
            "\n📊 Getting agent status (monitoring only - messaging is pure Kafka)..."
        )

        async with httpx.AsyncClient() as client:
            agents = [
                ("Requester", self.requester_url),
                ("Provider", self.provider_url),
                ("Executor", self.executor_url),
            ]

            for name, url in agents:
                try:
                    response = await client.get(f"{url}/status", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        print(f"\n{name} Agent Status:")
                        print(json.dumps(data, indent=2))
                    else:
                        print(f"❌ {name} Agent status: HTTP {response.status_code}")
                except Exception as e:
                    print(f"❌ {name} Agent status: {e}")

    async def simulate_task_workflow(self):
        """Explain the pure Kafka communication workflow"""
        print("\n🚀 A2A Communication Flow (Pure Kafka/RPK)...")

        print("📝 How agents communicate (NO REST messaging):")
        print(
            "  1. 🟢 Requester → Kafka Producer → 'task-requests' topic → Provider's Consumer"
        )
        print(
            "  2. 🔵 Provider → Kafka Producer → 'task-responses' topic → Requester's Consumer"
        )
        print("  3. 🟡 If negotiation: Bidirectional via 'negotiations' topic")
        print("  4. 🟣 Executor monitors 'task-responses' → executes ACCEPTED tasks")
        print(
            "  5. ✨ All messages are Avro schema-validated via Redpanda Schema Registry"
        )
        print("")
        print("🔧 The /health and /status endpoints are ONLY for monitoring!")
        print("🔧 All business logic happens via Kafka topics with schema validation.")
        print("🔧 Use MCP protocol via Docker MCP Toolkit for agent control.")

        # Future: Add actual Kafka message testing here
        print(
            "\n💡 To test actual messaging, implement Kafka producer/consumer test clients"
        )

    async def check_kafka_topics(self):
        """Check if Kafka topics exist and are ready for A2A communication"""
        print("\n📡 Checking A2A Kafka topics...")

        try:
            async with httpx.AsyncClient() as client:
                # Try to access Redpanda Console API
                response = await client.get(
                    f"{self.console_url}/api/topics", timeout=10
                )
                if response.status_code == 200:
                    topics = response.json()
                    print("✅ Redpanda Console accessible")

                    topic_names = [
                        t.get("topicName", "unknown") for t in topics.get("topics", [])
                    ]
                    print(f"📋 Available topics: {topic_names}")

                    # Check for required A2A topics
                    required_topics = [
                        "task-requests",
                        "task-responses",
                        "negotiations",
                    ]
                    missing_topics = [
                        t for t in required_topics if t not in topic_names
                    ]

                    if not missing_topics:
                        print("✅ All required A2A topics exist")
                    else:
                        print(f"⚠️  Missing topics: {missing_topics}")
                        print(
                            "💡 Run: docker exec redpanda rpk topic create <topic-name>"
                        )

                else:
                    print(f"⚠️  Redpanda Console: HTTP {response.status_code}")
        except Exception as e:
            print(f"⚠️  Could not access Redpanda Console: {e}")
            print("💡 You can manually check at http://localhost:8080")


async def main():
    """Run all tests"""
    client = A2ATestClient()

    print("🧪 A2A Communication System Test")
    print("=" * 50)
    print("NOTE: Agents communicate via Kafka topics ONLY")
    print("HTTP endpoints are for health/status monitoring only")
    print("=" * 50)

    await client.test_agent_health()
    await client.test_agent_status()
    await client.check_kafka_topics()
    await client.simulate_task_workflow()

    print("\n✨ Test completed!")
    print("\n💡 Next steps:")
    print("  - Visit http://localhost:8080 for Redpanda Console")
    print("  - Check agent logs: docker-compose logs -f")
    print("  - All A2A messaging happens via Kafka topics with Avro schemas")
    print("  - Use MCP protocol for agent control via Docker MCP Toolkit")


if __name__ == "__main__":
    asyncio.run(main())
