"use strict";

const state = {
  releases: [],
  query: "",
  sort: "newest",
  language: "zh",
  manualLanguage: false,
  generatedAt: "",
};

const i18n = window.SITE_I18N || { zh: {}, en: {}, releaseNames: {}, releaseBodies: {} };
const LANGUAGE_STORAGE_KEY = "war3-site-language";
const CHINESE_COUNTRIES = new Set(["CN", "HK", "MO", "TW"]);

const elements = {
  list: document.querySelector("#release-list"),
  template: document.querySelector("#release-template"),
  empty: document.querySelector("#empty-state"),
  error: document.querySelector("#error-state"),
  count: document.querySelector("#release-count"),
  search: document.querySelector("#release-search"),
  sort: document.querySelector("#release-sort"),
  latestTitle: document.querySelector("#latest-title"),
  latestSummary: document.querySelector("#latest-summary"),
  latestDownload: document.querySelector("#latest-download"),
  latestNotesLink: document.querySelector("#latest-notes-link"),
  latestCompatibility: document.querySelector("#latest-compatibility"),
  latestSize: document.querySelector("#latest-size"),
  latestDate: document.querySelector("#latest-date"),
  latestSha: document.querySelector("#latest-sha"),
  latestCopy: document.querySelector("#copy-latest-sha"),
  syncTime: document.querySelector("#sync-time"),
  languageToggle: document.querySelector("#language-toggle"),
  siteTitle: document.querySelector("#site-title"),
  siteDescription: document.querySelector("#site-description"),
};

function t(key, values = {}) {
  const dictionary = i18n[state.language] || i18n.zh;
  let value = dictionary[key] ?? i18n.zh[key] ?? key;
  Object.entries(values).forEach(([name, replacement]) => {
    value = value.replaceAll(`{${name}}`, String(replacement));
  });
  return value;
}

function localizedReleaseBody(release) {
  return i18n.releaseBodies?.[state.language]?.[release.tag] || release.body || "";
}

function localizedReleaseName(release) {
  return i18n.releaseNames?.[state.language]?.[release.tag]
    || release.name
    || release.tag;
}

function localizeRoot(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  });
  root.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.title = t(element.dataset.i18nTitle);
  });
  root.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
}

function readStoredLanguage() {
  try {
    const value = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return value === "zh" || value === "en" ? value : "";
  } catch {
    return "";
  }
}

function browserLanguage() {
  const languages = navigator.languages?.length ? navigator.languages : [navigator.language];
  return languages.some((value) => String(value).toLowerCase().startsWith("zh")) ? "zh" : "en";
}

function countryLanguage(country) {
  return CHINESE_COUNTRIES.has(String(country || "").toUpperCase()) ? "zh" : "en";
}

function saveLanguage(language) {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Private browsing can disable localStorage; the current page still switches.
  }
}

function applyLanguage(language, { manual = false } = {}) {
  state.language = language === "en" ? "en" : "zh";
  if (manual) {
    state.manualLanguage = true;
    saveLanguage(state.language);
  }
  document.documentElement.lang = state.language === "en" ? "en" : "zh-CN";
  document.title = t("siteTitle");
  elements.siteTitle?.setAttribute("data-i18n", "siteTitle");
  if (elements.siteDescription) elements.siteDescription.content = t("siteDescription");
  localizeRoot(document);
  if (elements.languageToggle) {
    elements.languageToggle.setAttribute("aria-label", t("languageToggleTitle"));
    elements.languageToggle.title = t("languageToggleTitle");
    const targetLanguage = state.language === "zh" ? "en" : "zh";
    const languageUrl = new URL(window.location.href);
    languageUrl.searchParams.set("lang", targetLanguage);
    languageUrl.hash = "";
    elements.languageToggle.href = `${languageUrl.pathname}${languageUrl.search}`;
  }
  if (state.releases.length) {
    renderLatest(state.releases[0]);
    renderList();
    elements.syncTime.textContent = state.generatedAt
      ? t("indexUpdated", { date: formatDate(state.generatedAt) })
      : "";
  }
}

