.DEFAULT_GOAL := help

# Per-review pipeline stages (runbook §5). Each run screens exactly one review, using
# that review's own reviews/<review>/reviews.toml + config.json subfolder (runbook §2, §6
# explain why: reviews are different screening questions, never pooled) -- proving
# attest's core mechanism means running this independently once per review, pointing
# REVIEWS_FILE/CONFIG/RUN_DIR/TRACK/VALIDATE_OUT at a different review's subfolder each
# time (a Makefile override, no file hand-editing). All stages after `screen` run
# entirely offline over data/run/; only `screen` touches vendor APIs.
#
# Override any variable on the command line, e.g.:
#   make all REVIEWS_FILE=reviews/Appenzeller-Herzog_2019/reviews.toml \
#            CONFIG=reviews/Appenzeller-Herzog_2019/config.json \
#            RUN_DIR=data/run_Appenzeller-Herzog_2019 TRACK=Appenzeller-Herzog_2019 \
#            VALIDATE_OUT=results/validation_record_Appenzeller-Herzog_2019.json
#   make audit-draw AUDIT_SIZE=3000   # a specific sample size instead

PROJECT      ?= attest-paper
REVIEWS_FILE ?= reviews/van_de_Schoot_2018/reviews.toml
CONFIG       ?= reviews/van_de_Schoot_2018/config.json
GOLD         ?= data/gold.json
RUN_DIR      ?= data/run
RESULTS_DIR  ?= results
# Free-text label recorded on the run's provenance record -- keep in sync with
# REVIEWS_FILE/CONFIG's active review (they must always name the same review).
TRACK        ?= van_de_Schoot_2018
# Set to an int to use network-free DeterministicRaters instead of live
# vendors, e.g. `make screen DETERMINISTIC_SEED=1` to smoke-test the
# pipeline before spending on real vendor calls. Empty (default) = live.
DETERMINISTIC_SEED ?=

# "all" audits the entire screen-excluded population instead of a sample --
# gold labels are free (SYNERGY is already published), so the recall floor
# is exact rather than merely a floor. Override with a number for a smaller
# sample when auditing against real, non-free human labels.
AUDIT_SIZE   ?= all
AUDIT_SEED   ?= 42
AUDIT_TODO   ?= data/audit_todo.json
AUDIT_DONE   ?= data/audit_done.json

CONFIDENCE   ?= 0.95
VALIDATE_OUT ?= $(RESULTS_DIR)/validation_record.json

# Cross-review summary (runbook §6) -- tabulates however many already-completed,
# independent runs' validation_record.json files exist. Not part of `all`: a single run
# has nothing to compare itself against yet. Supply pairs after at least two reviews have
# been run, e.g.:
#   make review-summary REVIEW_SUMMARY_INPUTS="van_de_Schoot_2018=results/validation_record_van_de_Schoot_2018.json Appenzeller-Herzog_2019=results/validation_record_Appenzeller-Herzog_2019.json"
REVIEW_SUMMARY_INPUTS ?=
REVIEW_SUMMARY_OUT     ?= $(RESULTS_DIR)/review_summary.json

# ablate reads its own --aggregation/--tau/--zero-policy; it does not read
# config.json. Keep these in sync with config.json's "aggregation"/"tau"/
# "zero_policy" by hand.
AGGREGATION  ?= boundary_dispersion
TAU          ?= 0.5386751345948129
ZERO_POLICY  ?= escalate
ABLATE_OUT   ?= $(RESULTS_DIR)/ablation.json

# Sentinel set for the latent-vendor-drift sentinel (runbook §6). Gitignored and rebuilt
# via `make sentinelset` at the start of a real run, same as $(GOLD) -- disposable until
# a second epoch is actually opened, at which point freeze the exact file epoch 1 used
# (`git add -f`) so both epochs compare against the identical probe. `all` assumes it
# already exists for this run and does not rebuild it.
SENTINEL_SET       ?= data/sentinel_set.json
SENTINEL_PER_TRACK ?= 10
SENTINEL_SEED      ?= 43

# Governance (runbook §6): empty by default -- a first `screen` on a fresh RUN_DIR logs an
# initial_config changelog event. Set all three together to log a deliberate config change
# against a predecessor run directory instead (same review, a new epoch -- not a switch to
# a different review's subfolder, which is a separate independent run, not an epoch), e.g.:
#   make screen RUN_DIR=data/run_van_de_Schoot_2018_epoch2 CONFIG=reviews/van_de_Schoot_2018/config_epoch2.json \
#        PREVIOUS_RUN_DIR=data/run_van_de_Schoot_2018 CHANGE_REASON="..." APPROVER=reviewer-a
PREVIOUS_RUN_DIR ?=
CHANGE_REASON    ?=
APPROVER         ?=

