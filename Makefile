.PHONY: install-precommit-hooks style-check test

install-precommit-hooks:
	pre-commit install --install-hooks

style-check:
	pre-commit run --all-files isort
	pre-commit run --all-files black

test:
	pytest --cov=opentelemetry_instrumentation_rq tests/unit_test

e2e_test:
	docker compose -f tests/e2e_test/env_setup/docker-compose.yaml down --remove-orphans
	docker compose -f tests/e2e_test/env_setup/docker-compose.yaml up -d --wait
	pytest --cov=opentelemetry_instrumentation_rq tests/e2e_test
