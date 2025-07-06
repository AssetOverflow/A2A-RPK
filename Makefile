# Makefile for A2A-RPK Project

# Variables
DOCKER_COMPOSE = docker-compose
PYTHON = python3

# Default target
.PHONY: all
all: help

# Help target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  up          - Start the Docker Compose stack"
	@echo "  down        - Stop and remove the Docker Compose stack"
	@echo "  restart     - Restart the Docker Compose stack"
	@echo "  up-and-test - Start stack, setup environment, and run full test suite"
	@echo "  test-health - Run health and status tests"
	@echo "  test-kafka  - Run Kafka messaging tests"
	@echo "  init-schemas - Initialize schemas in the registry"
	@echo "  setup-env   - Setup Python environment and install dependencies"

# Start the Docker Compose stack
.PHONY: up
up:
	$(DOCKER_COMPOSE) up -d

# Stop and remove the Docker Compose stack
.PHONY: down
down:
	$(DOCKER_COMPOSE) down

# Restart the Docker Compose stack
.PHONY: restart
restart: down up

# Run health and status tests
.PHONY: test-health
test-health:
	$(PYTHON) scripts/test_a2a_communication.py

# Run Kafka messaging tests
.PHONY: test-kafka
test-kafka:
	$(PYTHON) scripts/test_kafka_messaging.py

# Initialize schemas in the registry
.PHONY: init-schemas
init-schemas:
	$(PYTHON) scripts/init_schemas.py init

# Setup Python environment and install dependencies
.PHONY: setup-env
setup-env:
	@echo "🐍 Setting up Python environment..."
	@which pip > /dev/null || (echo "❌ pip not found. Please install Python/pip first." && exit 1)
	@echo "📦 Installing dependencies from requirements.txt..."
	pip install -r requirements.txt
	@echo "✅ Python environment ready!"

# Wait for services to be ready
.PHONY: wait-for-services
wait-for-services:
	@echo "⏳ Waiting for services to be ready..."
	@echo "Checking Schema Registry..."
	@for i in $$(seq 1 30); do \
		if curl -s http://localhost:18081/config > /dev/null 2>&1; then \
			echo "✅ Schema Registry ready"; \
			break; \
		fi; \
		if [ $$i -eq 30 ]; then \
			echo "❌ Schema Registry not ready after 60s"; \
			exit 1; \
		fi; \
		echo "Waiting for Schema Registry... ($$i/30)"; \
		sleep 2; \
	done
	@echo "Checking Agent services..."
	@for port in 8001 8002 8003; do \
		echo "Checking Agent on port $$port..."; \
		for i in $$(seq 1 30); do \
			if curl -s http://localhost:$$port/health > /dev/null 2>&1; then \
				echo "✅ Agent on port $$port ready"; \
				break; \
			fi; \
			if [ $$i -eq 30 ]; then \
				echo "❌ Agent on port $$port not ready after 60s"; \
				exit 1; \
			fi; \
			echo "Waiting for Agent $$port... ($$i/30)"; \
			sleep 2; \
		done; \
	done
	@echo "✅ All services are ready!"

# Run full test suite
.PHONY: run-tests
run-tests:
	@echo "🧪 Running A2A test suite..."
	@echo ""
	@echo "📋 Step 1: Initialize schemas..."
	$(PYTHON) scripts/init_schemas.py init
	@echo ""
	@echo "🔍 Step 2: Health and status tests..."
	$(PYTHON) scripts/test_a2a_communication.py
	@echo ""
	@echo "📡 Step 3: Kafka messaging tests..."
	$(PYTHON) scripts/test_kafka_messaging.py
	@echo ""
	@echo "🎉 All tests completed successfully!"

# Complete workflow: Start stack, setup environment, and run full test suite
.PHONY: up-and-test
up-and-test: setup-env
	@echo "🚀 A2A-RPK Complete Workflow Starting..."
	@echo "================================================"
	@echo ""
	@echo "📦 Step 1: Building and starting containers..."
	$(DOCKER_COMPOSE) up --build -d
	@echo ""
	@$(MAKE) wait-for-services
	@echo ""
	@$(MAKE) run-tests
	@echo ""
	@echo "🎉 A2A-RPK Complete Workflow Finished Successfully!"
	@echo "================================================"
	@echo ""
	@echo "💡 Services available:"
	@echo "   - Redpanda Console: http://localhost:8080"
	@echo "   - Schema Registry:  http://localhost:18081"
	@echo "   - Agent 1 (Requester): http://localhost:8001/docs"
	@echo "   - Agent 2 (Provider):  http://localhost:8002/docs"
	@echo "   - Agent 3 (Executor):  http://localhost:8003/docs"
