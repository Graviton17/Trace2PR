.PHONY: install dev lint format typecheck test docker-build docker-run migrate

install:
	pip install -e ".[dev]"

dev:
	python main.py

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy trace2pr

test:
	pytest

docker-build:
	docker build -t trace2pr-backend .

docker-run:
	docker run -p 8000:8000 --env-file .env trace2pr-backend

migrate:
	@echo "Run migration scripts here"
