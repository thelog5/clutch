PY ?= .venv/bin/python
UV ?= uv

.PHONY: setup pull pull-smoke pull-sample explore refresh features train eval precompute deploy-bundle synthetic api api-fake web test lint

## Python env with training + dev extras (torch, matplotlib, pytest, ruff)
setup:
	$(UV) venv --python 3.12 .venv
	$(UV) pip install --python .venv -e ".[train,dev]"
	cd web && npm install

## Real data: pull game lists + play-by-play from stats.nba.com (1-2 hours, resumable)
pull:
	$(PY) -m pipeline.pull

## Check stats.nba.com access with a handful of games before the long pull
pull-smoke:
	$(PY) -m pipeline.pull --limit 5

## Quick real-data test: 150 games per season (~25 min). The full pull reuses them.
## Then: make features train precompute, make api, make web
pull-sample:
	$(PY) -m pipeline.pull --per-season 150

## New games since the last pull -> replay bundle (no retraining). Run weekly.
refresh:
	$(PY) -m pipeline.pull
	$(PY) -m pipeline.features
	$(PY) -m api.precompute
	$(PY) -m api.precompute --seasons 2024-25 2025-26 2026-27 --out api/data

## Build one feature row per play -> data/features.parquet
features:
	$(PY) -m pipeline.features

## Train logistic regression, XGBoost and the MLP, then write the eval report
train:
	$(PY) -m model.train
	$(PY) -m model.evaluate

## Page for looking inside the trained models -> reports/explorer.html (rerun after make train)
explore:
	$(PY) -m scripts.model_explorer

eval:
	$(PY) -m model.evaluate

## Precompute per-game probability series the API serves for replay
precompute:
	$(PY) -m api.precompute

## Slim bundle the deployed API serves: last two seasons + the current one -> api/data/
deploy-bundle:
	$(PY) -m api.precompute --seasons 2024-25 2025-26 2026-27 --out api/data

## Synthetic dataset for development (no network). Writes to data/synthetic/
synthetic:
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m pipeline.synthetic
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m pipeline.features
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m model.train
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m model.evaluate
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m api.precompute

api:
	CLUTCH_DOCS=1 $(PY) -m uvicorn api.main:app --reload --port 8000

## API on the synthetic dataset with fake live games (no network needed)
api-fake:
	CLUTCH_DATA_DIR=data/synthetic CLUTCH_LIVE_SOURCE=fake $(PY) -m uvicorn api.main:app --reload --port 8000

web:
	cd web && npm run dev

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .
