# attest-runbook

Paper-level pipeline for the `attest` screening-and-self-validation kernel. This repo
imports `attest`; the kernel never imports it. It holds everything needed to take the
finished kernel to the empirical results for the methods paper: the gold standard, the
chosen reviews, the ensemble configuration, the run sequence, and the small result
artifacts the paper cites.

Order: create the repo (§0) → gold standard (§1) → the chosen reviews (§2) → build the
gold set (§3) → keys and config (§4) → run the CLI (§5) → assemble the paper (§6). §7 is
the pre-run checklist.

---

## §0 The `attest-runbook` private repo

Layout:
```
attest-runbook/
  pyproject.toml            # deps: attest (from git or path), synergy-dataset
  README.md                 # this runbook, plus SYNERGY attribution (CC0, cite De Bruin et al. 2023)
  .gitignore                # .env, large data, raw run/ (see below)
  .env.example              # names of the four vendor key vars, no values
  reviews.toml              # the selected SYNERGY reviews (§2), the single source of truth
  config.json               # ensemble Config: vendors, models, prompts, aggregation, tau, x=4
  src/build_goldset.py      # SYNERGY -> attest input contract (§3)
  tests/                    # tests for build_goldset.py
  Makefile                  # one target per pipeline stage (§5)
  results/                  # SMALL committed artifacts: validation_record*.json, ablation.json
  data/                     # gitignored: gold.json (large), run/ (frozen votes)
```

What to commit vs not:
- Commit: `build_goldset.py`, `reviews.toml`, `config.json`, `Makefile`, and the small result
  artifacts in `results/` (validation records, ablation). These are the paper's numbers.
- Do NOT commit: `.env` (keys), `data/gold.json` (large, regenerable from `build_goldset.py`).
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
- Extreme label sparsity (~1.67%) is the regime the rule-of-three recall floor exists for.
- Each review is a natural track, so multi-track stratification is built in.
- It is the benchmark the field already uses, so results are comparable and recognizable.
- OpenAlex-native, consistent with the intended production pipeline.

Label mapping: SYNERGY's `label_included` is the review's final inclusion decision (1
included, 0 excluded), the accepted relevance ground truth. It is binary, so gold maps
to +1 (included) / −1 (excluded); the ordinal 0 is a live-screening category, not a gold
category. Precision/recall against gold collapse the ensemble's operational decision to
include-vs-exclude.

---

## §2 The chosen reviews (5 tracks)

Selected for spread in domain and inclusion rate, at a total size that keeps 4-vendor
screening affordable. Put these in `reviews.toml`.

| Review | Domain | Records | Incl | Incl % | Why in the set |
| --- | --- | --- | --- | --- | --- |
| `van_de_Schoot_2018` | Psychology/Medicine | 4544 | 38 | 0.8% | Iconic PTSD review; sparse regime |
| `Appenzeller-Herzog_2019` | Medicine | 2873 | 26 | 0.9% | Very sparse medicine; exercises the rule-of-three floor |
| `Hall_2012` | Computer science | 8793 | 104 | 1.2% | Non-medical domain (software fault prediction); enough includes to estimate precision |
| `Moran_2021` | Biology/Medicine | 5214 | 111 | 2.1% | Ecology/biology; mid inclusion rate |
| `Muthu_2021` | Medicine | 2719 | 336 | 12.4% | Dense contrast; many includes; anchors the high end |

Total ≈ 24,143 records; domains: psychology, medicine, computer science, biology;
inclusion-rate span 0.8% → 12.4%.

Cost lever: ~24k records × 4 vendors ≈ ~96k screening calls. To trim, drop `Hall_2012`
(largest at 8.8k) for a ~15k-record run, accepting less computer-science coverage; or
swap it for `Smid_2020` (CS/Math, 2627 records, 27 incl, 1.0%) to keep a CS track at a
fraction of the cost, accepting noisier precision from fewer includes. Confirm exact
current counts with `synergy_dataset show <NAME>` before committing `reviews.toml`.

---

## §3 Gold-set builder

`build_goldset.py` imports the `synergy-dataset` package and emits JSON conforming to
`attest.contracts.input` (schema_version "1.0"). CLI:

```
build-goldset --reviews-file reviews.toml --project attest-paper --out data/gold.json
```

Mapping: `id` = OpenAlex id (fallback DOI); `title`, `abstract` from the metadata;
`track` = the review name; `ids` = DOI and OpenAlex id when present; `gold_label` = +1
if `label_included == 1`, else −1. Records with an empty/missing abstract are dropped
(standard benchmark practice); the count dropped per review is printed. Output is
validated via `attest.contracts.input.validate_and_normalize` before being written.

---

## §4 Keys, environment, and the ensemble config

