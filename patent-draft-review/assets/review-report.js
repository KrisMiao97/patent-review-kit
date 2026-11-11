"use strict";

const byId = (id) => document.getElementById(id);
function hashTarget(hash) {
  try { return byId(decodeURIComponent(hash.slice(1))); } catch { return null; }
}
const issueCards = Array.from(document.querySelectorAll("article.issue"));
const evidenceRows = Array.from(document.querySelectorAll("tr[data-claim]"));
const issueFields = ["issue-query", "section-filter", "issue-filter", "priority-filter", "confirmation-filter"].map(byId).filter(Boolean);
const evidenceFields = ["claim-filter", "visual-filter"].map(byId);
const searchable = new Map(issueCards.map(item => [item, item.textContent.toLowerCase()]));
const sectionLinks = Array.from(document.querySelectorAll(".navigation a"));
const sectionTargets = sectionLinks.map((link) => byId(link.hash.slice(1)));
const navigation = document.querySelector(".navigation");
function measureNavigation() {
  const previousHeight = parseFloat(document.documentElement.style.getPropertyValue("--nav-height"));
  const height = navigation.getBoundingClientRect().height;
  const target = hashTarget(location.hash);
  const aligned = target && Number.isFinite(previousHeight) &&
    Math.abs(target.getBoundingClientRect().top - previousHeight - 18) < 2;
  document.documentElement.style.setProperty("--nav-height", height + "px");
  if (aligned && height !== previousHeight) target.scrollIntoView({ block: "start" });
}
measureNavigation();
new ResizeObserver(measureNavigation).observe(navigation);
let locatedIssue = null;

const relatedIndex = {};
for (const sectionId of ["evidence", "figures"]) {
  const index = new Map();
  for (const row of byId(sectionId).querySelectorAll("tr[data-related]")) {
    for (const id of row.dataset.related.split(" ").filter(Boolean)) {
      if (!index.has(id)) index.set(id, []);
      index.get(id).push(row);
    }
  }
  relatedIndex[sectionId] = index;
}

function populateRelated(panel) {
  if (panel.dataset.loaded) return;
  for (const record of panel.querySelectorAll(".related-records")) {
    const rows = relatedIndex[record.dataset.source].get(panel.dataset.issue);
    if (!rows?.length) continue;
    const original = rows[0].closest("table");
    const table = original.cloneNode(false);
    table.classList.add("related-table");
    const head = original.tHead.cloneNode(true);
    head.rows[0].lastElementChild.remove();
    table.append(head);
    const body = table.createTBody();
    body.setAttribute("role", "rowgroup");
    for (const row of rows) {
      const copy = body.insertRow();
      copy.setAttribute("role", "row");
      for (const cell of Array.from(row.cells).slice(0, -1)) copy.append(cell.cloneNode(true));
    }
    record.querySelector(".related-fallback").hidden = true;
    record.append(table);
  }
  panel.dataset.loaded = "true";
}

function filter(items, predicate, prefix, noun) {
  if (!items.length) return;
  let count = 0;
  for (const item of items) {
    item.hidden = !predicate(item);
    if (!item.hidden) count += 1;
  }
  byId(prefix + "-count").textContent = "显示 " + count + " / " + items.length + " " + noun;
  byId(prefix + "-empty").hidden = count > 0;
}

function updateIssues() {
  if (!issueCards.length) return;
  const [query, section, status, priority, confirmation] = issueFields.map(field => field.value.trim().toLowerCase());
  let matches = 0;
  let exception = null;
  for (const item of issueCards) {
    const match = (!section || item.dataset.section === section) && (!status || item.dataset.status === status) &&
      (!priority || item.dataset.priority === priority) && (!confirmation || item.dataset.confirmation === confirmation) &&
      (!query || searchable.get(item).includes(query));
    const outside = !match && item === locatedIssue;
    item.hidden = !match && !outside;
    item.querySelector(".filter-exception").hidden = !outside;
    if (match) matches += 1;
    if (outside) exception = item;
  }
  byId("issue-count").textContent = "匹配 " + matches + " / " + issueCards.length + " 条意见" +
    (exception ? "，另显示定位项 " + exception.id.slice(6) : "");
  byId("issue-empty").hidden = matches > 0 || Boolean(exception);
}

