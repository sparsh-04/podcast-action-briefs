#!/usr/bin/env python3
"""Export stored podcast briefs from the private loopback dashboard."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_EPISODE_FIELDS = (
    "title",
    "published_at",
    "duration_seconds",
    "guest",
    "show_notes_url",
)


def public_slug(title: str, stable_id: str) -> str:
    """Return a readable, collision-resistant public slug."""
    if not isinstance(title, str) or not isinstance(stable_id, str) or not stable_id:
        raise ValueError("title and stable_id must be strings")
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    stem = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")[:72].rstrip("-")
    digest = sha256(stable_id.encode("utf-8")).hexdigest()[:10]
    return f"{stem or 'episode'}-{digest}"


def _require_mapping(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_text(mapping: dict, key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} {key} must be a non-empty string")
    return value


def build_snapshot(
    podcasts: list[dict],
    episodes_by_podcast: dict[str, list[dict]],
    details_by_episode: dict[str, dict],
) -> dict:
    """Build the allowlisted public snapshot without changing brief values."""
    if not isinstance(podcasts, list):
        raise ValueError("podcasts must be an array")
    if not isinstance(episodes_by_podcast, dict):
        raise ValueError("episodes_by_podcast must be an object")
    if not isinstance(details_by_episode, dict):
        raise ValueError("details_by_episode must be an object")

    published_podcasts = []
    for raw_podcast in podcasts:
        podcast = _require_mapping(raw_podcast, "podcast")
        podcast_id = _require_text(podcast, "id", "podcast")
        podcast_title = _require_text(podcast, "title", "podcast")
        raw_episodes = episodes_by_podcast.get(podcast_id, [])
        if not isinstance(raw_episodes, list):
            raise ValueError("podcast episodes must be an array")

        published_episodes = []
        for raw_episode in raw_episodes:
            episode_summary = _require_mapping(raw_episode, "episode")
            episode_id = _require_text(episode_summary, "id", "episode")
            detail_payload = details_by_episode.get(episode_id)
            if detail_payload is None:
                continue
            detail = _require_mapping(detail_payload, "episode detail")
            episode = _require_mapping(detail.get("episode"), "episode detail episode")
            brief = episode.get("brief")
            if brief is None:
                continue
            if not isinstance(brief, dict):
                raise ValueError("brief must be an object")

            title = _require_text(episode, "title", "episode detail")
            published = {
                "slug": public_slug(title, episode_id),
                **{field: episode.get(field) for field in _EPISODE_FIELDS},
                "brief": brief,
            }
            published_episodes.append(published)

        published_episodes.sort(
            key=lambda item: (
                item.get("published_at") or "",
                item["title"].casefold(),
                item["slug"],
            ),
            reverse=True,
        )
        if published_episodes:
            published_podcasts.append(
                {
                    "slug": public_slug(podcast_title, podcast_id),
                    "title": podcast_title,
                    "episodes": published_episodes,
                }
            )

    published_podcasts.sort(key=lambda item: (item["title"].casefold(), item["slug"]))
    return {"schema_version": 1, "podcasts": published_podcasts}


def _validated_base_url(base_url: str) -> str:
    if not isinstance(base_url, str):
        raise ValueError("dashboard URL must be a loopback HTTP URL")
    parsed = urlparse(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in _LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("dashboard URL must be a loopback HTTP URL")
    return base_url.rstrip("/")


def _fetch_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
    return _require_mapping(payload, "API response")


def _write_json_atomically(output_path: Path, payload: dict) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def export_snapshot(base_url: str, output_path: Path) -> dict:
    """Fetch final briefs from a private dashboard and write one snapshot."""
    base = _validated_base_url(base_url)
    podcast_payload = _fetch_json(f"{base}/api/podcasts")
    podcasts = podcast_payload.get("podcasts")
    if not isinstance(podcasts, list):
        raise ValueError("podcasts response must contain an array")

    episodes_by_podcast: dict[str, list[dict]] = {}
    details_by_episode: dict[str, dict] = {}
    for podcast in podcasts:
        podcast = _require_mapping(podcast, "podcast")
        podcast_id = _require_text(podcast, "id", "podcast")
        encoded_podcast_id = quote(podcast_id, safe="")
        episode_payload = _fetch_json(
            f"{base}/api/podcasts/{encoded_podcast_id}/episodes"
        )
        episodes = episode_payload.get("episodes")
        if not isinstance(episodes, list):
            raise ValueError("episodes response must contain an array")
        episodes_by_podcast[podcast_id] = episodes
        for episode in episodes:
            episode = _require_mapping(episode, "episode")
            if "schema_version" not in episode:
                continue
            episode_id = _require_text(episode, "id", "episode")
            encoded_episode_id = quote(episode_id, safe="")
            details_by_episode[episode_id] = _fetch_json(
                f"{base}/api/episodes/{encoded_episode_id}"
            )

    snapshot = build_snapshot(podcasts, episodes_by_podcast, details_by_episode)
    _write_json_atomically(Path(output_path), snapshot)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    snapshot = export_snapshot(arguments.base_url, arguments.output)
    count = sum(len(podcast["episodes"]) for podcast in snapshot["podcasts"])
    print(f"exported {count} briefs to {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