- Install: depend on `attest[all]` (git or local path) and `synergy-dataset`.
- Copy `.env.example` to `.env` and set the four vendors' API keys. `.env` is gitignored.
- Use four distinct vendor families (e.g. Anthropic, OpenAI, Google, one open model via
  its provider) so x = 4 with genuinely different families, per the method.
- `config.json`: vendors, per-vendor model+version, per-vendor prompt version,
  aggregation rule, `tau`, `x = 4`. Start `tau` at a small dispersion value and treat it
  as tunable; report whatever is used. Keep the prompt identical across vendors except
  for provider-required formatting, and version it so `ensemble_config_id` is meaningful.

---

## §5 Run sequence (Makefile targets; offline after `screen`)

All stages operate on files via the kernel's `io/store`; only `screen` touches the
network. Freeze `data/run/` once produced.

1. `make goldset`  -> `build-goldset ... --out data/gold.json`
2. `make screen`   -> `attest screen --config config.json --input data/gold.json --out data/run/` (the only paid, networked step; freeze `data/run/` after)
3. `make audit-draw` -> `attest audit-draw --run data/run/ --n <budget> --strata track --out data/audit_todo.json`
4. Review `audit_todo.json` and produce `audit_done.json` (+1/−1 per sampled exclusion).
   Because SYNERGY carries the true label, the draw can be scored against SYNERGY for a
   fully reproducible audit, optionally adding an independent human pass.
5. `make audit-apply` -> `attest audit-apply --run data/run/ --audit data/audit_done.json`
6. `make validate` -> `attest validate --run data/run/ --gold data/gold.json --out results/validation_record.json`
7. `make ablate`   -> `attest ablate --config config.json --gold data/gold.json --out results/ablation.json`

Audit budget sets recall precision, not the maths: to claim an exclusion error rate at
or below 0.005 with zero observed misses, the rule of three needs on the order of 600
audited exclusions; below 0.001, about 3000. Set `--n` accordingly, stratified by track,
and report the budget with the floor. With x = 4, `ablate` enumerates all 11 subsets; no
subset sampling needed.

Run at least two epochs: after the first pass, make a deliberate config change (swap a
model version or a prompt version, which yields a new `ensemble_config_id`) and re-run
`screen` + `validate`, writing `results/validation_record_epoch2.json`. This demonstrates
the per-epoch, versioned-instrument reporting the paper claims rather than describing it
hypothetically.

---

## §6 Outputs to paper

| Artifact (in `results/`) | Feeds |
| --- | --- |
| `run/` PRISMA counts | Methods flow / PRISMA diagram |
| `validation_record.json` alpha + pairwise matrix | Inter-vendor reliability |
| `validation_record.json` conditional FN correlation | Independence-as-empirical-property (2.6) |
| `validation_record.json` escalation rate | Human-escalation-rate result |
| `validation_record.json` recall point + floor + CI | Headline recall claim, reported as floor with its audit budget |
| `validation_record.json` confusion | Confusion structure beside the coefficients |
| `ablation.json` (alpha/recall/escalation vs x) | Ablation knee figure; the "why this x" answer |
| `ablation.json` leave-one-out | Marginal vendor contribution / best subset at each x |
| `config.json` + `ensemble_config_id` + change log | Reproducibility package + TRIPOD-LLM crosswalk |
| both epochs' validation records | Per-epoch versioned-instrument demonstration |

---

## §7 Pre-run checklist

- [ ] `attest-runbook` private repo created; `.gitignore` excludes `.env`, `data/gold.json`, `data/run/`.
- [ ] `reviews.toml` holds the five reviews (or a trimmed set); counts confirmed with `synergy_dataset show`.
- [ ] `build_goldset.py` produces `data/gold.json` that validates against the input contract.
- [ ] Four distinct vendor families configured in `.env`; `config.json` has `x = 4`, a stated `tau`, versioned prompts.
- [ ] Audit budget chosen from the recall precision to be claimed.
- [ ] `data/run/` frozen immediately after `screen`; downstream stages offline; `run/` archived (LFS or data release).
- [ ] Two epochs run to exercise per-epoch reporting.
- [ ] SYNERGY cited (De Bruin et al. 2023, DOI 10.34894/HE6NAQ) in the paper and this README.

---

## Data attribution

This project's gold standard is built from the **SYNERGY** dataset:

> De Bruin, J., Ma, Y., Ferdinands, G., Teijema, J., & Van de Schoot, R. (2023).
> *SYNERGY - Open machine learning dataset on study selection in systematic reviews*
> (Version 2.0) [Data set]. DataverseNL.
> https://doi.org/10.34894/HE6NAQ

SYNERGY is released under CC0; record metadata is sourced from OpenAlex. This repo
redistributes no SYNERGY data directly — `build_goldset.py` fetches it at build time via
the `synergy-dataset` package.
