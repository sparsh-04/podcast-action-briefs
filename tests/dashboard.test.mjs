import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const Dashboard = require("../site/dashboard.js");

const snapshot = {
  schema_version: 1,
  podcasts: [
    {
      slug: "boundless-a1",
      title: "Boundless Life",
      episodes: [
        {
          slug: "family-health-1",
          title: "Family Health",
          published_at: "2026-09-01T00:00:00Z",
          duration_seconds: 3600,
          guest: "Dr. Example",
          show_notes_url: "https://publisher.example/family",
          brief: {
            domain: "health",
            conclusion: "Omega-3 may help selected people.",
            outcome: "actions",
            actions: [
              {
                priority: "consider",
                action: "Discuss omega-3 with a clinician.",
                evidence_verdict: "moderate",
                applicability: ["primary_user", "father"],
                risk_dimensions: ["interactions"],
                why: ["Dose and medicines affect safety."],
                risks: ["Bleeding risk may change."],
                sources: [],
              },
            ],
          },
        },
      ],
    },
    {
      slug: "tools-b2",
      title: "Tools Weekly",
      episodes: [
        {
          slug: "passkeys-2",
          title: "Passkeys for Teams",
          published_at: "2026-10-01T00:00:00Z",
          duration_seconds: 1800,
          guest: null,
          show_notes_url: "https://publisher.example/passkeys",
          brief: {
            domain: "technology",
            conclusion: "Pilot passkeys before a broad rollout.",
            outcome: "actions",
            actions: [
              {
                priority: "recommended",
                action: "Run a five-person pilot.",
                evidence_verdict: "strong",
                applicability: ["technology_users"],
                risk_dimensions: ["security"],
                why: ["A pilot exposes recovery gaps."],
                risks: ["Recovery needs testing."],
                sources: [],
              },
            ],
          },
        },
      ],
    },
  ],
};

test("flattenBriefs returns display records in deterministic newest-first order", () => {
  const items = Dashboard.flattenBriefs(snapshot);

  assert.deepEqual(items.map((item) => item.episodeSlug), ["passkeys-2", "family-health-1"]);
  assert.equal(items[1].podcastTitle, "Boundless Life");
  assert.equal(items[1].brief.actions[0].applicability[1], "father");
});

test("filterBriefs searches title conclusion action and reason case-insensitively", () => {
  const items = Dashboard.flattenBriefs(snapshot);

  assert.deepEqual(Dashboard.filterBriefs(items, { query: "OMEGA-3" }).map((item) => item.episodeSlug), ["family-health-1"]);
  assert.deepEqual(Dashboard.filterBriefs(items, { query: "recovery gaps" }).map((item) => item.episodeSlug), ["passkeys-2"]);
});

test("filterBriefs applies exact individual filters", () => {
  const items = Dashboard.flattenBriefs(snapshot);

  assert.equal(Dashboard.filterBriefs(items, { podcast: "boundless-a1" }).length, 1);
  assert.equal(Dashboard.filterBriefs(items, { domain: "technology" }).length, 1);
  assert.equal(Dashboard.filterBriefs(items, { verdict: "moderate" }).length, 1);
  assert.equal(Dashboard.filterBriefs(items, { priority: "recommended" }).length, 1);
  assert.equal(Dashboard.filterBriefs(items, { applicability: "father" }).length, 1);
  assert.equal(Dashboard.filterBriefs(items, { applicability: "mother" }).length, 0);
});

test("filterBriefs combines filters rather than widening them", () => {
  const items = Dashboard.flattenBriefs(snapshot);

  assert.equal(
    Dashboard.filterBriefs(items, {
      domain: "health",
      verdict: "moderate",
      priority: "consider",
      applicability: "father",
    }).length,
    1,
  );
  assert.equal(
    Dashboard.filterBriefs(items, { domain: "health", verdict: "strong" }).length,
    0,
  );
});

test("filterOptions deduplicates and sorts deterministic labels", () => {
  const options = Dashboard.filterOptions(Dashboard.flattenBriefs(snapshot));

  assert.deepEqual(options.podcasts, [
    { value: "boundless-a1", label: "Boundless Life" },
    { value: "tools-b2", label: "Tools Weekly" },
  ]);
  assert.deepEqual(options.domains, ["health", "technology"]);
  assert.deepEqual(options.verdicts, ["moderate", "strong"]);
  assert.deepEqual(options.priorities, ["consider", "recommended"]);
  assert.deepEqual(options.applicability, ["father", "primary_user", "technology_users"]);
});

test("flattenBriefs returns an empty array for malformed snapshots", () => {
  for (const malformed of [null, {}, { schema_version: 1, podcasts: {} }]) {
    assert.deepEqual(Dashboard.flattenBriefs(malformed), []);
  }
});

test("appendText assigns external content through textContent", () => {
  const appended = [];
  const document = {
    createElement(tagName) {
      return { tagName, textContent: "", className: "" };
    },
  };
  const parent = { append(node) { appended.push(node); } };
  const attack = '<img src=x onerror="globalThis.compromised=true">';

  Dashboard.appendText(document, parent, "p", attack, "copy");

  assert.equal(appended[0].textContent, attack);
  assert.equal(appended[0].className, "copy");
  assert.equal("innerHTML" in appended[0], false);
});

test("safeExternalUrl accepts only credential-free HTTP(S) links", () => {
  assert.equal(Dashboard.safeExternalUrl("https://authority.example/path"), "https://authority.example/path");
  assert.equal(Dashboard.safeExternalUrl("javascript:alert(1)"), null);
  assert.equal(Dashboard.safeExternalUrl("https://user:pass@authority.example/"), null);
});
