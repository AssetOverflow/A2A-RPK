<!-- @format -->

# A2A-RPK: Agent-to-Agent Communication with Redpanda Kafka

A complete implementation of agent-to-agent communication infrastructure using Redpanda Kafka, Docker MCP Toolkit, and schema-verified messaging.

## Architecture

This project demonstrates:

- **Redpanda Kafka** for schema-verified, durable message streaming
- **Docker MCP Toolkit** for standardized agent protocol
- **Pure Kafka Communication** - agents communicate ONLY via Kafka topics
- **Schema Registry** for Avro/Protobuf message validation
- **Docker Compose** orchestration for complete stack
- **Health Endpoints** for monitoring (NO business logic via REST)

## Components

- `redpanda/` - Redpanda Kafka broker with schema registry
- `agents/` - MCP-compatible agents with pure Kafka communication
- `schemas/` - Avro/Protobuf schema definitions
- `docker-compose.yml` - Complete infrastructure stack
- `scripts/` - Utility scripts for testing and management

## Communication Flow

**✅ Messaging (Pure Kafka/RPK):**

- Requester → `task-requests` topic → Provider
- Provider → `task-responses` topic → Requester
- Bidirectional negotiation via `negotiations` topic
- Executor monitors `task-responses` for ACCEPTED tasks
- All messages are Avro schema-validated

**✅ Monitoring (HTTP endpoints):**

- `/health` - Container health checks
- `/status` - Agent status monitoring
- MCP protocol for agent control

## Quick Start

### One-Command Complete Setup and Test

```bash
# Complete workflow: setup environment, start stack, and run tests
make up-and-test
```

This single command will:

1. 🐍 Setup Python environment and install dependencies
2. 📦 Build and start all Docker containers
3. ⏳ Wait for all services to be ready
4. 📋 Initialize Avro schemas in the registry
5. 🔍 Run health and status tests
6. 📡 Run end-to-end Kafka messaging tests

### Manual Step-by-Step

```bash
# Setup Python environment (run once)
make setup-env

# Start the complete stack
make up
# OR: docker-compose up -d

# Initialize schemas (run once)
make init-schemas
# OR: python scripts/init_schemas.py init

# Check Redpanda console
open http://localhost:8080

# Test health/monitoring
make test-health
# OR: python scripts/test_a2a_communication.py

# Test actual Kafka messaging
make test-kafka
# OR: python scripts/test_kafka_messaging.py
```

### Available Make Commands

```bash
make help           # Show all available commands
make up             # Start Docker containers
make down           # Stop and remove containers
make up-and-test    # Complete setup and test workflow
make setup-env      # Setup Python environment
make init-schemas   # Initialize schema registry
make test-health    # Run health/status tests
make test-kafka     # Run Kafka messaging tests
```

## Schema Management

The project includes a comprehensive schema registry manager:

```bash
# Initialize all schemas and policies
python scripts/init_schemas.py init

# Check schema registry health
python scripts/init_schemas.py health

# List all registered schemas
python scripts/init_schemas.py list

# Get schema details
python scripts/init_schemas.py info --subject task-requests-value

# Export schemas for backup
python scripts/init_schemas.py export --output-dir ./backup-schemas
```

## Features

- ✅ Schema-verified messaging (Avro/Protobuf)
- ✅ Replayable event logs
- ✅ Multi-turn agent negotiation via Kafka
- ✅ Durable, fault-tolerant storage
- ✅ MCP-standard agent protocol
- ✅ Auto-discovery and authentication
- ✅ Pure Kafka communication (NO REST messaging)
- ✅ Health monitoring endpoints

## Environment Requirements

- Docker Desktop with MCP Toolkit enabled
- Python 3.11+
- Docker Compose v2+
