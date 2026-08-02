"""Score a drawn recall-audit sample against SYNERGY's published gold labels.

Reads the record ids `attest audit-draw` printed (saved to a file) and the
gold labels in the same gold-set file that was screened, and writes a
labels file in the shape `attest audit-apply --labels` expects: a JSON
object mapping record id to its ordinal gold label. Since SYNERGY's
inclusion decisions are already human-adjudicated ground truth, this makes
the recall audit fully reproducible without a second manual pass -- an
independent human pass can still be layered on top by editing the output
before running `attest audit-apply`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_drawn_ids(todo_file: Path) -> list[str]:
    """Read the record ids drawn by `attest audit-draw` out of its saved JSON output."""
    payload = json.loads(todo_file.read_text())
    drawn = payload.get("drawn")
    if not isinstance(drawn, list):
        raise ValueError(
            f"{todo_file}: expected a 'drawn' list, as printed by 'attest audit-draw'"
        )
    return [str(row["record_id"]) for row in drawn]


def load_gold_labels(gold_file: Path) -> dict[str, int]:
    """Read record id -> gold_label out of an input-contract gold-set JSON file."""
    payload = json.loads(gold_file.read_text())
    labels: dict[str, int] = {}
    for record in payload.get("records", []):
        gold_label = record.get("gold_label")
        if gold_label is not None:
            labels[str(record["id"])] = int(gold_label)
    return labels


def score_audit(todo_file: Path, gold_file: Path, out: Path) -> dict[str, int]:
    """Score every drawn record id against the gold set and write the result.

    Returns:
        The record id -> gold_label mapping that was written to `out`.

    Raises:
        ValueError: If a drawn record id has no gold label in `gold_file`.
    """
    drawn_ids = load_drawn_ids(todo_file)
    gold_labels = load_gold_labels(gold_file)

    missing = [record_id for record_id in drawn_ids if record_id not in gold_labels]
    if missing:
        shown = ", ".join(missing[:5])
        raise ValueError(
            f"{len(missing)} drawn record id(s) have no gold label in {gold_file}: {shown}"
        )

    scored = {record_id: gold_labels[record_id] for record_id in drawn_ids}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scored, indent=2, sort_keys=True))
    return scored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="score-audit")
    parser.add_argument(
        "--todo", required=True, type=Path, help="Drawn sample JSON from 'attest audit-draw'."
    )
    parser.add_argument(
        "--gold", required=True, type=Path, help="Gold-set input-contract JSON that was screened."
    )
    parser.add_argument("--out", required=True, type=Path, help="Where to write scored labels.")
    args = parser.parse_args(argv)

    scored = score_audit(args.todo, args.gold, args.out)
    print(f"scored {len(scored)} drawn record(s) against SYNERGY gold, wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
