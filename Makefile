.PHONY: setup generate validate load build reconcile all clean

PY := python3
DBT := dbt --project-dir dbt --profiles-dir dbt

setup:
	$(PY) -m pip install -r requirements.txt

generate:                ## synthetic raw layer + reference frames
	$(PY) src/generate_data.py --out data/raw --emit-reference

validate:                ## are the planted findings still there?
	$(PY) src/validate_findings.py

load:                    ## raw CSVs -> Postgres schema `raw`
	$(PY) src/load_to_postgres.py --dir data/raw

build:                   ## staging -> intermediate -> marts, with tests
	$(DBT) build

reconcile:               ## does the pipeline recover the truth?
	$(PY) src/reconcile_marts.py

golden:                  ## regenerate the values Power BI must reproduce
	$(PY) src/export_golden_values.py > powerbi/golden_values.md

dashboard:               ## rebuild the static demo in docs/index.html
	$(PY) src/export_dashboard_data.py > powerbi/dashboard_data.json
	$(PY) src/build_dashboard.py

serve:                   ## preview the demo locally
	@echo "http://localhost:8000/"
	@cd docs && $(PY) -m http.server 8000

docs:
	$(DBT) docs generate && $(DBT) docs serve

all: generate validate load build reconcile golden dashboard

clean:
	rm -rf data dbt/target dbt/logs
