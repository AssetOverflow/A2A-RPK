#!/bin/bash

# Setup script for A2A-RPK project

echo "🚀 Setting up A2A-RPK project..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✅ Docker is running"

# Check if Docker Compose is available
if ! docker compose version >/dev/null 2>&1; then
    echo "❌ Docker Compose not found. Please install Docker Compose v2+."
    exit 1
fi

echo "✅ Docker Compose is available"

# Pull required images
echo "📥 Pulling Docker images..."
docker pull redpandadata/redpanda:latest
docker pull redpandadata/console:latest

# Create Kafka topics
echo "🗂️  Creating Kafka topics..."

# Start only Redpanda first to create topics
docker compose up -d redpanda

# Wait for Redpanda to be ready
echo "⏳ Waiting for Redpanda to be ready..."
sleep 30

# Create topics using rpk
docker exec redpanda rpk topic create task-requests --partitions 3 --replicas 1
docker exec redpanda rpk topic create task-responses --partitions 3 --replicas 1  
docker exec redpanda rpk topic create negotiations --partitions 3 --replicas 1

echo "✅ Kafka topics created"

# Start the complete stack
echo "🏗️  Starting complete A2A stack..."
docker compose up -d

echo "⏳ Waiting for all services to be ready..."
sleep 45

# Check service health
echo "🔍 Checking service health..."

# Check Redpanda
if curl -f -s http://localhost:9644/v1/cluster/health_overview >/dev/null; then
    echo "✅ Redpanda is healthy"
else
    echo "⚠️  Redpanda may not be ready yet"
fi

# Check Console
if curl -f -s http://localhost:8080 >/dev/null; then
    echo "✅ Redpanda Console is accessible"
else
    echo "⚠️  Redpanda Console may not be ready yet"
fi

# Check agents
for port in 8001 8002 8003; do
    if curl -f -s http://localhost:$port/health >/dev/null; then
        echo "✅ Agent on port $port is healthy"
    else
        echo "⚠️  Agent on port $port may not be ready yet"
    fi
done

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 Available services:"
echo "  - Redpanda Console: http://localhost:8080"
echo "  - Requester Agent:   http://localhost:8001"
echo "  - Provider Agent:    http://localhost:8002" 
echo "  - Executor Agent:    http://localhost:8003"
echo ""
echo "🧪 Run tests with:"
echo "  python scripts/test_a2a_communication.py"
echo ""
echo "📊 Monitor logs with:"
echo "  docker compose logs -f"
