/**
 * Local Manga Reader - Vanilla Frontend (Phase 5: Safari Polish & UX)
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
  const readerEmpty = document.getElementById("reader-empty");
  const readerFooter = document.getElementById("reader-footer");
  const btnReaderBack = document.getElementById("btn-reader-back");
  const btnReaderBottomBack = document.getElementById("btn-reader-bottom-back");
  const btnReaderBookmark = document.getElementById("btn-reader-bookmark");
  const btnReaderFullscreen = document.getElementById("btn-reader-fullscreen");
  const btnReaderPrev = document.getElementById("btn-reader-prev");
  const btnReaderNext = document.getElementById("btn-reader-next");
  const btnReaderFooterPrev = document.getElementById("btn-reader-footer-prev");
  const btnReaderFooterNext = document.getElementById("btn-reader-footer-next");
  const btnStyleSpaced = document.getElementById("btn-style-spaced");
  const btnStyleSeamless = document.getElementById("btn-style-seamless");

  // Fullscreen icons
  const iconFullscreenEnter = btnReaderFullscreen ? btnReaderFullscreen.querySelector(".icon-fullscreen-enter") : null;
  const iconFullscreenExit = btnReaderFullscreen ? btnReaderFullscreen.querySelector(".icon-fullscreen-exit") : null;

  // DOM Elements - Header & Navigation
  const breadcrumbs = document.getElementById("breadcrumbs");
  const statusBanner = document.getElementById("status-banner");
  const btnRefresh = document.getElementById("btn-refresh");
  const btnBackToLibrary = document.getElementById("btn-back-to-library");

  // State
  let currentSeries = null;
  let currentChapter = null;
  let currentSeriesBookmarks = new Set();
  let currentSeriesProgress = {};
  let currentPrevChapter = null;
  let currentNextChapter = null;

  // Reading progress observer state
  let readerObserver = null;
  let currentVisibleImage = null;
  let saveProgressTimeout = null;
  let isInitialResume = false;

  // Reading style preference (defaults to spaced)
  let currentReadingStyle = "spaced";

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
    document.body.classList.toggle("reader-active", viewName === "reader");
    viewLibrary.classList.toggle("hidden", viewName !== "library");
    viewChapters.classList.toggle("hidden", viewName !== "chapters");
    viewReader.classList.toggle("hidden", viewName !== "reader");

    if (viewName !== "reader") {
      readerLoading.classList.add("hidden");
      if (readerEmpty) readerEmpty.classList.add("hidden");
      if (readerObserver) {
        readerObserver.disconnect();
        readerObserver = null;
      }
      if (saveProgressTimeout) {
        clearTimeout(saveProgressTimeout);
        saveProgressTimeout = null;
      }
      currentPrevChapter = null;
      currentNextChapter = null;
    }
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  // Reading Style Manager (per-series preference persisted to .reader/reader_data.json)
  function applyReadingStyle(style, persist = false) {
    currentReadingStyle = style === "seamless" ? "seamless" : "spaced";

    if (currentReadingStyle === "seamless") {
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

    if (persist && currentSeries) {
      fetch("/api/style", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          series: currentSeries,
          style: currentReadingStyle
        })
      }).catch((err) => {
        console.warn("Failed to persist reader style preference:", err);
      });
    }
  }

  // Fullscreen Helper Functions
  function isFullscreenActive() {
    return !!(
      document.fullscreenElement ||
      document.webkitFullscreenElement ||
      document.mozFullScreenElement ||
      document.msFullscreenElement
    );
  }

  function updateFullscreenUI() {
    if (!btnReaderFullscreen) return;
    const active = isFullscreenActive();
    document.body.classList.toggle("in-fullscreen", active);
    if (iconFullscreenEnter && iconFullscreenExit) {
      iconFullscreenEnter.classList.toggle("hidden", active);
      iconFullscreenExit.classList.toggle("hidden", !active);
    }
    btnReaderFullscreen.title = active ? "Exit fullscreen (F)" : "Toggle fullscreen (F)";
    btnReaderFullscreen.setAttribute("aria-label", active ? "Exit fullscreen" : "Toggle fullscreen");
  }

  function toggleFullscreen() {
    const doc = document;
    const docEl = document.documentElement;

    if (!isFullscreenActive()) {
      if (docEl.requestFullscreen) {
        docEl.requestFullscreen().catch(() => {});
      } else if (docEl.webkitRequestFullscreen) {
        docEl.webkitRequestFullscreen();
      } else if (docEl.mozRequestFullScreen) {
        docEl.mozRequestFullScreen();
      } else if (docEl.msRequestFullscreen) {
        docEl.msRequestFullscreen();
      }
    } else {
      if (doc.exitFullscreen) {
        doc.exitFullscreen().catch(() => {});
      } else if (doc.webkitExitFullscreen) {
        doc.webkitExitFullscreen();
      } else if (doc.mozCancelFullScreen) {
        doc.mozCancelFullScreen();
      } else if (doc.msExitFullscreen) {
        doc.msExitFullscreen();
      }
    }
  }

  // Check if Fullscreen is supported
  const isFullscreenSupported = !!(
    document.fullscreenEnabled ||
    document.webkitFullscreenEnabled ||
    document.documentElement.requestFullscreen ||
    document.documentElement.webkitRequestFullscreen
  );

  if (btnReaderFullscreen) {
    if (!isFullscreenSupported) {
      btnReaderFullscreen.classList.add("hidden");
    } else {
      btnReaderFullscreen.addEventListener("click", toggleFullscreen);
      document.addEventListener("fullscreenchange", updateFullscreenUI);
      document.addEventListener("webkitfullscreenchange", updateFullscreenUI);
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

  // API Helper: Fetch Reader Data (Bookmarks & Progress)
  async function fetchReaderData(seriesName) {
    try {
      const res = await fetch(`/api/reader-data?series=${encodeURIComponent(seriesName)}`);
      if (!res.ok) return { progress: {}, bookmarks: [] };
      return await res.json();
    } catch {
      return { progress: {}, bookmarks: [] };
    }
  }

  // API Helper: Toggle Bookmark
  async function toggleBookmark(seriesName, chapterName, shouldBookmark = null) {
    try {
      const res = await fetch("/api/bookmark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          series: seriesName,
          chapter: chapterName,
          bookmarked: shouldBookmark
        })
      });
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      currentSeriesBookmarks = new Set(data.bookmarks || []);
      return data;
    } catch (err) {
      showError(`Failed to update bookmark: ${err.message}`);
      return null;
    }
  }

  // Update Reader Bookmark Button in Header
  function updateReaderBookmarkButton(chapterName) {
    const isBookmarked = currentSeriesBookmarks.has(chapterName);
    btnReaderBookmark.classList.toggle("bookmarked", isBookmarked);
    btnReaderBookmark.title = isBookmarked ? "Remove bookmark (B)" : "Bookmark this chapter (B)";
    btnReaderBookmark.setAttribute("aria-label", isBookmarked ? "Remove bookmark" : "Bookmark this chapter");
  }

  // Update Previous / Next Chapter Buttons State
  function updateChapterNavButtons() {
    const hasPrev = !!currentPrevChapter;
    const hasNext = !!currentNextChapter;

    if (btnReaderPrev) {
      btnReaderPrev.disabled = !hasPrev;
      btnReaderPrev.title = hasPrev ? `Previous: ${currentPrevChapter} (←)` : "No previous chapter";
    }
    if (btnReaderFooterPrev) {
      btnReaderFooterPrev.disabled = !hasPrev;
    }

    if (btnReaderNext) {
      btnReaderNext.disabled = !hasNext;
      btnReaderNext.title = hasNext ? `Next: ${currentNextChapter} (→)` : "No next chapter";
    }
    if (btnReaderFooterNext) {
      btnReaderFooterNext.disabled = !hasNext;
    }
  }

  // Navigate to Chapter Helper
  function navigateToChapter(chapter) {
    if (currentSeries && chapter) {
      window.location.hash = `#/read/${encodeURIComponent(currentSeries)}/${encodeURIComponent(chapter)}`;
    }
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

        const coverHtml = s.has_cover && s.cover_url
          ? `<div class="series-cover-wrapper">
               <img class="series-cover-img" src="${s.cover_url}" alt="${escapeHtml(s.name)} cover" loading="lazy" />
             </div>`
          : `<div class="series-cover-wrapper series-cover-placeholder">
               <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                 <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
                 <path d="M6 6h10"/>
                 <path d="M6 10h10"/>
               </svg>
             </div>`;

        card.innerHTML = `
          ${coverHtml}
          <div class="series-card-content">
            <div class="series-card-title" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</div>
            <div class="series-card-footer">
              <span class="badge">${s.chapter_count} ${s.chapter_count === 1 ? "chapter" : "chapters"}</span>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="chapter-arrow">
                <path d="M9 18l6-6-6-6"/>
              </svg>
            </div>
          </div>
        `;

        // Handle image loading errors gracefully without broken image icon
        const coverImg = card.querySelector(".series-cover-img");
        if (coverImg) {
          coverImg.addEventListener("error", () => {
            const wrapper = card.querySelector(".series-cover-wrapper");
            if (wrapper) {
              wrapper.className = "series-cover-wrapper series-cover-placeholder";
              wrapper.innerHTML = `
                <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
                  <path d="M6 6h10"/>
                  <path d="M6 10h10"/>
                </svg>
              `;
            }
          });
        }

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

  // 2. Load Chapters View (shows Bookmarks and Reading Progress)
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
      const [chaptersRes, readerData] = await Promise.all([
        fetch(`/api/chapters?series=${encodeURIComponent(seriesName)}`),
        fetchReaderData(seriesName)
      ]);

      if (!chaptersRes.ok) throw new Error(`HTTP error ${chaptersRes.status}`);
      const data = await chaptersRes.json();

      currentSeriesBookmarks = new Set(readerData.bookmarks || []);
      currentSeriesProgress = readerData.progress || {};

      const chapters = data.chapters || [];
      chaptersList.innerHTML = "";

      if (chapters.length === 0) {
        seriesMeta.textContent = "0 chapters";
        chaptersEmpty.classList.remove("hidden");
        return;
      }

      const bookmarkCount = currentSeriesBookmarks.size;
      const countText = `${chapters.length} ${chapters.length === 1 ? "chapter" : "chapters"}`;
      seriesMeta.textContent = bookmarkCount > 0 ? `${countText} • ${bookmarkCount} bookmarked` : countText;

      chapters.forEach((ch) => {
        const item = document.createElement("div");
        item.className = "chapter-item";
        item.setAttribute("role", "button");
        item.setAttribute("tabindex", "0");

        const isBookmarked = currentSeriesBookmarks.has(ch.name);

        item.innerHTML = `
          <div class="chapter-info">
            <button class="btn-chapter-bookmark ${isBookmarked ? "bookmarked" : ""}" title="${isBookmarked ? "Remove bookmark" : "Bookmark chapter"}" aria-label="Bookmark">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
              </svg>
            </button>
            <span class="chapter-title">${escapeHtml(ch.name)}</span>
            ${isBookmarked ? `<span class="badge badge-bookmark"><svg viewBox="0 0 24 24"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>Bookmarked</span>` : ""}
          </div>
          <div class="chapter-actions">
            <span class="badge">${ch.image_count} pages</span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="chapter-arrow">
              <path d="M9 18l6-6-6-6"/>
            </svg>
          </div>
        `;

        // Bookmark button click
        const bookmarkBtn = item.querySelector(".btn-chapter-bookmark");
        bookmarkBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          const willBookmark = !currentSeriesBookmarks.has(ch.name);
          const result = await toggleBookmark(seriesName, ch.name, willBookmark);
          if (result) {
            loadChapters(seriesName);
          }
        });

        // Row click navigates to chapter reader
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

  // 3. Load Real Vertical Scroll Reader View with Reading Progress, Bookmark & Navigation
  async function loadReader(seriesName, chapterName) {
    currentSeries = seriesName;
    currentChapter = chapterName;
    switchView("reader");

    readerSeriesName.textContent = seriesName;
    readerChapterName.textContent = chapterName;
    readerContainer.innerHTML = "";
    readerFooter.classList.add("hidden");
    if (readerEmpty) readerEmpty.classList.add("hidden");
    readerLoading.classList.remove("hidden");

    // Clear previous observer and pending saves
    if (readerObserver) {
      readerObserver.disconnect();
      readerObserver = null;
    }
    if (saveProgressTimeout) {
      clearTimeout(saveProgressTimeout);
      saveProgressTimeout = null;
    }
    currentVisibleImage = null;

    updateBreadcrumbs([
      { label: "Library", href: "#/" },
      { label: seriesName, href: `#/series/${encodeURIComponent(seriesName)}` },
      { label: chapterName }
    ]);

    try {
      const [imagesRes, readerData, chaptersData] = await Promise.all([
        fetch(`/api/images?series=${encodeURIComponent(seriesName)}&chapter=${encodeURIComponent(chapterName)}`),
        fetchReaderData(seriesName),
        fetch(`/api/chapters?series=${encodeURIComponent(seriesName)}`).then((r) => (r.ok ? r.json() : { chapters: [] })).catch(() => ({ chapters: [] }))
      ]);

      if (!imagesRes.ok) throw new Error(`HTTP error ${imagesRes.status}`);
      const data = await imagesRes.json();

      currentSeriesBookmarks = new Set(readerData.bookmarks || []);
      currentSeriesProgress = readerData.progress || {};

      // Apply saved series reading style preference (defaults to spaced)
      const savedStyle = (readerData.reader && (readerData.reader.style === "seamless" || readerData.reader.style === "spaced"))
        ? readerData.reader.style
        : "spaced";
      applyReadingStyle(savedStyle, false);

      // Determine Previous & Next Chapters from natural ordering
      const chapterList = (chaptersData.chapters || []).map((c) => c.name);
      const currentIndex = chapterList.indexOf(chapterName);
      currentPrevChapter = currentIndex > 0 ? chapterList[currentIndex - 1] : null;
      currentNextChapter = currentIndex >= 0 && currentIndex < chapterList.length - 1 ? chapterList[currentIndex + 1] : null;

      updateChapterNavButtons();
      updateReaderBookmarkButton(chapterName);

      const images = data.images || [];

      // Loading completed: hide loading spinner
      readerLoading.classList.add("hidden");

      if (images.length === 0) {
        if (readerEmpty) readerEmpty.classList.remove("hidden");
        showError("No images found in this chapter.");
        return;
      }

      if (readerEmpty) readerEmpty.classList.add("hidden");

      // Render images vertically in natural order
      images.forEach((img) => {
        const pageDiv = document.createElement("div");
        pageDiv.className = "reader-page";
        // Identified by filename in DOM for progress tracking
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

      // Resume reading progress
      const savedImage = currentSeriesProgress[chapterName];
      let targetPage = null;
      if (savedImage) {
        targetPage = document.getElementById(`page-${savedImage}`);
      }

      if (targetPage) {
        currentVisibleImage = savedImage;
        isInitialResume = true;
        targetPage.scrollIntoView({ behavior: "instant", block: "start" });
        setTimeout(() => {
          isInitialResume = false;
        }, 300);
      } else {
        currentVisibleImage = images[0] ? images[0].filename : null;
        isInitialResume = false;
      }

      // Track reading progress with IntersectionObserver
      const pageElements = readerContainer.querySelectorAll(".reader-page");
      const visiblePages = new Map();

      readerObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            visiblePages.set(entry.target, entry.boundingClientRect.top);
          } else {
            visiblePages.delete(entry.target);
          }
        });

        if (isInitialResume || visiblePages.size === 0) return;

        // Choose page currently closest to upper reading line
        let bestPage = null;
        let bestTop = -Infinity;

        for (const [pageEl, top] of visiblePages.entries()) {
          if (top <= window.innerHeight * 0.6) {
            if (top > bestTop) {
              bestTop = top;
              bestPage = pageEl;
            }
          }
        }

        if (!bestPage) {
          bestPage = visiblePages.keys().next().value;
        }

        if (bestPage) {
          const filename = bestPage.dataset.filename;
          if (filename && filename !== currentVisibleImage) {
            currentVisibleImage = filename;

            // Debounced save (~750ms after scrolling settles)
            clearTimeout(saveProgressTimeout);
            saveProgressTimeout = setTimeout(() => {
              fetch("/api/progress", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  series: seriesName,
                  chapter: chapterName,
                  image: filename
                })
              }).catch((err) => {
                console.warn("Failed to persist reading progress:", err);
              });
            }, 750);
          }
        }
      }, {
        root: null,
        threshold: [0, 0.25, 0.5, 0.75, 1.0]
      });

      pageElements.forEach((el) => readerObserver.observe(el));

    } catch (err) {
      readerLoading.classList.add("hidden");
      if (readerEmpty) readerEmpty.classList.add("hidden");
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

  // Reader Prev / Next Buttons
  if (btnReaderPrev) {
    btnReaderPrev.addEventListener("click", () => navigateToChapter(currentPrevChapter));
  }
  if (btnReaderFooterPrev) {
    btnReaderFooterPrev.addEventListener("click", () => navigateToChapter(currentPrevChapter));
  }
  if (btnReaderNext) {
    btnReaderNext.addEventListener("click", () => navigateToChapter(currentNextChapter));
  }
  if (btnReaderFooterNext) {
    btnReaderFooterNext.addEventListener("click", () => navigateToChapter(currentNextChapter));
  }

  // Reader Bookmark Toggle Button in Header
  btnReaderBookmark.addEventListener("click", async () => {
    if (!currentSeries || !currentChapter) return;
    const willBookmark = !currentSeriesBookmarks.has(currentChapter);
    const result = await toggleBookmark(currentSeries, currentChapter, willBookmark);
    if (result) {
      updateReaderBookmarkButton(currentChapter);
    }
  });

  // Style Toggle Buttons (Spaced vs Seamless)
  btnStyleSpaced.addEventListener("click", () => {
    applyReadingStyle("spaced", true);
  });

  btnStyleSeamless.addEventListener("click", () => {
    applyReadingStyle("seamless", true);
  });

  // Lightweight Keyboard Shortcuts
  window.addEventListener("keydown", (e) => {
    // Ignore if user is typing in form controls or editable elements
    const active = document.activeElement;
    if (active) {
      const tag = active.tagName ? active.tagName.toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || tag === "select" || active.isContentEditable) {
        return;
      }
    }

    // Ignore if system modifier keys are pressed
    if (e.metaKey || e.ctrlKey || e.altKey) {
      return;
    }

    // Only active when Reader View is open
    if (viewReader.classList.contains("hidden")) {
      return;
    }

    if (e.key === "ArrowLeft") {
      if (currentPrevChapter) {
        e.preventDefault();
        navigateToChapter(currentPrevChapter);
      }
    } else if (e.key === "ArrowRight") {
      if (currentNextChapter) {
        e.preventDefault();
        navigateToChapter(currentNextChapter);
      }
    } else if (e.key === "f" || e.key === "F") {
      e.preventDefault();
      toggleFullscreen();
    } else if (e.key === "b" || e.key === "B") {
      e.preventDefault();
      btnReaderBookmark.click();
    }
  });

  // Initial load
  handleRoute();
});
