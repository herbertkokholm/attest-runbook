"""Resolve ensemble-escalated decisions from SYNERGY's published gold labels.

attest-runbook evaluates attest retrospectively against SYNERGY's already-published,
human-adjudicated inclusion decisions -- there is no live human reviewer in this repo's
pipeline (see score_audit.py, which does the analogous thing for the recall-audit plane).
This script does the same for the *operational adjudication* plane: every record the
ensemble escalated (a tied or boundary-straddling vote vector, from
attest.ensemble.aggregate.g) is resolved to its SYNERGY gold label rather than to a live
human judgement.

This is NOT a substitute for adjudication in a real deployment, and must never be mistaken
for one: the manuscript's methods (Sec. 2.9) require every include-and-escalate record to be
either adjudicated or covered by a separate inclusion audit before a recall record is valid,
and this script exists only so that condition is actually met for the benchmark evaluation,
where the gold label is already public and known. Every resolution this writes is stamped
with `REVIEWER_LABEL` ("oracle-benchmark-gold"), never a person's name or pseudonym, so a
benchmark-oracle-resolved record is always distinguishable from genuine human adjudication in
the run's own adjudication_records.json provenance.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from attest.ensemble.aggregate import Decision
from attest.io.store import RunStore
from attest.planes.adjudication import AdjudicationItem, escalation_reason, final_label
from attest.provenance.config import compute_ensemble_config_id

REVIEWER_LABEL = "oracle-benchmark-gold"


def load_gold_labels(gold_file: Path) -> dict[str, int]:
    """Read record id -> gold_label out of an input-contract gold-set JSON file."""
    payload = json.loads(gold_file.read_text())
    labels: dict[str, int] = {}
    for record in payload.get("records", []):
        gold_label = record.get("gold_label")
        if gold_label is not None:
            labels[str(record["id"])] = int(gold_label)
    return labels


def adjudicate_from_gold(run_dir: Path, gold_file: Path) -> list[str]:
    """Resolve every pending escalated decision in `run_dir` from `gold_file`'s gold labels.

    Mirrors what `attest adjudicate --record-id ... --label ...` does per record (rewrites
    the stored `Decision` and appends adjudication provenance), batched over every currently
    pending escalation and sourcing the label from SYNERGY gold instead of a CLI argument.

    Returns:
        The record ids resolved, sorted.

    Raises:
        ValueError: If a pending escalated record has no gold label in `gold_file`.
    """
    store = RunStore(run_dir)
    ensemble_config_id = compute_ensemble_config_id(store.read_config())
    decisions = store.read_decisions()
    gold_labels = load_gold_labels(gold_file)

    pending = {record_id: d for record_id, d in decisions.items() if d.escalate}
    missing = sorted(record_id for record_id in pending if record_id not in gold_labels)
    if missing:
        shown = ", ".join(missing[:5])
        raise ValueError(
            f"{len(missing)} pending escalated record(s) have no gold label in {gold_file}: {shown}"
        )

    resolved_at = datetime.now(UTC)
    for record_id, decision in pending.items():
        resolved_label = final_label(record_id, decision, gold_labels[record_id])
        store.write_decisions(
            ensemble_config_id,
            {
                record_id: Decision(
                    auto_label=resolved_label,
                    escalate=False,
                    dispersion=decision.dispersion,
                    boundary=decision.boundary,
                )
            },
        )
        store.write_adjudication_record(
            AdjudicationItem(
                record_id=record_id,
                ensemble_config_id=ensemble_config_id,
                dispersion=decision.dispersion,
                boundary=decision.boundary,
                selection_reason=escalation_reason(decision),
                human_label=resolved_label,
                reviewer=REVIEWER_LABEL,
                resolved_at=resolved_at,
            )
        )

    return sorted(pending)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adjudicate-from-gold")
    parser.add_argument("--run-dir", required=True, type=Path, help="Run directory to read/write.")
    parser.add_argument(
        "--gold", required=True, type=Path, help="Gold-set input-contract JSON that was screened."
    )
    args = parser.parse_args(argv)

    resolved = adjudicate_from_gold(args.run_dir, args.gold)
    print(
        f"resolved {len(resolved)} escalated decision(s) from SYNERGY gold as "
        f"'{REVIEWER_LABEL}' (benchmark evaluation only, not live human adjudication): {resolved}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
