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

# ===== CLEAN =====

clean:
	rm -rf $(VENV)