# attest-runbook

Paper-level pipeline for the `attest` screening-and-self-validation kernel. This repo
imports `attest`; the kernel never imports it. It proves attest's core mechanism — read a
title/abstract, apply one eligibility instruction, four vendors each vote
include/exclude/uncertain, decide whether to escalate to a human — by running the whole
pipeline **independently once per SYNERGY review**, scored against that review's own real
gold labels. See §6 for why runs are never pooled across reviews.

Order: create the repo (§0) → gold standard (§1) → the chosen reviews (§2) → build the
gold set (§3) → keys and config (§4) → run the CLI (§5) → configuration governance,
protocol, the sentinel, and why runs are never pooled (§6) → assemble the paper (§7). §8
is the pre-run checklist.

---

## §0 The `attest-runbook` private repo

Layout:
```
attest-runbook/
  pyproject.toml            # deps: attest (from git or path), synergy-dataset
  README.md                 # this runbook, plus SYNERGY attribution (CC0, cite De Bruin et al. 2023)
  .gitignore                # .env, large data, raw run/ (see below)
  .env.example               # names of the four vendor key vars, no values
  example_config.json       # TEMPLATE for drafting a new review's config (§2, §4) -- not runnable as-is
  reviews/                  # one subfolder per review this repo can run against (§2)
    van_de_Schoot_2018/
      reviews.toml          # `reviews = ["van_de_Schoot_2018"]` -- what build-goldset fetches
      config.json           # ensemble Config for this review: vendors, its own default_prompt, aggregation, tau, x=4
    Appenzeller-Herzog_2019/
      reviews.toml
      config.json
    Muthu_2021/
      reviews.toml
      config.json
  src/build_goldset.py      # SYNERGY -> attest input contract (§3)
  src/build_sentinelset.py  # SYNERGY -> sentinel-set input contract (§6)
  src/score_audit.py        # scores a drawn audit sample against SYNERGY gold (§5)
  src/review_summary.py     # tabulates N independent runs' validation_record.json files side by side (§6)
  tests/                    # tests for build_goldset.py, build_sentinelset.py, score_audit.py, review_summary.py
  Makefile                  # one target per pipeline stage (§5, §6)
  results/                  # SMALL committed artifacts: validation_record_<review>.json, review_summary.json, ablation.json
  data/                     # gitignored: gold.json (large), sentinel_set.json, run/ (frozen votes)
```

What to commit vs not:
- Commit: `example_config.json`, everything under `reviews/`, `build_goldset.py`,
  `build_sentinelset.py`, `review_summary.py`, `Makefile`, and the small result artifacts
  in `results/` (one `validation_record_<review>.json` per review run, `review_summary.json`,
  ablation). These are the paper's numbers.
- Do NOT commit: `.env` (keys), `data/gold.json` (large, regenerable from `build_goldset.py`).
- `data/sentinel_set.json` is gitignored and rebuilt via `make sentinelset` at the start of
  a real run, same as `data/gold.json` — disposable until you actually open a second
  epoch *for the same review*, at which point deliberately freeze the exact file the first
  epoch used (`git add -f data/sentinel_set.json`) so both epochs compare against the
  identical probe. A review that only ever runs one epoch never needs to commit it. See §6.
- The frozen `run/` (raw votes) is the true reproducibility artifact, because vendor outputs
  are not deterministic and cannot be regenerated identically. Archive it deliberately: Git
  LFS in this repo, or a tagged data release / DataverseNL deposit referenced from the paper.
  Do not rely on regenerating it.

---

## §1 Gold standard: use SYNERGY, not self-annotation

The single decision that governs whether the recall claim survives review. Do NOT
hand-annotate a fresh OpenAlex pull: a single annotator's judgment becomes the ground
truth, which is exactly the bias the method must be measured against, and reviewers
reject it.

Use SYNERGY (De Bruin, Ma, Ferdinands, Teijema, Van de Schoot, 2023; DOI
10.34894/HE6NAQ; CC0): 26 published systematic reviews, ~169k records, ~1.67%
inclusion, metadata sourced from OpenAlex, distributed via the `synergy-dataset` Python
package. Why it fits:

- Ground truth is published, human-adjudicated inclusion from real reviews, not ours.
- Extreme label sparsity (~1.67%) is the regime the recall floor exists for: `validate`
  reports both a rule-of-three/Wilson asymptotic floor and an exact, design-based
  hypergeometric floor (`recall.floor` / `recall.exact_floor`) side by side, not one
  replacing the other.
- 26 independent reviews across many domains, so the core mechanism can be proven
  review-by-review rather than on a single dataset.
