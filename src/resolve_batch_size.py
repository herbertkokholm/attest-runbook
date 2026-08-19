"""Batch-size resolution and config patching (attest-runbook §4).

`attest.provenance.config.Config.batch_size` ("b_e", the request batch
size) is hashed into `ensemble_config_id` on par with `vendors`/
`aggregation`/`tau`, and `attest.cli._check_batch_size` refuses to run
`screen` unless it equals the number of records the kernel's own prefilter
keeps from the gold set for this run -- it is not a value this repo is free
to guess or hand-maintain in a checked-in `config.json`, since the exact
count depends on whichever `synergy-dataset` package version built
`data/gold.json` (see `reviews/<review>/reviews.toml`'s note on this).

This script computes that count with the kernel's own prefilter rule
(`attest.prefilter.framework.require_nonempty("abstract")`, mirroring
`attest.cli._DEFAULT_PREFILTER` -- keep in sync if that rule ever changes),
not `build_goldset.py`'s own empty-abstract drop, so the declared
`batch_size` stays correct even if that upstream drop logic ever changes.
It writes a copy of the review's checked-in `config.json` with `batch_size`
set, ready to pass to `attest screen --config` -- the checked-in template
itself deliberately carries no `batch_size` field, so a stale, hand-copied
number can never sit in git unnoticed (see each `config.json`'s `_notes`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from attest.io.store import load_input
from attest.prefilter.framework import Prefilter, require_nonempty

_PREFILTER = Prefilter(rules=[require_nonempty("abstract")])


def resolve_batch_size(gold_path: Path) -> int:
    """Return the number of records attest's own prefilter would keep from `gold_path`."""
    normalized = load_input(gold_path)
    outcome = _PREFILTER.run(normalized.records)
    return len(outcome.kept)


def write_resolved_config(config_in: Path, gold_path: Path, config_out: Path) -> int:
    """Copy `config_in`, set `batch_size` from `gold_path`'s prefiltered count, write `config_out`.

    Args:
        config_in: The review's checked-in `config.json` template.
        gold_path: The gold-set file this run will actually screen.
        config_out: Where to write the resolved config (gitignored --
            regenerated every run from `config_in` + the current `gold_path`).

    Returns:
        The resolved `batch_size`, so the caller can report it.
    """
    payload = json.loads(config_in.read_text(encoding="utf-8"))
    batch_size = resolve_batch_size(gold_path)
    payload["batch_size"] = batch_size
    config_out.parent.mkdir(parents=True, exist_ok=True)
    config_out.write_text(json.dumps(payload, indent=2))
    return batch_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resolve-batch-size")
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--config-in", required=True, type=Path)
    parser.add_argument("--config-out", required=True, type=Path)
    args = parser.parse_args(argv)

    batch_size = write_resolved_config(args.config_in, args.gold, args.config_out)
    print(f"batch_size={batch_size} -> wrote {args.config_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
