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
  const librarySearch = document.getElementById("library-search");
  const librarySearchClear = document.getElementById("library-search-clear");
  const librarySort = document.getElementById("library-sort");
  const libraryNoResults = document.getElementById("library-no-results");

  // DOM Elements - Chapters & Metadata
  const chaptersList = document.getElementById("chapters-list");
  const chaptersEmpty = document.getElementById("chapters-empty");
  const seriesTitle = document.getElementById("series-title");
  const seriesMeta = document.getElementById("series-meta");
  const seriesCoverThumbWrapper = document.getElementById("series-cover-thumb-wrapper");
  const seriesCoverThumb = document.getElementById("series-cover-thumb");
  const seriesHeroBackdrop = document.getElementById("series-hero-backdrop");
  const seriesMetadataDisplay = document.getElementById("series-metadata-display");
  const seriesAuthor = document.getElementById("series-author");
  const seriesAuthorName = document.getElementById("series-author-name");
  const seriesSummaryPanel = document.getElementById("series-summary-panel");
  const seriesSummary = document.getElementById("series-summary");
  const seriesLinksPanel = document.getElementById("series-links-panel");
  const seriesLinksList = document.getElementById("series-links-list");
  const btnEditMetadata = document.getElementById("btn-edit-metadata");

  // DOM Elements - Metadata Editor
  const seriesMetadataEditor = document.getElementById("series-metadata-editor");
  const editorCoverPreviewWrapper = document.getElementById("editor-cover-preview-wrapper");
  const editorCoverPreview = document.getElementById("editor-cover-preview");
  const editorCoverPlaceholder = document.getElementById("editor-cover-placeholder");
  const editorCoverFile = document.getElementById("editor-cover-file");
  const editorCoverFileName = document.getElementById("editor-cover-file-name");

  const editorBgPreviewWrapper = document.getElementById("editor-bg-preview-wrapper");
  const editorBgPreview = document.getElementById("editor-bg-preview");
  const editorBgPlaceholder = document.getElementById("editor-bg-placeholder");
  const editorBgFile = document.getElementById("editor-bg-file");
  const editorBgFileName = document.getElementById("editor-bg-file-name");
  const btnRemoveBg = document.getElementById("btn-remove-bg");

  const editorAuthor = document.getElementById("editor-author");
  const editorSummary = document.getElementById("editor-summary");
  const btnAddLink = document.getElementById("btn-add-link");
  const editorLinksList = document.getElementById("editor-links-list");
  const btnCancelMetadata = document.getElementById("btn-cancel-metadata");
  const btnSaveMetadata = document.getElementById("btn-save-metadata");
  const editorError = document.getElementById("editor-error");

  let currentSeriesReaderData = null;
  let selectedCoverFile = null;
  let selectedBgFile = null;
  let removeBackgroundFlag = false;

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
  const readerProgressContainer = document.getElementById("reader-progress-container");
  const readerProgressCurrent = document.getElementById("reader-progress-current");
  const readerProgressTotal = document.getElementById("reader-progress-total");
  const readerProgressTrack = document.getElementById("reader-progress-track");

  // Fullscreen icons
  const iconFullscreenEnter = btnReaderFullscreen ? btnReaderFullscreen.querySelector(".icon-fullscreen-enter") : null;
  const iconFullscreenExit = btnReaderFullscreen ? btnReaderFullscreen.querySelector(".icon-fullscreen-exit") : null;

  // DOM Elements - Header & Navigation
  const appHeader = document.getElementById("app-header");
  const headerSeriesTitle = document.getElementById("header-series-title");
  const headerBackLink = document.getElementById("header-back-link");
  const statusBanner = document.getElementById("status-banner");

  // State
  let allSeriesList = [];
  let librarySearchQuery = "";
  let librarySortMode = "az";
  let currentSeries = null;
  let currentChapter = null;
  let currentSeriesBookmarks = new Set();
  let currentSeriesProgress = {};
  let currentPrevChapter = null;
  let currentNextChapter = null;
  let currentChapterImages = [];
  const chapterImagesCache = new Map();

  // Reading progress observer state
  let readerObserver = null;
  let currentVisibleImage = null;
  let saveProgressTimeout = null;
  let isInitialResume = false;

  // Persistent bottom reader progress timeline state
  let chapterTotalPages = 0;
  let numProgressSegments = 0;
  let hoveredProgressSegment = null;

  // Bottom Reader Progress Timeline (Segmented, Full-Width & Interactive)
  function setupReaderProgress(totalPages) {
    if (!readerProgressContainer || !readerProgressTrack) return;
    chapterTotalPages = totalPages;
    if (totalPages <= 0) {
      readerProgressContainer.classList.add("hidden");
      return;
    }

    // Adaptive segmented representation (max 80 segments)
    numProgressSegments = Math.min(totalPages, 80);
    readerProgressTrack.innerHTML = "";
    const fragment = document.createDocumentFragment();

    for (let i = 0; i < numProgressSegments; i++) {
      const seg = document.createElement("div");
      seg.className = "progress-segment future";

      // Calculate 1-based page range for this segment
      const startPage = Math.floor((i * totalPages) / numProgressSegments) + 1;
      const endPage = Math.floor(((i + 1) * totalPages) / numProgressSegments);
      const targetPage = Math.min(totalPages, Math.max(startPage, Math.round((startPage + endPage) / 2)));
      const targetImg = currentChapterImages[targetPage - 1];

      seg.dataset.segmentIndex = i;
      seg.dataset.startPage = startPage;
      seg.dataset.endPage = endPage;
      seg.dataset.targetPage = targetPage;
      if (targetImg) {
        seg.dataset.targetFilename = targetImg.filename;
      }
      seg.setAttribute("title", totalPages <= numProgressSegments ? `Page ${targetPage}` : `Pages ${startPage}–${endPage} (Jump to ${targetPage})`);

      fragment.appendChild(seg);
    }
    readerProgressTrack.appendChild(fragment);

    if (readerProgressTotal) {
      readerProgressTotal.textContent = totalPages;
    }
    readerProgressContainer.classList.remove("hidden");
  }

  function updateReaderProgress(pageIndex) {
    if (!readerProgressContainer || chapterTotalPages <= 0) return;
    const clampedIndex = Math.max(1, Math.min(pageIndex, chapterTotalPages));

    if (readerProgressCurrent) {
      readerProgressCurrent.textContent = clampedIndex;
    }

    if (readerProgressTrack && numProgressSegments > 0) {
      let activeSegIndex = 0;
      if (chapterTotalPages <= numProgressSegments) {
        activeSegIndex = clampedIndex - 1;
      } else {
        activeSegIndex = Math.min(
          numProgressSegments - 1,
          Math.floor(((clampedIndex - 1) * numProgressSegments) / chapterTotalPages)
        );
      }

      const segments = readerProgressTrack.children;
      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        const isHovered = (seg === hoveredProgressSegment);
        seg.className = isHovered ? "progress-segment hovered" : "progress-segment";
        if (i < activeSegIndex) {
          seg.classList.add("past", "completed");
        } else if (i === activeSegIndex) {
          seg.classList.add("current", "completed");
        } else {
          seg.classList.add("future");
        }
      }
    }
  }

  // Progress Timeline Interactions (Hover glow preview & Click-to-jump)
  if (readerProgressTrack) {
    readerProgressTrack.addEventListener("pointermove", (e) => {
      // Hover effects for mouse/pointer only (avoid stuck states on touch devices)
      if (e.pointerType === "touch") return;

      const segment = e.target.closest(".progress-segment");
      if (segment && segment !== hoveredProgressSegment) {
        if (hoveredProgressSegment) {
          hoveredProgressSegment.classList.remove("hovered");
        }
        hoveredProgressSegment = segment;
        hoveredProgressSegment.classList.add("hovered");
      }
    });

    readerProgressTrack.addEventListener("pointerleave", () => {
      if (hoveredProgressSegment) {
        hoveredProgressSegment.classList.remove("hovered");
        hoveredProgressSegment = null;
      }
    });

    // Ensure touch interactions don't leave lingering hover styles
    readerProgressTrack.addEventListener("pointerup", (e) => {
      if (e.pointerType === "touch") {
        if (hoveredProgressSegment) {
          hoveredProgressSegment.classList.remove("hovered");
          hoveredProgressSegment = null;
        }
      }
    });

    // Click on segment jumps directly to that page
    readerProgressTrack.addEventListener("click", (e) => {
      const segment = e.target.closest(".progress-segment");
      if (!segment) return;

      const targetFilename = segment.dataset.targetFilename;
      const targetPage = parseInt(segment.dataset.targetPage, 10);

      if (targetFilename) {
        const targetPageEl = document.getElementById(`page-${targetFilename}`);
        if (targetPageEl) {
          targetPageEl.scrollIntoView({ behavior: "instant", block: "start" });
          if (targetPage) {
            updateReaderProgress(targetPage);
          }
        }
      }
    });
  }

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

  // Series Detail Page: Scroll-based Hero & Header Transition
  let seriesScrollTicking = false;

  function updateSeriesScrollTransition() {
    seriesScrollTicking = false;
    if (!document.body.classList.contains("series-active")) return;

    const banner = document.getElementById("series-hero");
    if (!banner || !seriesHeroBackdrop) return;

    // Transition range dynamically matches the hero banner height
    const heroHeight = banner.offsetHeight || 360;
    const scrollY = window.scrollY || window.pageYOffset || 0;
    const progress = Math.min(1, Math.max(0, scrollY / heroHeight));

    // 1. Background image:
    // At top: sharp, recognizable (filter: none, opacity: 0.70)
    // Scrolling through hero: progressively blurs and fades toward page background
    // After hero: effectively invisible
    if (progress >= 1) {
      if (seriesHeroBackdrop.style.visibility !== "hidden") {
        seriesHeroBackdrop.style.visibility = "hidden";
      }
      seriesHeroBackdrop.style.opacity = "0";
      seriesHeroBackdrop.style.filter = "blur(28px)";
      seriesHeroBackdrop.style.webkitFilter = "blur(28px)";
    } else {
      if (seriesHeroBackdrop.style.visibility !== "visible") {
        seriesHeroBackdrop.style.visibility = "visible";
      }
      seriesHeroBackdrop.style.opacity = (0.70 * (1 - progress)).toFixed(3);
      if (progress === 0) {
        seriesHeroBackdrop.style.filter = "none";
        seriesHeroBackdrop.style.webkitFilter = "none";
      } else {
        const blurPx = (progress * 28).toFixed(1);
        seriesHeroBackdrop.style.filter = `blur(${blurPx}px)`;
        seriesHeroBackdrop.style.webkitFilter = `blur(${blurPx}px)`;
      }
    }

    // 2. Global header:
    // At top: translucent dark charcoal with subtle red tint (~65% transparent)
    // Scrolling through hero: gradually becomes more opaque and solid
    // After hero: fully opaque normal solid dark header
    if (appHeader) {
      const headerAlpha = (0.35 + (0.95 - 0.35) * progress).toFixed(3);
      const borderAlpha = (0.25 + (1.0 - 0.25) * progress).toFixed(3);
      appHeader.style.backgroundColor = `rgba(18, 14, 16, ${headerAlpha})`;
      appHeader.style.borderBottomColor = `rgba(42, 32, 34, ${borderAlpha})`;
    }
  }

  function onSeriesScroll() {
    if (!seriesScrollTicking) {
      seriesScrollTicking = true;
      requestAnimationFrame(updateSeriesScrollTransition);
    }
  }

  function startSeriesScrollTransition() {
    window.addEventListener("scroll", onSeriesScroll, { passive: true });
    updateSeriesScrollTransition();
  }

  function stopSeriesScrollTransition() {
    window.removeEventListener("scroll", onSeriesScroll);
    seriesScrollTicking = false;
  }

  // View switcher
  function switchView(viewName) {
    clearError();
    document.body.classList.toggle("reader-active", viewName === "reader");
    document.body.classList.toggle("series-active", viewName === "chapters");
    viewLibrary.classList.toggle("hidden", viewName !== "library");
    viewChapters.classList.toggle("hidden", viewName !== "chapters");
    viewReader.classList.toggle("hidden", viewName !== "reader");

    if (viewName !== "reader") {
      readerLoading.classList.add("hidden");
      if (readerProgressContainer) readerProgressContainer.classList.add("hidden");
      if (hoveredProgressSegment) {
        hoveredProgressSegment.classList.remove("hovered");
        hoveredProgressSegment = null;
      }
      currentChapterImages = [];
      chapterTotalPages = 0;
      numProgressSegments = 0;
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

    if (viewName !== "chapters") {
      if (headerSeriesTitle) {
        headerSeriesTitle.textContent = "";
        headerSeriesTitle.title = "";
      }
      stopSeriesScrollTransition();
      if (seriesCoverThumbWrapper && seriesCoverThumb) {
        seriesCoverThumbWrapper.classList.add("hidden");
        seriesCoverThumb.classList.add("hidden");
        seriesCoverThumb.src = "";
      }
      if (seriesHeroBackdrop) {
        seriesHeroBackdrop.classList.remove("loaded");
        seriesHeroBackdrop.style.backgroundImage = "none";
        seriesHeroBackdrop.style.removeProperty("filter");
        seriesHeroBackdrop.style.removeProperty("-webkit-filter");
        seriesHeroBackdrop.style.removeProperty("opacity");
        seriesHeroBackdrop.style.visibility = "";
      }
      if (seriesSummary) {
        seriesSummary.textContent = "";
      }
      if (seriesMetadataDisplay && seriesMetadataEditor) {
        seriesMetadataEditor.classList.add("hidden");
        seriesMetadataDisplay.classList.remove("hidden");
      }
      if (seriesLinksPanel) {
        seriesLinksPanel.classList.add("hidden");
      }
      if (editorError) {
        editorError.textContent = "";
        editorError.classList.add("hidden");
      }
      if (appHeader) {
        appHeader.style.removeProperty("background-color");
        appHeader.style.removeProperty("border-bottom-color");
      }
    } else {
      startSeriesScrollTransition();
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


  // API Helper: Fetch Reader Data (Bookmarks, Progress & Metadata)
  async function fetchReaderData(seriesName) {
    try {
      const res = await fetch(`/api/reader-data?series=${encodeURIComponent(seriesName)}`);
      if (!res.ok) return { progress: {}, bookmarks: [], summary: "", author: "", links: {} };
      return await res.json();
    } catch {
      return { progress: {}, bookmarks: [], summary: "", author: "", links: {} };
    }
  }

  // API Helper: Save Series Metadata (Author, Summary, Links)
  async function saveSeriesMetadata(seriesName, metadata) {
    const res = await fetch("/api/reader-data", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        series: seriesName,
        action: "metadata",
        author: metadata.author,
        summary: metadata.summary,
        links: metadata.links
      })
    });
    if (!res.ok) {
      let errMsg = `HTTP error ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.error) errMsg = errJson.error;
      } catch {}
      throw new Error(errMsg);
    }
    return await res.json();
  }

  // API Helper: Upload Series Image (Cover or Background)
  async function uploadSeriesImage(seriesName, file, type = "cover") {
    const endpoint = type === "cover" ? "/api/cover" : "/api/background";
    const res = await fetch(`${endpoint}?series=${encodeURIComponent(seriesName)}`, {
      method: "POST",
      headers: {
        "Content-Type": file.type || "application/octet-stream"
      },
      body: file
    });
    if (!res.ok) {
      let errMsg = `Failed to upload ${type} image (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.error) errMsg = errJson.error;
      } catch {}
      throw new Error(errMsg);
    }
    return await res.json();
  }

  // API Helper: Remove Series Background Image
  async function removeSeriesBackground(seriesName) {
    const res = await fetch(`/api/background?series=${encodeURIComponent(seriesName)}&action=remove`, {
      method: "POST"
    });
    if (!res.ok) {
      let errMsg = `Failed to remove background image (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.error) errMsg = errJson.error;
      } catch {}
      throw new Error(errMsg);
    }
    return await res.json();
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

  // Helper to fetch reading progress info for a series in library view
  async function fetchSeriesProgressInfo(seriesName) {
    try {
      const readerData = await fetchReaderData(seriesName);
      const progress = readerData && readerData.progress ? readerData.progress : {};
      const progressChapters = Object.keys(progress);
      if (progressChapters.length === 0) {
        return { hasProgress: false };
      }

      // Fetch chapters list to respect natural reading order
      const chRes = await fetch(`/api/chapters?series=${encodeURIComponent(seriesName)}`);
      if (!chRes.ok) return { hasProgress: false };
      const chData = await chRes.json();
      const chapters = chData.chapters || [];
      if (chapters.length === 0) return { hasProgress: false };

      // Find the latest chapter in natural reading order that exists in progress
      let activeChapter = null;
      for (let i = chapters.length - 1; i >= 0; i--) {
        if (progress[chapters[i].name]) {
          activeChapter = chapters[i];
          break;
        }
      }

      if (!activeChapter) {
        const fallbackName = progressChapters[progressChapters.length - 1];
        activeChapter = chapters.find((c) => c.name === fallbackName) || { name: fallbackName, image_count: 0 };
      }

      const savedImage = progress[activeChapter.name];
      let percentage = 0;

      if (savedImage) {
        try {
          const imgRes = await fetch(`/api/images?series=${encodeURIComponent(seriesName)}&chapter=${encodeURIComponent(activeChapter.name)}`);
          if (imgRes.ok) {
            const imgData = await imgRes.json();
            const images = imgData.images || [];
            if (images.length > 0) {
              const imgIndex = images.findIndex((img) => img.filename === savedImage);
              const pageNum = imgIndex >= 0 ? imgIndex + 1 : 1;
              percentage = Math.min(100, Math.max(1, Math.round((pageNum / images.length) * 100)));
            }
          }
        } catch {
          percentage = 0;
        }
      }

      return {
        hasProgress: true,
        chapterName: activeChapter.name,
        percentage: percentage
      };
    } catch {
      return { hasProgress: false };
    }
  }

  // 1. Load Library View
  async function loadLibrary() {
    switchView("library");
    librarySubtitle.textContent = "";

    try {
      const res = await fetch("/api/series");
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();

      allSeriesList = data.series || [];

      // Concurrently resolve existing progress data for all series
      if (allSeriesList.length > 0) {
        await Promise.all(
          allSeriesList.map(async (s) => {
            s.progressInfo = await fetchSeriesProgressInfo(s.name);
          })
        );
      }

      renderLibrarySeries();
    } catch (err) {
      showError(`Failed to load library: ${err.message}`);
      librarySubtitle.textContent = "Could not connect to the backend server.";
    }
  }

  function renderLibrarySeries() {
    seriesGrid.innerHTML = "";

    if (allSeriesList.length === 0) {
      librarySubtitle.textContent = "0 series";
      libraryEmpty.classList.remove("hidden");
      if (libraryNoResults) libraryNoResults.classList.add("hidden");
      return;
    }

    libraryEmpty.classList.add("hidden");

    // Local filter by search query
    let filtered = allSeriesList;
    const query = librarySearchQuery.trim().toLowerCase();
    if (query) {
      filtered = allSeriesList.filter((s) => s.name.toLowerCase().includes(query));
    }

    // Local sort
    filtered = [...filtered].sort((a, b) => {
      if (librarySortMode === "za") {
        return b.name.localeCompare(a.name, undefined, { numeric: true, sensitivity: "base" });
      } else if (librarySortMode === "chapters") {
        return (b.chapter_count || 0) - (a.chapter_count || 0);
      } else {
        // "az" (default)
        return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
      }
    });

    // Update metadata subtitle: quiet, natural casing (e.g. "12 series")
    const totalCount = allSeriesList.length;
    if (query) {
      librarySubtitle.textContent = `${filtered.length} of ${totalCount} ${totalCount === 1 ? "series" : "series"}`;
    } else {
      librarySubtitle.textContent = `${totalCount} ${totalCount === 1 ? "series" : "series"}`;
    }

    // Show/hide no results state
    if (filtered.length === 0 && query) {
      if (libraryNoResults) {
        libraryNoResults.classList.remove("hidden");
        const querySpan = document.getElementById("no-results-query");
        if (querySpan) querySpan.textContent = librarySearchQuery;
      }
      return;
    }

    if (libraryNoResults) libraryNoResults.classList.add("hidden");

    // Render series cards
    filtered.forEach((s) => {
      const card = document.createElement("div");
      card.className = "series-card";
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");

      const countText = `${s.chapter_count} ${s.chapter_count === 1 ? "chapter" : "chapters"}`;
      const prog = s.progressInfo;

      let progressEdgeHtml = "";
      let readingHtml = "";
      if (prog && prog.hasProgress && prog.chapterName) {
        const percent = typeof prog.percentage === "number" ? prog.percentage : 0;
        const targetChapter = prog.chapterName;
        const readUrl = `#/read/${encodeURIComponent(s.name)}/${encodeURIComponent(targetChapter)}`;
        progressEdgeHtml = `
          <div class="series-cover-progress" aria-hidden="true">
            <div class="series-cover-progress-fill" style="width: ${percent}%;"></div>
          </div>
        `;
        readingHtml = `
          <div class="series-card-status">${escapeHtml(targetChapter)}</div>
          <a href="${readUrl}" class="series-card-continue" title="Continue reading ${escapeHtml(targetChapter)}">
            <span class="continue-text">Continue reading</span>
            <span class="continue-arrow" aria-hidden="true">→</span>
          </a>
        `;
      } else {
        readingHtml = `
          <div class="series-card-status status-unstarted">Not started</div>
        `;
      }

      const coverHtml = s.has_cover && s.cover_url
        ? `<div class="series-cover-wrapper">
             <img class="series-cover-img" src="${s.cover_url}" alt="${escapeHtml(s.name)} cover" loading="lazy" />
             ${progressEdgeHtml}
           </div>`
        : `<div class="series-cover-wrapper series-cover-placeholder">
             <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
               <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
               <path d="M6 6h10"/>
               <path d="M6 10h10"/>
             </svg>
             ${progressEdgeHtml}
           </div>`;

      card.innerHTML = `
        ${coverHtml}
        <div class="series-card-content">
          <div class="series-card-title" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</div>
          <div class="series-card-meta">${countText}</div>
          ${readingHtml}
        </div>
      `;

      // Handle image loading errors gracefully without broken image icon
      const coverImg = card.querySelector(".series-cover-img");
      if (coverImg) {
        coverImg.addEventListener("error", () => {
          const wrapper = card.querySelector(".series-cover-wrapper");
          if (wrapper) {
            wrapper.className = "series-cover-wrapper series-cover-placeholder";
            const progEdge = wrapper.querySelector(".series-cover-progress");
            wrapper.innerHTML = `
              <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
                <path d="M6 6h10"/>
                <path d="M6 10h10"/>
              </svg>
            `;
            if (progEdge) {
              wrapper.appendChild(progEdge);
            }
          }
        });
      }

      const continueLink = card.querySelector(".series-card-continue");
      if (continueLink) {
        continueLink.addEventListener("click", (e) => {
          e.stopPropagation();
          window.location.hash = continueLink.getAttribute("href");
        });
      }

      card.addEventListener("click", (e) => {
        if (e.target.closest(".series-card-continue")) return;
        window.location.hash = `#/series/${encodeURIComponent(s.name)}`;
      });

      card.addEventListener("keydown", (e) => {
        if (e.target.closest(".series-card-continue")) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          window.location.hash = `#/series/${encodeURIComponent(s.name)}`;
        }
      });

      seriesGrid.appendChild(card);
    });
  }

  // Series Metadata Rendering & Editing
  function renderSeriesMetadata(readerData) {
    currentSeriesReaderData = readerData || {};

    // 1. Author
    if (seriesAuthor && seriesAuthorName) {
      const authorText = (currentSeriesReaderData.author || "").trim();
      if (authorText) {
        seriesAuthorName.textContent = authorText;
        seriesAuthor.classList.remove("hidden");
      } else {
        seriesAuthor.classList.add("hidden");
        seriesAuthorName.textContent = "";
      }
    }

    // 2. Summary
    if (seriesSummaryPanel && seriesSummary) {
      const summaryText = (currentSeriesReaderData.summary || "").trim();
      if (summaryText) {
        seriesSummary.textContent = summaryText;
        seriesSummaryPanel.classList.remove("hidden");
      } else {
        seriesSummaryPanel.classList.add("hidden");
        seriesSummary.textContent = "";
      }
    }

    // 3. Links
    if (seriesLinksPanel && seriesLinksList) {
      const links = currentSeriesReaderData.links;
      seriesLinksList.innerHTML = "";
      if (links && typeof links === "object" && Object.keys(links).length > 0) {
        Object.entries(links).forEach(([label, url]) => {
          const a = document.createElement("a");
          a.className = "series-link-item";
          a.href = url;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.title = `Open ${label}`;
          a.innerHTML = `
            <span>${escapeHtml(label)}</span>
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" class="link-external-icon">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
            </svg>
          `;
          seriesLinksList.appendChild(a);
        });
        seriesLinksPanel.classList.remove("hidden");
      } else {
        seriesLinksPanel.classList.add("hidden");
      }
    }

    // Ensure display is active and editor is closed
    if (seriesMetadataDisplay && seriesMetadataEditor) {
      seriesMetadataDisplay.classList.remove("hidden");
      seriesMetadataEditor.classList.add("hidden");
    }
    if (editorError) {
      editorError.textContent = "";
      editorError.classList.add("hidden");
    }
  }

  function openMetadataEditor() {
    if (!seriesMetadataEditor || !seriesMetadataDisplay) return;

    // Reset image selections
    selectedCoverFile = null;
    selectedBgFile = null;
    removeBackgroundFlag = false;
    if (editorCoverFile) editorCoverFile.value = "";
    if (editorBgFile) editorBgFile.value = "";
    if (editorCoverFileName) editorCoverFileName.textContent = "Choose image...";
    if (editorBgFileName) editorBgFileName.textContent = "Choose image...";

    const cacheBust = Date.now();
    // Load current cover preview
    if (editorCoverPreview) {
      editorCoverPreview.onload = () => {
        editorCoverPreview.classList.remove("hidden");
        if (editorCoverPlaceholder) editorCoverPlaceholder.classList.add("hidden");
      };
      editorCoverPreview.onerror = () => {
        editorCoverPreview.classList.add("hidden");
        if (editorCoverPlaceholder) {
          editorCoverPlaceholder.textContent = "No cover";
          editorCoverPlaceholder.classList.remove("hidden");
        }
      };
      editorCoverPreview.src = `/api/cover?series=${encodeURIComponent(currentSeries)}&t=${cacheBust}`;
    }

    // Load current background preview
    if (editorBgPreview) {
      if (currentSeriesReaderData && currentSeriesReaderData.has_background) {
        editorBgPreview.onload = () => {
          editorBgPreview.classList.remove("hidden");
          if (editorBgPlaceholder) editorBgPlaceholder.classList.add("hidden");
        };
        editorBgPreview.onerror = () => {
          editorBgPreview.classList.add("hidden");
          if (editorBgPlaceholder) {
            editorBgPlaceholder.textContent = "No custom background";
            editorBgPlaceholder.classList.remove("hidden");
          }
        };
        editorBgPreview.src = `/api/background?series=${encodeURIComponent(currentSeries)}&t=${cacheBust}`;
        if (btnRemoveBg) btnRemoveBg.classList.remove("hidden");
      } else {
        editorBgPreview.src = "";
        editorBgPreview.classList.add("hidden");
        if (editorBgPlaceholder) {
          editorBgPlaceholder.textContent = "No custom background";
          editorBgPlaceholder.classList.remove("hidden");
        }
        if (btnRemoveBg) btnRemoveBg.classList.add("hidden");
      }
    }

    const data = currentSeriesReaderData || {};
    if (editorAuthor) editorAuthor.value = data.author || "";
    if (editorSummary) editorSummary.value = data.summary || "";

    if (editorLinksList) {
      editorLinksList.innerHTML = "";
      const links = data.links || {};
      const entries = Object.entries(links);
      if (entries.length > 0) {
        entries.forEach(([label, url]) => {
          addEditorLinkRow(label, url);
        });
      }
    }

    if (editorError) {
      editorError.textContent = "";
      editorError.classList.add("hidden");
    }

    seriesMetadataDisplay.classList.add("hidden");
    seriesMetadataEditor.classList.remove("hidden");
    if (seriesLinksPanel) {
      seriesLinksPanel.classList.add("hidden");
    }
    if (editorAuthor) editorAuthor.focus();
  }

  function closeMetadataEditor() {
    if (!seriesMetadataEditor || !seriesMetadataDisplay) return;
    selectedCoverFile = null;
    selectedBgFile = null;
    removeBackgroundFlag = false;
    if (editorCoverFile) editorCoverFile.value = "";
    if (editorBgFile) editorBgFile.value = "";
    seriesMetadataEditor.classList.add("hidden");
    seriesMetadataDisplay.classList.remove("hidden");
    if (seriesLinksPanel && currentSeriesReaderData && currentSeriesReaderData.links && Object.keys(currentSeriesReaderData.links).length > 0) {
      seriesLinksPanel.classList.remove("hidden");
    }
    if (editorError) {
      editorError.textContent = "";
      editorError.classList.add("hidden");
    }
  }

  function addEditorLinkRow(label = "", url = "") {
    if (!editorLinksList) return null;
    const row = document.createElement("div");
    row.className = "editor-link-row";
    row.innerHTML = `
      <input type="text" class="editor-input editor-link-label" placeholder="Label (e.g. AniList)" value="${escapeHtml(label)}" autocomplete="off" spellcheck="false" />
      <input type="url" class="editor-input editor-link-url" placeholder="https://..." value="${escapeHtml(url)}" autocomplete="off" spellcheck="false" />
      <button type="button" class="btn-remove-link" title="Remove link" aria-label="Remove link">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6 6 18M6 6l12 12"/>
        </svg>
      </button>
    `;

    const btnRemove = row.querySelector(".btn-remove-link");
    btnRemove.addEventListener("click", () => {
      row.remove();
    });

    editorLinksList.appendChild(row);
    return row;
  }

  async function handleSaveMetadata() {
    if (!currentSeries) return;

    if (editorError) {
      editorError.textContent = "";
      editorError.classList.add("hidden");
    }

    const authorVal = editorAuthor ? editorAuthor.value.trim() : "";
    const summaryVal = editorSummary ? editorSummary.value.trim() : "";

    // Parse and validate links
    const linksObj = {};
    if (editorLinksList) {
      const rows = editorLinksList.querySelectorAll(".editor-link-row");
      for (const row of rows) {
        const labelInput = row.querySelector(".editor-link-label");
        const urlInput = row.querySelector(".editor-link-url");
        const label = labelInput ? labelInput.value.trim() : "";
        const url = urlInput ? urlInput.value.trim() : "";

        // If both empty, ignore row
        if (!label && !url) continue;

        if (!label) {
          showEditorError("Please enter a label for each link or remove the empty row.");
          if (labelInput) labelInput.focus();
          return;
        }

        if (!url) {
          showEditorError(`Please enter a URL for "${label}".`);
          if (urlInput) urlInput.focus();
          return;
        }

        // Validate URL format
        try {
          const parsed = new URL(url);
          if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
            showEditorError(`Invalid URL for "${label}". Must start with http:// or https://`);
            if (urlInput) urlInput.focus();
            return;
          }
        } catch {
          showEditorError(`Invalid URL format for "${label}". Must be a valid HTTP or HTTPS URL.`);
          if (urlInput) urlInput.focus();
          return;
        }

        linksObj[label] = url;
      }
    }

    if (btnSaveMetadata) {
      btnSaveMetadata.disabled = true;
      btnSaveMetadata.textContent = "Saving...";
    }

    try {
      // 1. Upload Cover Image if selected
      if (selectedCoverFile) {
        await uploadSeriesImage(currentSeries, selectedCoverFile, "cover");
      }

      // 2. Remove or Upload Background Image if requested
      if (removeBackgroundFlag) {
        await removeSeriesBackground(currentSeries);
      } else if (selectedBgFile) {
        await uploadSeriesImage(currentSeries, selectedBgFile, "background");
      }

      // 3. Save text metadata (Author, Summary, Links)
      await saveSeriesMetadata(currentSeries, {
        author: authorVal,
        summary: summaryVal,
        links: linksObj
      });

      // 4. Update UI previews with cache-busting timestamp
      const t = Date.now();

      // Update series cover thumbnail on detail page
      if (seriesCoverThumb && seriesCoverThumbWrapper) {
        seriesCoverThumb.src = `/api/cover?series=${encodeURIComponent(currentSeries)}&t=${t}`;
        seriesCoverThumb.classList.remove("hidden");
        seriesCoverThumbWrapper.classList.remove("hidden");
      }

      // Update hero backdrop on detail page
      if (seriesHeroBackdrop) {
        const bgUrl = `/api/background?series=${encodeURIComponent(currentSeries)}&t=${t}`;
        seriesHeroBackdrop.style.backgroundImage = `url("${bgUrl}")`;
        seriesHeroBackdrop.classList.add("loaded");
      }

      // Update cached library item
      const cached = allSeriesList.find((s) => s.name === currentSeries);
      if (cached) {
        cached.has_cover = true;
        cached.cover_url = `/api/cover?series=${encodeURIComponent(currentSeries)}&t=${t}`;
      }

      // 5. Fetch fresh reader data (which contains updated has_cover and has_background)
      const freshReaderData = await fetchReaderData(currentSeries);
      renderSeriesMetadata(freshReaderData);
      closeMetadataEditor();
    } catch (err) {
      showEditorError(err.message || "Failed to save metadata");
    } finally {
      if (btnSaveMetadata) {
        btnSaveMetadata.disabled = false;
        btnSaveMetadata.textContent = "Save";
      }
    }
  }

  function showEditorError(msg) {
    if (editorError) {
      editorError.textContent = msg;
      editorError.classList.remove("hidden");
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

    if (headerSeriesTitle) {
      headerSeriesTitle.textContent = seriesName;
      headerSeriesTitle.title = `Scroll ${seriesName} to top`;
    }

    if (seriesHeroBackdrop) {
      const bgUrl = `/api/background?series=${encodeURIComponent(seriesName)}&t=${Date.now()}`;
      seriesHeroBackdrop.style.backgroundImage = `url("${bgUrl}")`;
      seriesHeroBackdrop.classList.add("loaded");

      const testImg = new Image();
      testImg.onerror = () => {
        seriesHeroBackdrop.style.backgroundImage = "none";
        seriesHeroBackdrop.classList.remove("loaded");
      };
      testImg.src = bgUrl;
    }

    if (seriesCoverThumbWrapper && seriesCoverThumb) {
      seriesCoverThumb.onload = () => {
        seriesCoverThumb.classList.remove("hidden");
        seriesCoverThumbWrapper.classList.remove("hidden");
      };
      seriesCoverThumb.onerror = () => {
        seriesCoverThumb.classList.add("hidden");
        seriesCoverThumbWrapper.classList.add("hidden");
      };
      seriesCoverThumb.src = `/api/cover?series=${encodeURIComponent(seriesName)}&t=${Date.now()}`;
    }

    try {
      const [chaptersRes, readerData] = await Promise.all([
        fetch(`/api/chapters?series=${encodeURIComponent(seriesName)}`),
        fetchReaderData(seriesName)
      ]);

      if (!chaptersRes.ok) throw new Error(`HTTP error ${chaptersRes.status}`);
      const data = await chaptersRes.json();

      currentSeries = seriesName;
      currentSeriesBookmarks = new Set(readerData.bookmarks || []);
      currentSeriesProgress = readerData.progress || {};

      renderSeriesMetadata(readerData);

      const chapters = data.chapters || [];
      chaptersList.innerHTML = "";

      if (chapters.length === 0) {
        seriesMeta.textContent = "0 chapters";
        chaptersEmpty.classList.remove("hidden");
        return;
      }

      const bookmarkCount = currentSeriesBookmarks.size;
      const countText = `${chapters.length} ${chapters.length === 1 ? "chapter" : "chapters"}`;
      seriesMeta.textContent = bookmarkCount > 0 ? `${countText} · ${bookmarkCount} bookmarked` : countText;

      // Compute reading progress percentage for chapters with saved progress
      const chapterProgressMap = new Map();
      const progressChapters = chapters.filter((ch) => currentSeriesProgress[ch.name]);
      if (progressChapters.length > 0) {
        await Promise.all(
          progressChapters.map(async (ch) => {
            const savedImage = currentSeriesProgress[ch.name];
            if (!savedImage) return;

            const cacheKey = `${seriesName}:::${ch.name}`;
            let images = chapterImagesCache ? chapterImagesCache.get(cacheKey) : null;
            if (!images) {
              try {
                const imgRes = await fetch(
                  `/api/images?series=${encodeURIComponent(seriesName)}&chapter=${encodeURIComponent(ch.name)}`
                );
                if (imgRes.ok) {
                  const imgData = await imgRes.json();
                  images = imgData.images || [];
                  if (chapterImagesCache) chapterImagesCache.set(cacheKey, images);
                }
              } catch {
                images = null;
              }
            }

            if (images && images.length > 0) {
              const imgIndex = images.findIndex((img) => img.filename === savedImage);
              const pageNum = imgIndex >= 0 ? imgIndex + 1 : 1;
              const pct = Math.min(100, Math.max(1, Math.round((pageNum / images.length) * 100)));
              chapterProgressMap.set(ch.name, pct);
              return;
            }

            // Fallback estimation using chapter.image_count and numeric match
            if (ch.image_count > 0) {
              const match = savedImage.match(/(\d+)(?:\.[^.]+)?$/);
              if (match) {
                const num = parseInt(match[1], 10);
                if (!isNaN(num) && num >= 1) {
                  const pageNum = Math.min(num, ch.image_count);
                  const pct = Math.min(100, Math.max(1, Math.round((pageNum / ch.image_count) * 100)));
                  chapterProgressMap.set(ch.name, pct);
                }
              }
            }
          })
        );
      }

      chapters.forEach((ch) => {
        const item = document.createElement("div");
        item.className = "chapter-item";
        item.setAttribute("role", "button");
        item.setAttribute("tabindex", "0");

        const isBookmarked = currentSeriesBookmarks.has(ch.name);
        const hasProgress = chapterProgressMap.has(ch.name);
        const progressPct = hasProgress ? chapterProgressMap.get(ch.name) : null;

        item.innerHTML = `
          <div class="chapter-info">
            <button class="btn-chapter-bookmark ${isBookmarked ? "bookmarked" : ""}" title="${isBookmarked ? "Remove bookmark" : "Bookmark chapter"}" aria-label="${isBookmarked ? "Remove bookmark" : "Bookmark chapter"}">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
              </svg>
            </button>
            <span class="chapter-title">${escapeHtml(ch.name)}</span>
          </div>
          <div class="chapter-actions">
            <span class="chapter-progress">${progressPct != null ? `${progressPct}%` : ""}</span>
            <span class="chapter-pages">${ch.image_count} ${ch.image_count === 1 ? "page" : "pages"}</span>
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

        // Keyboard navigation (Enter or Space)
        item.addEventListener("keydown", (e) => {
          if ((e.key === "Enter" || e.key === " ") && e.target === item) {
            e.preventDefault();
            window.location.hash = `#/read/${encodeURIComponent(seriesName)}/${encodeURIComponent(ch.name)}`;
          }
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
    if (readerProgressContainer) readerProgressContainer.classList.add("hidden");
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
        if (readerProgressContainer) readerProgressContainer.classList.add("hidden");
        if (readerEmpty) readerEmpty.classList.remove("hidden");
        showError("No images found in this chapter.");
        return;
      }

      if (readerEmpty) readerEmpty.classList.add("hidden");

      // Map filename to 1-based page index
      const filenameToIndex = new Map();
      images.forEach((img, idx) => {
        filenameToIndex.set(img.filename, idx + 1);
      });

      // Setup bottom reading progress timeline
      currentChapterImages = images;
      setupReaderProgress(images.length);

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
      let initialPageIndex = 1;
      if (savedImage && filenameToIndex.has(savedImage)) {
        targetPage = document.getElementById(`page-${savedImage}`);
        initialPageIndex = filenameToIndex.get(savedImage);
      }

      updateReaderProgress(initialPageIndex);

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
          if (filename && filenameToIndex.has(filename)) {
            const activeIndex = filenameToIndex.get(filename);
            updateReaderProgress(activeIndex);
          }

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
      if (readerProgressContainer) readerProgressContainer.classList.add("hidden");
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

  if (headerSeriesTitle) {
    headerSeriesTitle.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // Library Search & Sort Controls
  if (librarySearch) {
    librarySearch.addEventListener("input", (e) => {
      librarySearchQuery = e.target.value;
      if (librarySearchClear) {
        librarySearchClear.classList.toggle("hidden", !librarySearchQuery);
      }
      renderLibrarySeries();
    });

    librarySearch.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        librarySearch.value = "";
        librarySearchQuery = "";
        if (librarySearchClear) librarySearchClear.classList.add("hidden");
        renderLibrarySeries();
        librarySearch.blur();
      }
    });
  }

  if (librarySearchClear) {
    librarySearchClear.addEventListener("click", () => {
      if (librarySearch) {
        librarySearch.value = "";
        librarySearch.focus();
      }
      librarySearchQuery = "";
      librarySearchClear.classList.add("hidden");
      renderLibrarySeries();
    });
  }

  if (librarySort) {
    librarySort.addEventListener("change", (e) => {
      librarySortMode = e.target.value;
      renderLibrarySeries();
    });
  }

  if (headerBackLink) {
    headerBackLink.addEventListener("click", () => {
      window.location.hash = "#/";
    });
  }

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

  // Metadata Editor Event Listeners
  if (btnEditMetadata) {
    btnEditMetadata.addEventListener("click", openMetadataEditor);
  }
  if (btnCancelMetadata) {
    btnCancelMetadata.addEventListener("click", closeMetadataEditor);
  }
  if (btnAddLink) {
    btnAddLink.addEventListener("click", () => {
      const row = addEditorLinkRow();
      if (row) {
        const labelInput = row.querySelector(".editor-link-label");
        if (labelInput) labelInput.focus();
      }
    });
  }
  if (btnSaveMetadata) {
    btnSaveMetadata.addEventListener("click", handleSaveMetadata);
  }

  // Cover image file selection
  if (editorCoverFile) {
    editorCoverFile.addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        selectedCoverFile = file;
        if (editorCoverFileName) editorCoverFileName.textContent = file.name;
        const objUrl = URL.createObjectURL(file);
        if (editorCoverPreview) {
          editorCoverPreview.src = objUrl;
          editorCoverPreview.classList.remove("hidden");
        }
        if (editorCoverPlaceholder) editorCoverPlaceholder.classList.add("hidden");
      }
    });
  }

  // Background image file selection
  if (editorBgFile) {
    editorBgFile.addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        selectedBgFile = file;
        removeBackgroundFlag = false;
        if (editorBgFileName) editorBgFileName.textContent = file.name;
        const objUrl = URL.createObjectURL(file);
        if (editorBgPreview) {
          editorBgPreview.src = objUrl;
          editorBgPreview.classList.remove("hidden");
        }
        if (editorBgPlaceholder) editorBgPlaceholder.classList.add("hidden");
        if (btnRemoveBg) btnRemoveBg.classList.remove("hidden");
      }
    });
  }

  // Background remove button
  if (btnRemoveBg) {
    btnRemoveBg.addEventListener("click", () => {
      removeBackgroundFlag = true;
      selectedBgFile = null;
      if (editorBgFile) editorBgFile.value = "";
      if (editorBgFileName) editorBgFileName.textContent = "Choose image...";
      if (editorBgPreview) {
        editorBgPreview.src = "";
        editorBgPreview.classList.add("hidden");
      }
      if (editorBgPlaceholder) {
        editorBgPlaceholder.textContent = "Will revert to cover on save";
        editorBgPlaceholder.classList.remove("hidden");
      }
      btnRemoveBg.classList.add("hidden");
    });
  }

  // Keyboard accessibility for file select labels
  document.querySelectorAll(".btn-file-select").forEach((lbl) => {
    lbl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        const forId = lbl.getAttribute("for");
        if (forId) {
          const inp = document.getElementById(forId);
          if (inp) inp.click();
        }
      }
    });
  });

  // Initial load
  handleRoute();
});