- It is the benchmark the field already uses, so results are comparable and recognizable.
- OpenAlex-native, consistent with the intended production pipeline.

Label mapping: SYNERGY's `label_included` is the review's final inclusion decision (1
included, 0 excluded), the accepted relevance ground truth. It is binary, so gold maps
to +1 (included) / −1 (excluded); the ordinal 0 is a live-screening category, not a gold
category. Precision/recall against gold collapse the ensemble's operational decision to
include-vs-exclude.

---

## §2 The reviews: one subfolder per review, never pooled

Each SYNERGY review is a genuinely different screening question — its own eligibility
criteria, its own domain — not a repeat of the same measurement on different data. Running 
attest against three such reviews doesn't mean pooling their answers into one bucket-of-everything 
count; it means proving the same core mechanism (read, instruct, vote, escalate-or-not) 
works independently on each. Each review therefore gets its own `reviews/<review>/` 
subfolder — a `reviews.toml` naming just that one review, paired with a
`config.json` whose `default_prompt` is that review's own criteria — not a shared file
pooling several.

Review subfolders already drafted, vetted for a sparse-to-dense, cross-domain spread:

| Review | Domain | Records | Incl | Incl % | Why a good proof case |
| --- | --- | --- | --- | --- | --- |
| `van_de_Schoot_2018` | Psychology/Medicine | 4544 | 38 | 0.8% | Iconic PTSD review; sparse regime; the Makefile's default review |
| `Appenzeller-Herzog_2019` | Medicine | 2873 | 26 | 0.9% | Very sparse medicine; exercises the rule-of-three floor |
| `Muthu_2021` | Medicine | 2719 | 336 | 12.4% | Dense contrast; many includes; anchors the high end |

Confirm exact current counts with `synergy_dataset show <NAME>` before a real run — not
re-derived at build time. Any of SYNERGY's 26 reviews works — proving the core mechanism
means running against as many as it takes, 3 or 26, not picking one "best" benchmark; run
`synergy_dataset show <NAME>` for any new one before using it, don't assume unstated numbers.

**To run against a different review:** if it already has a `reviews/<review>/` subfolder,
just point the Makefile at it (below) — no file editing needed. To add a new one, copy
`example_config.json` (its own header comments walk through the steps: look up the
review's real `eligibility_criteria` in `asreview/synergy-dataset`'s `datasets.toml` and
verify it word for word — don't trust an old paraphrase, see
`reviews/Appenzeller-Herzog_2019/config.json`'s `_notes` for a worked example of a
paraphrase that silently dropped two real exclusion criteria on a first pass). Then run
`make all` pointed at that subfolder, under a fresh `RUN_DIR` per review (e.g.
`RUN_DIR=data/run_Appenzeller-Herzog_2019`):
```
make all REVIEWS_FILE=reviews/Appenzeller-Herzog_2019/reviews.toml \
         CONFIG=reviews/Appenzeller-Herzog_2019/config.json \
         RUN_DIR=data/run_Appenzeller-Herzog_2019 TRACK=Appenzeller-Herzog_2019 \
         VALIDATE_OUT=results/validation_record_Appenzeller-Herzog_2019.json
```
Each review's run is its own independent, self-contained proof — its own gold set, its own
votes, its own validation record, archived separately from every other review's run. Cost
per review: records × 4 vendors screening calls (e.g. `van_de_Schoot_2018` ≈ 4544 × 4 ≈
18.2k calls).

---

## §3 Gold-set builder

`build_goldset.py` imports the `synergy-dataset` package and emits JSON conforming to
`attest.contracts.input` (schema_version "1.0"). CLI:

```
build-goldset --reviews-file reviews/van_de_Schoot_2018/reviews.toml --project attest-paper --out data/gold.json
```

