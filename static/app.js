/**
 * Local Manga Reader - Vanilla Frontend (Phase 3)
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements - Views
  const viewLibrary = document.getElementById("view-library");
  const viewChapters = document.getElementById("view-chapters");
  const viewReader = document.getElementById("view-reader");

  // DOM Elements - Library
  const seriesGrid = document.getElementById("series-grid");
  const libraryEmpty = document.getElementById("library-empty");
  const librarySubtitle = document.getElementById("library-subtitle");

  // DOM Elements - Chapters
  const chaptersList = document.getElementById("chapters-list");
  const chaptersEmpty = document.getElementById("chapters-empty");
  const seriesTitle = document.getElementById("series-title");
  const seriesMeta = document.getElementById("series-meta");

  // DOM Elements - Reader
  const readerSeriesName = document.getElementById("reader-series-name");
  const readerChapterName = document.getElementById("reader-chapter-name");
  const readerContainer = document.getElementById("reader-container");
  const readerLoading = document.getElementById("reader-loading");
  const readerFooter = document.getElementById("reader-footer");
  const btnReaderBack = document.getElementById("btn-reader-back");
  const btnReaderBottomBack = document.getElementById("btn-reader-bottom-back");
  const btnStyleSpaced = document.getElementById("btn-style-spaced");
  const btnStyleSeamless = document.getElementById("btn-style-seamless");

  // DOM Elements - Header & Navigation
  const breadcrumbs = document.getElementById("breadcrumbs");
  const statusBanner = document.getElementById("status-banner");
  const btnRefresh = document.getElementById("btn-refresh");
  const btnBackToLibrary = document.getElementById("btn-back-to-library");

  // State
  let currentSeries = null;
  let currentChapter = null;
  // Persist reading style across chapters within the current session
  let currentReadingStyle = sessionStorage.getItem("manga_reader_style") || "spaced";

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
    viewReader.classList.toggle("hidden", viewName !== "reader");
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  // Reading Style Manager
  function applyReadingStyle(style) {
    currentReadingStyle = style;
    sessionStorage.setItem("manga_reader_style", style);

    if (style === "seamless") {
      readerContainer.classList.remove("mode-spaced");
      readerContainer.classList.add("mode-seamless");
      btnStyleSeamless.classList.add("active");
      btnStyleSpaced.classList.remove("active");
    } else {
      readerContainer.classList.remove("mode-seamless");
      readerContainer.classList.add("mode-spaced");
      btnStyleSpaced.classList.add("active");
      btnStyleSeamless.classList.remove("active");
    }
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

  // 1. Load Library View
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

  // 2. Load Chapters View
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

  // 3. Load Real Vertical Scroll Reader View (Phase 3)
  async function loadReader(seriesName, chapterName) {
    currentSeries = seriesName;
    currentChapter = chapterName;
    switchView("reader");

    readerSeriesName.textContent = seriesName;
    readerChapterName.textContent = chapterName;
    readerContainer.innerHTML = "";
    readerFooter.classList.add("hidden");
    readerLoading.classList.remove("hidden");

    // Apply stored reading style (Spaced vs Seamless)
    applyReadingStyle(currentReadingStyle);

    updateBreadcrumbs([
      { label: "Library", href: "#/" },
      { label: seriesName, href: `#/series/${encodeURIComponent(seriesName)}` },
      { label: chapterName }
    ]);

    try {
      const res = await fetch(`/api/images?series=${encodeURIComponent(seriesName)}&chapter=${encodeURIComponent(chapterName)}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();

      const images = data.images || [];
      readerLoading.classList.add("hidden");

      if (images.length === 0) {
        showError("No images found in this chapter.");
        return;
      }

      // Render images vertically in natural order
      images.forEach((img) => {
        const pageDiv = document.createElement("div");
        pageDiv.className = "reader-page";
        // Identified by filename in DOM for Phase 4 progress tracking
        pageDiv.id = `page-${img.filename}`;
        pageDiv.dataset.filename = img.filename;

        const imgEl = document.createElement("img");
        imgEl.className = "reader-image";
        imgEl.src = img.url;
        imgEl.alt = img.filename;
        imgEl.dataset.filename = img.filename;
        imgEl.loading = "lazy";
        imgEl.decoding = "async";

        pageDiv.appendChild(imgEl);
        readerContainer.appendChild(pageDiv);
      });

      readerFooter.classList.remove("hidden");
    } catch (err) {
      readerLoading.classList.add("hidden");
      showError(`Failed to load chapter images: ${err.message}`);
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
        loadReader(series, chapter);
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

  // Reader Back Buttons
  function navigateBackToChapters() {
    if (currentSeries) {
      window.location.hash = `#/series/${encodeURIComponent(currentSeries)}`;
    } else {
      window.location.hash = "#/";
    }
  }

  btnReaderBack.addEventListener("click", navigateBackToChapters);
  btnReaderBottomBack.addEventListener("click", navigateBackToChapters);

  // Style Toggle Buttons (Spaced vs Seamless)
  btnStyleSpaced.addEventListener("click", () => {
    applyReadingStyle("spaced");
  });

  btnStyleSeamless.addEventListener("click", () => {
    applyReadingStyle("seamless");
  });

  // Initial load
  handleRoute();
});
