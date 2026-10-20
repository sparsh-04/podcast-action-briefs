#!/usr/bin/env python3
"""Fail closed when deployable files contain private dashboard artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


_FORBIDDEN_PARTS = frozenset(
    {".vercel", "capture", "captures", "transcript", "transcripts", "work", "outputs"}
)
_DATABASE_NAME = re.compile(r"\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm))?$", re.IGNORECASE)
_HOME_PATH = re.compile(r"(?:/Users/|/home/)[^\s\"'<>/]+/")
_CREDENTIAL_KEY = re.compile(
    r"(?:^|_)(?:access_token|refresh_token|api_key|authorization|cookie|password|secret)(?:$|_)",
    re.IGNORECASE,
)
_ROOT_FIELDS = frozenset({"schema_version", "podcasts"})
_PODCAST_FIELDS = frozenset({"slug", "title", "episodes"})
_EPISODE_FIELDS = frozenset(
    {"slug", "title", "published_at", "duration_seconds", "guest", "show_notes_url", "brief"}
)


def _credential_issues(value, location: str, issues: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and _CREDENTIAL_KEY.search(key):
                issues.append(f"credential-shaped key at {location}.{key}")
            _credential_issues(child, f"{location}.{key}", issues)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _credential_issues(child, f"{location}[{index}]", issues)


def _unexpected_fields(value: dict, allowed: frozenset[str], location: str) -> list[str]:
    return [f"forbidden field {location}.{key}" for key in sorted(set(value) - allowed)]


def _snapshot_issues(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return [f"invalid public snapshot {path}: {error}"]
    if not isinstance(payload, dict):
        return [f"public snapshot root must be an object: {path}"]

    issues = _unexpected_fields(payload, _ROOT_FIELDS, "snapshot")
    podcasts = payload.get("podcasts")
    if not isinstance(podcasts, list):
        issues.append("snapshot.podcasts must be an array")
        return issues
    for podcast_index, podcast in enumerate(podcasts):
        location = f"snapshot.podcasts[{podcast_index}]"
        if not isinstance(podcast, dict):
            issues.append(f"{location} must be an object")
            continue
        issues.extend(_unexpected_fields(podcast, _PODCAST_FIELDS, location))
        episodes = podcast.get("episodes")
        if not isinstance(episodes, list):
            issues.append(f"{location}.episodes must be an array")
            continue
        for episode_index, episode in enumerate(episodes):
            episode_location = f"{location}.episodes[{episode_index}]"
            if not isinstance(episode, dict):
                issues.append(f"{episode_location} must be an object")
                continue
            issues.extend(_unexpected_fields(episode, _EPISODE_FIELDS, episode_location))
            if not isinstance(episode.get("brief"), dict):
                issues.append(f"{episode_location}.brief must be an object")
    _credential_issues(payload, "snapshot", issues)
    return issues


def scan_public_tree(root: Path) -> list[str]:
    """Return publication-blocking issues beneath a deployable tree."""
    root = Path(root)
    if not root.is_dir():
        return [f"public tree is not a directory: {root}"]
    issues: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        lowered_parts = [part.casefold() for part in relative.parts]
        forbidden_parts = [part for part in lowered_parts if part in _FORBIDDEN_PARTS]
        if forbidden_parts:
            issues.append(f"forbidden private artifact path: {relative}")
            if path.is_dir():
                continue
        if path.is_dir():
            continue
        if _DATABASE_NAME.search(path.name):
            issues.append(f"forbidden database file: {relative}")
        try:
            content = path.read_bytes()
        except OSError as error:
            issues.append(f"could not inspect {relative}: {error}")
            continue
        if content.startswith(b"SQLite format 3\x00"):
            issues.append(f"SQLite database signature found: {relative}")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if _HOME_PATH.search(text):
            issues.append(f"absolute home path found: {relative}")
        if relative.as_posix() == "data/briefs.json":
            issues.extend(_snapshot_issues(path))
    return sorted(set(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    issues = scan_public_tree(arguments.root)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1
    print("public tree check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
