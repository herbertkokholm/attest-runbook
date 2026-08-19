# `Muthu_2021`

Paired with [`./config.json`](./config.json) and [`./reviews.toml`](./reviews.toml). This
subfolder screens one SYNERGY review independently — see the root
[`README.md`](../../README.md) §1 (why SYNERGY, not self-annotation), §2 (why one
subfolder per review, never pooled), and §6 (governance/sentinel) for the rationale shared
across all three review subfolders; not repeated here.

## Study this review covers

> Muthu, S., & Ramakrishnan, E. (2021). Fragility Analysis of Statistically Significant
> Outcomes of Randomized Control Trials in Spine Surgery. *Spine*, 46(3), 198–208.
> https://doi.org/10.1097/BRS.0000000000003645

A systematic review assessing the statistical fragility of significant outcomes reported
in randomized controlled trials of spine surgery.

## Eligibility criteria

`config.json`'s `default_prompt` is this review's own published inclusion criteria: an RCT
with 1:1 parallel two-arm design; related to spine surgery involving preoperative,
intraoperative, or postoperative variables; with a dichotomous primary or secondary
outcome. Excludes non-human studies, continuous-variable outcomes without predefined
clinical success criteria, and studies without a statistically significant reported
outcome. Verified word for word against `asreview/synergy-dataset`'s `datasets.toml` (see
`config.json`'s `_notes` — checked out accurate as originally written, no correction
needed).

## Data

This review is one of 26 in the **SYNERGY** dataset (De Bruin, Ma, Ferdinands, Teijema, &
Van de Schoot, 2023), distributed via the `synergy-dataset` Python package and sourced
from OpenAlex:

| Field | Value |
| --- | --- |
| SYNERGY key | `Muthu_2021` |
| Domain | Medicine |
| Records | 2,719 |
| Included | 336 (12.4%) |
| Underlying review data | https://osf.io/68ezp |

The densest of the three review subfolders here — anchors the high-inclusion-rate end of
the sparse-to-dense spread (root README §2). Counts as published in `synergy-dataset`'s
README; re-confirm with `synergy_dataset show Muthu_2021` before a real run, since they
are not re-derived at build time here.

This repo does not redistribute the data — `make goldset` (`build-goldset`, reading
[`./reviews.toml`](./reviews.toml)) fetches it at build time into the gitignored
`data/gold.json`.

## Citing

If you use this review's data, cite both the original review and the SYNERGY dataset:

> Muthu, S., & Ramakrishnan, E. (2021). Fragility Analysis of Statistically Significant
> Outcomes of Randomized Control Trials in Spine Surgery. *Spine*, 46(3), 198–208.
> https://doi.org/10.1097/BRS.0000000000003645

> De Bruin, J., Ma, Y., Ferdinands, G., Teijema, J., & Van de Schoot, R. (2023). SYNERGY —
> Open machine learning dataset on study selection in systematic reviews. DataverseNL, V1.
> https://doi.org/10.34894/HE6NAQ
