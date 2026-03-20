# ===== CONFIG =====
APP=app.main:app
PORT=8000
VENV=.venv
PYTHON=python3.11

# ===== SETUP =====

install:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -r requirements.txt

deps:
	. $(VENV)/bin/activate && pip install -r requirements.txt

# ===== RUN =====

run:
	. $(VENV)/bin/activate && uvicorn $(APP) --host 0.0.0.0 --port $(PORT)

debug:
	. $(VENV)/bin/activate && uvicorn $(APP) --reload --host 0.0.0.0 --port $(PORT)

# ===== CODEBASE INDEXER =====

# Index a single service — generic entry point
# Examples:
#   make index-service SERVICE_REPO=/path/to/repo SERVICE_NAME=order-service LANG=go
#   make index-service SERVICE_REPO=/path/to/web2 SERVICE_NAME=web2 LANG=react
index-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo $(SERVICE_REPO) --service $(SERVICE_NAME) $(if $(LANG),--lang $(LANG)) --vectors

# Shortcuts for pre-configured services (reads repo path from .env)
index-order-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep ORDER_SERVICE_REPO_PATH | cut -d= -f2)" --service order-service --lang go --vectors

index-user-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep USER_SERVICE_REPO_PATH | cut -d= -f2)" --service user-service --lang go --vectors

index-driver-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep DRIVER_SERVICE_REPO_PATH | cut -d= -f2)" --service driver-service --lang go --vectors

index-common-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep COMMON_SERVICE_REPO_PATH | cut -d= -f2)" --service common-service --lang go --vectors

index-web2:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep WEB2_REPO_PATH | cut -d= -f2)" --service web2 --lang react --vectors

# Java Spring Boot services (web-admin, etc.)
index-admin-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep ADMIN_SERVICE_REPO_PATH | cut -d= -f2)" --service admin-service --lang java --vectors

# Cross-service endpoint linking — matches React API calls to Go handlers
# Run after indexing both backend and frontend services
link:
	. $(VENV)/bin/activate && python -m indexer.linker

# Index all configured services + run linker in one command
# Reads all *_REPO_PATH vars from .env automatically
index-all:
	. $(VENV)/bin/activate && python -m indexer.index_all

# Seed persona tags (one-time, run after re-indexing order-service)
seed-personas:
	. $(VENV)/bin/activate && PYTHONPATH=. python scripts/seed_persona_tags.py

# ===== DOCKER =====

docker-run:
	docker compose up --build

# ===== CLEAN =====

clean:
	rm -rf $(VENV)