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