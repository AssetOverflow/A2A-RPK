<!-- @format -->

# A2A-RPK: Agent-to-Agent Communication with Redpanda Kafka

## Problem Statement

Modern agent-to-agent (A2A) communication systems face several critical challenges:

1. **Schema Drift**: Messages between agents can become inconsistent over time
2. **Non-Replayable Communications**: Lost audit trails and debugging capabilities
3. **Fragile REST APIs**: Synchronous HTTP calls create tight coupling and failure cascades
4. **No Event Sourcing**: Inability to reconstruct system state from message history
5. **Complex Multi-Turn Negotiations**: Difficult to manage asynchronous, stateful conversations
6. **Monitoring vs Messaging Confusion**: Business logic mixed with health monitoring

## Proposed Solution

A **pure Kafka-based A2A communication infrastructure** that separates concerns:

### Core Principles

- **Schema-Verified Messaging**: All business communication via Kafka with Avro validation
- **HTTP for Monitoring Only**: Health checks and status endpoints (NO business messaging)
- **Event Sourcing**: Complete audit trail of all agent interactions
- **Asynchronous by Default**: Multi-turn negotiations without blocking
- **MCP Integration**: Standardized agent discovery and control protocol

## Solution Architecture

### 1. Communication Layers

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Monitoring    │    │    Control      │    │   Messaging     │
│   (HTTP/REST)   │    │     (MCP)       │    │   (Kafka RPK)   │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ /health         │    │ Agent Discovery │    │ task-requests   │
│ /status         │    │ Authentication  │    │ task-responses  │
│ /metrics        │    │ Tool Invocation │    │ negotiations    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2. Agent Types & Responsibilities

#### Requester Agent (Port 8001)

**Purpose**: Initiates task requests and manages negotiations

**Kafka Communication**:

- **Publishes to**: `task-requests` (task submissions)
- **Subscribes to**: `task-responses` (status updates), `negotiations` (negotiation responses)

**HTTP Endpoints** (monitoring only):

- `GET /health` - Container health for orchestration
- `GET /status` - Current state and metrics

**Key Methods**:

```python
await requester.request_task(description, proposed_cost)
await requester.get_pending_requests()
```

#### Provider Agent (Port 8002)

**Purpose**: Evaluates requests, negotiates terms, accepts/rejects tasks

**Kafka Communication**:

- **Subscribes to**: `task-requests` (incoming requests), `negotiations` (negotiation messages)
- **Publishes to**: `task-responses` (acceptance/rejection), `negotiations` (counter-offers)

**Capabilities**: Configurable skill sets for task matching
**Negotiation Logic**: Automatic or rule-based offer evaluation

#### Executor Agent (Port 8003)

**Purpose**: Executes accepted tasks and provides progress updates

**Kafka Communication**:

- **Subscribes to**: `task-responses` (monitoring for ACCEPTED tasks)
- **Publishes to**: `task-responses` (execution progress: RUNNING → COMPLETED/FAILED)

**Execution**: Asynchronous task processing with status broadcasting

### 3. Message Flow & Schema Design

#### Complete A2A Workflow:

```
1. 🟢 Requester → kafka-producer → task-requests → Provider-consumer
2. 🔵 Provider → kafka-producer → task-responses[NEGOTIATING] → Requester-consumer
3. 🟡 Multi-turn: negotiations topic ↔ bidirectional messages
4. 🟢 Provider → kafka-producer → task-responses[ACCEPTED] → Executor-consumer
5. 🟣 Executor → kafka-producer → task-responses[RUNNING/COMPLETED] → All-consumers
```

#### Schema Evolution Strategy:

- **Backward Compatibility**: New fields with defaults
- **Forward Compatibility**: Ignore unknown fields
- **Schema Registry**: Centralized validation and versioning
- **Gradual Migration**: Deploy schema changes incrementally

### 4. Redpanda Kafka Infrastructure

#### Why Redpanda over Apache Kafka?

