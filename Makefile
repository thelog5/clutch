PY ?= .venv/bin/python
UV ?= uv

.PHONY: setup pull features train eval precompute synthetic api web test lint

## Python env with training + dev extras (torch, matplotlib, pytest, ruff)
setup:
	$(UV) venv --python 3.12 .venv
	$(UV) pip install --python .venv -e ".[train,dev]"
	cd web && npm install

## Real data: pull game lists + play-by-play from stats.nba.com (1-2 hours, resumable)
pull:
	$(PY) -m pipeline.pull

## Build one feature row per play -> data/features.parquet
features:
	$(PY) -m pipeline.features

## Train logistic regression, XGBoost and the MLP, then write the eval report
train:
	$(PY) -m model.train
	$(PY) -m model.evaluate

eval:
	$(PY) -m model.evaluate

## Precompute per-game probability series the API serves for replay
precompute:
	$(PY) -m api.precompute

## Synthetic dataset for development (no network). Writes to data/synthetic/
synthetic:
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m pipeline.synthetic
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m pipeline.features
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m model.train
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m model.evaluate
	CLUTCH_DATA_DIR=data/synthetic $(PY) -m api.precompute

api:
	$(PY) -m uvicorn api.main:app --reload --port 8000

web:
	cd web && npm run dev

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .
