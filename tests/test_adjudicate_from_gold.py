"""Tests for adjudicate_from_gold.py: resolving escalations from SYNERGY gold, not a human."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from attest.ensemble.aggregate import g
from attest.ensemble.votes import build_vote_vector
from attest.io.store import RunStore
from attest.provenance.config import Config, VendorSpec, compute_ensemble_config_id
from attest.provenance.epochs import open_epoch

import adjudicate_from_gold

_VENDORS = ("v1", "v2", "v3")


def _config() -> Config:
    return Config(
        vendors={
            vendor: VendorSpec(model="m", model_version="1", prompt_version="p", temperature=0.0)
            for vendor in _VENDORS
        },
        aggregation="boundary_dispersion",
        tau=1.0,
    )


def _write_run(tmp_path: Path, *, votes_by_record: dict[str, dict[str, int]]) -> Path:
    config = _config()
    epoch = open_epoch(config)
    config_id = epoch.ensemble_config_id

    store = RunStore(tmp_path / "run")
    store.write_config(config)
    store.write_epoch(epoch)

    votes = [
        build_vote_vector(record_id, config_id, ratings)
        for record_id, ratings in votes_by_record.items()
    ]
    store.write_votes(votes)
    decisions = {
        vv.record_id: g(vv, aggregation=config.aggregation, tau=config.tau) for vv in votes
    }
    store.write_decisions(config_id, decisions)
    return store.root


def _write_gold(tmp_path: Path, labels: dict[str, int]) -> Path:
    gold = tmp_path / "gold.json"
    gold.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "project": "p",
                "records": [
                    {"id": rid, "title": "t", "abstract": "a", "track": 1, "gold_label": label}
                    for rid, label in labels.items()
                ],
            }
        )
    )
    return gold


def test_resolves_only_pending_escalations_from_gold(tmp_path: Path) -> None:
    run_dir = _write_run(
        tmp_path,
        votes_by_record={
            "included": {v: 1 for v in _VENDORS},  # auto-labels, never escalates
            "tie": {v: 0 for v in _VENDORS},  # mean-zero: escalates under zero_policy=escalate
        },
    )
    gold = _write_gold(tmp_path, {"included": 1, "tie": -1})

    resolved = adjudicate_from_gold.adjudicate_from_gold(run_dir, gold)

    assert resolved == ["tie"]

    store = RunStore(run_dir)
    decisions = store.read_decisions()
    assert decisions["tie"].escalate is False
    assert decisions["tie"].auto_label == -1
    assert decisions["included"].escalate is False  # untouched: was never pending

    records = store.read_adjudication_records()
    assert records["tie"]["human_label"] == -1
    assert records["tie"]["reviewer"] == "oracle-benchmark-gold"
    assert "included" not in records  # never escalated, so never adjudicated


def test_no_pending_escalations_is_a_noop(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path, votes_by_record={"included": {v: 1 for v in _VENDORS}})
    gold = _write_gold(tmp_path, {"included": 1})

    resolved = adjudicate_from_gold.adjudicate_from_gold(run_dir, gold)

    assert resolved == []


def test_missing_gold_label_for_a_pending_escalation_raises(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path, votes_by_record={"tie": {v: 0 for v in _VENDORS}})
    gold = _write_gold(tmp_path, {})  # no gold label for "tie"

    with pytest.raises(ValueError, match="tie"):
        adjudicate_from_gold.adjudicate_from_gold(run_dir, gold)


def test_already_resolved_by_attest_adjudicate_is_left_alone(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from attest.ensemble.aggregate import Decision
    from attest.planes.adjudication import AdjudicationItem

    run_dir = _write_run(tmp_path, votes_by_record={"tie": {v: 0 for v in _VENDORS}})
    store = RunStore(run_dir)
    config_id = compute_ensemble_config_id(store.read_config())

    # A human already resolved "tie" via 'attest adjudicate' before this script runs.
    store.write_decisions(
        config_id, {"tie": Decision(auto_label=1, escalate=False, dispersion=0.0, boundary=False)}
    )
    store.write_adjudication_record(
        AdjudicationItem(
            record_id="tie",
            ensemble_config_id=config_id,
            dispersion=0.0,
            boundary=False,
            human_label=1,
            reviewer="a-real-reviewer",
            resolved_at=datetime.now(UTC),
        )
    )

    gold = _write_gold(tmp_path, {"tie": -1})  # disagrees with the human -- must not be applied
    resolved = adjudicate_from_gold.adjudicate_from_gold(run_dir, gold)

    assert resolved == []
    assert store.read_decisions()["tie"].auto_label == 1
    assert store.read_adjudication_records()["tie"]["reviewer"] == "a-real-reviewer"
