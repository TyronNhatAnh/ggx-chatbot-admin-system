# ===== CONFIG =====
APP=app.main:app
PORT=8000
VENV=.venv

# ===== SETUP =====

install:
	python3 -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -r requirements.txt

deps:
	. $(VENV)/bin/activate && pip install -r requirements.txt

# ===== RUN =====

run:
	. $(VENV)/bin/activate && uvicorn $(APP) --host 0.0.0.0 --port $(PORT)

debug:
	. $(VENV)/bin/activate && uvicorn $(APP) --reload --host 0.0.0.0 --port $(PORT)

# ===== DISCOVERY / EXPLORER =====

scan-fe:
	. $(VENV)/bin/activate && python scripts/run_discovery.py scan-fe

scan-be:
	. $(VENV)/bin/activate && python scripts/run_discovery.py scan-be

map-flows:
	. $(VENV)/bin/activate && python scripts/run_discovery.py map-flows

scan-all:
	. $(VENV)/bin/activate && python scripts/run_discovery.py scan-all

discover:
	. $(VENV)/bin/activate && python scripts/run_discovery.py scan-all

# ===== CODEBASE INDEXER =====

index:
	. $(VENV)/bin/activate && python -m indexer.runner --repo $(BE_REPO) --service $(SERVICE)

index-vectors:
	. $(VENV)/bin/activate && python -m indexer.runner --repo $(BE_REPO) --service $(SERVICE) --vectors

index-order-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep ORDER_SERVICE_REPO_PATH | cut -d= -f2)" --service order-service --lang go --vectors

# Full pipeline: index codebase + regenerate docs (endpoints, handler contexts)
index-order-service-full:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep ORDER_SERVICE_REPO_PATH | cut -d= -f2)" --service order-service --lang go --vectors --docs

# Index any service by name — set SERVICE_REPO, SERVICE_NAME, and optionally LANG
# Examples:
#   make index-service SERVICE_REPO=/path/to/repo SERVICE_NAME=admin-service LANG=java
#   make index-service SERVICE_REPO=/path/to/web2 SERVICE_NAME=web2 LANG=react
index-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo $(SERVICE_REPO) --service $(SERVICE_NAME) $(if $(LANG),--lang $(LANG)) --vectors --docs

# Cross-service endpoint linking — matches React API calls to Go handlers
# Run after indexing both backend and frontend services
link:
	. $(VENV)/bin/activate && python -m indexer.linker

# Index all configured services + run linker in one command
# Reads ORDER_SERVICE_REPO_PATH, WEB2_REPO_PATH, USER_SERVICE_REPO_PATH from .env
index-all:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep ORDER_SERVICE_REPO_PATH | cut -d= -f2)" --service order-service --lang go --vectors --docs
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep WEB2_REPO_PATH | cut -d= -f2)" --service web2 --lang react --vectors
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep USER_SERVICE_REPO_PATH | cut -d= -f2)" --service user-service --lang go --vectors --docs
	. $(VENV)/bin/activate && python -m indexer.linker

explore:
	. $(VENV)/bin/activate && python scripts/explore_feature.py --interactive

explore-feature:
	. $(VENV)/bin/activate && python scripts/explore_feature.py --interactive

explore-feature-auto:
	. $(VENV)/bin/activate && python scripts/explore_feature.py --feature "$(FEATURE)"

explore-feature-all:
	. $(VENV)/bin/activate && python scripts/explore_feature.py --full-auto --feature "$(FEATURE)"

# ===== DOCKER =====

docker-run:
	docker compose up --build

# ===== CLEAN =====

clean:
	rm -rf $(VENV)