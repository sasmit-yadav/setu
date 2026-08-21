PY ?= python

.PHONY: demo db-up db-migrate seed check snapshot doctor fetch-basemap ml provision-demo neon-seed-config

demo:
	$(PY) run.py demo

fetch-basemap:
	$(PY) run.py fetch-basemap

ml:
	$(PY) run.py ml

provision-demo:
	$(PY) run.py provision-demo

neon-seed-config:
	$(PY) run.py neon-seed-config

db-up:
	$(PY) run.py db-up

db-migrate:
	$(PY) run.py db-migrate

seed:
	$(PY) run.py seed

snapshot:
	$(PY) run.py snapshot

doctor:
	$(PY) run.py doctor

check:
	$(PY) run.py check
