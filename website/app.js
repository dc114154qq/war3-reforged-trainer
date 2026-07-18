"use strict";

const state = {
  releases: [],
  query: "",
  sort: "newest",
};

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
};

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
  if (!Number.isFinite(value) || value <= 0) return "未知";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const amount = value / 1024 ** exponent;
  return `${amount.toFixed(exponent >= 2 ? 2 : 0)} ${units[exponent]}`;
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未知";
  return new Intl.DateTimeFormat("zh-CN", {
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
  return "查看该版本的完整更新、验证记录和兼容性说明。";
}

async function copyText(value, button) {
  try {
    await navigator.clipboard.writeText(value);
    const originalTitle = button.title;
    button.title = "已复制";
    button.classList.add("is-copied");
    setTimeout(() => {
      button.title = originalTitle;
      button.classList.remove("is-copied");
    }, 1400);
  } catch {
    button.title = "复制失败";
  }
}

function renderLatest(release) {
  elements.latestTitle.textContent = release.tag;
  elements.latestSummary.textContent = firstParagraph(release.body);
  elements.latestCompatibility.textContent = release.compatibility || "Warcraft III 2.0.4.23745";
  elements.latestSize.textContent = formatBytes(release.asset?.size);
  elements.latestDate.textContent = formatDate(release.published_at);
  elements.latestSha.textContent = release.asset?.sha256 || "未提供";
  elements.latestDownload.href = release.asset?.url || "#";
  elements.latestDownload.classList.remove("is-disabled");
  elements.latestDownload.removeAttribute("aria-disabled");
  elements.latestNotesLink.href = `#release-${release.tag.replace(/[^a-zA-Z0-9.-]/g, "-")}`;
  elements.latestCopy.disabled = !release.asset?.sha256;
  elements.latestCopy.addEventListener("click", () => copyText(release.asset.sha256, elements.latestCopy));
}

function createReleaseElement(release, index) {
  const fragment = elements.template.content.cloneNode(true);
  const article = fragment.querySelector(".release-item");
  const title = fragment.querySelector("h3");
  const badge = fragment.querySelector(".latest-badge");
  const download = fragment.querySelector(".release-download");
  const sha = release.asset?.sha256 || "未提供";

  article.id = `release-${release.tag.replace(/[^a-zA-Z0-9.-]/g, "-")}`;
  title.textContent = release.name && release.name !== release.tag ? `${release.tag} · ${release.name}` : release.tag;
  badge.hidden = index !== 0;
  fragment.querySelector(".release-date").textContent = `${formatDate(release.published_at)} 发布`;
  fragment.querySelector(".release-intro").textContent = firstParagraph(release.body);
  fragment.querySelector(".asset-name").textContent = release.asset?.name || "未提供";
  fragment.querySelector(".asset-size").textContent = formatBytes(release.asset?.size);
  fragment.querySelector(".asset-sha").textContent = sha;
  fragment.querySelector(".markdown-body").innerHTML = markdownToHtml(release.body);
  download.href = release.asset?.url || "#";
  if (!release.asset?.url) {
    download.setAttribute("aria-disabled", "true");
  }

  const copyButton = fragment.querySelector(".asset-copy");
  copyButton.disabled = !release.asset?.sha256;
  copyButton.addEventListener("click", () => copyText(sha, copyButton));
  return fragment;
}

function filteredReleases() {
  const query = state.query.trim().toLocaleLowerCase("zh-CN");
  const matches = query
    ? state.releases.filter((release) =>
        [release.tag, release.name, release.body, release.asset?.name]
          .filter(Boolean)
          .some((value) => String(value).toLocaleLowerCase("zh-CN").includes(query)),
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
  elements.count.textContent = `共 ${releases.length} 个版本`;
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
    renderLatest(state.releases[0]);
    renderList();
    elements.syncTime.textContent = data.generated_at ? `版本索引更新于 ${formatDate(data.generated_at)}` : "";
  } catch (error) {
    elements.list.replaceChildren();
    elements.error.hidden = false;
    elements.count.textContent = "";
    elements.latestTitle.textContent = "版本索引不可用";
    elements.latestSummary.textContent = "服务器未能返回版本数据。";
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

loadReleases();
