"""Best-effort resolution of the installed `attest` package's source commit.

Printed to stdout (or nothing) for the Makefile to capture into
ATTEST_SOURCE_COMMIT (see attest.provenance.manifest.software_version),
so a run's manifest records a real commit by default instead of requiring
the caller to look it up and set it by hand every time.

Reads the commit from whichever install method actually produced the
currently-importable `attest` package, via its dist-info's direct_url.json:
a pinned VCS install (e.g. `attest @ git+https://...`) records the exact
commit directly. An editable local install (`pip install -e /path/to/attest`,
this project's own development setup) has no pinned commit -- the working
tree can move -- so this falls back to `git rev-parse HEAD` inside that
local checkout instead, which is the actual answer to "what commit is this
run using" for that setup.

Prints nothing and exits 0 if neither is resolvable (e.g. attest is not
installed, or installed some other way) -- ATTEST_SOURCE_COMMIT is
documented as optional, so a Makefile capturing this into a variable must
never fail a run over it.
"""

from __future__ import annotations

import json
import subprocess
from importlib import metadata
from pathlib import Path


def resolve_attest_source_commit() -> str | None:
    """Return the installed `attest` package's source commit, or None if unresolvable."""
    try:
        dist = metadata.distribution("attest")
    except metadata.PackageNotFoundError:
        return None

    direct_url_text = dist.read_text("direct_url.json")
    if direct_url_text is None:
        return None
    direct_url = json.loads(direct_url_text)

    vcs_info = direct_url.get("vcs_info", {})
    if vcs_info.get("vcs") == "git" and vcs_info.get("commit_id"):
        return str(vcs_info["commit_id"])

    url = direct_url.get("url", "")
    if direct_url.get("dir_info", {}).get("editable") and url.startswith("file://"):
        path = Path(url[len("file://") :])
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return result.stdout.strip()

    return None


def main() -> int:
    commit = resolve_attest_source_commit()
    if commit:
        print(commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