# Validation-protocol descriptor (runbook §6) -- analysis-plan provenance, hashed into its
# own protocol_id, separate from config.json/ensemble_config_id. hard-trigger-crossings/
# advisory-alpha-threshold are the kernel's own sentinel defaults
# (attest.provenance.sentinel.DEFAULT_HARD_TRIGGER_CROSSINGS/DEFAULT_ADVISORY_ALPHA_THRESHOLD),
# passed explicitly here so they're on record in the persisted protocol rather than implicit.
# STRATIFY_BY=track (also audit-draw's --stratify-by-track below) is a harmless no-op with
# a single review per run -- one track, one stratum -- kept as the honest default rather
# than STRATIFY_NONE so both still work unchanged if a pooled multi-review run ever returns.
STRATIFY_BY              ?= track
AUDIT_SIZE_POLICY        ?= n=$(AUDIT_SIZE) exclusions (rule-of-three floor)
ADJUDICATION_DESCRIPTION ?= Fully automatic: score-audit scores drawn records against SYNERGY's published gold labels; no live human reviewer in this repo's pipeline.
HARD_TRIGGER_CROSSINGS   ?= 2
ADVISORY_ALPHA_THRESHOLD ?= 0.80
SENTINEL_CADENCE_NOTE    ?= sentinel-init runs immediately after screen; sentinel-check runs once after the epoch's pipeline completes. For a --mode batch --wait screen run spanning hours, re-run 'make sentinel-check' manually every few hours while the batch is outstanding.

.PHONY: help dirs goldset sentinelset screen sentinel-init audit-draw audit-score audit-apply \
	validate ablate protocol sentinel-check manifest verify review-summary all clean-run

help:
	@echo "targets: goldset sentinelset screen sentinel-init audit-draw audit-score audit-apply \\"
	@echo "         validate ablate protocol sentinel-check manifest verify review-summary all clean-run"

dirs:
	mkdir -p data $(RESULTS_DIR)

## 0. Build the sentinel set (runbook §6), gitignored like $(GOLD) -- rebuild freely
##    until a second epoch is opened, then freeze that exact file (`git add -f`).
##    Not part of `all`, since a run assumes $(SENTINEL_SET) already exists for it.
sentinelset: dirs
	build-sentinelset --reviews-file $(REVIEWS_FILE) --project $(PROJECT) \
		--per-track $(SENTINEL_PER_TRACK) --seed $(SENTINEL_SEED) --out $(SENTINEL_SET)

## 1. Build the gold set from the selected SYNERGY reviews (runbook §3).
goldset: dirs
	build-goldset --reviews-file $(REVIEWS_FILE) --project $(PROJECT) --out $(GOLD)

## 2. Run the prefilter + x-vendor ensemble over the gold set. The only
##    paid, networked stage -- freeze $(RUN_DIR) once this succeeds. On a fresh
##    RUN_DIR, logs an initial_config changelog event by default, or an
##    explicit_config_change event when PREVIOUS_RUN_DIR/CHANGE_REASON/APPROVER are set.
screen: dirs
	attest screen --input $(GOLD) --config $(CONFIG) --run-dir $(RUN_DIR) --track $(TRACK) \
		$(if $(DETERMINISTIC_SEED),--deterministic-seed $(DETERMINISTIC_SEED),) \
		$(if $(PREVIOUS_RUN_DIR),--previous-run-dir $(PREVIOUS_RUN_DIR),) \
		$(if $(CHANGE_REASON),--change-reason "$(CHANGE_REASON)",) \
		$(if $(APPROVER),--approver $(APPROVER),)

## 2b. Capture this epoch's baseline sentinel ratings, immediately after screen.
sentinel-init: dirs
	attest sentinel-init --run-dir $(RUN_DIR) --sentinel-input $(SENTINEL_SET) \
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
##    rate, confusion) for the run directory's current epoch -- for the one review
##    this run screened. Never pooled across reviews; see review-summary below for
##    comparing multiple already-completed, independent runs side by side.
validate: dirs
	attest validate --run-dir $(RUN_DIR) --input $(GOLD) --confidence $(CONFIDENCE) \
		--out $(VALIDATE_OUT)