Mapping: `id` = OpenAlex id (fallback DOI); `title`, `abstract` from the metadata;
`track` = the review name; `ids` = DOI and OpenAlex id when present; `gold_label` = +1
if `label_included == 1`, else −1. Records with an empty/missing abstract are dropped
(standard benchmark practice); the count dropped per review is printed. Output is
validated via `attest.contracts.input.validate_and_normalize` before being written.
Reads whichever single review the given `--reviews-file` lists (§2) — the `track` field
this sets is still useful downstream (audit-draw's `--stratify-by-track`, provenance),
even though a run's population never spans more than one track today.

---

## §4 Keys, environment, and the ensemble config

- Install: depend on `attest[all]` (git or local path) and `synergy-dataset`.
- Copy `.env.example` to `.env` and set the vendors' API keys. `.env` is gitignored.
- Four distinct vendor families, x = 4: Anthropic `claude-sonnet-5` (pinned), OpenAI and
  Google (currently `TODO:pin-*-current-gen-dated-snapshot` — resolve before a real run),
  Mistral `mistral-large-2512` (pinned). The Mistral vendor needs the `attest[mistral]`
  extra (`mistralai>=2.9.1`, already included in `attest[all]`) and `MISTRAL_API_KEY`.
- Each `reviews/<review>/config.json`: vendors, per-vendor model+version, per-vendor prompt
  version, aggregation rule (only `"boundary_dispersion"` is implemented in the kernel
  today; `majority`/`unanimity` are recognized names but raise `NotImplementedError`),
  `tau` (currently `0.5386751345948129`, treat as tunable and report whatever is used),
  `zero_policy`, and `default_prompt`. Validated against the kernel's own loader
  (`attest.cli._load_ensemble_config`) — see `reviews/README.md` for the full rationale
  behind every field shared across reviews (each review's own `config.json`'s `_notes`
  covers only what's specific to that review, so the shared rationale isn't repeated three
  times over and going stale independently in each copy).
- **`batch_size`** (`attest.provenance.config.Config.batch_size`, "b_e") is the number of
  records attest packs into one screening request, hashed into `ensemble_config_id` like
  every field above. Set to `1` explicitly in every `reviews/<review>/config.json` — one
  record per request, this pipeline's actual instrument (§4/§6: one record at a time, four
  vendors voting independently on it) — rather than left to attest's own fallback default
  (also `1`), so the file states its instrument outright instead of implying it. See
  `reviews/README.md`'s `batch_size` section for the full rationale.
