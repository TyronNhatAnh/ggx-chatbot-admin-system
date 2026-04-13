# ===== CONFIG =====
APP=app.main:app
PORT=8000
VENV=.venv
PYTHON=python3.11
# Default to local config; override with: APP_ENV=stag make run
APP_ENV ?= local

# ===== SETUP =====

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install -r requirements.txt

deps:
	$(VENV)/bin/python -m pip install -r requirements.txt

# ===== RUN =====

run:
	. $(VENV)/bin/activate && APP_ENV=$(APP_ENV) uvicorn $(APP) --host 0.0.0.0 --port $(PORT)

debug:
	. $(VENV)/bin/activate && APP_ENV=$(APP_ENV) uvicorn $(APP) --reload --host 0.0.0.0 --port $(PORT)

# ===== CODEBASE INDEXER =====

# Index a single service — generic entry point
# Examples:
#   make index-service SERVICE_REPO=/path/to/repo SERVICE_NAME=order-service LANG=go
#   make index-service SERVICE_REPO=/path/to/web2 SERVICE_NAME=web2 LANG=react
#   make index-service ... FORCE=1   # bypass incremental hash check
index-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo $(SERVICE_REPO) --service $(SERVICE_NAME) $(if $(LANG),--lang $(LANG)) --vectors $(if $(FORCE),--force)

# Shortcuts for pre-configured services (reads repo path from shell env vars)
# Export these in your shell, e.g.: export ORDER_SERVICE_REPO_PATH=/path/to/repo
# Add FORCE=1 to any target to bypass the incremental hash check and re-index.
index-order-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$(ORDER_SERVICE_REPO_PATH)" --service order-service --lang go --vectors $(if $(FORCE),--force)

index-user-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$(USER_SERVICE_REPO_PATH)" --service user-service --lang go --vectors $(if $(FORCE),--force)

index-driver-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$(DRIVER_SERVICE_REPO_PATH)" --service driver-service --lang go --vectors $(if $(FORCE),--force)

index-common-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$(COMMON_SERVICE_REPO_PATH)" --service common-service --lang go --vectors $(if $(FORCE),--force)

index-web2:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$(WEB2_REPO_PATH)" --service web2 --lang react --vectors $(if $(FORCE),--force)

# Java Spring Boot services (web-admin, etc.)
index-admin-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$(ADMIN_SERVICE_REPO_PATH)" --service admin-service --lang java --vectors $(if $(FORCE),--force)

# Cross-service endpoint linking — matches React API calls to Go handlers
# Run after indexing both backend and frontend services
link:
	. $(VENV)/bin/activate && python -m indexer.linker

# Index all configured services + run linker in one command
# Reads all *_REPO_PATH vars from .env automatically
# Skips vector embeddings (vectordb/ not used by active tools — saves ~105MB)
# Use FORCE=1 to bypass incremental hash check: make index-all FORCE=1
index-all:
	. $(VENV)/bin/activate && python -m indexer.index_all --no-vectors $(if $(FORCE),--force)

# Seed persona tags (one-time, run after re-indexing order-service)
seed-personas:
	. $(VENV)/bin/activate && PYTHONPATH=. python scripts/seed_persona_tags.py

# ===== DOCKER =====

# Image registry + name.  Set IMAGE in your shell or override per-call:
#   export IMAGE=gcr.io/my-gcp-project/ai-admin-assistant
#   make docker-release
IMAGE ?= ai-admin-assistant
TAG   ?= local

# Build the Docker image with knowledge data baked in.
# Run `make index-all` first so data/ is populated.
docker-build:
	docker build -t $(IMAGE):$(TAG) .
	@echo "Built $(IMAGE):$(TAG)"

# Run the container locally — mounts local vertex-ai.json, passes APP_ENV=local.
# Requires: app/config/local/vertex-ai.json to exist.
docker-run-local:
	docker run --rm \
		-p $(PORT):8000 \
		-e APP_ENV=local \
		-v "$$(pwd)/app/config/local/vertex-ai.json:/app/app/config/local/vertex-ai.json:ro" \
		$(IMAGE):$(TAG)

# Build then run locally in one step
docker-test: docker-build docker-run-local

# Run via Docker Compose (local convenience, uses docker-compose.yml)
docker-run:
	docker compose up --build -d

# ===== CLEAN =====

clean:
	rm -rf $(VENV)