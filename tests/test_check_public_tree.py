from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import check_public_tree as checker


class PublicTreeCheckTests(unittest.TestCase):
    def make_root(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def write_snapshot(self, root: Path, episode_overrides=None, brief_overrides=None):
        brief = {
            "domain": "health",
            "conclusion": "Keep the final brief exactly as written.",
            "actions": [
                {
                    "action": "Discuss with a clinician.",
                    "applicability": ["primary_user", "father", "mother", "sister"],
                    "sources": [{"url": "https://authority.example/guideline"}],
                }
            ],
        }
        if brief_overrides:
            brief.update(brief_overrides)
        episode = {
            "slug": "episode-123",
            "title": "Episode",
            "published_at": "2026-10-20T00:00:00Z",
            "duration_seconds": 1800,
            "guest": None,
            "show_notes_url": "https://publisher.example/episode",
            "brief": brief,
        }
        if episode_overrides:
            episode.update(episode_overrides)
        payload = {
            "schema_version": 1,
            "podcasts": [
                {
                    "slug": "podcast-123",
                    "title": "Podcast",
                    "episodes": [episode],
                }
            ],
        }
        data = root / "data"
        data.mkdir(parents=True)
        (data / "briefs.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_rejects_database_and_journal_filenames(self):
        for filename in ("dashboard.sqlite3", "dashboard.sqlite3-wal", "dashboard.sqlite3-shm"):
            with self.subTest(filename=filename):
                root = self.make_root()
                (root / filename).write_text("private", encoding="utf-8")
                self.assertTrue(any(filename in issue for issue in checker.scan_public_tree(root)))

    def test_rejects_private_artifact_directories(self):
        for directory in ("transcripts", "capture", "work", "outputs", ".vercel"):
            with self.subTest(directory=directory):
                root = self.make_root()
                private = root / directory
                private.mkdir()
                (private / "artifact.txt").write_text("private", encoding="utf-8")
                self.assertTrue(any(directory in issue for issue in checker.scan_public_tree(root)))

    def test_rejects_absolute_home_paths(self):
        root = self.make_root()
        (root / "index.html").write_text(
            "Generated from /Users/example/private/transcript.txt", encoding="utf-8"
        )

        self.assertTrue(any("absolute home path" in issue for issue in checker.scan_public_tree(root)))

    def test_rejects_credential_shaped_json_keys(self):
        root = self.make_root()
        self.write_snapshot(root, brief_overrides={"access_token": "secret"})

        self.assertTrue(any("credential-shaped key" in issue for issue in checker.scan_public_tree(root)))

    def test_rejects_forbidden_episode_sibling_fields(self):
        root = self.make_root()
        self.write_snapshot(
            root,
            episode_overrides={
                "events": [{"event_type": "brief_saved"}],
                "pocket_casts_url": "https://pocketcasts.example/private",
                "transcript_path": "/private/transcript.txt",
            },
        )

        issues = checker.scan_public_tree(root)

        self.assertTrue(any("events" in issue for issue in issues))
        self.assertTrue(any("pocket_casts_url" in issue for issue in issues))
        self.assertTrue(any("transcript_path" in issue for issue in issues))

    def test_accepts_unchanged_personal_and_family_applicability(self):
        root = self.make_root()
        self.write_snapshot(root)

        self.assertEqual(checker.scan_public_tree(root), [])


if __name__ == "__main__":
    unittest.main()