- **One list, one prompt.** Every vendor is screened with that review's `default_prompt` —
  its own published eligibility criteria (verbatim from SYNERGY's `datasets.toml`,
  reflowed to prose), not a generic instruction and not a per-track dict:
  `attest.provenance.config.Config.prompt_for_track` falls back to `default_prompt` for
  every record, since these files carry no `track_prompts` entries. This is deliberate,
  not a simplification of convenience — it's the literal shape attest's core mechanism
  assumes (one list of records, one instruction), and it's why each subfolder screens one
  review only (§2, §6): `track_prompts` (a dict routing per-track prompts within one
  pooled run) still works if a future pooled run ever needs it again, but the default
  design deliberately doesn't use it. **The kernel, not this file, owns the output-format
  instruction**: `attest.vendors.base.compose_system_prompt` appends its own
  `OUTPUT_CONTRACT` ("Respond with exactly one letter and nothing else: E to exclude, U if
  related but uncertain, or I to include.") to whatever criteria text is supplied, on
  every rater path, and warns if the supplied criteria already contains a copy of it. So
  `default_prompt` must carry only eligibility criteria — never a trailing output-format
  sentence of its own, or the composed prompt ships that instruction twice and trips the
  kernel's warning on every screen run. The vote itself is that single letter; the kernel
  separately translates it to a number (`-1`/`0`/`+1`) purely so `aggregation`/`tau`'s
  dispersion arithmetic has something to compute over (see `reviews/README.md`'s tau
  section) — the number is a computational convention, not what the vote is.
  `prompt_version` is still a provenance label only (`attest.provenance.config.VendorSpec`
  doesn't read it back), so keep it bumped by hand whenever `default_prompt` changes, or it
  will misrepresent what ran.
- Every field except `default_prompt` is identical across all three `reviews/*/config.json`
  files by design — the same fixed instrument (vendors, aggregation, tau, `zero_policy`) is
  what's being proven reliable across reviews, so it must not vary between them.
- **Sentinel set** (`data/sentinel_set.json`, gitignored — rebuilt via `make sentinelset`
  at the start of a real run, then frozen only if/when a second epoch is opened for the
  same review; see §6) is a separate, small input used only for the latent-vendor-drift
  sentinel — never for screening, accuracy, or recall numbers. Built via
  `build-sentinelset` (`src/`), which draws a deterministic, seeded sample of
  `SENTINEL_PER_TRACK` records (default 10) from whichever single review the active
  `reviews/<review>/reviews.toml` lists, stratified by that review's own `gold_label` split
  so the sample is naturally exclude-dominated for sparse reviews without a hardcoded
  ratio, and drops `gold_label` from the output (a diagnostic set, not a second gold set).
  Reusing real gold-set text as sentinel content is safe: `attest.provenance.sentinel`
  persists baselines/evaluations in their own files (`sentinel_baseline.json`,
  `sentinel_evaluations.json`), fully separate from `votes.json`/`decisions.json`, and its
  comparison is a vendor's rating on the same record over time (baseline vs. current) — it
  never reads `gold_label`, so there is no leakage into the recall/accuracy claims. Real
  abstracts also mean sentinel calls exercise the same `default_prompt` production
  screening uses, rather than generic filler text.
- `zero_policy` (default `"escalate"`) governs the one case the boundary+dispersion rule
  can't resolve by sign alone: a non-boundary vote vector whose mean lands exactly on `0`
  (e.g. all four vendors vote `0`). `Decision.auto_label` can never be `0` — under
  `"escalate"` (the recall-safe default, used here) it routes to human adjudication like
  any other escalation; the only other option is `"include"` (folds it into `+1`). There is
  deliberately no `"exclude"` option, since that's the one disposition that would silently
  destroy recall. This repo's `src/score_audit.py` only maps drawn record ids to SYNERGY
  gold labels for `audit-apply` and never itself branches on a predicted/auto label, so it
  needed no change for this.

---

## §5 Run sequence (Makefile targets; offline after `screen`)

All stages operate on files via the kernel's `io/store`; only `screen` touches the
network. Freeze `data/run/` once produced. Every target reads its inputs and writes its
outputs through variables (`GOLD`, `RUN_DIR`, `CONFIG`, `REVIEWS_FILE`, ...) with sensible
defaults (`reviews/van_de_Schoot_2018/`) — override them together on the command line to
run against a different review's subfolder; see the `Makefile`'s header comment.

0. `make sentinelset` (before a real run) -> `build-sentinelset --reviews-file reviews/van_de_Schoot_2018/reviews.toml --project attest-paper --per-track 10 --seed 43 --out data/sentinel_set.json`.
   Gitignored, like `data/gold.json` — rebuild it freely for each review's first epoch.
   Not part of `make all`, since a run assumes it already exists. Freeze it
   (`git add -f`) only if/when a second epoch is opened for the same review — see §6.
1. `make goldset` -> `build-goldset --reviews-file reviews/van_de_Schoot_2018/reviews.toml --project attest-paper --out data/gold.json`
2. `make screen` -> `attest screen --input data/gold.json --config reviews/van_de_Schoot_2018/config.json --run-dir data/run --track van_de_Schoot_2018`
   (the only paid, networked step; freeze `data/run/` after). `--track` is a free-text
   provenance label only (keep it naming the same review as `REVIEWS_FILE`/`CONFIG`) —
   which review's criteria actually get applied comes from `CONFIG`'s `default_prompt`,
   not this flag. Set `DETERMINISTIC_SEED=1` to smoke-test the whole pipeline with
   network-free, seeded raters first. This also runs `attest.ensemble.tau.validate_tau`
   against `CONFIG`'s `tau` and `x`, writes the proof to `data/run/tau_report.json`, and
   warns (not fails) on a suspicious tau (inert, or sitting exactly on an attainable
   dispersion value) — check for warnings after the first `screen` of an epoch. On a
   fresh `RUN_DIR` this also logs this epoch's first changelog event: `initial_config` by
   default, or `explicit_config_change` when `PREVIOUS_RUN_DIR`/`CHANGE_REASON`/`APPROVER`
   are set — see §6.
   1. `make sentinel-init` -> `attest sentinel-init --run-dir data/run --sentinel-input data/sentinel_set.json`
      captures this epoch's baseline sentinel ratings, immediately after `screen` — see §6.
3. `make audit-draw` -> `attest audit-draw --run-dir data/run --input data/gold.json --size 600 --stratify-by-track --seed 42 > data/audit_todo.json`.
   `--stratify-by-track` is a harmless no-op with one review per run (one track, one
   stratum) — kept on so it still works unchanged if a pooled multi-review run ever
   returns.
4. `make audit-score` -> scores the drawn sample against SYNERGY's own gold labels (via
   `score-audit`, this repo's script), writing `data/audit_done.json` — a fully
   reproducible audit with no manual step required. To layer an independent human pass on
   top, edit `data/audit_done.json` before the next step.
5. `make audit-apply` -> `attest audit-apply --run-dir data/run --labels data/audit_done.json
   --reviewer oracle-benchmark-gold --blinded` — stamped with the same
   `reviewer="oracle-benchmark-gold"` provenance as step 5b below; `--blinded` because
   `score-audit` looks up SYNERGY's published gold label without ever seeing the ensemble's
   screen-excluded decision, same as a real blinded human auditor would be.
5b. `make adjudicate` -> `adjudicate-from-gold --run-dir data/run --gold data/gold.json` resolves
    every ensemble-escalated decision (a tied or boundary-straddling vote vector) to SYNERGY's
    published gold label, stamped `reviewer="oracle-benchmark-gold"` in
    `data/run/adjudication_records.json` — benchmark evaluation only, never presented as live
    human adjudication. Without this step, `validate` refuses to run whenever screening
    produced any escalation (methods Sec. 2.9 requires every include-and-escalate record
    resolved before TP/recall means anything). To layer an independent human pass instead,
    resolve escalations via `attest adjudicate --run-dir data/run --record-id ... --label ...`
    before this step; it becomes a no-op once nothing is left pending.
6. `make validate` -> `attest validate --run-dir data/run --input data/gold.json --confidence 0.95
   --max-staleness-days 1 --out results/validation_record.json`
   assembles alpha, the confusion matrix, escalation rate, and the recall floor + CI for
   this one review's run. Never pooled across reviews — see §6 for `review-summary`, which
   compares multiple already-completed, independent runs once more than one exists. Reads
   this run's own `adjudication_records.json` automatically to resolve escalations (from
   either `adjudicate-from-gold` or `attest adjudicate`) and, since v1.2 of the
   validation-record schema, refuses to run while any escalation remains unresolved unless
   `--allow-unresolved-escalations` is passed explicitly — see the field
   `unresolved_escalations` in the output. Since v1.4, `recall.floor` (the rule-of-three/
   Wilson asymptotic approximation) is reported alongside `recall.exact_floor` (an exact,
   design-based hypergeometric bound, see §1) rather than one replacing the other; with
   `AUDIT_SIZE=all` (a full census of the screen-excluded population, this repo's default)
   both collapse toward the point estimate, since a census leaves no sampling uncertainty to
   bound — the gap between them only opens up if `AUDIT_SIZE` is overridden to a real sample
   smaller than the full population. `--max-staleness-days` (`SENTINEL_MAX_STALENESS_DAYS`
   in the Makefile) reports `sentinel_staleness` in the output, warning (not failing) if the
   sentinel's last recorded evaluation is older than that many days — see §6.
7. `make ablate` -> `attest ablate --run-dir data/run --input data/gold.json --aggregation boundary_dispersion --tau 0.5386751345948129 --zero-policy escalate --out results/ablation.json`
   (`ablate` reads its own `--aggregation`/`--tau`/`--zero-policy`, not `CONFIG` — the
   Makefile's `AGGREGATION`/`TAU`/`ZERO_POLICY` variables must be kept in sync with the
   active `reviews/<review>/config.json` by hand). Because the set of attainable
   dispersion values depends on ensemble size, one fixed `tau` is not comparable in
   strength across the swept subset sizes x' < 4; each subset's own `tau_report` is
   attached to `ablation.json` and the kernel warns once per sweep about this — expected,
   not a config error.
8. `make protocol` -> `attest protocol --run-dir data/run ...` builds and persists this
   run directory's validation-protocol descriptor (audit design, adjudication protocol,
   sentinel thresholds, reporting spec), hashed into its own `protocol_id`. Run once this
   epoch's artifacts are in their final state, and before `sentinel-check` so its
   thresholds come from this persisted protocol rather than the kernel's bare defaults.
9. `make sentinel-check` -> `attest sentinel-check --run-dir data/run --sentinel-input data/sentinel_set.json`
   re-evaluates every vendor against its stored baseline. See §6 for what a hard trigger
   means and how to respond.
10. `make manifest` -> `attest manifest --run-dir data/run --input data/gold.json --seed ...`
    hashes every artifact this run directory holds (config, protocol, votes,
    raw_responses, decisions, epoch, changelog, audit-draw/audit-labels/validation-record
    snapshots) into a run manifest. Run last, after every other stage, so it hashes final
    state.
11. `make verify` -> `attest verify --run-dir data/run` offline-recomputes every artifact's
    SHA-256 against the manifest and exits non-zero on any mismatch or missing artifact —
    gate archival (or CI) on this before treating `data/run/` as frozen.

`make all` runs steps 1-11 in order (assumes `data/sentinel_set.json` already exists —
step 0 is separate) for whichever review `REVIEWS_FILE`/`CONFIG` point at. `make clean-run`
removes one epoch's `data/run/` and audit files (never `data/gold.json`,
`data/sentinel_set.json`, or `results/`) to redo an epoch from scratch. Full example
pointed at a non-default review:
```
make all REVIEWS_FILE=reviews/Appenzeller-Herzog_2019/reviews.toml \
         CONFIG=reviews/Appenzeller-Herzog_2019/config.json \
         RUN_DIR=data/run_Appenzeller-Herzog_2019 TRACK=Appenzeller-Herzog_2019 \
         VALIDATE_OUT=results/validation_record_Appenzeller-Herzog_2019.json
```

