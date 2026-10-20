(function attachDashboard(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PodcastBriefDashboard = api;
})(typeof globalThis === "object" ? globalThis : this, function buildDashboardApi() {
  "use strict";

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function asText(value) {
    return typeof value === "string" ? value : "";
  }

  function flattenBriefs(snapshot) {
    if (!snapshot || typeof snapshot !== "object" || !Array.isArray(snapshot.podcasts)) {
      return [];
    }
    const items = [];
    for (const podcast of snapshot.podcasts) {
      if (!podcast || typeof podcast !== "object" || !Array.isArray(podcast.episodes)) continue;
      for (const episode of podcast.episodes) {
        if (!episode || typeof episode !== "object" || !episode.brief || typeof episode.brief !== "object") continue;
        items.push({
          podcastSlug: asText(podcast.slug),
          podcastTitle: asText(podcast.title),
          episodeSlug: asText(episode.slug),
          title: asText(episode.title),
          publishedAt: asText(episode.published_at),
          durationSeconds: Number.isFinite(episode.duration_seconds) ? episode.duration_seconds : null,
          guest: asText(episode.guest),
          showNotesUrl: asText(episode.show_notes_url),
          brief: episode.brief,
        });
      }
    }
    return items.sort((left, right) => {
      const byDate = right.publishedAt.localeCompare(left.publishedAt);
      if (byDate) return byDate;
      const byTitle = left.title.localeCompare(right.title, undefined, { sensitivity: "base" });
      return byTitle || left.episodeSlug.localeCompare(right.episodeSlug);
    });
  }

  function actionHas(action, field, expected) {
    if (!action || typeof action !== "object") return false;
    const value = action[field];
    return Array.isArray(value) ? value.includes(expected) : value === expected;
  }

  function searchableText(item) {
    const actions = asArray(item.brief.actions);
    const values = [item.podcastTitle, item.title, asText(item.brief.conclusion)];
    for (const action of actions) {
      if (!action || typeof action !== "object") continue;
      values.push(
        asText(action.action),
        asText(action.protocol),
        asText(action.podcast_claim),
        asText(action.evidence_reason),
        ...asArray(action.why),
        ...asArray(action.risks),
      );
    }
    return values.join(" ").casefold ? values.join(" ").casefold() : values.join(" ").toLocaleLowerCase();
  }

  function filterBriefs(items, filters = {}) {
    if (!Array.isArray(items)) return [];
    const query = asText(filters.query).trim().toLocaleLowerCase();
    return items.filter((item) => {
      const actions = asArray(item.brief && item.brief.actions);
      if (query && !searchableText(item).includes(query)) return false;
      if (filters.podcast && item.podcastSlug !== filters.podcast) return false;
      if (filters.domain && item.brief.domain !== filters.domain) return false;
      if (filters.verdict && !actions.some((action) => actionHas(action, "evidence_verdict", filters.verdict))) return false;
      if (filters.priority && !actions.some((action) => actionHas(action, "priority", filters.priority))) return false;
      if (filters.applicability && !actions.some((action) => actionHas(action, "applicability", filters.applicability))) return false;
      return true;
    });
  }

  function sortedValues(values) {
    return [...new Set(values.filter((value) => typeof value === "string" && value))]
      .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }));
  }

  function filterOptions(items) {
    const podcastLabels = new Map();
    const domains = [];
    const verdicts = [];
    const priorities = [];
    const applicability = [];
    for (const item of Array.isArray(items) ? items : []) {
      podcastLabels.set(item.podcastSlug, item.podcastTitle);
      domains.push(item.brief && item.brief.domain);
      for (const action of asArray(item.brief && item.brief.actions)) {
        if (!action || typeof action !== "object") continue;
        verdicts.push(action.evidence_verdict);
        priorities.push(action.priority);
        applicability.push(...asArray(action.applicability));
      }
    }
    const podcasts = [...podcastLabels]
      .map(([value, label]) => ({ value, label }))
      .sort((left, right) => left.label.localeCompare(right.label, undefined, { sensitivity: "base" }));
    return {
      podcasts,
      domains: sortedValues(domains),
      verdicts: sortedValues(verdicts),
      priorities: sortedValues(priorities),
      applicability: sortedValues(applicability),
    };
  }

  function appendText(document, parent, tagName, value, className = "") {
    const node = document.createElement(tagName);
    node.textContent = value == null ? "" : String(value);
    if (className) node.className = className;
    parent.append(node);
    return node;
  }

  function safeExternalUrl(value) {
    if (typeof value !== "string" || !value) return null;
    try {
      const url = new URL(value);
      if (!new Set(["http:", "https:"]).has(url.protocol)) return null;
      if (url.username || url.password) return null;
      return url.href;
    } catch (_error) {
      return null;
    }
  }

  return {
    appendText,
    filterBriefs,
    filterOptions,
    flattenBriefs,
    safeExternalUrl,
  };
});
