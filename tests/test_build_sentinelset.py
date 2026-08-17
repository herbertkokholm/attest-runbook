"""Tests for build_sentinelset.py against a fake synergy-dataset source (no network)."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from attest.contracts.input import ContractError

import build_goldset
import build_sentinelset


class FakeDataset:
    """Stand-in for synergy_dataset.Dataset that serves canned works."""

    _WORKS: dict[str, list[tuple[dict, int]]] = {}

    def __init__(self, name: str) -> None:
        self.name = name

    def iter(self):
        yield from self._WORKS[self.name]


@pytest.fixture(autouse=True)
def patch_dataset(monkeypatch):
    monkeypatch.setattr(build_goldset, "Dataset", FakeDataset)
    monkeypatch.setattr(build_sentinelset, "ensure_raw_dataset_downloaded", lambda: None)


def _work(id_: str, title: str, abstract: str, doi: str = "") -> dict:
    raw: dict = {"id": id_, "title": title, "abstract": abstract}
    if doi:
        raw["doi"] = doi
    return raw


def _reviews_file(tmp_path: Path, names: list[str]) -> Path:
    reviews_file = tmp_path / "reviews.toml"
    quoted = ", ".join(f'"{n}"' for n in names)
    reviews_file.write_text(f"reviews = [{quoted}]\n")
    return reviews_file


def test_output_validates_against_input_contract(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work("https://openalex.org/W1", "Included", "Abstract 1"), 1),
            (_work("https://openalex.org/W2", "Excluded", "Abstract 2"), 0),
        ],
    }
    reviews_file = _reviews_file(tmp_path, ["reviewA"])
    out = tmp_path / "sentinel.json"

    build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 43, out)

    payload = json.loads(out.read_text())
    assert payload["schema_version"] == "1.0"
    assert payload["project"] == "test-project"
    assert len(payload["records"]) == 2


def test_per_track_caps_sample_size(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work(f"https://openalex.org/W{i}", f"T{i}", f"A{i}"), 1 if i % 5 == 0 else 0)
            for i in range(50)
        ],
    }
    reviews_file = _reviews_file(tmp_path, ["reviewA"])
    out = tmp_path / "sentinel.json"

    build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 43, out)

    payload = json.loads(out.read_text())
    assert len(payload["records"]) == 10


def test_smaller_track_than_per_track_keeps_all_records(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work("https://openalex.org/W1", "T1", "A1"), 1),
            (_work("https://openalex.org/W2", "T2", "A2"), 0),
        ],
    }
    reviews_file = _reviews_file(tmp_path, ["reviewA"])
    out = tmp_path / "sentinel.json"

    build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 43, out)

    payload = json.loads(out.read_text())
    assert len(payload["records"]) == 2


def test_deterministic_for_a_fixed_seed(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work(f"https://openalex.org/W{i}", f"T{i}", f"A{i}"), 1 if i % 5 == 0 else 0)
            for i in range(50)
        ],
    }
    reviews_file = _reviews_file(tmp_path, ["reviewA"])
    out1 = tmp_path / "sentinel1.json"
    out2 = tmp_path / "sentinel2.json"

    build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 43, out1)
    build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 43, out2)

    ids1 = {r["id"] for r in json.loads(out1.read_text())["records"]}
    ids2 = {r["id"] for r in json.loads(out2.read_text())["records"]}
    assert ids1 == ids2


def test_different_seeds_can_draw_different_samples(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work(f"https://openalex.org/W{i}", f"T{i}", f"A{i}"), 1 if i % 5 == 0 else 0)
            for i in range(50)
        ],
    }
    reviews_file = _reviews_file(tmp_path, ["reviewA"])
    out1 = tmp_path / "sentinel1.json"
    out2 = tmp_path / "sentinel2.json"

    build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 43, out1)
    build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 99, out2)

    ids1 = {r["id"] for r in json.loads(out1.read_text())["records"]}
    ids2 = {r["id"] for r in json.loads(out2.read_text())["records"]}
    assert ids1 != ids2


def test_sample_stratifies_across_both_labels_when_both_have_enough_records():
    included = [
        {"id": f"i{i}", "title": f"i{i}", "abstract": f"a{i}", "track": "t", "gold_label": 1}
        for i in range(20)
    ]
    excluded = [
        {"id": f"e{i}", "title": f"e{i}", "abstract": f"a{i}", "track": "t", "gold_label": -1}
        for i in range(20)
    ]
    sampled = build_sentinelset.sample_track(
        included + excluded, per_track=10, rng=random.Random(1)
    )
    labels = {r["gold_label"] for r in sampled}
    assert labels == {1, -1}
    assert len(sampled) == 10


def test_gold_label_absent_from_output(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work("https://openalex.org/W1", "Included", "Abstract 1"), 1),
            (_work("https://openalex.org/W2", "Excluded", "Abstract 2"), 0),
        ],
    }
    reviews_file = _reviews_file(tmp_path, ["reviewA"])
    out = tmp_path / "sentinel.json"

    build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 43, out)

    for record in json.loads(out.read_text())["records"]:
        assert "gold_label" not in record


def test_track_equals_review_name(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [(_work("https://openalex.org/W1", "T", "A"), 1)],
        "reviewB": [(_work("https://openalex.org/W2", "T2", "A2"), 0)],
    }
    reviews_file = _reviews_file(tmp_path, ["reviewA", "reviewB"])
    out = tmp_path / "sentinel.json"

    build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 43, out)

    records = json.loads(out.read_text())["records"]
    tracks = {r["id"]: r["track"] for r in records}
    assert tracks["https://openalex.org/W1"] == "reviewA"
    assert tracks["https://openalex.org/W2"] == "reviewB"


def test_invalid_payload_raises_contract_error(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [(_work("", "T", "A"), 1)],
    }
    reviews_file = _reviews_file(tmp_path, ["reviewA"])
    out = tmp_path / "sentinel.json"

    with pytest.raises(ContractError):
        build_sentinelset.build_sentinelset(reviews_file, "test-project", 10, 43, out)