function updateEvidence() {
  const [claim, visual] = evidenceFields.map((field) => field.value);
  filter(evidenceRows, (row) => (!claim || row.dataset.claim === claim) &&
    (!visual || row.dataset.visual === visual), "evidence", "条记录");
}

function reset(fields, update) {
  for (const field of fields) field.value = "";
  update();
}

function revealIssue(hash) {
  measureNavigation();
  const target = hashTarget(hash);
  const issue = target?.closest("article.issue");
  if (!target) return;
  if (!issue) {
    for (const panel of document.querySelectorAll("details")) {
      if (panel === target || panel.contains(target)) panel.open = true;
    }
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "start" });
    return;
  }
  locatedIssue = issue;
  updateIssues();
  const panel = target.closest("details");
  if (panel) {
    panel.open = true;
    if (panel.classList.contains("related")) populateRelated(panel);
  }
  for (const parent of document.querySelectorAll("details")) { if (parent.contains(target)) parent.open = true; }
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: "start" });
}

function updateSection() {
  const readingLine = navigation.getBoundingClientRect().bottom + 28;
  let current = 0;
  for (const [index, section] of sectionTargets.entries()) {
    if (section.getBoundingClientRect().top <= readingLine) current = index;
  }
  const last = sectionTargets.length - 1;
  if (window.scrollY > 0 && window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2 &&
      sectionTargets[last].getBoundingClientRect().top < window.innerHeight) {
    current = last;
  }
  for (const [index, link] of sectionLinks.entries()) {
    if (index === current) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  }
}

if (issueCards.length) {
  byId("issues").querySelector(".toolbar").hidden = false;
  for (const field of issueFields) field.addEventListener("input", () => {
    locatedIssue = null;
    updateIssues();
  });
  byId("reset-issues").addEventListener("click", () => {
    locatedIssue = null;
    reset(issueFields, updateIssues);
  });
}
if (evidenceRows.length) {
  byId("evidence").querySelector(".toolbar").hidden = false;
  for (const field of evidenceFields) field.addEventListener("change", updateEvidence);
  byId("reset-evidence").addEventListener("click", () => reset(evidenceFields, updateEvidence));
}

document.addEventListener("click", (event) => {
  if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  const link = event.target.closest("a");
  if (!link) return;
  if (link.hash === "#reading-guide") {
    const origin = link.closest(".edits");
    const back = byId("guide-return");
    if (origin && back) {
      back.href = "#" + origin.id;
      back.textContent = "返回 " + origin.id.slice(5) + " 的修改建议";
      back.hidden = false;
    }
  }
  if (link.dataset.filterSection && issueCards.length &&
      Array.from(byId("section-filter").options).some(option => option.value === link.dataset.filterSection)) {
    locatedIssue = null;
    for (const field of issueFields) field.value = "";
    byId("section-filter").value = link.dataset.filterSection;
    updateIssues();
  }
  if (link.getAttribute("href")?.startsWith("#") && link.hash === location.hash) revealIssue(link.hash);
});
for (const panel of document.querySelectorAll("details.related")) {
  panel.addEventListener("toggle", () => { if (panel.open) populateRelated(panel); });
}
window.addEventListener("hashchange", () => {
  revealIssue(location.hash);
  updateSection();
});
window.addEventListener("scroll", updateSection, { passive: true });
window.addEventListener("resize", () => { measureNavigation(); updateSection(); });
window.addEventListener("load", () => requestAnimationFrame(() => {
  revealIssue(location.hash);
  updateSection();
}));
updateIssues();
updateEvidence();
revealIssue(location.hash);
updateSection();

      let closedForPrint = null;
      window.addEventListener('beforeprint', () => {
        if (closedForPrint !== null) return;
        closedForPrint = Array.from(document.querySelectorAll('details.review-extra:not([open]), details.legal:not([open])'));
        closedForPrint.forEach(panel => { panel.open = true; });
      });
      window.addEventListener('afterprint', () => {
        (closedForPrint || []).forEach(panel => { panel.open = false; });
        closedForPrint = null;
      });
