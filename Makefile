.PHONY: install-precommit-hooks style-check test

install-precommit-hooks:
	pre-commit install --install-hooks

style-check:
	pre-commit run --all-files isort
	pre-commit run --all-files black

test:
	pytest --cov=opentelemetry_instrumentation_rq tests/
