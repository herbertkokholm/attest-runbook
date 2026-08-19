"""Tests for resolve_batch_size.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import resolve_batch_size as rbs


def _gold(path: Path, *, with_empty_abstract: bool = False) -> None:
    records = [
        {"id": "rec-1", "title": "t1", "abstract": "a1", "track": "reviewA"},
        {"id": "rec-2", "title": "t2", "abstract": "a2", "track": "reviewA"},
        {"id": "rec-3", "title": "t3", "abstract": "a3", "track": "reviewA"},
    ]
    if with_empty_abstract:
        records.append({"id": "rec-4", "title": "t4", "abstract": "", "track": "reviewA"})
    path.write_text(
        json.dumps({"schema_version": "1.0", "project": "p", "records": records}),
        encoding="utf-8",
    )


def test_resolve_batch_size_counts_records_the_kernel_prefilter_keeps(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    _gold(gold_path)

    assert rbs.resolve_batch_size(gold_path) == 3


def test_resolve_batch_size_excludes_records_dropped_for_an_empty_abstract(
    tmp_path: Path,
) -> None:
    # Mirrors attest.cli._DEFAULT_PREFILTER: a record with an empty abstract
    # is never submitted to the ensemble, so it must not be counted here
    # either -- otherwise a declared batch_size attest itself would reject.
    gold_path = tmp_path / "gold.json"
    _gold(gold_path, with_empty_abstract=True)

    assert rbs.resolve_batch_size(gold_path) == 3


def test_write_resolved_config_patches_batch_size_and_preserves_other_fields(
    tmp_path: Path,
) -> None:
    gold_path = tmp_path / "gold.json"
    _gold(gold_path)
    config_in = tmp_path / "config.json"
    config_in.write_text(
        json.dumps(
            {
                "vendors": {
                    "v1": {
                        "model": "m",
                        "model_version": "1",
                        "prompt_version": "p1",
                        "temperature": 0.0,
                    }
                },
                "aggregation": "boundary_dispersion",
                "tau": 1.0,
                "_notes": ["kept as-is"],
            }
        ),
        encoding="utf-8",
    )
    config_out = tmp_path / "nested" / "config.resolved.json"

    batch_size = rbs.write_resolved_config(config_in, gold_path, config_out)

    assert batch_size == 3
    written = json.loads(config_out.read_text(encoding="utf-8"))
    assert written["batch_size"] == 3
    assert written["aggregation"] == "boundary_dispersion"
    assert written["tau"] == 1.0
    assert written["_notes"] == ["kept as-is"]


def test_write_resolved_config_overwrites_a_stale_batch_size(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.json"
    _gold(gold_path)
    config_in = tmp_path / "config.json"
    config_in.write_text(json.dumps({"aggregation": "x", "tau": 1.0, "batch_size": 999}))
    config_out = tmp_path / "config.resolved.json"

    rbs.write_resolved_config(config_in, gold_path, config_out)

    assert json.loads(config_out.read_text(encoding="utf-8"))["batch_size"] == 3


def test_main_prints_the_resolved_batch_size(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gold_path = tmp_path / "gold.json"
    _gold(gold_path)
    config_in = tmp_path / "config.json"
    config_in.write_text(json.dumps({"aggregation": "x", "tau": 1.0}))
    config_out = tmp_path / "config.resolved.json"

    rc = rbs.main(
        [
            "--gold",
            str(gold_path),
            "--config-in",
            str(config_in),
            "--config-out",
            str(config_out),
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "batch_size=3" in out
    assert str(config_out) in out
