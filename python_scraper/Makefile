.PHONY: lint

lint:
	@echo "=== Esecuzione Pylint ==="
	pylint $$(git ls-files '*.py')
	@echo "=== Esecuzione Flake8 ==="
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	@echo "=== Esecuzione Mypy ==="
	mypy $$(git ls-files '*.py')
	@echo "=== Esecuzione Black ==="
	black --check --diff $$(git ls-files '*.py')
	@echo "=== Esecuzione Isort ==="
	isort --profile black --check-only --diff $$(git ls-files '*.py')
	@echo "🎉 Tutti i controlli sono passati!"