Audit budget sets recall precision, not the maths: to claim an exclusion error rate at
or below 0.005 with zero observed misses, the rule of three needs on the order of 600
audited exclusions (the Makefile's default); below 0.001, about 3000 (`AUDIT_SIZE=3000`).
Report the budget with the floor. With x = 4, `ablate` enumerates all 11 subsets; no
subset sampling needed.

Run at least two epochs for one review to exercise per-epoch reporting: after the first
pass, make a deliberate config change (swap a model version or a prompt version, which
yields a new `ensemble_config_id`) and rerun `screen` + `validate` — but under a **fresh
`RUN_DIR`**, not the same one: a run directory is locked to one ensemble configuration
(`attest.io.store.RunStore.write_epoch` raises if asked to reuse a run directory across a
config change), so a second epoch needs its own directory. A same-review config variant
lives as a sibling file in that review's own subfolder, e.g.
`reviews/van_de_Schoot_2018/config_epoch2.json`. Set
`PREVIOUS_RUN_DIR`/`CHANGE_REASON`/`APPROVER` on the `screen` call so the new epoch's first
changelog event records *why* it exists instead of looking like an unrelated fresh start —
`--previous-run-dir` reads the predecessor's own persisted `config.json` back (not a
hand-passed file, which could go stale) to compute the `before` id and a machine-readable
field diff:
```
make all RUN_DIR=data/run_van_de_Schoot_2018_epoch2 CONFIG=reviews/van_de_Schoot_2018/config_epoch2.json \
         VALIDATE_OUT=results/validation_record_van_de_Schoot_2018_epoch2.json \
         PREVIOUS_RUN_DIR=data/run_van_de_Schoot_2018 CHANGE_REASON="bumped openai model_version after a vendor snapshot change" \
         APPROVER=reviewer-a
```
This demonstrates the per-epoch, versioned-instrument reporting the paper claims rather
than describing it hypothetically. This is orthogonal to running against a *different
review* (§2) — a second epoch changes the instrument for the *same* review; a different
`RUN_DIR` pointed at a different review's subfolder is a separate, independent proof, not
an epoch.

