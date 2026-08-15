"""Tests for build_goldset.py against a fake synergy-dataset source (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from attest.contracts.input import ContractError

import build_goldset


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
    monkeypatch.setattr(build_goldset, "ensure_raw_dataset_downloaded", lambda: None)


def _work(id_: str, title: str, abstract: str | None, doi: str = "") -> dict:
    raw: dict = {"id": id_, "title": title}
    if abstract is not None:
        raw["abstract"] = abstract
    if doi:
        raw["doi"] = doi
    return raw


def test_output_validates_against_input_contract(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work("https://openalex.org/W1", "Title 1", "Abstract 1", doi="10.1/a"), 1),
            (_work("https://openalex.org/W2", "Title 2", "Abstract 2"), 0),
        ],
    }
    reviews_file = tmp_path / "reviews.toml"
    reviews_file.write_text('reviews = ["reviewA"]\n')
    out = tmp_path / "gold.json"

    build_goldset.build_goldset(reviews_file, "test-project", out)

    payload = json.loads(out.read_text())
    assert payload["schema_version"] == "1.0"
    assert payload["project"] == "test-project"
    assert len(payload["records"]) == 2


def test_inclusion_maps_to_gold_label(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work("https://openalex.org/W1", "Included", "Abstract 1"), 1),
            (_work("https://openalex.org/W2", "Excluded", "Abstract 2"), 0),
        ],
    }
    reviews_file = tmp_path / "reviews.toml"
    reviews_file.write_text('reviews = ["reviewA"]\n')
    out = tmp_path / "gold.json"

    build_goldset.build_goldset(reviews_file, "test-project", out)

    records = {r["title"]: r for r in json.loads(out.read_text())["records"]}
    assert records["Included"]["gold_label"] == 1
    assert records["Excluded"]["gold_label"] == -1


def test_empty_abstract_records_dropped(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work("https://openalex.org/W1", "Has abstract", "Abstract 1"), 1),
            (_work("https://openalex.org/W2", "No abstract", ""), 1),
            (_work("https://openalex.org/W3", "Missing abstract key", None), 1),
        ],
    }
    reviews_file = tmp_path / "reviews.toml"
    reviews_file.write_text('reviews = ["reviewA"]\n')
    out = tmp_path / "gold.json"

    build_goldset.build_goldset(reviews_file, "test-project", out)

    titles = {r["title"] for r in json.loads(out.read_text())["records"]}
    assert titles == {"Has abstract"}


def test_track_equals_review_name(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [(_work("https://openalex.org/W1", "T", "A"), 1)],
        "reviewB": [(_work("https://openalex.org/W2", "T2", "A2"), 0)],
    }
    reviews_file = tmp_path / "reviews.toml"
    reviews_file.write_text('reviews = ["reviewA", "reviewB"]\n')
    out = tmp_path / "gold.json"

    build_goldset.build_goldset(reviews_file, "test-project", out)

    records = json.loads(out.read_text())["records"]
    tracks = {r["id"]: r["track"] for r in records}
    assert tracks["https://openalex.org/W1"] == "reviewA"
    assert tracks["https://openalex.org/W2"] == "reviewB"


def test_ids_carried_when_present(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (_work("https://openalex.org/W1", "T", "A", doi="10.1/xyz"), 1),
        ],
    }
    reviews_file = tmp_path / "reviews.toml"
    reviews_file.write_text('reviews = ["reviewA"]\n')
    out = tmp_path / "gold.json"

    build_goldset.build_goldset(reviews_file, "test-project", out)

    record = json.loads(out.read_text())["records"][0]
    kinds = {entry["kind"] for entry in record["ids"]}
    assert kinds == {"doi", "openalex"}


def test_strip_html_removes_tags_and_preserves_word_boundaries():
    assert build_goldset.strip_html("plain text") == "plain text"
    assert build_goldset.strip_html("<i>DSM-5</i> PTSD") == "DSM-5 PTSD"
    # No original whitespace around the tags: stripping must still separate words.
    assert build_goldset.strip_html("MS<i>Estonia</i>disaster") == "MS Estonia disaster"
    assert build_goldset.strip_html('<sub xmlns:mml="http://x">2</sub>O') == "2 O"


def test_html_markup_stripped_from_title_and_abstract(tmp_path: Path):
    FakeDataset._WORKS = {
        "reviewA": [
            (
                _work(
                    "https://openalex.org/W1",
                    "MS<i>Estonia</i>disaster",
                    "<h2>Abstract</h2> Some text.",
                ),
                1,
            ),
        ],
    }
    reviews_file = tmp_path / "reviews.toml"
    reviews_file.write_text('reviews = ["reviewA"]\n')
    out = tmp_path / "gold.json"

    build_goldset.build_goldset(reviews_file, "test-project", out)

    record = json.loads(out.read_text())["records"][0]
    assert record["title"] == "MS Estonia disaster"
    assert record["abstract"] == "Abstract Some text."


def test_dropped_report_written_with_included_excluded_breakdown(tmp_path: Path):
    # Asymmetric counts (2 vs 1) so a swapped included/excluded assignment
    # in build_goldset's report assembly would fail this test.
    FakeDataset._WORKS = {
        "reviewA": [
            (_work("https://openalex.org/W1", "Has abstract", "Abstract 1"), 1),
            (_work("https://openalex.org/W2", "Dropped include 1", ""), 1),
            (_work("https://openalex.org/W3", "Dropped include 2", None), 1),
            (_work("https://openalex.org/W4", "Dropped exclude", ""), 0),
        ],
    }
    reviews_file = tmp_path / "reviews.toml"
    reviews_file.write_text('reviews = ["reviewA"]\n')
    out = tmp_path / "gold.json"

    build_goldset.build_goldset(reviews_file, "test-project", out)

    report = json.loads((tmp_path / "gold.dropped.json").read_text())
    assert report["project"] == "test-project"
    assert report["by_track"]["reviewA"] == {"dropped_included": 2, "dropped_excluded": 1}
    assert report["total_dropped_included"] == 2


def test_build_records_returns_label_keyed_drop_counter():
    FakeDataset._WORKS = {
        "reviewA": [
            (_work("https://openalex.org/W1", "T", "A"), 1),
            (_work("https://openalex.org/W2", "No abs include", ""), 1),
            (_work("https://openalex.org/W3", "No abs exclude", ""), 0),
            (_work("https://openalex.org/W4", "No abs exclude 2", None), 0),
        ],
    }
    records, dropped = build_goldset.build_records("reviewA")
    assert len(records) == 1
    assert dropped[1] == 1
    assert dropped[-1] == 2


def test_invalid_payload_raises_contract_error(tmp_path: Path):
    # A blank record id (no OpenAlex id, no DOI) must fail loudly, not silently.
    FakeDataset._WORKS = {
        "reviewA": [(_work("", "T", "A"), 1)],
    }
    reviews_file = tmp_path / "reviews.toml"
    reviews_file.write_text('reviews = ["reviewA"]\n')
    out = tmp_path / "gold.json"

    with pytest.raises(ContractError):
        build_goldset.build_goldset(reviews_file, "test-project", out)
