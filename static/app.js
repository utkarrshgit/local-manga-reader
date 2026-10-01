/**
 * Local Manga Reader - Vanilla Frontend (Phase 2)
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const viewLibrary = document.getElementById("view-library");
  const viewChapters = document.getElementById("view-chapters");
  const viewPlaceholder = document.getElementById("view-placeholder");

  const seriesGrid = document.getElementById("series-grid");
  const libraryEmpty = document.getElementById("library-empty");
  const librarySubtitle = document.getElementById("library-subtitle");

  const chaptersList = document.getElementById("chapters-list");
  const chaptersEmpty = document.getElementById("chapters-empty");
  const seriesTitle = document.getElementById("series-title");
  const seriesMeta = document.getElementById("series-meta");

  const placeholderChapterTitle = document.getElementById("placeholder-chapter-title");
  const placeholderSeriesTitle = document.getElementById("placeholder-series-title");
  const placeholderPageCount = document.getElementById("placeholder-page-count");

  const breadcrumbs = document.getElementById("breadcrumbs");
  const statusBanner = document.getElementById("status-banner");
  const btnRefresh = document.getElementById("btn-refresh");
  const btnBackToLibrary = document.getElementById("btn-back-to-library");
  const btnBackToChapters = document.getElementById("btn-back-to-chapters");

  // State
  let currentSeries = null;
  let currentChapter = null;

  // Notification helper
  function showError(message) {
    statusBanner.textContent = message;
    statusBanner.className = "status-banner error";
    statusBanner.classList.remove("hidden");
  }

  function clearError() {
    statusBanner.textContent = "";
    statusBanner.classList.add("hidden");
  }

  // View switcher
  function switchView(viewName) {
    clearError();
    viewLibrary.classList.toggle("hidden", viewName !== "library");
    viewChapters.classList.toggle("hidden", viewName !== "chapters");
    viewPlaceholder.classList.toggle("hidden", viewName !== "placeholder");
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  // Breadcrumbs builder
  function updateBreadcrumbs(items) {
    breadcrumbs.innerHTML = "";
    items.forEach((item, index) => {
      if (index > 0) {
        const sep = document.createElement("span");
        sep.className = "separator";
        sep.textContent = "/";
        breadcrumbs.appendChild(sep);
      }

      if (item.href) {
        const link = document.createElement("a");
        link.href = item.href;
        link.textContent = item.label;
        breadcrumbs.appendChild(link);
      } else {
        const current = document.createElement("span");
        current.className = "crumb active";
        current.textContent = item.label;
        breadcrumbs.appendChild(current);
      }
    });
  }

  // 1. Load Library
  async function loadLibrary() {
    switchView("library");
    updateBreadcrumbs([{ label: "Library" }]);
    librarySubtitle.textContent = "Scanning local collection...";

    try {
      const res = await fetch("/api/series");
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();

      const series = data.series || [];
      seriesGrid.innerHTML = "";

      if (series.length === 0) {
        librarySubtitle.textContent = `Scanned ${data.library_path || "library"}`;
        libraryEmpty.classList.remove("hidden");
        return;
      }

      libraryEmpty.classList.add("hidden");
      librarySubtitle.textContent = `${series.length} series found in ${data.library_path}`;

      series.forEach((s) => {
        const card = document.createElement("div");
        card.className = "series-card";
        card.setAttribute("role", "button");
        card.setAttribute("tabindex", "0");

        card.innerHTML = `
          <div class="series-card-top">
            <div class="series-card-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
                <path d="M6 6h10"/>
                <path d="M6 10h10"/>
              </svg>
            </div>
            <div class="series-card-title">${escapeHtml(s.name)}</div>
          </div>
          <div class="series-card-footer">
            <span class="badge">${s.chapter_count} ${s.chapter_count === 1 ? "chapter" : "chapters"}</span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="chapter-arrow">
              <path d="M9 18l6-6-6-6"/>
            </svg>
          </div>
        `;

        card.addEventListener("click", () => {
          window.location.hash = `#/series/${encodeURIComponent(s.name)}`;
        });

        seriesGrid.appendChild(card);
      });
    } catch (err) {
      showError(`Failed to load library: ${err.message}`);
      librarySubtitle.textContent = "Could not connect to the backend server.";
    }
  }

  // 2. Load Chapters for Series
  async function loadChapters(seriesName) {
    currentSeries = seriesName;
    switchView("chapters");
    seriesTitle.textContent = seriesName;
    seriesMeta.textContent = "Loading chapters...";
    chaptersList.innerHTML = "";
    chaptersEmpty.classList.add("hidden");

    updateBreadcrumbs([
      { label: "Library", href: "#/" },
      { label: seriesName }
    ]);

    try {
      const res = await fetch(`/api/chapters?series=${encodeURIComponent(seriesName)}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();

      const chapters = data.chapters || [];
      chaptersList.innerHTML = "";

      if (chapters.length === 0) {
        seriesMeta.textContent = "0 chapters";
        chaptersEmpty.classList.remove("hidden");
        return;
      }

      seriesMeta.textContent = `${chapters.length} ${chapters.length === 1 ? "chapter" : "chapters"}`;

      chapters.forEach((ch) => {
        const item = document.createElement("div");
        item.className = "chapter-item";
        item.setAttribute("role", "button");
        item.setAttribute("tabindex", "0");

        item.innerHTML = `
          <div class="chapter-info">
            <svg class="chapter-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <span class="chapter-title">${escapeHtml(ch.name)}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <span class="badge">${ch.image_count} pages</span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="chapter-arrow">
              <path d="M9 18l6-6-6-6"/>
            </svg>
          </div>
        `;

        item.addEventListener("click", () => {
          window.location.hash = `#/read/${encodeURIComponent(seriesName)}/${encodeURIComponent(ch.name)}`;
        });

        chaptersList.appendChild(item);
      });
    } catch (err) {
      showError(`Failed to load chapters: ${err.message}`);
      seriesMeta.textContent = "Error loading chapters.";
    }
  }

  // 3. Load Placeholder Chapter Page
  async function loadPlaceholder(seriesName, chapterName) {
    currentSeries = seriesName;
    currentChapter = chapterName;
    switchView("placeholder");

    placeholderSeriesTitle.textContent = seriesName;
    placeholderChapterTitle.textContent = chapterName;
    placeholderPageCount.textContent = "Checking images...";

    updateBreadcrumbs([
      { label: "Library", href: "#/" },
      { label: seriesName, href: `#/series/${encodeURIComponent(seriesName)}` },
      { label: chapterName }
    ]);

    try {
      const res = await fetch(`/api/images?series=${encodeURIComponent(seriesName)}&chapter=${encodeURIComponent(chapterName)}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      const count = data.image_count || 0;
      placeholderPageCount.textContent = `${count} ${count === 1 ? "page" : "pages"} verified`;
    } catch (err) {
      showError(`Failed to verify chapter images: ${err.message}`);
      placeholderPageCount.textContent = "Could not load image count";
    }
  }

  // Simple HTML Escaping
  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>"']/g, (m) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    })[m]);
  }

  // Route Dispatcher
  function handleRoute() {
    const hash = window.location.hash || "#/";

    if (hash.startsWith("#/read/")) {
      const parts = hash.slice(7).split("/");
      const series = decodeURIComponent(parts[0] || "");
      const chapter = decodeURIComponent(parts[1] || "");
      if (series && chapter) {
        loadPlaceholder(series, chapter);
        return;
      }
    }

    if (hash.startsWith("#/series/")) {
      const series = decodeURIComponent(hash.slice(9));
      if (series) {
        loadChapters(series);
        return;
      }
    }

    // Default to Library
    loadLibrary();
  }

  // Event Listeners
  window.addEventListener("hashchange", handleRoute);

  btnRefresh.addEventListener("click", () => {
    handleRoute();
  });

  btnBackToLibrary.addEventListener("click", () => {
    window.location.hash = "#/";
  });

  btnBackToChapters.addEventListener("click", () => {
    if (currentSeries) {
      window.location.hash = `#/series/${encodeURIComponent(currentSeries)}`;
    } else {
      window.location.hash = "#/";
    }
  });

  // Initial load
  handleRoute();
});