**Hard-trigger response.** When `sentinel-check` (step 9) finds >= 2 one-directional
polarity crossings for a vendor (see §6), it appends a `sentinel_drift` changelog event to
the *current* run directory and prints the newly opened epoch id — but, like an explicit
config change, this run directory keeps its original epoch's artifacts. Continued
screening under the drifted behavior belongs in a fresh `RUN_DIR`, opened the same way as
any other deliberate config change: `make screen RUN_DIR=data/run_van_de_Schoot_2018_epoch3 PREVIOUS_RUN_DIR=data/run_van_de_Schoot_2018_epoch2 CHANGE_REASON="sentinel drift: <vendor>, N polarity crossings" APPROVER=<id>`.
A sentinel hard trigger and an explicit config change share one operational escape hatch,
not two.

---

## §6 Configuration governance, protocol, the sentinel, and why runs are never pooled

**Why runs are never pooled.** `attest`'s core mechanism assumes one list of records and
one screening instruction (§4). Three (or 26) SYNERGY reviews are not the same measurement
repeated on different data — each is a different screening question with its own
eligibility criteria and domain (PTSD trajectories vs. Wilson's-disease drug trials vs.
spine-surgery RCTs). Averaging their confusion matrices, alpha, or escalation rates into
one pooled number would be averaging together answers to different questions — a number no
more meaningful than picking at random. So this repo
proves the core mechanism the other way: run the whole pipeline independently once per
review, each in its own `reviews/<review>/` subfolder, scored against its own real SYNERGY
gold, never combined into one `attest screen` call. `make review-summary` (§5 step 6's
companion, run manually once at least two reviews are done):
```
make review-summary REVIEW_SUMMARY_INPUTS="van_de_Schoot_2018=results/validation_record_van_de_Schoot_2018.json Appenzeller-Herzog_2019=results/validation_record_Appenzeller-Herzog_2019.json"
```
reads each already-completed run's `validation_record.json` directly (`src/review_summary.py`
— pure JSON tabulation, no recomputation, no attest imports) and writes
`results/review_summary.json`: alpha, confusion, escalation rate, and recall side by side
per review. That's the actual proof artifact — not one pooled headline number, but the
same mechanism holding up (or not) independently across as many differently-shaped reviews
as were run.