- **Built-in Schema Registry**: No separate Confluent services needed
- **C++ Performance**: Lower latency than JVM-based Kafka
- **Raft Consensus**: No ZooKeeper dependency
- **Kafka API Compatible**: Drop-in replacement for existing tools
- **Single Binary**: Simplified deployment and operations

#### Topic Configuration:

```bash
# Task workflow topics
rpk topic create task-requests --partitions 3 --replicas 1
rpk topic create task-responses --partitions 3 --replicas 1
rpk topic create negotiations --partitions 3 --replicas 1
```

### 5. Docker MCP Toolkit Integration

#### MCP Server Configuration:

```json
{
  "mcpServers": {
    "a2a-requester": {
      "command": "docker",
      "args": ["exec", "-it", "agent-requester", "python", "-m", "mcp_server"]
    }
  }
}
```

#### MCP Tools Available:

- `get_agent_status` - Current agent state
- `request_task` - Submit new task (Requester only)
- `get_execution_queue` - View pending tasks (Executor only)
- Resource access to agent state and task history

## Implementation Details

### 1. Core Technologies & Libraries

**Python Dependencies**:

```
confluent-kafka[avro,schemaregistry]==2.3.0  # Kafka + Schema Registry
fastapi==0.104.1                              # HTTP monitoring endpoints
pydantic==2.5.0                               # Data validation
mcp==1.0.0                                    # Model Context Protocol
```

**Infrastructure**:

- **Redpanda**: `redpandadata/redpanda:latest`
- **Console UI**: `redpandadata/console:latest`
- **Docker Compose**: Orchestration and networking

### 2. Schema Definitions (Avro)

#### TaskRequest Schema:

```json
{
  "type": "record",
  "name": "TaskRequest",
  "fields": [
    { "name": "task_id", "type": "string" },
    { "name": "requester_id", "type": "string" },
    { "name": "description", "type": "string" },
    { "name": "proposed_cost", "type": ["null", "double"], "default": null },
    { "name": "priority", "type": "int", "default": 1 },
    { "name": "timestamp", "type": "long" }
  ]
}
```

#### TaskResponse Schema:

```json
{
  "type": "record",
  "name": "TaskResponse",
  "fields": [
    { "name": "task_id", "type": "string" },
    { "name": "responder_id", "type": "string" },
    {
      "name": "status",
      "type": {
        "type": "enum",
        "symbols": [
          "PENDING",
          "ACCEPTED",
          "REJECTED",
          "NEGOTIATING",
          "RUNNING",
          "COMPLETED",
          "FAILED"
        ]
      }
    },
    { "name": "counter_offer", "type": ["null", "double"], "default": null },
    { "name": "message", "type": ["null", "string"], "default": null },
    { "name": "timestamp", "type": "long" }
  ]
}
```

### 3. Agent Base Implementation

```python
class AgentBase(ABC):
    def __init__(self, agent_id: str):
        self.kafka_broker = os.getenv("KAFKA_BROKER", "localhost:19092")
        self.schema_registry_url = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:18081")

    async def initialize(self):
        # Setup Kafka producer/consumer + schema registry
        # Register Avro schemas and create serializers/deserializers
        # Subscribe to relevant topics
        # Start background message consumer loop

    async def send_message(self, topic: str, message_type: str, data: Dict):
        # Serialize with schema validation
        # Produce to Kafka topic

    @abstractmethod
    async def _process_message(self, msg):
        # Handle incoming Kafka messages (implemented by subclasses)
```

## Usage Guide

### 1. Quick Start

```bash
# Clone and start the complete stack
git clone <repo>
cd A2A-RPK
./scripts/setup.sh

# Verify health
python scripts/test_a2a_communication.py

# Test actual Kafka messaging
python scripts/test_kafka_messaging.py
```

### 2. Accessing Services

| Service          | URL                          | Purpose                  |
| ---------------- | ---------------------------- | ------------------------ |
| Redpanda Console | http://localhost:8080        | Topic/message inspection |
| Requester Agent  | http://localhost:8001/health | Health monitoring        |
| Provider Agent   | http://localhost:8002/status | Status monitoring        |
| Executor Agent   | http://localhost:8003/status | Status monitoring        |

### 3. Monitoring Communication

