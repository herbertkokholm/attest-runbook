"""Cross-review summary (attest-runbook, companion to independent per-review runs).

attest-runbook proves attest's core mechanism -- read a title/abstract, apply one
eligibility instruction, four vendors each vote include/exclude/uncertain, decide whether
to escalate to a human -- by running the whole pipeline independently once per SYNERGY
review, never pooled: each review is a genuinely different screening question (its own
eligibility criteria, its own domain), not a repeat of the same measurement on different
data. Pooling PTSD-trajectory criteria with Wilson's-disease-drug criteria with
spine-surgery-RCT criteria into one confusion matrix would be averaging together answers
to three different questions.

This tabulates however many already-completed, independent runs' validation_record.json
files exist side by side, so it's possible to see whether the core mechanism holds up
review by review, not just on whichever one happened to be run. Pure aggregation of
already-computed numbers -- reads each validation_record.json directly, no attest imports,
no recomputation. Run manually once at least two independent reviews have been screened;
not part of `make all`, since a single run has nothing to compare itself against yet.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_summary(path: Path) -> dict[str, Any]:
    """Extract the headline fields from one review's validation_record.json."""
    record = json.loads(path.read_text())
    return {
        "n_records": record.get("prisma", {}).get("screened"),
        "escalation_rate": record.get("escalation_rate"),
        "agreement": {
            "krippendorff_alpha": record.get("agreement", {}).get("krippendorff_alpha"),
            "pairwise": record.get("agreement", {}).get("pairwise", {}),
        },
        "confusion": record.get("confusion", {}),
        "recall": record.get("recall"),
        "ensemble_config_id": record.get("ensemble_config_id"),
    }


def build_summary(reviews: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Load and tabulate one summary entry per review name -> validation_record.json path."""
    return {name: load_summary(path) for name, path in reviews.items()}


def _parse_review_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"expected NAME=PATH, got '{value}'")
    name, _, path = value.partition("=")
    if not name or not path:
        raise argparse.ArgumentTypeError(f"expected NAME=PATH, got '{value}'")
    return name, Path(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="review-summary")
    parser.add_argument(
        "--review",
        action="append",
        required=True,
        type=_parse_review_arg,
        metavar="NAME=PATH",
        help="One review's name and its validation_record.json path. Repeatable.",
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    reviews = dict(args.review)
    summary = build_summary(reviews)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(f"wrote {args.out} ({len(summary)} review(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