Three provenance levels are kept deliberately separate, mirroring the kernel's own split
(`attest.provenance.protocol`'s module docstring):

- **Screening config** (`reviews/<review>/config.json`) — vendors, models, prompt,
  aggregation, tau, zero policy. The only thing `ensemble_config_id` hashes.
- **Validation protocol** (built by `make protocol`) — audit design, adjudication
  protocol, the sentinel's thresholds, reporting spec. Hashed into its own `protocol_id`,
  never into `ensemble_config_id`: changing the audit budget or the sentinel's advisory
  threshold is an analysis-plan revision, not a new measurement instrument.
- **Run manifest** (built by `make manifest`) — one execution's software version, the
  input file's hash, every random seed used, and a SHA-256 per artifact the run directory
  holds — `make verify` offline-recomputes these and reports exactly what's missing or
  changed.

**Changelog.** `screen`'s first invocation over a fresh `RUN_DIR` logs a changelog event
(`data/run/changelog.json`, append-only): `initial_config` by default, or
`explicit_config_change` — with a machine-readable, dot-flattened field diff — when
`PREVIOUS_RUN_DIR`/`CHANGE_REASON`/`APPROVER` are set (§5, step 2). `APPROVER` requires
`PREVIOUS_RUN_DIR`: there is nothing to approve on an ordinary first run.

**Sentinel cadence.** No cron or scheduler — this repo's `screen` is a single offline
batch call over a fixed record set, not a long-lived service, and scheduling is
deliberately out of the kernel's own scope (`docs/sentinel_drift_rule.md`'s "Split with
the runbook" section explicitly assigns cadence to the runbook, not attest). The policy
here is manual and Makefile-driven: `sentinel-init` runs immediately after `screen` (§5,
step 2.1) to capture this epoch's baseline; `sentinel-check` runs once after the rest of
the epoch's pipeline completes (§5, step 9), reading its hard-trigger/advisory thresholds
from the protocol persisted in step 8. If a `screen --mode batch --wait` run spans a long
vendor batch queue (hours), re-run `make sentinel-check` manually every few hours while it
is outstanding — there is no automated poller for this, by design. This cadence policy is
itself recorded, verbatim, in every persisted protocol's `sentinel_policy.cadence_note`
(the Makefile's `SENTINEL_CADENCE_NOTE`).

`validate`'s `--max-staleness-days` (`SENTINEL_MAX_STALENESS_DAYS`, default 1 day) is the
machine-checkable counterpart to this manual cadence: it compares the sentinel's last
recorded `evaluated_at` against that threshold and reports the result in
`sentinel_staleness`, warning by default (or failing closed with
`--fail-on-stale-sentinel`, not wired into this Makefile) if `sentinel-check` was never run
this epoch or hasn't run recently enough — a trace, in the validation record itself, that
this section's manual cadence was actually followed rather than an unverifiable claim.

**The sentinel set: build vs. freeze.** `data/sentinel_set.json` is gitignored, like
`data/gold.json` — everything before a real run (including any copy currently in this repo
during development) is disposable, just a "is the pipeline in mint condition" check, not a
measurement. At the start of a real run, `make sentinelset` builds it fresh from whichever
review is active; used only within that review's first epoch, it never needs to be
committed if that review stays at one epoch. **Only if/when a second epoch is opened for
the same review**, deliberately freeze the exact file the first epoch's `sentinel-init`
already used — `git add -f data/sentinel_set.json` — so both epochs' sentinel checks
compare against the identical probe, giving the before/after trackback a drift claim
across epochs actually needs. A different review's run builds its own separate sentinel
set from scratch regardless — sentinel sets are never shared across reviews, same as gold
sets aren't. See §4 for what it is and why reusing real gold-set text as sentinel content
doesn't leak into the recall/accuracy numbers.

**The rule and the response.** `attest.provenance.sentinel` implements the hybrid rule
`docs/sentinel_drift_rule.md` recommends: a hard trigger (>= 2 one-directional polarity
crossings per vendor, `baseline in {0, +1} -> current == -1`, on the frozen sentinel set)
opens a new epoch and appends a `sentinel_drift` changelog event; a looser Krippendorff's-
alpha bound (default 0.80) is logged as advisory-only and never opens an epoch on its own.
See §5's "Hard-trigger response" paragraph for the operational reply — it reuses the same
`PREVIOUS_RUN_DIR`/`CHANGE_REASON`/`APPROVER` escape hatch as a deliberate config change,
not a separate mechanism.

---

## §7 Outputs to paper

| Artifact (in `results/`) | Feeds |
| --- | --- |
| `run/` PRISMA counts (per review) | Methods flow / PRISMA diagram |
| `validation_record_<review>.json` alpha + pairwise matrix | Inter-vendor reliability, per review |
| `validation_record_<review>.json` conditional FN correlation | Independence-as-empirical-property (2.6), per review |
| `validation_record_<review>.json` escalation rate | Human-escalation-rate result, per review |
| `validation_record_<review>.json` recall point + floor + exact_floor + CI | Headline recall claim per review, reported as floor with its audit budget |
| `validation_record_<review>.json` confusion | Confusion structure beside the coefficients, per review |
| `review_summary.json` (from `review-summary`) | The actual cross-review proof: does the core mechanism hold independently across every review run, not a pooled average |
| `ablation.json` (alpha/recall/escalation vs x), per review | Ablation knee figure; the "why this x" answer |
| `ablation.json` leave-one-out, per review | Marginal vendor contribution / best subset at each x |
| `reviews/<review>/config.json` + `ensemble_config_id` + `data/run/changelog.json` | Reproducibility package + TRIPOD-LLM crosswalk |
| multiple epochs' validation records (same review) | Per-epoch versioned-instrument demonstration |
| `validation_record.json`'s `tau_report` (from `data/run/tau_report.json`) | Self-documenting proof that `tau` behaves as claimed at this `x` |
| `config.json`'s `zero_policy` | States how a would-be `auto_label == 0` tie is resolved; never silently dropped into the confusion matrix |
| `protocol.json` + `protocol_id` | Methods provenance / TRIPOD-LLM crosswalk for the analysis plan, separate from the screening config |
| `manifest.json` + a passing `make verify` | Reproducibility / data-availability statement: every archived artifact's integrity is offline-checkable |
| `sentinel_evaluations.json` (from `sentinel-check`) | Drift-monitoring statement for a limitations/QA paragraph — confirms no hard-triggered vendor drift went unaddressed during any review's run |

---

## §8 Pre-run checklist

- [ ] `REVIEWS_FILE`/`CONFIG` point at the same review's `reviews/<review>/` subfolder — check both, not just one.
- [ ] Four distinct vendor families configured in `.env`; the active `config.json` has `x = 4`, a stated `tau`, a stated `zero_policy`, versioned prompt.
- [ ] `default_prompt` carries only eligibility criteria — no trailing output-format sentence of its own; the kernel appends the `E`/`U`/`I` output contract itself.
- [ ] `default_prompt` was verified word for word against `asreview/synergy-dataset`'s live `datasets.toml`, not trusted from an old paraphrase (see `reviews/Appenzeller-Herzog_2019/config.json`'s `_notes` for why this matters).
- [ ] `RUN_DIR`/`VALIDATE_OUT`/`TRACK` all reflect the active review's name (e.g. `data/run_van_de_Schoot_2018`), not a stale value from a previous review's run.
- [ ] Audit budget chosen from the recall precision to be claimed.
- [ ] `data/run/` frozen immediately after `screen`; downstream stages offline; `run/` archived (LFS or data release). Check `screen`'s output / `tau_report.json` for tau warnings first.
- [ ] `data/sentinel_set.json` built (`make sentinelset`) before the first real `screen` for this review; if a second epoch is planned for the same review, the exact file used by epoch 1 is frozen (`git add -f`) before epoch 2's `screen`.
- [ ] `make protocol` run with the intended audit/sentinel thresholds before `make sentinel-check`.
- [ ] `make verify` passes (exit 0) before `data/run/` is treated as frozen/archived.
- [ ] Hard-trigger response (§6) understood before a live run: know in advance which `RUN_DIR` a drift-triggered new epoch continues into.
- [ ] Once at least two reviews have real runs, `make review-summary` run and checked — that table, not any single review's number, is the actual proof of the core mechanism.

---

## Data attribution

This project's gold standard is built from the **SYNERGY** dataset:

> De Bruin, J., Ma, Y., Ferdinands, G., Teijema, J., & Van de Schoot, R. (2023).
> SYNERGY — Open machine learning dataset on study selection in systematic reviews.
> DataverseNL, V1. https://doi.org/10.34894/HE6NAQ

SYNERGY is released under CC0; record metadata is sourced from OpenAlex. This repo
redistributes no SYNERGY data directly — `build_goldset.py` fetches it at build time via
the `synergy-dataset` package.