## 7. Run the x-sweep ablation (all 11 subsets at x = 4) over stored votes
##    restricted to gold-labeled records.
ablate: dirs
	attest ablate --run-dir $(RUN_DIR) --input $(GOLD) --aggregation $(AGGREGATION) \
		--tau $(TAU) --zero-policy $(ZERO_POLICY) --out $(ABLATE_OUT)

## 8. Build and persist this run directory's validation-protocol descriptor, hashed
##    into its own protocol_id. Run once artifacts are in their final state for this
##    epoch, and before sentinel-check so its thresholds come from this protocol.
protocol: dirs
	attest protocol --run-dir $(RUN_DIR) --stratify-by $(STRATIFY_BY) \
		--audit-size-policy "$(AUDIT_SIZE_POLICY)" --confidence-level $(CONFIDENCE) \
		--adjudication-description "$(ADJUDICATION_DESCRIPTION)" \
		--hard-trigger-crossings $(HARD_TRIGGER_CROSSINGS) \
		--advisory-alpha-threshold $(ADVISORY_ALPHA_THRESHOLD) \
		--sentinel-cadence-note "$(SENTINEL_CADENCE_NOTE)"

## 9. Re-evaluate every vendor against its stored sentinel baseline (thresholds read
##    from the protocol persisted in step 8). On a hard trigger, see runbook §6 for
##    the response: open a fresh RUN_DIR the same way as an explicit config change.
sentinel-check: dirs
	attest sentinel-check --run-dir $(RUN_DIR) --sentinel-input $(SENTINEL_SET) \
		$(if $(DETERMINISTIC_SEED),--deterministic-seed $(DETERMINISTIC_SEED),)

## 10. Build and persist a run manifest hashing every artifact this run directory
##     holds (config, protocol, votes, changelog, sentinel evaluations, ...).
manifest: dirs
	attest manifest --run-dir $(RUN_DIR) --input $(GOLD) --seed audit-draw=$(AUDIT_SEED) \
		--seed sentinel=$(SENTINEL_SEED) \
		$(if $(DETERMINISTIC_SEED),--seed screen=$(DETERMINISTIC_SEED),)

## 11. Offline-verify every artifact's SHA-256 against the manifest built in step 10.
##     Exits non-zero on any mismatch or missing artifact -- gate CI/archival on this.
verify:
	attest verify --run-dir $(RUN_DIR)

## Cross-review: tabulate however many already-completed, independent runs' validation
## records exist side by side. Run manually once at least two reviews are done; see
## REVIEW_SUMMARY_INPUTS above.
review-summary: dirs
	review-summary $(foreach r,$(REVIEW_SUMMARY_INPUTS),--review $(r)) --out $(REVIEW_SUMMARY_OUT)

## Full reproducible pipeline for whichever review's REVIEWS_FILE/CONFIG point at
## (default: van_de_Schoot_2018), in order. Assumes $(SENTINEL_SET) already exists for
## this run (build it via `make sentinelset` first). To run against a different review:
## point REVIEWS_FILE/CONFIG at that review's reviews/<review>/ subfolder (see
## example_config.json to draft a new one) and use a fresh RUN_DIR, so each review's run
## is its own independent, self-contained proof, e.g.:
##   make all REVIEWS_FILE=reviews/Appenzeller-Herzog_2019/reviews.toml \
##            CONFIG=reviews/Appenzeller-Herzog_2019/config.json \
##            RUN_DIR=data/run_Appenzeller-Herzog_2019 TRACK=Appenzeller-Herzog_2019 \
##            VALIDATE_OUT=results/validation_record_Appenzeller-Herzog_2019.json
## An epoch is locked to one ensemble configuration per run directory
## (attest.io.store.RunStore.write_epoch refuses to reuse a run directory across a config
## change) -- the same fresh-RUN_DIR convention also applies to a deliberate config change
## within one review's own sequence of epochs, via PREVIOUS_RUN_DIR/CHANGE_REASON/APPROVER
## above.
all: goldset screen sentinel-init audit-draw audit-score audit-apply validate \
	ablate protocol sentinel-check manifest verify

## Remove one epoch's run directory and audit files so it can be redone.
## Never touches data/gold.json (expensive to rebuild) or results/ (the
## paper's committed numbers).
clean-run:
	rm -rf $(RUN_DIR) $(AUDIT_TODO) $(AUDIT_DONE)
