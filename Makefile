.PHONY: install dev test lint demo clean

install:
	python -m pip install -e .

dev:
	python -m pip install -e '.[dev]'

test:
	pytest

lint:
	ruff check .

demo:
	guardrail-lab --config config.demo.yaml all --archive

clean:
	rm -rf data reports archives demo-output .pytest_cache .ruff_cache build dist *.egg-info
