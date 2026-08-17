"""Tests for review_summary.py's cross-review aggregation."""

from __future__ import annotations

import json
from pathlib import Path

import review_summary


def _write_validation_record(path: Path, *, alpha: float, tp: int, escalation_rate: float) -> None:
    path.write_text(
        json.dumps(
            {
                "ensemble_config_id": "cfg123",
                "epoch": "epoch1",
                "config": {},
                "agreement": {"krippendorff_alpha": alpha, "pairwise": {"a|b": alpha}},
                "escalation_rate": escalation_rate,
                "recall": {"point": 1.0, "floor": 1.0, "ci": [1.0, 1.0], "audit_n": 5},
                "confusion": {"tp": tp, "fp": 0, "fn": 0, "tn": 3},
                "prisma": {"screened": tp + 3},
            }
        )
    )


def test_load_summary_extracts_headline_fields(tmp_path: Path):
    record = tmp_path / "validation_record.json"
    _write_validation_record(record, alpha=0.9, tp=2, escalation_rate=0.1)

    summary = review_summary.load_summary(record)

    assert summary["n_records"] == 5
    assert summary["escalation_rate"] == 0.1
    assert summary["agreement"]["krippendorff_alpha"] == 0.9
    assert summary["confusion"] == {"tp": 2, "fp": 0, "fn": 0, "tn": 3}
    assert summary["recall"]["point"] == 1.0
    assert summary["ensemble_config_id"] == "cfg123"


def test_build_summary_keys_by_review_name(tmp_path: Path):
    record_a = tmp_path / "a.json"
    record_b = tmp_path / "b.json"
    _write_validation_record(record_a, alpha=0.9, tp=2, escalation_rate=0.1)
    _write_validation_record(record_b, alpha=0.2, tp=1, escalation_rate=0.5)

    summary = review_summary.build_summary({"reviewA": record_a, "reviewB": record_b})

    assert set(summary) == {"reviewA", "reviewB"}
    assert summary["reviewA"]["agreement"]["krippendorff_alpha"] == 0.9
    assert summary["reviewB"]["agreement"]["krippendorff_alpha"] == 0.2


def test_parse_review_arg_splits_name_and_path():
    name, path = review_summary._parse_review_arg("reviewA=results/validation_record.json")
    assert name == "reviewA"
    assert path == Path("results/validation_record.json")


def test_main_writes_combined_summary(tmp_path: Path):
    record_a = tmp_path / "a.json"
    _write_validation_record(record_a, alpha=0.9, tp=2, escalation_rate=0.1)
    out = tmp_path / "summary.json"

    exit_code = review_summary.main(["--review", f"reviewA={record_a}", "--out", str(out)])

    assert exit_code == 0
    written = json.loads(out.read_text())
    assert set(written) == {"reviewA"}
