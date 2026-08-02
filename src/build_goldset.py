"""SYNERGY-to-attest gold-set builder (attest-runbook §3).

Reads the review names selected in ``reviews.toml``, loads each review via
the ``synergy-dataset`` package, and writes one combined JSON file
conforming to ``attest.contracts.input`` (schema_version "1.0"), with
``track`` set to the review name and ``gold_label`` set from SYNERGY's
published inclusion decision. The output is validated with
``attest.contracts.input.validate_and_normalize`` before being written, so
a malformed gold set fails here rather than downstream in the kernel.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from attest.contracts.input import ContractError, validate_and_normalize
from synergy_dataset import Dataset, download_raw_dataset
from synergy_dataset.base import _dataset_available

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Strip HTML-like markup from OpenAlex title/abstract text.

    A small fraction of SYNERGY/OpenAlex records carry structural or
    formatting tags (``<i>``, ``<sub>``, ``<h3>``, ...), sometimes with no
    surrounding whitespace (e.g. ``"MS<i>Estonia</i>disaster"``), so each
    tag is replaced with a single space -- rather than deleted outright --
    to avoid gluing the adjacent words together, then runs of whitespace
    are collapsed.
    """
    return re.sub(r"\s+", " ", _HTML_TAG_RE.sub(" ", text)).strip()


def ensure_raw_dataset_downloaded() -> None:
    """Download the raw SYNERGY archive if it isn't already cached locally.

    ``Dataset.iter()`` silently yields nothing if the raw archive hasn't
    been downloaded yet (it just globs a directory that doesn't exist), so
    this must run before iterating any review -- mirroring what the
    package's own CLI (``synergy_dataset get``) does automatically.
    """
    if not _dataset_available():
        download_raw_dataset()


def load_review_names(reviews_file: Path) -> list[str]:
    """Read the ``reviews`` list of review names out of a reviews.toml file."""
    with reviews_file.open("rb") as f:
        data = tomllib.load(f)
    reviews = data.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        raise ValueError(f"{reviews_file}: 'reviews' must be a non-empty list of review names")
    return [str(name) for name in reviews]


def _external_ids(doi: str, openalex_id: str) -> list[dict[str, str]]:
    ids: list[dict[str, str]] = []
    if doi:
        ids.append({"kind": "doi", "value": doi})
    if openalex_id:
        ids.append({"kind": "openalex", "value": openalex_id})
    return ids


def build_records(review_name: str) -> tuple[list[dict[str, Any]], int]:
    """Map one SYNERGY review's works to input-contract records.

    Returns:
        The mapped records, and the count of records dropped for having an
        empty or missing abstract.
    """
    records: list[dict[str, Any]] = []
    n_dropped = 0
    for work, label_included in Dataset(review_name).iter():
        try:
            abstract = work["abstract"]
        except KeyError:
            abstract = None
        abstract = strip_html(abstract) if abstract else None
        if not abstract:
            n_dropped += 1
            continue

        openalex_id = work.get("id") or ""
        doi = work.get("doi") or ""
        record_id = openalex_id or doi
        records.append(
            {
                "id": record_id,
                "title": strip_html(work.get("title") or ""),
                "abstract": abstract,
                "track": review_name,
                "ids": _external_ids(doi, openalex_id),
                "gold_label": 1 if label_included == 1 else -1,
            }
        )
    return records, n_dropped


def build_goldset(reviews_file: Path, project: str, out: Path) -> None:
    review_names = load_review_names(reviews_file)
    ensure_raw_dataset_downloaded()

    all_records: list[dict[str, Any]] = []
    for review_name in review_names:
        records, n_dropped = build_records(review_name)
        print(f"{review_name}: {len(records)} kept, {n_dropped} dropped (empty abstract)")
        all_records.extend(records)

    payload = {
        "schema_version": "1.0",
        "project": project,
        "records": all_records,
    }

    normalized = validate_and_normalize(payload)
    print(f"validated: {len(normalized.records)} records across {len(review_names)} review(s)")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build-goldset")
    parser.add_argument("--reviews-file", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        build_goldset(args.reviews_file, args.project, args.out)
    except ContractError as exc:
        print(f"error: gold set failed input-contract validation: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
