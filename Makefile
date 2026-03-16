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
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep BE_REPO_PATH | cut -d= -f2)" --service order-service --vectors

# Full pipeline: index codebase + regenerate docs (endpoints, handler contexts)
index-order-service-full:
	. $(VENV)/bin/activate && python -m indexer.runner --repo "$$(cat .env | grep BE_REPO_PATH | cut -d= -f2)" --service order-service --vectors --docs

# Index any service by name (set SERVICE_NAME and SERVICE_REPO in .env or pass as args)
index-service:
	. $(VENV)/bin/activate && python -m indexer.runner --repo $(SERVICE_REPO) --service $(SERVICE_NAME) --vectors --docs

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