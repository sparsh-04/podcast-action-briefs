from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import export_snapshot as exporter


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False


class ExportSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.brief = {
            "episode_id": "episode-private-id",
            "domain": "health",
            "conclusion": "A literal <b>family</b> conclusion.",
            "checked_at": "2026-10-20T08:00:00Z",
            "outcome": "actions",
            "schema_version": 1,
            "actions": [
                {
                    "priority": "consider",
                    "action": "Discuss this with a clinician.",
                    "why": ["Individual circumstances change the balance."],
                    "protocol": "Bring a medication list.",
                    "podcast_claim": "The guest recommends this approach.",
                    "evidence_verdict": "moderate",
                    "evidence_reason": "Evidence is promising but incomplete.",
                    "risks": ["Medication interactions require review."],
                    "risk_dimensions": ["interactions"],
                    "applicability": ["primary_user", "father", "mother", "sister"],
                    "sources": [
                        {
                            "title": "Clinical guideline",
                            "url": "https://authority.example/guideline",
                            "kind": "clinical_guideline",
                            "checked_at": "2026-10-20T08:00:00Z",
                        }
                    ],
                }
            ],
        }
        self.podcasts = [
            {
                "id": "podcast-private-id",
                "title": "Boundless Life",
                "pocket_casts_url": "https://pocketcasts.example/private",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]
        self.episode = {
            "id": "episode-private-id",
            "podcast_id": "podcast-private-id",
            "title": "A family health episode",
            "published_at": "2026-09-01T00:00:00Z",
            "duration_seconds": 3600,
            "guest": "Dr. Example",
            "show_notes_url": "https://publisher.example/show-notes",
            "schema_version": 1,
            "pocket_casts_url": "https://pocketcasts.example/private-episode",
            "state": "completed",
            "retry_count": 4,
            "observed_archived": True,
            "error_detail": "/Users/private/transcripts/secret.txt",
        }
        self.detail = {
            "episode": self.episode
            | {
                "brief": self.brief,
                "events": [{"event_type": "brief_saved"}],
                "evidence_sources": [{"url": "https://internal.example"}],
                "transcript_path": "/Users/private/transcripts/secret.txt",
                "archive_token": "do-not-publish",
            }
        }

    def build(self, *, detail=None):
        return exporter.build_snapshot(
            self.podcasts,
            {"podcast-private-id": [self.episode]},
            {"episode-private-id": self.detail if detail is None else detail},
        )

    def test_build_snapshot_preserves_brief_value_exactly(self):
        snapshot = self.build()

        published = snapshot["podcasts"][0]["episodes"][0]["brief"]
        self.assertEqual(published, self.brief)
        self.assertEqual(
            published["actions"][0]["applicability"],
            ["primary_user", "father", "mother", "sister"],
        )

    def test_build_snapshot_exports_only_allowlisted_metadata(self):
        published = self.build()["podcasts"][0]["episodes"][0]

        self.assertEqual(
            set(published),
            {
                "slug",
                "title",
                "published_at",
                "duration_seconds",
                "guest",
                "show_notes_url",
                "brief",
            },
        )
        serialized = json.dumps(published)
        for forbidden in (
            "pocket_casts_url",
            "retry_count",
            "observed_archived",
            "events",
            "transcript_path",
            "archive_token",
            "/Users/private",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_build_snapshot_skips_null_briefs(self):
        detail = {"episode": self.episode | {"brief": None}}

        snapshot = self.build(detail=detail)

        self.assertEqual(snapshot["podcasts"], [])

    def test_build_snapshot_rejects_non_object_brief(self):
        detail = {"episode": self.episode | {"brief": ["not", "an", "object"]}}

        with self.assertRaisesRegex(ValueError, "brief must be an object"):
            self.build(detail=detail)

    def test_public_slug_is_stable_distinct_and_has_fallback(self):
        first = exporter.public_slug("Same title", "episode-1")
        second = exporter.public_slug("Same title", "episode-2")

        self.assertEqual(first, exporter.public_slug("Same title", "episode-1"))
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^same-title-[0-9a-f]{10}$")
        self.assertRegex(exporter.public_slug("!!!", "episode-3"), r"^episode-[0-9a-f]{10}$")

    def test_export_snapshot_rejects_non_loopback_url(self):
        with patch.object(exporter, "urlopen") as opener:
            with self.assertRaisesRegex(ValueError, "loopback"):
                exporter.export_snapshot("https://dashboard.example", Path("ignored.json"))

        opener.assert_not_called()

    def test_export_snapshot_writes_atomically(self):
        payloads = {
            "http://127.0.0.1:8765/api/podcasts": {"podcasts": self.podcasts},
            "http://127.0.0.1:8765/api/podcasts/podcast-private-id/episodes": {
                "episodes": [self.episode]
            },
            "http://127.0.0.1:8765/api/episodes/episode-private-id": self.detail,
        }

        def open_fixture(request, timeout):
            self.assertEqual(timeout, 10)
            return FakeResponse(json.dumps(payloads[request.full_url]).encode("utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "briefs.json"
            output.write_text("old snapshot", encoding="utf-8")
            with patch.object(exporter, "urlopen", side_effect=open_fixture):
                with patch.object(exporter.os, "replace", side_effect=OSError("replace failed")):
                    with self.assertRaisesRegex(OSError, "replace failed"):
                        exporter.export_snapshot("http://127.0.0.1:8765", output)

            self.assertEqual(output.read_text(encoding="utf-8"), "old snapshot")
            self.assertEqual([path.name for path in Path(directory).iterdir()], ["briefs.json"])


if __name__ == "__main__":
    unittest.main()
