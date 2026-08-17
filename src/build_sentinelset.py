"""SYNERGY-to-attest sentinel-set builder (attest-runbook, latent-vendor-drift sentinel).

Draws a small, deterministic, frozen sample from whichever single review is currently
listed in ``reviews.toml`` for use with ``attest sentinel-init``/``attest sentinel-check``.
Reuses ``build_goldset.build_records`` for the SYNERGY-fetch/HTML-stripping/id logic, so
the sentinel set's records are built identically to the real gold set's -- same abstracts,
same ``track`` value, so the same ``config.json`` ``default_prompt`` applies. The sample is
stratified by the review's own ``gold_label`` split, so it comes out naturally
exclude-dominated for a sparse review without a hardcoded ratio.

The sentinel set is a diagnostic instrument, not a second gold set: it never carries
``gold_label`` in its output, and ``attest``'s sentinel machinery never reads one -- it only
compares a vendor's own rating on the same frozen record over time (baseline vs. current),
never against ground truth. See attest-runbook README §6, "Configuration governance,
protocol, the sentinel, and why runs are never pooled".
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

from attest.contracts.input import ContractError, validate_and_normalize

from build_goldset import build_records, ensure_raw_dataset_downloaded, load_review_names


def sample_track(
    records: list[dict[str, Any]], per_track: int, rng: random.Random
) -> list[dict[str, Any]]:
    """Draw up to `per_track` records from one track, stratified by gold_label.

    Splits `records` into included/excluded buckets and draws from each in
    proportion to the bucket's share of the track, so the sample mirrors the
    track's own inclusion rate rather than an arbitrary fixed ratio. Rounds
    the excluded share up (and the included share down) when `per_track`
    doesn't divide evenly, since excludes are what the sentinel's hard-trigger
    crossing direction (included/uncertain -> excluded) actually watches.
    """
    included = [r for r in records if r["gold_label"] == 1]
    excluded = [r for r in records if r["gold_label"] == -1]

    if len(included) + len(excluded) <= per_track:
        return included + excluded

    included_share = len(included) / len(records)
    n_included = min(len(included), int(included_share * per_track))
    n_excluded = min(len(excluded), per_track - n_included)
    n_included = min(len(included), per_track - n_excluded)

    return rng.sample(included, n_included) + rng.sample(excluded, n_excluded)


def build_sentinelset(
    reviews_file: Path, project: str, per_track: int, seed: int, out: Path
) -> None:
    review_names = load_review_names(reviews_file)
    ensure_raw_dataset_downloaded()
    rng = random.Random(seed)

    all_records: list[dict[str, Any]] = []
    for review_name in review_names:
        records, _dropped = build_records(review_name)
        sampled = sample_track(records, per_track, rng)
        for record in sampled:
            record = dict(record)
            del record["gold_label"]
            all_records.append(record)
        print(f"{review_name}: {len(sampled)} sentinel record(s) drawn from {len(records)}")

    payload = {
        "schema_version": "1.0",
        "project": project,
        "records": all_records,
    }

    normalized = validate_and_normalize(payload)
    print(
        f"validated: {len(normalized.records)} sentinel record(s) across "
        f"{len(review_names)} review(s)"
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build-sentinelset")
    parser.add_argument("--reviews-file", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--per-track", type=int, default=10)
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        build_sentinelset(args.reviews_file, args.project, args.per_track, args.seed, args.out)
    except ContractError as exc:
        print(f"error: sentinel set failed input-contract validation: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