```bash
# View real-time messages
docker exec redpanda rpk topic consume task-requests --format json

# Check topic status
docker exec redpanda rpk topic list

# View agent logs
docker-compose logs -f agent-requester
```

## Refactoring for Production Use

### 1. Replace In-Memory Storage

**Current**: Tasks stored in Python dictionaries
**Production**:

```python
# Use persistent database
from sqlalchemy import create_engine
from redis import Redis

# Task state in PostgreSQL/Redis
async def store_task(task_id: str, task_data: dict):
    await db.execute("INSERT INTO tasks ...")
```

### 2. Add Authentication & Authorization

```python
# JWT token validation
from fastapi import Depends, HTTPException
from jwt import decode

async def verify_agent_token(token: str = Depends(oauth2_scheme)):
    # Validate agent identity and permissions

# Kafka message encryption
producer_config = {
    'security.protocol': 'SASL_SSL',
    'sasl.mechanisms': 'PLAIN',
    'sasl.username': config.kafka_username,
    'sasl.password': config.kafka_password
}
```

### 3. Production Infrastructure

**Kubernetes Deployment**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: a2a-requester
spec:
  replicas: 3
  selector:
    matchLabels:
      app: a2a-requester
  template:
    spec:
      containers:
        - name: agent
          image: your-registry/a2a-agent:latest
          env:
            - name: AGENT_TYPE
              value: "requester"
            - name: KAFKA_BROKER
              value: "redpanda-cluster:9092"
```

**Monitoring & Alerting**:

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

message_count = Counter('a2a_messages_total', 'Total messages', ['agent_type', 'topic'])
processing_time = Histogram('a2a_processing_seconds', 'Processing time')

# Custom health checks
async def check_kafka_connectivity():
    # Verify can produce/consume from topics
```

### 4. Schema Evolution Process

1. **Add new optional fields** with defaults
2. **Deploy updated agents** gradually
3. **Monitor compatibility** via schema registry
4. **Migrate data** if needed for breaking changes
5. **Remove deprecated fields** after full migration

### 5. Scaling Strategies

**Horizontal Agent Scaling**:

```bash
# Scale specific agent types
docker-compose up --scale agent-provider=3
docker-compose up --scale agent-executor=5
```

**Kafka Partitioning**:

```bash
# Increase partitions for parallel processing
rpk topic alter task-requests --partitions 10
```

**Load Balancing**:

- Use agent pools with round-robin task assignment
- Implement back-pressure when queues are full
- Add circuit breakers for failing agents

## Development Benefits

### 1. **Event Sourcing Capabilities**

- Complete audit trail of all agent interactions
- Ability to replay scenarios for debugging
- State reconstruction from message history
- Compliance and regulatory reporting

### 2. **Schema Evolution**

- Add new message fields without breaking existing agents
- Gradual migration strategies
- Backward/forward compatibility enforcement

### 3. **Testing & Debugging**

- Message replay from production logs
- Schema validation in development
- Integration testing with real Kafka messages
- Monitoring via Redpanda Console

### 4. **Operational Excellence**

- Health monitoring separate from business logic
- Structured logging with correlation IDs
- Metrics and alerting via standard tools
- Blue-green deployments with message compatibility

### 5. **Future Extensions**

- Add new agent types without architectural changes
- Implement complex workflow orchestration
- Integration with external systems via Kafka Connect
- Machine learning on message patterns and agent behavior

## Summary

This A2A-RPK implementation provides a robust, scalable foundation for agent-to-agent communication that:

- ✅ **Separates concerns**: Monitoring (HTTP) vs Messaging (Kafka) vs Control (MCP)
- ✅ **Ensures data integrity**: Schema validation prevents message corruption
- ✅ **Enables audit trails**: Complete event sourcing and replay capabilities
- ✅ **Supports async workflows**: Multi-turn negotiations without blocking
- ✅ **Scales horizontally**: Add agents without architectural changes
- ✅ **Future-proof**: Schema evolution and gradual migration support

The architecture is production-ready with clear paths for authentication, persistence, monitoring, and scaling.
