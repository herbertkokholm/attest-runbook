.DEFAULT_GOAL := help

# Paper-level pipeline stages (runbook §5). All stages after `screen` run
# entirely offline over data/run/; only `screen` touches vendor APIs.
#
# Override any variable on the command line, e.g.:
#   make screen RUN_DIR=data/run_epoch2 CONFIG=config_epoch2.json
#   make audit-draw AUDIT_SIZE=3000   # tighter recall-floor claim

PROJECT      ?= attest-paper
REVIEWS_FILE ?= reviews.toml
CONFIG       ?= config.json
GOLD         ?= data/gold.json
RUN_DIR      ?= data/run
RESULTS_DIR  ?= results
TRACK        ?= synergy-5-reviews
# Set to an int to use network-free DeterministicRaters instead of live
# vendors, e.g. `make screen DETERMINISTIC_SEED=1` to smoke-test the
# pipeline before spending on real vendor calls. Empty (default) = live.
DETERMINISTIC_SEED ?=

AUDIT_SIZE   ?= 600
AUDIT_SEED   ?= 42
AUDIT_TODO   ?= data/audit_todo.json
AUDIT_DONE   ?= data/audit_done.json

CONFIDENCE   ?= 0.95
VALIDATE_OUT ?= $(RESULTS_DIR)/validation_record.json

# ablate reads its own --aggregation/--tau; it does not read config.json.
# Keep these in sync with config.json's "aggregation"/"tau" by hand.
AGGREGATION  ?= boundary_dispersion
TAU          ?= 0.75
ABLATE_OUT   ?= $(RESULTS_DIR)/ablation.json

.PHONY: help dirs goldset screen audit-draw audit-score audit-apply validate ablate all clean-run

help:
	@echo "targets: goldset screen audit-draw audit-score audit-apply validate ablate all clean-run"

dirs:
	mkdir -p data $(RESULTS_DIR)

## 1. Build the gold set from the selected SYNERGY reviews (runbook §3).
goldset: dirs
	build-goldset --reviews-file $(REVIEWS_FILE) --project $(PROJECT) --out $(GOLD)

## 2. Run the prefilter + x-vendor ensemble over the gold set. The only
##    paid, networked stage -- freeze $(RUN_DIR) once this succeeds.
screen: dirs
	attest screen --input $(GOLD) --config $(CONFIG) --run-dir $(RUN_DIR) --track $(TRACK) \
		$(if $(DETERMINISTIC_SEED),--deterministic-seed $(DETERMINISTIC_SEED),)

## 3. Draw a stratified random recall-audit sample from the screen-excluded
##    population.
audit-draw: dirs
	attest audit-draw --run-dir $(RUN_DIR) --input $(GOLD) --size $(AUDIT_SIZE) \
		--stratify-by-track --seed $(AUDIT_SEED) > $(AUDIT_TODO)

## 4. Score the drawn sample against SYNERGY's published gold labels, for a
##    fully reproducible audit (runbook §5 step 4). To layer an independent
##    human pass on top, edit $(AUDIT_DONE) after this and before audit-apply.
audit-score: dirs
	score-audit --todo $(AUDIT_TODO) --gold $(GOLD) --out $(AUDIT_DONE)

## 5. Apply the scored audit labels to the run.
audit-apply:
	attest audit-apply --run-dir $(RUN_DIR) --labels $(AUDIT_DONE)

## 6. Assemble the validation record (alpha, recall floor + CI, escalation
##    rate, confusion) for the run directory's current epoch.
validate: dirs
	attest validate --run-dir $(RUN_DIR) --input $(GOLD) --confidence $(CONFIDENCE) \
		--out $(VALIDATE_OUT)

## 7. Run the x-sweep ablation (all 11 subsets at x = 4) over stored votes
##    restricted to gold-labeled records.
ablate: dirs
	attest ablate --run-dir $(RUN_DIR) --input $(GOLD) --aggregation $(AGGREGATION) \
		--tau $(TAU) --out $(ABLATE_OUT)

## Full reproducible pipeline for one epoch, in order. For a second epoch,
## change config.json (a new model/prompt version) and rerun with a fresh
## RUN_DIR (an epoch is locked to one ensemble configuration per run
## directory -- attest.io.store.RunStore.write_epoch refuses to reuse a run
## directory across a config change), e.g.:
##   make all RUN_DIR=data/run_epoch2 CONFIG=config_epoch2.json \
##            VALIDATE_OUT=results/validation_record_epoch2.json
all: goldset screen audit-draw audit-score audit-apply validate ablate

## Remove one epoch's run directory and audit files so it can be redone.
## Never touches data/gold.json (expensive to rebuild) or results/ (the
## paper's committed numbers).
clean-run:
	rm -rf $(RUN_DIR) $(AUDIT_TODO) $(AUDIT_DONE)
