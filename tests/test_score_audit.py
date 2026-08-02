"""Tests for score_audit.py (no attest CLI invocation, pure file-shape tests)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import score_audit


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload))
    return path


def test_scores_drawn_ids_against_gold(tmp_path: Path):
    todo = _write_json(
        tmp_path / "audit_todo.json",
        {
            "drawn": [
                {"record_id": "W1", "stratum": "reviewA"},
                {"record_id": "W2", "stratum": "reviewA"},
            ]
        },
    )
    gold = _write_json(
        tmp_path / "gold.json",
        {
            "schema_version": "1.0",
            "project": "p",
            "records": [
                {"id": "W1", "title": "t", "abstract": "a", "track": "reviewA", "gold_label": -1},
                {"id": "W2", "title": "t", "abstract": "a", "track": "reviewA", "gold_label": 1},
                {"id": "W3", "title": "t", "abstract": "a", "track": "reviewA", "gold_label": -1},
            ],
        },
    )
    out = tmp_path / "audit_done.json"

    scored = score_audit.score_audit(todo, gold, out)

    assert scored == {"W1": -1, "W2": 1}
    assert json.loads(out.read_text()) == {"W1": -1, "W2": 1}


def test_missing_gold_label_raises(tmp_path: Path):
    todo = _write_json(
        tmp_path / "audit_todo.json",
        {"drawn": [{"record_id": "W1", "stratum": "reviewA"}]},
    )
    gold = _write_json(
        tmp_path / "gold.json",
        {"schema_version": "1.0", "project": "p", "records": []},
    )
    out = tmp_path / "audit_done.json"

    with pytest.raises(ValueError, match="no gold label"):
        score_audit.score_audit(todo, gold, out)
