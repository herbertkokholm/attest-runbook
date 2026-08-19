# `Appenzeller-Herzog_2019`

Paired with [`./config.json`](./config.json) and [`./reviews.toml`](./reviews.toml). This
subfolder screens one SYNERGY review independently — see the root
[`README.md`](../../README.md) §1 (why SYNERGY, not self-annotation), §2 (why one
subfolder per review, never pooled), and §6 (governance/sentinel) for the rationale shared
across all three review subfolders; not repeated here.

## Study this review covers

> Appenzeller-Herzog, C., Mathes, T., Heeres, M. L. S., Weiss, K. H., Houwen, R. H. J., &
> Ewald, H. (2019). Comparative effectiveness of common therapies for Wilson disease: A
> systematic review and meta-analysis of controlled studies. *Liver International*, 39(11),
> 2136–2152. https://doi.org/10.1111/liv.14179

A systematic review and meta-analysis comparing the four established drug therapies for
Wilson disease (D-penicillamine, trientine, TTM, zinc) across controlled studies.

## Eligibility criteria

`config.json`'s `default_prompt` is this review's own published inclusion criteria:
patients with Wilson's disease of any age or stage; study drug one of the four established
therapies; control/comparator excluding the study drug itself, with matched doses;
identical concomitant therapies across arms; monotherapy-vs-combination comparisons
sharing the same drug excluded outright; at least one of a defined outcome set reported
(mortality, transplantation, neurological/liver-related symptoms, adverse effects,
discontinuation); prospective or retrospective controlled study in one of six languages.
Verified word for word against `asreview/synergy-dataset`'s `datasets.toml` (see
`config.json`'s `_notes` — an earlier paraphrase had silently dropped two of these
exclusion nuances, both restored).

## Data

This review is one of 26 in the **SYNERGY** dataset (De Bruin, Ma, Ferdinands, Teijema, &
Van de Schoot, 2023), distributed via the `synergy-dataset` Python package and sourced
from OpenAlex:

| Field | Value |
| --- | --- |
| SYNERGY key | `Appenzeller-Herzog_2019` |
| Domain | Medicine |
| Records | 2,873 |
| Included | 26 (0.9%) |
| Underlying review data | https://doi.org/10.5281/zenodo.3625931 |

Counts as published in `synergy-dataset`'s README; re-confirm with `synergy_dataset show
Appenzeller-Herzog_2019` before a real run, since they are not re-derived at build time
here.

This repo does not redistribute the data — `make goldset` (`build-goldset`, reading
[`./reviews.toml`](./reviews.toml)) fetches it at build time into the gitignored
`data/gold.json`.

## Citing

If you use this review's data, cite both the original review and the SYNERGY dataset:

> Appenzeller-Herzog, C., Mathes, T., Heeres, M. L. S., Weiss, K. H., Houwen, R. H. J., &
> Ewald, H. (2019). Comparative effectiveness of common therapies for Wilson disease: A
> systematic review and meta-analysis of controlled studies. *Liver International*, 39(11),
> 2136–2152. https://doi.org/10.1111/liv.14179

> De Bruin, J., Ma, Y., Ferdinands, G., Teijema, J., & Van de Schoot, R. (2023). SYNERGY —
> Open machine learning dataset on study selection in systematic reviews. DataverseNL, V1.
> https://doi.org/10.34894/HE6NAQ
