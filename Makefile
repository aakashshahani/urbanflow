# UrbanFlow developer entrypoints. Local-first (free), AWS at the end.
.DEFAULT_GOAL := help
SHELL := /bin/bash
DBT_DIR := dbt/urbanflow

.PHONY: help up down seed build test demo lint api measure tf-init tf-apply tf-destroy deploy-aws

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Start local stack (MinIO + Iceberg REST + Trino + Postgres + Airflow)
	docker compose up -d
	@echo "MinIO console  http://localhost:9001  (minioadmin/minioadmin)"
	@echo "Trino          http://localhost:8080"
	@echo "Airflow        http://localhost:8081"

down: ## Stop the local stack
	docker compose down

seed: ## Download a sample month of TLC + weather into bronze Iceberg
	python -m ingestion.tlc --months $${TLC_MONTHS:-2024-01}
	python -m ingestion.weather --months $${TLC_MONTHS:-2024-01}

build: ## dbt build: staging -> marts (local Trino/Iceberg)
	cd $(DBT_DIR) && dbt build --target local

test: ## pytest + dbt tests + Great Expectations
	pytest -q
	cd $(DBT_DIR) && dbt test --target local
	python -m quality.run_checks

lint: ## ruff + sqlfluff
	ruff check .
	cd $(DBT_DIR) && sqlfluff lint models

api: ## Run the FastAPI /metrics service
	uvicorn api.main:app --reload --port 8000

METABASE_DRIVER := metabase/plugins/starburst-6.1.0.metabase-driver.jar
metabase: ## Fetch the Trino driver, start Metabase, build the mobility dashboard
	@test -f $(METABASE_DRIVER) || curl -L -o $(METABASE_DRIVER) \
	  https://github.com/starburstdata/metabase-driver/releases/download/6.1.0/starburst-6.1.0.metabase-driver.jar
	docker compose up -d metabase
	python -m scripts.setup_metabase

measure: ## Benchmark Athena/Trino bytes-scanned before/after optimization
	python -m scripts.measure_scan

demo: up seed build test ## One-command end-to-end on the sample slice
	@echo "UrbanFlow demo complete. See Metabase or make api"

tf-init: ## terraform init
	cd terraform && terraform init

tf-apply: ## Provision AWS (S3 + Glue + Athena + IAM); no VPC/NAT, no Redshift, no MWAA
	cd terraform && terraform apply

deploy-aws: ## Run the pipeline once against AWS (URBANFLOW_TARGET=aws)
	URBANFLOW_TARGET=aws python -m ingestion.tlc --months $${TLC_MONTHS:-2024-01}
	URBANFLOW_TARGET=aws python -m ingestion.weather --months $${TLC_MONTHS:-2024-01}
	# unit tests excluded on Athena: its temp tables force millisecond timestamps
	cd $(DBT_DIR) && dbt build --target aws --exclude-resource-type unit_test

tf-destroy: ## Tear down all AWS resources
	cd terraform && terraform destroy
