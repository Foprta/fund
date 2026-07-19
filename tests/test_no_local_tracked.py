"""Public tree must not track private overlay files."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_SUFFIXES = (
    "policy_local.py",
    "tools_local.py",
    "models_local.py",
    "queries_local.py",
    "sync_sheets_local.py",
    "seed_demo_local.py",
    "restricted_terms_local.py",
)
FORBIDDEN_PREFIXES = (
    "local/",
    "tests_local/",
)


def _tracked_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        text=True,
    )
    return [p for p in out.split("\0") if p]


def test_no_private_overlay_paths_tracked():
    tracked = _tracked_files()
    bad: list[str] = []
    for path in tracked:
        if path.startswith(FORBIDDEN_PREFIXES):
            bad.append(path)
            continue
        if path.endswith(FORBIDDEN_SUFFIXES) or any(
            path.endswith("/" + s) for s in FORBIDDEN_SUFFIXES
        ):
            bad.append(path)
    assert bad == [], f"private overlay paths must not be tracked: {bad}"
