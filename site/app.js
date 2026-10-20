(function startPublicDashboard() {
  "use strict";

  const Dashboard = globalThis.PodcastBriefDashboard;
  const elements = {
    list: document.querySelector("#briefs"),
    count: document.querySelector("#brief-count"),
    status: document.querySelector("#results-status"),
    query: document.querySelector("#query"),
    podcast: document.querySelector("#podcast-filter"),
    domain: document.querySelector("#domain-filter"),
    verdict: document.querySelector("#verdict-filter"),
    priority: document.querySelector("#priority-filter"),
    applicability: document.querySelector("#applicability-filter"),
    reset: document.querySelector("#reset-filters"),
  };
  let items = [];

  function humanize(value) {
    if (typeof value !== "string" || !value) return "Not specified";
    return value.split("_").filter(Boolean).map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
  }

  function formatDate(value) {
    const date = new Date(value);
    if (!value || Number.isNaN(date.getTime())) return "Date unavailable";
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
  }

  function formatDuration(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) return null;
    const minutes = Math.round(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const remainder = minutes % 60;
    return hours ? `${hours}h${remainder ? ` ${remainder}m` : ""}` : `${minutes}m`;
  }

  function addList(parent, values, className = "") {
    if (!Array.isArray(values) || !values.length) return null;
    const list = document.createElement("ul");
    if (className) list.className = className;
    for (const value of values) Dashboard.appendText(document, list, "li", value);
    parent.append(list);
    return list;
  }

  function addBadge(parent, value, kind = "") {
    const badge = Dashboard.appendText(document, parent, "span", humanize(value), "badge");
    if (kind && value) badge.classList.add(`badge-${kind}-${value}`);
    return badge;
  }

  function addSources(parent, sources) {
    const safeSources = Array.isArray(sources) ? sources : [];
    const links = safeSources
      .map((source) => ({ source, url: Dashboard.safeExternalUrl(source && source.url) }))
      .filter((entry) => entry.url);
    if (!links.length) return;
    Dashboard.appendText(document, parent, "h5", "Sources", "action-subheading");
    const list = document.createElement("ul");
    list.className = "source-list";
    for (const { source, url } of links) {
      const item = document.createElement("li");
      const link = Dashboard.appendText(document, item, "a", source.title || url);
      link.href = url;
      link.target = "_blank";
      link.rel = "noreferrer noopener";
      list.append(item);
    }
    parent.append(list);
  }

  function renderAction(action, index) {
    const card = document.createElement("section");
    card.className = "action-card";
    const heading = document.createElement("div");
    heading.className = "action-heading";
    Dashboard.appendText(document, heading, "h4", `${index + 1}. ${action.action || "Action"}`);
    const badges = document.createElement("div");
    badges.className = "badges";
    addBadge(badges, action.priority, "priority");
    addBadge(badges, action.evidence_verdict, "verdict");
    heading.append(badges);
    card.append(heading);

    if (Array.isArray(action.why) && action.why.length) {
      Dashboard.appendText(document, card, "h5", "Why it may matter", "action-subheading");
      addList(card, action.why);
    }
    if (action.protocol) {
      Dashboard.appendText(document, card, "h5", "Practical protocol", "action-subheading");
      Dashboard.appendText(document, card, "p", action.protocol);
    }
    if (action.podcast_claim) {
      Dashboard.appendText(document, card, "h5", "Podcast claim", "action-subheading");
      Dashboard.appendText(document, card, "p", action.podcast_claim);
    }
    if (action.evidence_reason) {
      Dashboard.appendText(document, card, "h5", "Evidence check", "action-subheading");
      Dashboard.appendText(document, card, "p", action.evidence_reason);
    }
    if (Array.isArray(action.risks) && action.risks.length) {
      Dashboard.appendText(document, card, "h5", "Safety and limitations", "action-subheading warning-heading");
      addList(card, action.risks, "risk-list");
    }
    if (Array.isArray(action.applicability) && action.applicability.length) {
      Dashboard.appendText(document, card, "h5", "Applies to", "action-subheading");
      const applicability = document.createElement("div");
      applicability.className = "badges";
      for (const profile of action.applicability) addBadge(applicability, profile, "profile");
      card.append(applicability);
    }
    addSources(card, action.sources);
    return card;
  }

  function renderBrief(item) {
    const details = document.createElement("details");
    details.className = "brief-card";
    const summary = document.createElement("summary");
    const titleBlock = document.createElement("div");
    titleBlock.className = "title-block";
    Dashboard.appendText(document, titleBlock, "p", item.podcastTitle, "podcast-name");
    Dashboard.appendText(document, titleBlock, "h3", item.title);
    const meta = [formatDate(item.publishedAt), formatDuration(item.durationSeconds), item.guest ? `Guest: ${item.guest}` : null]
      .filter(Boolean).join(" · ");
    Dashboard.appendText(document, titleBlock, "p", meta, "episode-meta");
    summary.append(titleBlock);
    addBadge(summary, item.brief.domain, "domain");
    details.append(summary);

    const body = document.createElement("div");
    body.className = "brief-body";
    Dashboard.appendText(document, body, "p", "Bottom line", "content-label");
    Dashboard.appendText(document, body, "p", item.brief.conclusion || "No conclusion recorded.", "conclusion");
    const actions = Array.isArray(item.brief.actions) ? item.brief.actions : [];
    if (actions.length) {
      Dashboard.appendText(document, body, "h4", actions.length === 1 ? "Action item" : `${actions.length} action items`, "actions-title");
      actions.forEach((action, index) => body.append(renderAction(action, index)));
    } else {
      Dashboard.appendText(document, body, "p", "No practical action was supported in this brief.", "empty-inline");
    }
    const showNotes = Dashboard.safeExternalUrl(item.showNotesUrl);
    if (showNotes) {
      const link = Dashboard.appendText(document, body, "a", "Open full show notes", "show-notes-link");
      link.href = showNotes;
      link.target = "_blank";
      link.rel = "noreferrer noopener";
    }
    details.append(body);
    return details;
  }

  function currentFilters() {
    return {
      query: elements.query.value,
      podcast: elements.podcast.value,
      domain: elements.domain.value,
      verdict: elements.verdict.value,
      priority: elements.priority.value,
      applicability: elements.applicability.value,
    };
  }

  function render() {
    const filtered = Dashboard.filterBriefs(items, currentFilters());
    elements.list.replaceChildren();
    if (!filtered.length) {
      Dashboard.appendText(document, elements.list, "p", "No briefs match these filters.", "empty-state");
    } else {
      for (const item of filtered) elements.list.append(renderBrief(item));
    }
    elements.list.setAttribute("aria-busy", "false");
    elements.status.textContent = `${filtered.length} of ${items.length} published briefs shown`;
  }

  function addOptions(select, values, labels = null) {
    for (const value of values) {
      const option = document.createElement("option");
      option.value = labels ? value.value : value;
      option.textContent = labels ? value.label : humanize(value);
      select.append(option);
    }
  }

  function installOptions() {
    const options = Dashboard.filterOptions(items);
    addOptions(elements.podcast, options.podcasts, true);
    addOptions(elements.domain, options.domains);
    addOptions(elements.verdict, options.verdicts);
    addOptions(elements.priority, options.priorities);
    addOptions(elements.applicability, options.applicability);
  }

  function resetFilters() {
    elements.query.value = "";
    for (const select of [elements.podcast, elements.domain, elements.verdict, elements.priority, elements.applicability]) select.value = "";
    render();
    elements.query.focus();
  }

  async function load() {
    try {
      const response = await fetch("/data/briefs.json", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Snapshot request failed: ${response.status}`);
      const snapshot = await response.json();
      items = Dashboard.flattenBriefs(snapshot);
      elements.count.textContent = String(items.length);
      installOptions();
      render();
    } catch (_error) {
      elements.count.textContent = "0";
      elements.list.replaceChildren();
      Dashboard.appendText(document, elements.list, "p", "The published briefs could not be loaded. Please try again later.", "empty-state error");
      elements.list.setAttribute("aria-busy", "false");
      elements.status.textContent = "Briefs unavailable";
    }
  }

  for (const control of [elements.query, elements.podcast, elements.domain, elements.verdict, elements.priority, elements.applicability]) {
    control.addEventListener(control === elements.query ? "input" : "change", render);
  }
  elements.reset.addEventListener("click", resetFilters);
  load();
})();
