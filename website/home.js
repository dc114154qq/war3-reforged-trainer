"use strict";

const i18n = window.SITE_I18N || { zh: {}, en: {} };
const LANGUAGE_STORAGE_KEY = "war3-site-language";
const CHINESE_COUNTRIES = new Set(["CN", "HK", "MO", "TW"]);
let language = "zh";
let manualLanguage = false;

function t(key) {
  return i18n[language]?.[key] ?? i18n.zh?.[key] ?? key;
}

function localizeRoot() {
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.title = t(element.dataset.i18nTitle);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
}

function storedLanguage() {
  try {
    const value = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return value === "zh" || value === "en" ? value : "";
  } catch {
    return "";
  }
}

function applyLanguage(nextLanguage, { manual = false } = {}) {
  language = nextLanguage === "en" ? "en" : "zh";
  if (manual) {
    manualLanguage = true;
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    } catch {
      // The current page can still switch when storage is unavailable.
    }
  }
  document.documentElement.lang = language === "en" ? "en" : "zh-CN";
  document.title = t("homeSiteTitle");
  const description = document.querySelector("#site-description");
  if (description) description.content = t("homeSiteDescription");
  localizeRoot();

  const toggle = document.querySelector("#language-toggle");
  if (toggle) {
    const target = language === "zh" ? "en" : "zh";
    const url = new URL(window.location.href);
    url.searchParams.set("lang", target);
    url.hash = "";
    toggle.href = `${url.pathname}${url.search}`;
    toggle.title = t("languageToggleTitle");
    toggle.setAttribute("aria-label", t("languageToggleTitle"));
  }
}

async function detectCountryLanguage() {
  if (manualLanguage) return;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1800);
  try {
    const response = await fetch("https://api.country.is/", {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!manualLanguage && data.country) {
      applyLanguage(CHINESE_COUNTRIES.has(String(data.country).toUpperCase()) ? "zh" : "en");
    }
  } catch {
    // Browser language remains the fallback.
  } finally {
    clearTimeout(timeout);
  }
}

document.querySelector("#language-toggle")?.addEventListener("click", (event) => {
  event.preventDefault();
  applyLanguage(language === "zh" ? "en" : "zh", { manual: true });
});

const queryLanguage = new URLSearchParams(window.location.search).get("lang");
const savedLanguage = storedLanguage();
if (queryLanguage === "zh" || queryLanguage === "en") {
  applyLanguage(queryLanguage, { manual: true });
} else if (savedLanguage) {
  manualLanguage = true;
  applyLanguage(savedLanguage);
} else {
  const languages = navigator.languages?.length ? navigator.languages : [navigator.language];
  applyLanguage(languages.some((value) => String(value).toLowerCase().startsWith("zh")) ? "zh" : "en");
  detectCountryLanguage();
}

window.addEventListener("DOMContentLoaded", () => window.lucide?.createIcons());