async function detectCountryLanguage() {
  if (state.manualLanguage) return;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1800);
  try {
    const response = await fetch("https://api.country.is/", {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!state.manualLanguage && data.country) applyLanguage(countryLanguage(data.country));
  } catch {
    // The browser locale is already applied; language detection is best-effort.
  } finally {
    clearTimeout(timeout);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderInline(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function markdownToHtml(markdown) {
  const lines = String(markdown ?? "").replaceAll("\r\n", "\n").split("\n");
  const output = [];
  let paragraph = [];
  let listOpen = false;
  let codeOpen = false;
  let codeLines = [];

  const closeParagraph = () => {
    if (paragraph.length) {
      output.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
      paragraph = [];
    }
  };
  const closeList = () => {
    if (listOpen) {
      output.push("</ul>");
      listOpen = false;
    }
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      closeParagraph();
      closeList();
      if (codeOpen) {
        output.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        codeLines = [];
      }
      codeOpen = !codeOpen;
      continue;
    }
    if (codeOpen) {
      codeLines.push(line);
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    const listItem = line.match(/^\s*[-*]\s+(.+)$/);
    if (heading) {
      closeParagraph();
      closeList();
      const level = heading[1].length;
      output.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
    } else if (listItem) {
      closeParagraph();
      if (!listOpen) {
        output.push("<ul>");
        listOpen = true;
      }
      output.push(`<li>${renderInline(listItem[1])}</li>`);
    } else if (!line.trim()) {
      closeParagraph();
      closeList();
    } else {
      closeList();
      paragraph.push(line.trim());
    }
  }

  closeParagraph();
  closeList();
  if (codeOpen && codeLines.length) {
    output.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
  }
  return output.join("");
}

function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value <= 0) return t("unknown");
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const amount = value / 1024 ** exponent;
  return `${amount.toFixed(exponent >= 2 ? 2 : 0)} ${units[exponent]}`;
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t("unknown");
  return new Intl.DateTimeFormat(state.language === "en" ? "en-US" : "zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date);
}

function firstParagraph(body) {
  const lines = String(body ?? "").replaceAll("\r\n", "\n").split("\n");
  for (const line of lines) {
    const text = line.trim();
    if (!text || text.startsWith("#") || text.startsWith("-") || text.startsWith("```")) continue;
    return text.replaceAll("`", "").replaceAll("**", "");
  }
  return state.language === "en"
    ? "See the complete release notes, verification details and compatibility information."
    : "查看该版本的完整更新、验证记录和兼容性说明。";
}

async function copyText(value, button) {
  try {
    await navigator.clipboard.writeText(value);
    const originalTitle = button.title;
    button.title = t("copied");
    button.classList.add("is-copied");
    setTimeout(() => {
      button.title = originalTitle;
      button.classList.remove("is-copied");
    }, 1400);
  } catch {
    button.title = t("copyFailed");
  }
}

function renderLatest(release) {
  elements.latestTitle.textContent = release.tag;
  elements.latestSummary.textContent = firstParagraph(localizedReleaseBody(release));
  elements.latestCompatibility.textContent = release.compatibility || "Warcraft III 2.0.4.23745";
  elements.latestSize.textContent = formatBytes(release.asset?.size);
  elements.latestDate.textContent = formatDate(release.published_at);
  elements.latestSha.textContent = release.asset?.sha256 || t("noAsset");
  elements.latestDownload.href = release.asset?.url || "#";
  elements.latestDownload.classList.remove("is-disabled");
  elements.latestDownload.removeAttribute("aria-disabled");
  elements.latestNotesLink.href = `#release-${release.tag.replace(/[^a-zA-Z0-9.-]/g, "-")}`;
  elements.latestCopy.disabled = !release.asset?.sha256;
  elements.latestCopy.onclick = () => copyText(release.asset.sha256, elements.latestCopy);
}

function createReleaseElement(release, index) {
  const fragment = elements.template.content.cloneNode(true);
  const article = fragment.querySelector(".release-item");
  const title = fragment.querySelector("h3");
  const badge = fragment.querySelector(".latest-badge");
  const download = fragment.querySelector(".release-download");
  const sha = release.asset?.sha256 || t("noAsset");

  article.id = `release-${release.tag.replace(/[^a-zA-Z0-9.-]/g, "-")}`;
  const releaseName = localizedReleaseName(release);
  title.textContent = releaseName !== release.tag ? `${release.tag} · ${releaseName}` : release.tag;
  badge.hidden = index !== 0;
  fragment.querySelector(".release-date").textContent = `${formatDate(release.published_at)} ${t("published")}`;
  fragment.querySelector(".release-intro").textContent = firstParagraph(localizedReleaseBody(release));
  fragment.querySelector(".asset-name").textContent = release.asset?.name || t("noAsset");
  fragment.querySelector(".asset-size").textContent = formatBytes(release.asset?.size);
  fragment.querySelector(".asset-sha").textContent = sha;
  fragment.querySelector(".markdown-body").innerHTML = markdownToHtml(localizedReleaseBody(release));
  download.href = release.asset?.url || "#";
  if (!release.asset?.url) {
    download.setAttribute("aria-disabled", "true");
  }

  const copyButton = fragment.querySelector(".asset-copy");
  localizeRoot(fragment);
  copyButton.disabled = !release.asset?.sha256;
  copyButton.addEventListener("click", () => copyText(sha, copyButton));
  return fragment;
}

function filteredReleases() {
  const query = state.query.trim().toLocaleLowerCase(state.language === "en" ? "en-US" : "zh-CN");
  const matches = query
    ? state.releases.filter((release) =>
        [release.tag, localizedReleaseName(release), localizedReleaseBody(release), release.name, release.body, release.asset?.name]
          .filter(Boolean)
          .some((value) => String(value).toLocaleLowerCase(state.language === "en" ? "en-US" : "zh-CN").includes(query)),
      )
    : [...state.releases];
  return matches.sort((a, b) => {
    const difference = new Date(b.published_at) - new Date(a.published_at);
    return state.sort === "oldest" ? -difference : difference;
  });
}

function renderList() {
  const releases = filteredReleases();
  elements.list.replaceChildren();
  elements.empty.hidden = releases.length !== 0;
  elements.count.textContent = t("releaseCount", { count: releases.length });
  releases.forEach((release) => elements.list.append(createReleaseElement(release, state.releases.indexOf(release))));
  if (window.lucide) window.lucide.createIcons();
}

async function loadReleases() {
  try {
    const response = await fetch("releases.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.releases) || data.releases.length === 0) throw new Error("empty release index");
    state.releases = data.releases.sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
    state.generatedAt = data.generated_at || "";
    renderLatest(state.releases[0]);
    renderList();
    elements.syncTime.textContent = data.generated_at ? t("indexUpdated", { date: formatDate(data.generated_at) }) : "";
  } catch (error) {
    elements.list.replaceChildren();
    elements.error.hidden = false;
    elements.count.textContent = "";
    elements.latestTitle.textContent = t("indexErrorTitle");
    elements.latestSummary.textContent = t("indexErrorBody");
    console.error(error);
  }
}

elements.search.addEventListener("input", (event) => {
  state.query = event.target.value;
  renderList();
});

elements.sort.addEventListener("change", (event) => {
  state.sort = event.target.value;
  renderList();
});

window.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) window.lucide.createIcons();
});

const queryLanguage = new URLSearchParams(window.location.search).get("lang");
const storedLanguage = readStoredLanguage();
if (queryLanguage === "zh" || queryLanguage === "en") {
  applyLanguage(queryLanguage, { manual: true });
} else if (storedLanguage) {
  state.manualLanguage = true;
  applyLanguage(storedLanguage);
} else {
  applyLanguage(browserLanguage());
  detectCountryLanguage();
}

loadReleases();
