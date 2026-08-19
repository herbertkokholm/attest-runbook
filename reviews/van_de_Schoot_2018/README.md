# `van_de_Schoot_2018`

Paired with [`./config.json`](./config.json) and [`./reviews.toml`](./reviews.toml). This
subfolder screens one SYNERGY review independently — see the root
[`README.md`](../../README.md) §1 (why SYNERGY, not self-annotation), §2 (why one
subfolder per review, never pooled), and §6 (governance/sentinel) for the rationale shared
across all three review subfolders; not repeated here.

## Study this review covers

> van de Schoot, R., Sijbrandij, M., Depaoli, S., Winter, S. D., Olff, M., & van Loey, N.
> E. (2018). Bayesian PTSD-Trajectory Analysis with Informed Priors Based on a Systematic
> Literature Search and Expert Elicitation. *Multivariate Behavioral Research*, 53(2),
> 267–291. https://doi.org/10.1080/00273171.2017.1412293

A Bayesian latent-trajectory analysis of post-traumatic stress symptom courses, built on a
systematic literature search of longitudinal PTSD studies used to elicit informed priors.

## Eligibility criteria

`config.json`'s `default_prompt` is this review's own published inclusion criteria: a
longitudinal study with at least three measurement waves measuring PTSD, PTSD measured on
a continuous scale via interview or questionnaire, use of a clustering method (LGMM, LCGA,
or hierarchical cluster analysis), and traumatic stress symptoms following events that
appeared to fulfill DSM-IV criterion A1 for PTSD or acute stress disorder. Verified word
for word against `asreview/synergy-dataset`'s `datasets.toml` (see `config.json`'s
`_notes` for what that verification pass corrected).

## Data

This review is one of 26 in the **SYNERGY** dataset (De Bruin, Ma, Ferdinands, Teijema, &
Van de Schoot, 2023), distributed via the `synergy-dataset` Python package and sourced
from OpenAlex:

| Field | Value |
| --- | --- |
| SYNERGY key | `van_de_Schoot_2018` |
| Domain | Psychology, Medicine |
| Records | 4,544 |
| Included | 38 (0.8%) |
| Underlying review data | https://doi.org/10.17605/OSF.IO/VW3T7 |

Counts as published in `synergy-dataset`'s README; re-confirm with `synergy_dataset show
van_de_Schoot_2018` before a real run, since they are not re-derived at build time here.

This repo does not redistribute the data — `make goldset` (`build-goldset`, reading
[`./reviews.toml`](./reviews.toml)) fetches it at build time into the gitignored
`data/gold.json`.

## Citing

If you use this review's data, cite both the original review and the SYNERGY dataset:

> van de Schoot, R., Sijbrandij, M., Depaoli, S., Winter, S. D., Olff, M., & van Loey, N.
> E. (2018). Bayesian PTSD-Trajectory Analysis with Informed Priors Based on a Systematic
> Literature Search and Expert Elicitation. *Multivariate Behavioral Research*, 53(2),
> 267–291. https://doi.org/10.1080/00273171.2017.1412293

> De Bruin, J., Ma, Y., Ferdinands, G., Teijema, J., & Van de Schoot, R. (2023). SYNERGY —
> Open machine learning dataset on study selection in systematic reviews. DataverseNL, V1.
> https://doi.org/10.34894/HE6NAQ
