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
  const librarySortDir = document.getElementById("library-sort-dir");
  const librarySortArrow = document.getElementById("library-sort-arrow");
  const libraryNoResults = document.getElementById("library-no-results");
  const btnChangeFolder = document.getElementById("btn-change-folder");
  const libraryUnavailable = document.getElementById("library-unavailable");
  const unavailableFolderPath = document.getElementById("unavailable-folder-path");
  const btnReconnectFolder = document.getElementById("btn-reconnect-folder");
  const pinnedSection = document.getElementById("pinned-section");
  const pinnedGrid = document.getElementById("pinned-grid");
  const pinnedSectionCount = document.getElementById("pinned-section-count");

  // DOM Elements - Profile & Settings
  const headerProfileBtn = document.getElementById("header-profile-btn");
  const headerAvatarDefault = document.getElementById("header-avatar-default");
  const headerAvatarImg = document.getElementById("header-avatar-img");
  const headerProfileName = document.getElementById("header-profile-name");
  const profileDropdown = document.getElementById("profile-dropdown");
  const profileDropdownName = document.getElementById("profile-dropdown-name");
  const dropdownItemProfile = document.getElementById("dropdown-item-profile");
  const dropdownItemSettings = document.getElementById("dropdown-item-settings");

  const modalOverlay = document.getElementById("modal-overlay");
  const modalProfile = document.getElementById("modal-profile");
  const btnCloseProfileModal = document.getElementById("btn-close-profile-modal");
  const profileModalAvatarDefault = document.getElementById("profile-modal-avatar-default");
  const profileModalAvatarImg = document.getElementById("profile-modal-avatar-img");
  const profileAvatarInput = document.getElementById("profile-avatar-input");
  const btnRemoveAvatar = document.getElementById("btn-remove-avatar");
  const profileNameInput = document.getElementById("profile-name-input");
  const profileModalError = document.getElementById("profile-modal-error");
  const btnCancelProfile = document.getElementById("btn-cancel-profile");
  const btnSaveProfile = document.getElementById("btn-save-profile");

  const modalSettings = document.getElementById("modal-settings");
  const btnCloseSettingsModal = document.getElementById("btn-close-settings-modal");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const settingsLibraryPath = document.getElementById("settings-library-path");
  const formLibraryPath = document.getElementById("form-library-path");
  const inputLibraryPath = document.getElementById("input-library-path");
  const btnApplyLibraryPath = document.getElementById("btn-apply-library-path");
  const libraryPathError = document.getElementById("library-path-error");

  // DOM Elements - Keyboard Shortcuts Modal
  const modalShortcuts = document.getElementById("modal-shortcuts");
  const modalShortcutsBody = document.getElementById("modal-shortcuts-body");
  const btnCloseShortcutsModal = document.getElementById("btn-close-shortcuts-modal");
  const btnCloseShortcuts = document.getElementById("btn-close-shortcuts");
  const dropdownItemShortcuts = document.getElementById("dropdown-item-shortcuts");
  let previouslyFocusedElement = null;

  // DOM Elements - Remote Series Modal
  const btnOpenRemote = document.getElementById("btn-open-remote");
  const dropdownItemRemote = document.getElementById("dropdown-item-remote");
  const modalRemote = document.getElementById("modal-remote");
  const btnCloseRemoteModal = document.getElementById("btn-close-remote-modal");
  const btnCancelRemote = document.getElementById("btn-cancel-remote");
  const btnLoadRemote = document.getElementById("btn-load-remote");
  const btnLoadRemoteText = document.getElementById("btn-load-remote-text");
  const remoteUrlInput = document.getElementById("remote-url-input");
  const remoteModalError = document.getElementById("remote-modal-error");
  const remoteFormatsDisclosure = document.getElementById("remote-formats-disclosure");
  const remoteFormatsToggle = document.getElementById("remote-formats-toggle");
  const remoteFormatsContent = document.getElementById("remote-formats-content");
  const remoteFormatsList = document.getElementById("remote-formats-list") || document.getElementById("remote-sources-list");
  const remoteSourcesSection = document.getElementById("remote-sources-section") || remoteFormatsDisclosure;
  const remoteSourcesList = remoteFormatsList;
  const remoteRecentSection = document.getElementById("remote-recent-section");
  const remoteRecentList = document.getElementById("remote-recent-list");
  const btnClearRemoteRecent = document.getElementById("btn-clear-remote-recent");
  const formRemoteSeries = document.getElementById("form-remote-series");

  // DOM Elements - Chapters & Metadata
  const chaptersList = document.getElementById("chapters-list");
  const chaptersEmpty = document.getElementById("chapters-empty");
  const btnChapterOrder = document.getElementById("btn-chapter-order");
  const chapterOrderArrow = document.getElementById("chapter-order-arrow");
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

  const seriesActionBar = document.getElementById("series-action-bar");
  const btnResumeReading = document.getElementById("btn-resume-reading");
  const resumeReadingText = document.getElementById("resume-reading-text");
  const btnPinSeries = document.getElementById("btn-pin-series");
  const pinSeriesText = document.getElementById("pin-series-text");
  const seriesCompletedBadge = document.getElementById("series-completed-badge");

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
  const readerHeader = document.querySelector(".reader-header");
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
  let librarySortCriterion = "name";
  let librarySortDirection = "asc";
  let seriesChapterOrder = "asc";
  let currentSeriesChapters = [];
  let currentSeriesProgressMap = new Map();
  let currentSeries = null;
  let currentChapter = null;
  let currentSeriesBookmarks = new Set();
  let currentSeriesProgress = {};
  let currentPrevChapter = null;
  let currentNextChapter = null;
  let currentChapterImages = [];
  const chapterImagesCache = new Map();
  let pinnedSeriesSet = new Set();
  let currentSeriesCompleted = new Set();
  let currentSeriesUnread = new Set();
  let currentSeriesLastRead = null;
  let activeReaderComplete = null;
  let activeReaderSuppressAutoComplete = null;

  // Temporary Reader Zoom State (50% to 300%, default 100%, purely in-memory)
  const MIN_READER_ZOOM = 50;
  const MAX_READER_ZOOM = 300;
  const DEFAULT_READER_ZOOM = 100;
  let currentReaderZoom = DEFAULT_READER_ZOOM;
  const readerZoomIndicator = document.getElementById("reader-zoom-indicator");
  let zoomIndicatorTimeout = null;

  function showZoomIndicator(text) {
    if (!readerZoomIndicator) return;
    readerZoomIndicator.textContent = text;
    readerZoomIndicator.classList.remove("hidden");
    requestAnimationFrame(() => {
      readerZoomIndicator.classList.add("visible");
    });
    clearTimeout(zoomIndicatorTimeout);
    zoomIndicatorTimeout = setTimeout(() => {
      readerZoomIndicator.classList.remove("visible");
      setTimeout(() => {
        if (!readerZoomIndicator.classList.contains("visible")) {
          readerZoomIndicator.classList.add("hidden");
        }
      }, 250);
    }, 1200);
  }

  function hideZoomIndicator() {
    if (!readerZoomIndicator) return;
    clearTimeout(zoomIndicatorTimeout);
    readerZoomIndicator.classList.remove("visible");
    readerZoomIndicator.classList.add("hidden");
  }

  function preserveScrollPositionDuring(action) {
    if (!readerContainer) {
      action();
      return;
    }

    const pageElements = Array.from(readerContainer.querySelectorAll(".reader-page"));
    let anchorEl = null;
    let anchorOffsetRatio = 0;

    const isFullscreen = (typeof isFullscreenActive === "function") && isFullscreenActive();
    const headerHeight = (readerHeader && !isFullscreen) ? readerHeader.offsetHeight : 0;

    for (const el of pageElements) {
      const rect = el.getBoundingClientRect();
      if (rect.bottom > headerHeight && rect.top <= window.innerHeight) {
        anchorEl = el;
        const visibleTop = Math.max(0, headerHeight - rect.top);
        anchorOffsetRatio = rect.height > 0 ? (visibleTop / rect.height) : 0;
        break;
      }
    }

    const maxScrollBefore = document.documentElement.scrollHeight - window.innerHeight;
    const scrollRatio = maxScrollBefore > 0 ? (window.scrollY / maxScrollBefore) : 0;

    action();

    if (anchorEl) {
      const newRect = anchorEl.getBoundingClientRect();
      const currentScrollY = window.scrollY || window.pageYOffset || 0;
      const targetPageTop = currentScrollY + newRect.top;
      const newOffset = anchorOffsetRatio * newRect.height;
      const targetScrollY = Math.max(0, Math.round(targetPageTop + newOffset - headerHeight));
      window.scrollTo({ top: targetScrollY, behavior: "instant" });
    } else if (maxScrollBefore > 0) {
      const maxScrollAfter = document.documentElement.scrollHeight - window.innerHeight;
      if (maxScrollAfter > 0) {
        window.scrollTo({ top: Math.max(0, Math.round(scrollRatio * maxScrollAfter)), behavior: "instant" });
      }
    }
  }

  function setReaderZoom(zoomPercent, showFeedback = true) {
    const clamped = Math.max(MIN_READER_ZOOM, Math.min(MAX_READER_ZOOM, Math.round(zoomPercent)));
    currentReaderZoom = clamped;

    if (readerContainer) {
      readerContainer.style.setProperty("--reader-zoom", (clamped / 100).toString());
    }

    if (showFeedback) {
      showZoomIndicator(`${clamped}%`);
    } else {
      hideZoomIndicator();
    }
  }

  function resetReaderZoom(showFeedback = false) {
    if (showFeedback && viewReader && viewReader.classList.contains("hidden")) return;
    if (currentReaderZoom === DEFAULT_READER_ZOOM) {
      if (showFeedback) {
        showZoomIndicator(`${DEFAULT_READER_ZOOM}%`);
      } else {
        hideZoomIndicator();
      }
      return;
    }

    if (showFeedback) {
      preserveScrollPositionDuring(() => {
        setReaderZoom(DEFAULT_READER_ZOOM, true);
      });
    } else {
      setReaderZoom(DEFAULT_READER_ZOOM, false);
    }
  }

  function changeReaderZoom(deltaPercent) {
    if (viewReader.classList.contains("hidden")) return;
    const target = currentReaderZoom + deltaPercent;
    const clamped = Math.max(MIN_READER_ZOOM, Math.min(MAX_READER_ZOOM, target));
    if (clamped === currentReaderZoom && (target < MIN_READER_ZOOM || target > MAX_READER_ZOOM)) {
      showZoomIndicator(`${clamped}%`);
      return;
    }

    preserveScrollPositionDuring(() => {
      setReaderZoom(clamped, true);
    });
  }

  // Load saved preferences
  try {
    const savedSort = localStorage.getItem("local_manga_library_sort");
    if (savedSort) {
      const parsed = JSON.parse(savedSort);
      if (["name", "chapters", "unread"].includes(parsed.criterion)) {
        librarySortCriterion = parsed.criterion;
      } else if (parsed.criterion === "za") {
        librarySortCriterion = "name";
        librarySortDirection = "desc";
      } else if (parsed.criterion === "az") {
        librarySortCriterion = "name";
        librarySortDirection = "asc";
      }
      if (["asc", "desc"].includes(parsed.direction)) {
        librarySortDirection = parsed.direction;
      }
    }
  } catch {}

  try {
    const savedOrder = localStorage.getItem("local_manga_chapter_order");
    if (savedOrder === "asc" || savedOrder === "desc") {
      seriesChapterOrder = savedOrder;
    }
  } catch {}

  function updateLibrarySortUI() {
    if (librarySort) {
      librarySort.value = librarySortCriterion;
    }
    if (librarySortArrow) {
      librarySortArrow.textContent = librarySortDirection === "desc" ? "↓" : "↑";
    }
    if (librarySortDir) {
      const dirText = librarySortDirection === "desc" ? "descending" : "ascending";
      librarySortDir.title = `${dirText.charAt(0).toUpperCase() + dirText.slice(1)} (click to toggle)`;
      librarySortDir.setAttribute("aria-label", `Sort direction: ${dirText} (click to toggle)`);
    }
  }

  function saveLibrarySortPreference() {
    try {
      localStorage.setItem("local_manga_library_sort", JSON.stringify({
        criterion: librarySortCriterion,
        direction: librarySortDirection
      }));
    } catch {}
  }

  function updateChapterOrderUI() {
    if (chapterOrderArrow) {
      chapterOrderArrow.textContent = seriesChapterOrder === "desc" ? "↓" : "↑";
    }
    if (btnChapterOrder) {
      const dirText = seriesChapterOrder === "desc" ? "descending" : "ascending";
      btnChapterOrder.title = `${dirText.charAt(0).toUpperCase() + dirText.slice(1)} (click to toggle)`;
      btnChapterOrder.setAttribute("aria-label", `Toggle chapter order (currently ${dirText})`);
    }
  }

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

  function showSuccess(message, duration = 3500) {
    statusBanner.textContent = message;
    statusBanner.className = "status-banner success";
    statusBanner.classList.remove("hidden");
    if (duration > 0) {
      setTimeout(() => {
        statusBanner.classList.add("hidden");
      }, duration);
    }
  }

  function clearError() {
    statusBanner.textContent = "";
    statusBanner.classList.add("hidden");
  }

  // Profile State
  let currentProfile = {
    name: "User",
    has_avatar: false,
    avatar_url: null
  };
  let pendingAvatarBase64 = null;
  let pendingRemoveAvatar = false;

  function updateProfileUI(profile) {
    if (!profile) return;
    currentProfile = {
      name: profile.name || "User",
      has_avatar: Boolean(profile.has_avatar),
      avatar_url: profile.avatar_url || (profile.has_avatar ? "/api/profile/avatar" : null)
    };

    if (headerProfileName) {
      headerProfileName.textContent = currentProfile.name;
    }
    if (profileDropdownName) {
      profileDropdownName.textContent = currentProfile.name;
    }

    if (currentProfile.has_avatar && currentProfile.avatar_url) {
      const avatarSrc = `${currentProfile.avatar_url}?t=${Date.now()}`;
      if (headerAvatarImg) {
        headerAvatarImg.src = avatarSrc;
        headerAvatarImg.classList.remove("hidden");
      }
      if (headerAvatarDefault) {
        headerAvatarDefault.classList.add("hidden");
      }
    } else {
      if (headerAvatarImg) {
        headerAvatarImg.src = "";
        headerAvatarImg.classList.add("hidden");
      }
      if (headerAvatarDefault) {
        headerAvatarDefault.classList.remove("hidden");
      }
    }
  }

  // Settings State (Theme: crimson/kuromi)
  let currentSettings = {
    theme: "crimson"
  };

  function applyTheme(themeId) {
    const validTheme = (themeId === "kuromi") ? "kuromi" : "crimson";
    currentSettings.theme = validTheme;
    document.documentElement.setAttribute("data-theme", validTheme);

    document.querySelectorAll("#settings-theme-group .settings-option-btn").forEach((btn) => {
      const val = btn.getAttribute("data-theme-val");
      const isActive = val === validTheme;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-checked", isActive ? "true" : "false");
    });
  }

  function applySettings(settings) {
    if (!settings) return;
    if (settings.theme) applyTheme(settings.theme);
  }

  async function loadSettings() {
    // 1. Immediately apply cached settings to avoid flash
    try {
      const cached = localStorage.getItem("local_manga_settings");
      if (cached) {
        const parsed = JSON.parse(cached);
        applySettings(parsed);
      }
    } catch {}

    // 2. Fetch authoritative settings from server
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const data = await res.json();
        applySettings(data);
        try {
          localStorage.setItem("local_manga_settings", JSON.stringify(data));
        } catch {}
      }
    } catch {}
  }

  async function updateTheme(themeId) {
    applyTheme(themeId);

    try {
      localStorage.setItem("local_manga_settings", JSON.stringify(currentSettings));
    } catch {}

    try {
      await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme: currentSettings.theme })
      });
    } catch (err) {
      console.error("Failed to save theme setting to server:", err);
    }
  }

  async function loadProfile() {
    try {
      const res = await fetch("/api/profile");
      if (res.ok) {
        const data = await res.json();
        updateProfileUI(data);
        try {
          localStorage.setItem("local_manga_profile", JSON.stringify(data));
        } catch {}
        return;
      }
    } catch {}

    // Fallback to localStorage if offline/error
    try {
      const saved = localStorage.getItem("local_manga_profile");
      if (saved) {
        const parsed = JSON.parse(saved);
        updateProfileUI(parsed);
        return;
      }
    } catch {}

    updateProfileUI({ name: "User", has_avatar: false, avatar_url: null });
  }

  function toggleProfileDropdown(force) {
    if (!profileDropdown) return;
    const isCurrentlyOpen = !profileDropdown.classList.contains("hidden");
    const nextOpen = typeof force === "boolean" ? force : !isCurrentlyOpen;

    if (nextOpen) {
      profileDropdown.classList.remove("hidden");
      if (headerProfileBtn) headerProfileBtn.setAttribute("aria-expanded", "true");
    } else {
      profileDropdown.classList.add("hidden");
      if (headerProfileBtn) headerProfileBtn.setAttribute("aria-expanded", "false");
    }
  }

  function closeAllModals() {
    if (modalProfile) modalProfile.classList.add("hidden");
    if (modalSettings) modalSettings.classList.add("hidden");
    if (modalRemote) modalRemote.classList.add("hidden");
    if (modalShortcuts) modalShortcuts.classList.add("hidden");
    if (modalOverlay) modalOverlay.classList.add("hidden");
    if (previouslyFocusedElement && typeof previouslyFocusedElement.focus === "function") {
      try {
        previouslyFocusedElement.focus();
      } catch {}
      previouslyFocusedElement = null;
    }
    toggleProfileDropdown(false);
  }

  function openProfileModal() {
    toggleProfileDropdown(false);
    pendingAvatarBase64 = null;
    pendingRemoveAvatar = false;

    if (profileNameInput) {
      profileNameInput.value = currentProfile.name || "User";
    }
    if (profileAvatarInput) {
      profileAvatarInput.value = "";
    }
    if (profileModalError) {
      profileModalError.textContent = "";
      profileModalError.classList.add("hidden");
    }

    if (currentProfile.has_avatar && currentProfile.avatar_url) {
      if (profileModalAvatarImg) {
        profileModalAvatarImg.src = `${currentProfile.avatar_url}?t=${Date.now()}`;
        profileModalAvatarImg.classList.remove("hidden");
      }
      if (profileModalAvatarDefault) {
        profileModalAvatarDefault.classList.add("hidden");
      }
      if (btnRemoveAvatar) {
        btnRemoveAvatar.classList.remove("hidden");
      }
    } else {
      if (profileModalAvatarImg) {
        profileModalAvatarImg.src = "";
        profileModalAvatarImg.classList.add("hidden");
      }
      if (profileModalAvatarDefault) {
        profileModalAvatarDefault.classList.remove("hidden");
      }
      if (btnRemoveAvatar) {
        btnRemoveAvatar.classList.add("hidden");
      }
    }

    if (modalSettings) modalSettings.classList.add("hidden");
    if (modalOverlay) modalOverlay.classList.remove("hidden");
    if (modalProfile) modalProfile.classList.remove("hidden");
    if (profileNameInput) profileNameInput.focus();
  }

  function showLibraryPathError(message) {
    if (libraryPathError) {
      libraryPathError.textContent = message;
      libraryPathError.classList.remove("hidden");
    }
    if (inputLibraryPath) {
      inputLibraryPath.classList.add("input-error");
    }
  }

  function hideLibraryPathError() {
    if (libraryPathError) {
      libraryPathError.textContent = "";
      libraryPathError.classList.add("hidden");
    }
    if (inputLibraryPath) {
      inputLibraryPath.classList.remove("input-error");
    }
  }

  async function openSettingsModal() {
    toggleProfileDropdown(false);
    if (modalProfile) modalProfile.classList.add("hidden");

    applySettings(currentSettings);
    hideLibraryPathError();
    if (btnApplyLibraryPath) btnApplyLibraryPath.disabled = false;
    if (btnChangeFolder) btnChangeFolder.disabled = false;

    if (settingsLibraryPath) {
      settingsLibraryPath.textContent = "Loading...";
      try {
        const res = await fetch("/api/library");
        if (res.ok) {
          const data = await res.json();
          if (data && data.library_path) {
            settingsLibraryPath.textContent = data.library_path;
            if (inputLibraryPath) {
              inputLibraryPath.value = data.library_path;
            }
          } else {
            settingsLibraryPath.textContent = "No folder selected";
            if (inputLibraryPath) {
              inputLibraryPath.value = "";
            }
          }
        }
      } catch {
        settingsLibraryPath.textContent = "Unavailable";
      }
    }

    if (modalOverlay) modalOverlay.classList.remove("hidden");
    if (modalSettings) modalSettings.classList.remove("hidden");
  }

  // Shared Keyboard Shortcut Registry (Single Source of Truth)
  const KEYBOARD_SHORTCUTS = [
    // Reader navigation
    {
      id: "prev-chapter",
      category: "Reader navigation",
      description: "Navigate to previous chapter",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["←"] }
      ],
      matches: (e) => e.key === "ArrowLeft"
    },
    {
      id: "next-chapter",
      category: "Reader navigation",
      description: "Navigate to next chapter",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["→"] }
      ],
      matches: (e) => e.key === "ArrowRight"
    },
    {
      id: "scroll-up",
      category: "Reader navigation",
      description: "Scroll up (hold for continuous scroll)",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["↑"] }
      ],
      matches: (e) => !e.shiftKey && e.key === "ArrowUp"
    },
    {
      id: "scroll-down",
      category: "Reader navigation",
      description: "Scroll down (hold for continuous scroll)",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["↓"] }
      ],
      matches: (e) => !e.shiftKey && e.key === "ArrowDown"
    },
    {
      id: "jump-top",
      category: "Reader navigation",
      description: "Jump directly to top of chapter",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["Shift", "↑"], separator: "+" }
      ],
      matches: (e) => e.shiftKey && e.key === "ArrowUp"
    },
    {
      id: "jump-bottom",
      category: "Reader navigation",
      description: "Jump directly to bottom of chapter",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["Shift", "↓"], separator: "+" }
      ],
      matches: (e) => e.shiftKey && e.key === "ArrowDown"
    },

    // Reading controls
    {
      id: "toggle-fullscreen",
      category: "Reading controls",
      description: "Toggle fullscreen reader",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["F"] }
      ],
      matches: (e) => !e.shiftKey && (e.key === "f" || e.key === "F")
    },
    {
      id: "toggle-bookmark",
      category: "Reading controls",
      description: "Toggle chapter bookmark",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["B"] }
      ],
      matches: (e) => !e.shiftKey && (e.key === "b" || e.key === "B")
    },
    {
      id: "toggle-read-status",
      category: "Reading controls",
      description: "Toggle chapter Read / Unread status",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["Shift", "R"], separator: "+" }
      ],
      matches: (e) => e.shiftKey && (e.key === "R" || e.key === "r")
    },
    {
      id: "toggle-reading-mode",
      category: "Reading controls",
      description: "Toggle Spaced / Seamless reading mode",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["Shift", "S"], separator: "+" }
      ],
      matches: (e) => e.shiftKey && (e.key === "S" || e.key === "s" || e.code === "KeyS")
    },

    // Zoom and screenshots
    {
      id: "zoom-in",
      category: "Zoom and screenshots",
      description: "Zoom in by 10% (up to 300%)",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["="] },
        { keys: ["+"] }
      ],
      matches: (e) => (
        (e.key === "=" || e.key === "+") ||
        e.key === "Add" ||
        e.code === "Equal" ||
        e.code === "NumpadAdd" ||
        e.code === "NumpadEqual" ||
        e.keyCode === 187 ||
        e.keyCode === 61 ||
        e.keyCode === 107 ||
        e.which === 187 ||
        e.which === 61 ||
        e.which === 107
      )
    },
    {
      id: "zoom-out",
      category: "Zoom and screenshots",
      description: "Zoom out by 10% (down to 50%)",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["-"] }
      ],
      matches: (e) => (
        (e.key === "-" || e.key === "_") ||
        e.key === "Subtract" ||
        e.code === "Minus" ||
        e.code === "NumpadSubtract" ||
        e.keyCode === 189 ||
        e.keyCode === 173 ||
        e.keyCode === 109 ||
        e.which === 189 ||
        e.which === 173 ||
        e.which === 109
      )
    },
    {
      id: "zoom-reset",
      category: "Zoom and screenshots",
      description: "Reset zoom to 100%",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["0"] }
      ],
      matches: (e) => (
        !e.shiftKey &&
        (
          e.key === "0" ||
          e.code === "Digit0" ||
          e.code === "Numpad0" ||
          e.keyCode === 48 ||
          e.keyCode === 96 ||
          e.which === 48 ||
          e.which === 96
        )
      )
    },
    {
      id: "save-screenshot",
      category: "Zoom and screenshots",
      description: "Save currently displayed page screenshot",
      context: "reader",
      contextLabel: "Reader view",
      displayKeyCombinations: [
        { keys: ["S"] }
      ],
      matches: (e) => !e.shiftKey && (e.key === "s" || e.key === "S")
    }
  ];

  function getCurrentViewName() {
    if (viewReader && !viewReader.classList.contains("hidden")) return "reader";
    if (viewChapters && !viewChapters.classList.contains("hidden")) return "chapters";
    return "library";
  }

  function renderShortcutsOverlay() {
    if (!modalShortcutsBody) return;
    const currentView = getCurrentViewName();
    modalShortcutsBody.innerHTML = "";

    const categories = [];
    const categoryMap = new Map();

    KEYBOARD_SHORTCUTS.forEach((item) => {
      if (!categoryMap.has(item.category)) {
        categoryMap.set(item.category, []);
        categories.push(item.category);
      }
      categoryMap.get(item.category).push(item);
    });

    categories.forEach((catName) => {
      const items = categoryMap.get(catName);
      const groupEl = document.createElement("div");
      groupEl.className = "shortcuts-group";

      const isCategoryActive = items.some((it) => {
        if (it.context === "all") return true;
        if (it.context === "reader" && currentView === "reader") return true;
        if (it.context === "library_or_series" && (currentView === "library" || currentView === "chapters")) return true;
        return it.context === currentView;
      });

      if (isCategoryActive) {
        groupEl.classList.add("active-context");
      }

      const headerEl = document.createElement("div");
      headerEl.className = "shortcuts-group-header";

      const titleEl = document.createElement("h3");
      titleEl.className = "shortcuts-group-title";
      titleEl.textContent = catName;

      const sampleItem = items[0];
      const allSameContext = items.every((it) => it.contextLabel === sampleItem.contextLabel);
      if (allSameContext && sampleItem.contextLabel) {
        const badgeEl = document.createElement("span");
        badgeEl.className = "shortcuts-group-context";
        badgeEl.textContent = sampleItem.contextLabel;
        headerEl.appendChild(titleEl);
        headerEl.appendChild(badgeEl);
      } else {
        headerEl.appendChild(titleEl);
      }

      groupEl.appendChild(headerEl);

      items.forEach((item) => {
        const rowEl = document.createElement("div");
        rowEl.className = "shortcut-row";
        rowEl.dataset.shortcutId = item.id;

        const isItemActive = (
          item.context === "all" ||
          (item.context === "reader" && currentView === "reader") ||
          (item.context === "library_or_series" && (currentView === "library" || currentView === "chapters")) ||
          item.context === currentView
        );

        if (isItemActive) {
          rowEl.classList.add("active-context");
        }

        const descEl = document.createElement("span");
        descEl.className = "shortcut-desc";
        descEl.textContent = item.description;

        const keysEl = document.createElement("span");
        keysEl.className = "shortcut-keys";

        item.displayKeyCombinations.forEach((combo, comboIdx) => {
          if (comboIdx > 0) {
            const orEl = document.createElement("span");
            orEl.className = "shortcut-key-or";
            orEl.textContent = "/";
            keysEl.appendChild(orEl);
          }

          combo.keys.forEach((k, kIdx) => {
            if (kIdx > 0) {
              const sepEl = document.createElement("span");
              sepEl.className = "shortcut-key-separator";
              sepEl.textContent = combo.separator || "+";
              keysEl.appendChild(sepEl);
            }
            const kbd = document.createElement("kbd");
            kbd.className = "shortcut-keycap";
            kbd.textContent = k;
            keysEl.appendChild(kbd);
          });
        });

        rowEl.appendChild(descEl);
        rowEl.appendChild(keysEl);
        groupEl.appendChild(rowEl);
      });

      modalShortcutsBody.appendChild(groupEl);
    });
  }

  function openShortcutsModal() {
    toggleProfileDropdown(false);
    if (modalProfile) modalProfile.classList.add("hidden");
    if (modalSettings) modalSettings.classList.add("hidden");
    if (modalRemote) modalRemote.classList.add("hidden");

    previouslyFocusedElement = document.activeElement;

    renderShortcutsOverlay();

    if (modalOverlay) modalOverlay.classList.remove("hidden");
    if (modalShortcuts) {
      modalShortcuts.classList.remove("hidden");
      if (btnCloseShortcutsModal) {
        btnCloseShortcutsModal.focus();
      } else {
        modalShortcuts.focus();
      }
    }
  }

  function closeShortcutsModal() {
    if (modalShortcuts) {
      modalShortcuts.classList.add("hidden");
    }
    if (modalOverlay) {
      modalOverlay.classList.add("hidden");
    }
    if (previouslyFocusedElement && typeof previouslyFocusedElement.focus === "function") {
      try {
        previouslyFocusedElement.focus();
      } catch {}
      previouslyFocusedElement = null;
    }
  }

  function toggleShortcutsModal() {
    if (modalShortcuts && !modalShortcuts.classList.contains("hidden")) {
      closeShortcutsModal();
    } else {
      openShortcutsModal();
    }
  }

  // Remote Series State & Modal Helpers
  function isRemoteSeries(seriesStr) {
    if (!seriesStr || typeof seriesStr !== "string") return false;
    const s = seriesStr.trim();
    return s.startsWith("remote:") || s.startsWith("http://") || s.startsWith("https://");
  }

  // Remote Supported Providers & Single Source of Truth
  let supportedProviders = [];
  const providerDisplayNames = {
    weebcentral: "WeebCentral",
    nhentai: "nhentai"
  };

  function setFormatsDisclosureExpanded(expanded) {
    if (!remoteFormatsToggle || !remoteFormatsContent) return;
    remoteFormatsToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    remoteFormatsToggle.classList.toggle("expanded", expanded);
    remoteFormatsContent.classList.toggle("hidden", !expanded);
  }

  function toggleFormatsDisclosure() {
    if (!remoteFormatsToggle) return;
    const isExpanded = remoteFormatsToggle.getAttribute("aria-expanded") === "true";
    setFormatsDisclosureExpanded(!isExpanded);
  }

  async function loadSupportedProviders() {
    try {
      const res = await fetch("/api/remote/providers");
      if (res.ok) {
        const data = await res.json();
        if (data && Array.isArray(data.providers)) {
          supportedProviders = data.providers;
          data.providers.forEach((p) => {
            if (p && p.id && p.name) {
              providerDisplayNames[p.id.toLowerCase().trim()] = p.name;
            }
          });
          renderSupportedSources();
          renderRecentRemoteList();
        }
      }
    } catch {
      renderSupportedSources();
    }
  }

  function renderSupportedSources() {
    const targetList = remoteFormatsList || document.getElementById("remote-formats-list") || document.getElementById("remote-sources-list");
    if (!targetList) return;
    const sources = (supportedProviders && supportedProviders.length > 0)
      ? supportedProviders
      : [
          { id: "weebcentral", name: "WeebCentral", url_type: "Series URL", url_pattern: "weebcentral.com/series/…" },
          { id: "nhentai", name: "nhentai", url_type: "Gallery URL", url_pattern: "nhentai.net/g/…" }
        ];

    targetList.innerHTML = "";
    sources.forEach((source) => {
      const item = document.createElement("div");
      item.className = "remote-format-item";
      item.setAttribute("role", "listitem");

      const header = document.createElement("div");
      header.className = "remote-format-header";

      const nameEl = document.createElement("span");
      nameEl.className = "remote-format-name";
      nameEl.textContent = source.name || source.id;

      const typeEl = document.createElement("span");
      typeEl.className = "remote-format-type";
      typeEl.textContent = source.url_type || "Series URL";

      header.appendChild(nameEl);
      header.appendChild(typeEl);
      item.appendChild(header);

      if (source.url_pattern) {
        const patternEl = document.createElement("code");
        patternEl.className = "remote-format-pattern";
        patternEl.textContent = source.url_pattern;
        item.appendChild(patternEl);
      }

      targetList.appendChild(item);
    });
  }

  function getProviderDisplayName(item) {
    if (!item) return "";
    let providerId = "";
    if (item.provider && typeof item.provider === "string") {
      providerId = item.provider.toLowerCase().trim();
    } else if (item.id && typeof item.id === "string" && item.id.startsWith("remote:")) {
      const parts = item.id.split(":");
      if (parts.length >= 2 && parts[1]) {
        providerId = parts[1].toLowerCase().trim();
      }
    } else if (item.url && typeof item.url === "string") {
      if (item.url.includes("weebcentral.com")) providerId = "weebcentral";
      else if (item.url.includes("nhentai.net")) providerId = "nhentai";
    }

    if (providerDisplayNames[providerId]) {
      return providerDisplayNames[providerId];
    }
    if (providerId === "weebcentral") return "WeebCentral";
    if (providerId === "nhentai") return "nhentai";
    return "";
  }

  const RECENT_REMOTE_STORAGE_KEY = "local_manga_recent_remote";

  function getRecentRemoteSeries() {
    try {
      const raw = localStorage.getItem(RECENT_REMOTE_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch {}
    return [];
  }

  function saveRecentRemoteSeries(seriesIdentifier, title, url, extra = {}) {
    if (!seriesIdentifier) return;
    try {
      const existing = getRecentRemoteSeries();
      const prevItem = existing.find((item) => item && item.id === seriesIdentifier);
      const list = existing.filter((item) => item && item.id !== seriesIdentifier);

      const resolvedTitle = (title && typeof title === "string" && !title.startsWith("remote:"))
        ? title.trim()
        : (prevItem && prevItem.title && !prevItem.title.startsWith("remote:"))
        ? prevItem.title
        : "";

      const resolvedUrl = (url && typeof url === "string")
        ? url.trim()
        : (prevItem && prevItem.url)
        ? prevItem.url
        : "";

      let resolvedPageCount = (extra && typeof extra.pageCount === "number" && extra.pageCount > 0)
        ? extra.pageCount
        : (extra && typeof extra.pages === "number" && extra.pages > 0)
        ? extra.pages
        : (prevItem && typeof prevItem.pageCount === "number")
        ? prevItem.pageCount
        : undefined;

      const newItem = {
        id: seriesIdentifier,
        title: resolvedTitle || seriesIdentifier,
        url: resolvedUrl
      };
      if (typeof resolvedPageCount === "number") {
        newItem.pageCount = resolvedPageCount;
      }
      if (extra && extra.provider) {
        newItem.provider = extra.provider;
      } else if (prevItem && prevItem.provider) {
        newItem.provider = prevItem.provider;
      }

      list.unshift(newItem);
      const trimmed = list.slice(0, 8);
      localStorage.setItem(RECENT_REMOTE_STORAGE_KEY, JSON.stringify(trimmed));
    } catch {}
  }

  function removeRecentRemoteSeries(seriesIdentifier) {
    try {
      const list = getRecentRemoteSeries().filter((item) => item && item.id !== seriesIdentifier);
      localStorage.setItem(RECENT_REMOTE_STORAGE_KEY, JSON.stringify(list));
    } catch {}
    renderRecentRemoteList();
  }

  function clearAllRecentRemoteSeries() {
    try {
      localStorage.removeItem(RECENT_REMOTE_STORAGE_KEY);
    } catch {}
    renderRecentRemoteList();
  }

  function renderRecentRemoteList() {
    if (!remoteRecentList || !remoteRecentSection) return;
    const recent = getRecentRemoteSeries();
    if (recent.length === 0) {
      remoteRecentSection.classList.add("hidden");
      remoteRecentList.innerHTML = "";
      return;
    }

    remoteRecentList.innerHTML = "";
    recent.forEach((item) => {
      if (!item) return;

      const row = document.createElement("div");
      row.className = "remote-recent-item";
      row.setAttribute("role", "listitem");

      const info = document.createElement("div");
      info.className = "remote-recent-info";

      // Display series or gallery title; internal identifiers must never be shown
      const titleEl = document.createElement("div");
      titleEl.className = "remote-recent-title";
      const rawTitle = (item.title || "").trim();
      const isInternalId = !rawTitle || rawTitle.startsWith("remote:");
      const displayTitle = isInternalId ? "Untitled Series" : rawTitle;
      titleEl.textContent = displayTitle;
      titleEl.title = displayTitle;

      info.appendChild(titleEl);

      // Subtitle with provider display name and page count (when available)
      const providerName = getProviderDisplayName(item);
      const pageCount = (typeof item.pageCount === "number" && item.pageCount > 0)
        ? item.pageCount
        : (typeof item.pages === "number" && item.pages > 0)
        ? item.pages
        : null;

      let metaText = "";
      if (providerName && pageCount !== null) {
        metaText = `${providerName} · ${pageCount} ${pageCount === 1 ? "page" : "pages"}`;
      } else if (providerName) {
        metaText = providerName;
      } else if (pageCount !== null) {
        metaText = `${pageCount} ${pageCount === 1 ? "page" : "pages"}`;
      }

      if (metaText) {
        const metaEl = document.createElement("div");
        metaEl.className = "remote-recent-meta";
        metaEl.textContent = metaText;
        info.appendChild(metaEl);
      }

      const actions = document.createElement("div");
      actions.className = "remote-recent-actions";

      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "btn-recent-open";
      openBtn.textContent = "Open";
      openBtn.setAttribute("aria-label", `Open ${displayTitle}`);
      openBtn.addEventListener("click", () => {
        closeAllModals();
        window.location.hash = `#/series/${encodeURIComponent(item.id)}`;
      });

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "btn-recent-remove";
      removeBtn.title = "Remove from recents";
      removeBtn.setAttribute("aria-label", `Remove ${displayTitle} from recent series`);
      removeBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M18 6 6 18M6 6l12 12"/>
        </svg>
      `;
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        removeRecentRemoteSeries(item.id);
      });

      actions.appendChild(openBtn);
      actions.appendChild(removeBtn);

      row.appendChild(info);
      row.appendChild(actions);
      remoteRecentList.appendChild(row);
    });

    remoteRecentSection.classList.remove("hidden");
  }

  function setRemoteModalError(message) {
    if (!remoteModalError) return;
    remoteModalError.textContent = message || "";
    remoteModalError.classList.toggle("hidden", !message);
  }

  function openRemoteModal() {
    toggleProfileDropdown(false);
    if (modalProfile) modalProfile.classList.add("hidden");
    if (modalSettings) modalSettings.classList.add("hidden");

    if (remoteUrlInput) {
      remoteUrlInput.value = "";
    }
    setRemoteModalError("");
    setFormatsDisclosureExpanded(false);
    renderSupportedSources();
    renderRecentRemoteList();

    if (modalOverlay) modalOverlay.classList.remove("hidden");
    if (modalRemote) modalRemote.classList.remove("hidden");
    if (remoteUrlInput) remoteUrlInput.focus();
  }

  async function resolveAndOpenRemote(inputStr) {
    const raw = (inputStr || "").trim();
    if (!raw) {
      setRemoteModalError("Please enter a remote series or gallery URL.");
      return;
    }

    // Client-side quick checks & normalization
    let target = raw;
    if (target.startsWith("weebcentral.com/") || target.startsWith("www.weebcentral.com/")) {
      target = `https://${target}`;
    } else if (target.startsWith("nhentai.net/") || target.startsWith("www.nhentai.net/")) {
      target = `https://${target}`;
    }

    if (target.startsWith("http://")) {
      setRemoteModalError("Insecure HTTP is not allowed. Only HTTPS remote URLs are supported.");
      return;
    }

    if (target.startsWith("https://")) {
      try {
        const parsed = new URL(target);
        const host = parsed.hostname.toLowerCase();
        const isWeebCentral = host === "weebcentral.com" || host.endsWith(".weebcentral.com");
        const isNhentai = host === "nhentai.net" || host.endsWith(".nhentai.net");

        if (!isWeebCentral && !isNhentai) {
          setRemoteModalError(`Unsupported provider '${host}'. Only WeebCentral and nhentai URLs are currently supported.`);
          return;
        }

        if (isWeebCentral && !parsed.pathname.startsWith("/series/")) {
          setRemoteModalError("URL must point to a WeebCentral series page (e.g. https://weebcentral.com/series/<id>).");
          return;
        }

        if (isNhentai && !/^\/(?:g|api\/gallery|api\/v2\/galleries)\/\d+/.test(parsed.pathname)) {
          setRemoteModalError("URL must point to an nhentai gallery page (e.g. https://nhentai.net/g/<id>/).");
          return;
        }
      } catch {
        setRemoteModalError("Malformed URL format.");
        return;
      }
    } else if (target.startsWith("remote:nhentai:")) {
      const gId = target.slice("remote:nhentai:".length).trim();
      if (!/^\d+$/.test(gId)) {
        setRemoteModalError("nhentai identifier must be numeric (e.g. remote:nhentai:177013).");
        return;
      }
    } else if (!target.startsWith("remote:weebcentral:")) {
      // If it looks like a clean identifier, prefix with remote:weebcentral:
      if (/^[a-zA-Z0-9_-]+$/.test(target)) {
        target = `remote:weebcentral:${target}`;
      } else {
        setRemoteModalError("Please enter a valid remote URL (e.g. https://weebcentral.com/series/... or https://nhentai.net/g/...).");
        return;
      }
    }

    setRemoteModalError("");
    if (btnLoadRemote) btnLoadRemote.disabled = true;
    if (btnLoadRemoteText) btnLoadRemoteText.textContent = "Loading...";

    try {
      const res = await fetch(`/api/remote/resolve?url=${encodeURIComponent(target)}`);
      if (!res.ok) {
        let errMsg = `Failed to resolve series (${res.status})`;
        try {
          const errData = await res.json();
          if (errData && errData.error) errMsg = errData.error;
        } catch {}
        setRemoteModalError(errMsg);
        return;
      }

      const data = await res.json();
      const canonicalId = data.series_identifier || target;
      const title = (data.series && data.series.title) ? data.series.title : "";
      const url = (data.series && data.series.url) ? data.series.url : target;

      let pageCount = undefined;
      if (data.series) {
        if (data.series.metadata && typeof data.series.metadata.num_pages === "number" && data.series.metadata.num_pages > 0) {
          pageCount = data.series.metadata.num_pages;
        } else if (Array.isArray(data.series.chapters) && data.series.chapters[0] && Array.isArray(data.series.chapters[0].pages) && data.series.chapters[0].pages.length > 0) {
          pageCount = data.series.chapters[0].pages.length;
        }
      }

      saveRecentRemoteSeries(canonicalId, title, url, { pageCount, provider: data.provider });
      closeAllModals();
      window.location.hash = `#/series/${encodeURIComponent(canonicalId)}`;
    } catch (err) {
      setRemoteModalError(`Network error resolving remote series: ${err.message}`);
    } finally {
      if (btnLoadRemote) btnLoadRemote.disabled = false;
      if (btnLoadRemoteText) btnLoadRemoteText.textContent = "Open Series";
    }
  }

  async function saveProfile() {
    if (!btnSaveProfile) return;
    btnSaveProfile.disabled = true;
    if (profileModalError) {
      profileModalError.textContent = "";
      profileModalError.classList.add("hidden");
    }

    const newName = profileNameInput ? profileNameInput.value.trim() || "User" : "User";
    const payload = {
      name: newName,
      remove_avatar: pendingRemoveAvatar
    };
    if (pendingAvatarBase64) {
      payload.avatar = pendingAvatarBase64;
    }

    try {
      const res = await fetch("/api/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        let errMsg = `Failed to save profile (${res.status})`;
        try {
          const errData = await res.json();
          if (errData && errData.error) errMsg = errData.error;
        } catch {}
        if (profileModalError) {
          profileModalError.textContent = errMsg;
          profileModalError.classList.remove("hidden");
        }
        return;
      }

      const updated = await res.json();
      updateProfileUI(updated);
      try {
        localStorage.setItem("local_manga_profile", JSON.stringify(updated));
      } catch {}
      closeAllModals();
      showSuccess("Profile saved");
    } catch (err) {
      if (profileModalError) {
        profileModalError.textContent = `Error saving profile: ${err.message}`;
        profileModalError.classList.remove("hidden");
      }
    } finally {
      if (btnSaveProfile) btnSaveProfile.disabled = false;
    }
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

  // Held Arrow Key Smooth Continuous Scrolling State and Helpers
  let heldArrowKey = null;
  let heldScrollRafId = null;
  let lastHeldScrollTime = 0;

  function stopHeldArrowScroll() {
    if (heldScrollRafId) {
      cancelAnimationFrame(heldScrollRafId);
      heldScrollRafId = null;
    }
    heldArrowKey = null;
    lastHeldScrollTime = 0;
  }

  function startHeldArrowScroll(key) {
    if (heldArrowKey === key && heldScrollRafId) {
      return;
    }
    heldArrowKey = key;
    lastHeldScrollTime = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();

    if (heldScrollRafId) {
      cancelAnimationFrame(heldScrollRafId);
      heldScrollRafId = null;
    }

    const scrollLoop = (timestamp) => {
      if (!heldArrowKey || !viewReader || viewReader.classList.contains("hidden")) {
        stopHeldArrowScroll();
        return;
      }
      const now = timestamp || ((typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now());
      const dt = Math.min(0.05, Math.max(0.001, (now - (lastHeldScrollTime || now)) / 1000));
      lastHeldScrollTime = now;

      const speed = Math.max(800, Math.round(window.innerHeight * 1.8));
      const distance = Math.round(speed * dt);

      if (distance > 0) {
        const dir = heldArrowKey === "ArrowUp" ? -1 : 1;
        window.scrollBy({ top: dir * distance, behavior: "instant" });
      }

      heldScrollRafId = requestAnimationFrame(scrollLoop);
    };

    heldScrollRafId = requestAnimationFrame(scrollLoop);
  }

  // View switcher
  function switchView(viewName) {
    stopHeldArrowScroll();
    clearError();
    const isReader = viewName === "reader";
    document.body.classList.toggle("reader-active", isReader);
    document.documentElement.classList.toggle("reader-active", isReader);
    document.body.classList.toggle("series-active", viewName === "chapters");
    viewLibrary.classList.toggle("hidden", viewName !== "library");
    viewChapters.classList.toggle("hidden", viewName !== "chapters");
    viewReader.classList.toggle("hidden", !isReader);

    if (viewName !== "library") {
      if (libraryUnavailable) {
        libraryUnavailable.classList.add("hidden");
      }
    }

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
      activeReaderComplete = null;
      activeReaderSuppressAutoComplete = null;
      resetReaderZoom();
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
      if (btnEditMetadata) {
        btnEditMetadata.classList.remove("hidden");
      }
      if (appHeader) {
        appHeader.style.removeProperty("background-color");
        appHeader.style.removeProperty("border-bottom-color");
      }
    } else {
      startSeriesScrollTransition();
    }

    if (viewName === "library") {
      currentSeries = null;
      currentChapter = null;
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
      document.webkitCurrentFullScreenElement ||
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

  function exitFullscreen() {
    const doc = document;
    if (!isFullscreenActive()) {
      return Promise.resolve();
    }
    try {
      let p = null;
      if (doc.exitFullscreen) {
        p = doc.exitFullscreen();
      } else if (doc.webkitExitFullscreen) {
        p = doc.webkitExitFullscreen();
      } else if (doc.mozCancelFullScreen) {
        p = doc.mozCancelFullScreen();
      } else if (doc.msExitFullscreen) {
        p = doc.msExitFullscreen();
      }
      if (p && typeof p.then === "function") {
        return p.catch(() => {});
      }
    } catch {
      try {
        if (doc.webkitExitFullscreen) {
          doc.webkitExitFullscreen();
        }
      } catch {}
    }
    return Promise.resolve();
  }

  function toggleFullscreen() {
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
      exitFullscreen();
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

  // Pin Series Action
  async function togglePinSeries(seriesName, shouldPin = null) {
    if (!seriesName) return;
    const currentlyPinned = pinnedSeriesSet.has(seriesName);
    const targetState = shouldPin !== null ? Boolean(shouldPin) : !currentlyPinned;

    if (targetState) {
      pinnedSeriesSet.add(seriesName);
    } else {
      pinnedSeriesSet.delete(seriesName);
    }
    updatePinButtons(seriesName, targetState);
    renderLibrarySeries();

    try {
      const res = await fetch("/api/pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ series: seriesName, pinned: targetState })
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.pinned_series)) {
          pinnedSeriesSet = new Set(data.pinned_series);
        }
        updatePinButtons(seriesName, pinnedSeriesSet.has(seriesName));
        renderLibrarySeries();
      }
    } catch (err) {
      if (currentlyPinned) {
        pinnedSeriesSet.add(seriesName);
      } else {
        pinnedSeriesSet.delete(seriesName);
      }
      updatePinButtons(seriesName, currentlyPinned);
      renderLibrarySeries();
      showError(`Failed to update pin state: ${err.message}`);
    }
  }

  function updatePinButtons(seriesName, isPinned) {
    const sName = seriesName || currentSeries;
    const pinned = typeof isPinned === "boolean" ? isPinned : (sName ? pinnedSeriesSet.has(sName) : false);
    if (currentSeries === sName && btnPinSeries && pinSeriesText) {
      btnPinSeries.classList.toggle("pinned", pinned);
      pinSeriesText.textContent = pinned ? "Pinned" : "Pin Series";
      btnPinSeries.title = pinned ? "Unpin series from library" : "Pin series to library";
      btnPinSeries.setAttribute("aria-label", pinned ? "Unpin series from library" : "Pin series to library");
    }
  }

  // Chapter Read / Unread Completion Helpers
  function isChapterCompleted(ch) {
    if (!ch) return false;
    const name = typeof ch === "string" ? ch : (ch.name || ch.id);
    if (!name) return false;
    const base = name.replace(/\.(cbz|cbr|zip|tar)$/i, "");
    if (currentSeriesUnread.has(name) || currentSeriesUnread.has(base)) return false;
    if (currentSeriesCompleted.has(name) || currentSeriesCompleted.has(base)) return true;
    if (currentSeriesProgressMap && (currentSeriesProgressMap.get(name) === 100 || currentSeriesProgressMap.get(base) === 100)) return true;
    return false;
  }

  async function toggleChapterCompleted(seriesName, chapterName, completed) {
    if (!seriesName || !chapterName) return;

    if (completed) {
      currentSeriesCompleted.add(chapterName);
      currentSeriesUnread.delete(chapterName);
    } else {
      currentSeriesCompleted.delete(chapterName);
      currentSeriesUnread.add(chapterName);
      if (typeof activeReaderSuppressAutoComplete === "function") {
        activeReaderSuppressAutoComplete();
      }
    }

    renderSeriesChaptersList();
    updateResumeReadingButton();

    try {
      const completeEndpoint = isRemoteSeries(seriesName) ? "/api/remote/complete" : "/api/complete";
      const res = await fetch(completeEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          series: seriesName,
          chapter: chapterName,
          completed: completed
        })
      });
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      if (data.success) {
        if (Array.isArray(data.completed_chapters)) {
          currentSeriesCompleted = new Set(data.completed_chapters);
        }
        if (Array.isArray(data.unread_chapters)) {
          currentSeriesUnread = new Set(data.unread_chapters);
        }
        renderSeriesChaptersList();
        updateResumeReadingButton();
        showSuccess(completed ? `Marked "${chapterName}" as read` : `Marked "${chapterName}" as unread`);
      }
    } catch (err) {
      if (completed) {
        currentSeriesCompleted.delete(chapterName);
        currentSeriesUnread.add(chapterName);
      } else {
        currentSeriesCompleted.add(chapterName);
        currentSeriesUnread.delete(chapterName);
      }
      renderSeriesChaptersList();
      updateResumeReadingButton();
      showError(`Failed to update chapter state: ${err.message}`);
    }
  }

  // Resume Reading Contextual Button State Machine
  function updateResumeReadingButton() {
    if (!btnResumeReading || !resumeReadingText) return;

    if (!currentSeriesChapters || currentSeriesChapters.length === 0) {
      btnResumeReading.disabled = true;
      btnResumeReading.classList.add("hidden");
      if (seriesCompletedBadge) seriesCompletedBadge.classList.add("hidden");
      return;
    }

    btnResumeReading.disabled = false;
    btnResumeReading.classList.remove("hidden");

    const naturalCompare = (a, b) => (a.name || "").localeCompare(b.name || "", undefined, { numeric: true, sensitivity: "base" });
    const isRemote = isRemoteSeries(currentSeries);
    const canonicalChapters = isRemote
      ? [...currentSeriesChapters]
      : [...currentSeriesChapters].sort(naturalCompare);

    const totalChapters = canonicalChapters.length;
    const allCompleted = totalChapters > 0 && canonicalChapters.every((ch) => isChapterCompleted(ch));

    const matchChapter = (ch, name) => {
      if (!ch || !name) return false;
      const chName = ch.name || ch.id;
      if (chName === name) return true;
      const stripExt = (s) => s.replace(/\.(cbz|cbr|zip|tar)$/i, "");
      return stripExt(chName) === stripExt(name);
    };

    const hasChapterProgress = (ch) => {
      if (!currentSeriesProgress) return false;
      const chName = ch.name || ch.id;
      if (currentSeriesProgress[chName]) return true;
      const baseName = chName.replace(/\.(cbz|cbr|zip|tar)$/i, "");
      return Boolean(currentSeriesProgress[baseName]);
    };

    // Identify the last-read chapter (the specific chapter visited most recently)
    let lastReadingChapter = null;
    if (currentSeriesLastRead) {
      lastReadingChapter = canonicalChapters.find((ch) => matchChapter(ch, currentSeriesLastRead)) || null;
    }
    if (!lastReadingChapter) {
      for (let i = canonicalChapters.length - 1; i >= 0; i--) {
        const ch = canonicalChapters[i];
        if (hasChapterProgress(ch)) {
          lastReadingChapter = ch;
          break;
        }
      }
    }

    // Case F: All chapters in the series have been read or marked as Read
    if (allCompleted) {
      if (seriesCompletedBadge) seriesCompletedBadge.classList.remove("hidden");
      btnResumeReading.classList.remove("btn-primary");
      btnResumeReading.classList.add("btn-secondary");
      resumeReadingText.textContent = "Read Again";
      const targetCh = lastReadingChapter || canonicalChapters[0];
      btnResumeReading.title = `Read series again from ${targetCh.title || targetCh.name}`;
      btnResumeReading.setAttribute("aria-label", `Read series again from ${targetCh.title || targetCh.name}`);
      btnResumeReading.onclick = () => {
        window.location.hash = `#/read/${encodeURIComponent(currentSeries)}/${encodeURIComponent(targetCh.name)}`;
      };
      return;
    }

    if (seriesCompletedBadge) seriesCompletedBadge.classList.add("hidden");
    btnResumeReading.classList.remove("btn-secondary");
    btnResumeReading.classList.add("btn-primary");

    // Case A: No chapters have been read or opened
    if (!lastReadingChapter) {
      const targetCh = canonicalChapters.find((ch) => !isChapterCompleted(ch)) || canonicalChapters[0];
      resumeReadingText.textContent = "Start Reading";
      btnResumeReading.title = `Start reading ${targetCh.title || targetCh.name}`;
      btnResumeReading.setAttribute("aria-label", `Start reading ${targetCh.title || targetCh.name}`);
      btnResumeReading.onclick = () => {
        window.location.hash = `#/read/${encodeURIComponent(currentSeries)}/${encodeURIComponent(targetCh.name)}`;
      };
      return;
    }

    // Reading in progress has occurred:
    // Determine whether to resume at lastReadingChapter or advance to next unread chapter.
    let targetCh = null;

    if (!isChapterCompleted(lastReadingChapter)) {
      // Case B: In middle of unread chapter.
      // Case D: Saved progress exists, explicitly marked Unread.
      // Case G: Series was finished, but user marked this chapter Unread.
      targetCh = lastReadingChapter;
    } else {
      // The last reading chapter is completed.
      const lastChName = lastReadingChapter.name || lastReadingChapter.id;
      const baseName = lastChName.replace(/\.(cbz|cbr|zip|tar)$/i, "");
      let progressPct = null;
      if (currentSeriesProgressMap) {
        if (currentSeriesProgressMap.has(lastChName)) {
          progressPct = currentSeriesProgressMap.get(lastChName);
        } else if (currentSeriesProgressMap.has(baseName)) {
          progressPct = currentSeriesProgressMap.get(baseName);
        }
      }

      if (progressPct != null && progressPct < 100) {
        // Case C: Reader reached a specific page (< 100%), but chapter is marked Read.
        // Resume at saved page within that chapter, preserving Read status.
        targetCh = lastReadingChapter;
      } else {
        // Case E: Naturally completed final page;
        // or Case G: Last reading chapter remains Read while another chapter is Unread.
        // Resume at next unread chapter in canonical reading order.
        const lastIdx = canonicalChapters.indexOf(lastReadingChapter);
        let nextUnread = null;
        for (let i = lastIdx + 1; i < canonicalChapters.length; i++) {
          if (!isChapterCompleted(canonicalChapters[i])) {
            nextUnread = canonicalChapters[i];
            break;
          }
        }
        if (!nextUnread) {
          for (let i = 0; i < lastIdx; i++) {
            if (!isChapterCompleted(canonicalChapters[i])) {
              nextUnread = canonicalChapters[i];
              break;
            }
          }
        }
        targetCh = nextUnread || lastReadingChapter;
      }
    }

    resumeReadingText.textContent = "Resume Reading";
    btnResumeReading.title = `Resume reading ${targetCh.title || targetCh.name}`;
    btnResumeReading.setAttribute("aria-label", `Resume reading ${targetCh.title || targetCh.name}`);
    btnResumeReading.onclick = () => {
      window.location.hash = `#/read/${encodeURIComponent(currentSeries)}/${encodeURIComponent(targetCh.name)}`;
    };
  }

  // Helper to fetch reading progress info for a series in library view
  async function fetchSeriesProgressInfo(seriesName, totalChapters) {
    const fallbackTotal = typeof totalChapters === "number" ? totalChapters : 0;
    try {
      const readerData = await fetchReaderData(seriesName);
      const progress = readerData && readerData.progress ? readerData.progress : {};
      const completedList = (readerData && Array.isArray(readerData.completed)) ? readerData.completed : [];
      const unreadList = (readerData && Array.isArray(readerData.unread)) ? readerData.unread : [];
      const completedSet = new Set(completedList);
      const unreadSet = new Set(unreadList);
      const progressChapters = Object.keys(progress);

      if (progressChapters.length === 0 && completedList.length === 0) {
        return {
          hasProgress: false,
          readCount: 0,
          unreadCount: fallbackTotal,
          allCompleted: false
        };
      }

      // Fetch chapters list to respect natural reading order
      const chRes = await fetch(`/api/chapters?series=${encodeURIComponent(seriesName)}`);
      if (!chRes.ok) {
        const readCount = completedList.length > 0 ? completedList.length : progressChapters.length;
        return {
          hasProgress: readCount > 0,
          readCount: readCount,
          unreadCount: Math.max(0, fallbackTotal - readCount),
          allCompleted: fallbackTotal > 0 && readCount >= fallbackTotal
        };
      }
      const chData = await chRes.json();
      const chapters = chData.chapters || [];
      if (chapters.length === 0) {
        return {
          hasProgress: false,
          readCount: 0,
          unreadCount: 0,
          allCompleted: false
        };
      }

      const isChapterDone = (ch) => {
        if (unreadSet.has(ch.name)) return false;
        if (completedSet.has(ch.name)) return true;
        return false;
      };

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

      const savedImage = (activeChapter && progress[activeChapter.name]) ? progress[activeChapter.name] : null;
      let percentage = 0;

      if (savedImage && activeChapter) {
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

      const matchedReadCount = chapters.filter((c) => {
        if (isChapterDone(c)) return true;
        if (activeChapter && c.name === activeChapter.name && percentage === 100 && !unreadSet.has(c.name)) return true;
        return false;
      }).length;
      const accurateUnreadCount = Math.max(0, chapters.length - matchedReadCount);
      const allDone = chapters.length > 0 && matchedReadCount === chapters.length;

      return {
        hasProgress: true,
        chapterName: activeChapter ? activeChapter.name : null,
        percentage: percentage,
        readCount: matchedReadCount,
        unreadCount: accurateUnreadCount,
        allCompleted: allDone
      };
    } catch {
      return {
        hasProgress: false,
        readCount: 0,
        unreadCount: fallbackTotal,
        allCompleted: false
      };
    }
  }

  // Action: Change Manga Library Directory
  async function changeMangaFolder() {
    if (btnChangeFolder) btnChangeFolder.disabled = true;
    if (btnReconnectFolder) btnReconnectFolder.disabled = true;

    try {
      const res = await fetch("/api/library", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "select" })
      });

      if (!res.ok) {
        let errMsg = `Failed to change folder (${res.status})`;
        try {
          const errJson = await res.json();
          if (errJson && errJson.error) errMsg = errJson.error;
        } catch {}
        showError(errMsg);
        return;
      }

      const data = await res.json();
      if (data.cancelled) {
        // User closed/cancelled folder picker
        return;
      }

      if (data.success) {
        showSuccess(`Manga folder updated: ${data.library_path}`);
        if (settingsLibraryPath) {
          settingsLibraryPath.textContent = data.library_path;
        }
        if (inputLibraryPath) {
          inputLibraryPath.value = data.library_path;
        }
        if (Array.isArray(data.pinned)) {
          pinnedSeriesSet = new Set(data.pinned);
        }
        await loadLibrary();
        closeAllModals();
      }
    } catch (err) {
      showError(`Error changing manga folder: ${err.message}`);
    } finally {
      if (btnChangeFolder) btnChangeFolder.disabled = false;
      if (btnReconnectFolder) btnReconnectFolder.disabled = false;
    }
  }

  // Action: Apply Editable Manga Library Path
  async function applyManualLibraryPath() {
    if (!inputLibraryPath) return;
    const rawVal = inputLibraryPath.value;
    const trimmedPath = rawVal ? rawVal.trim() : "";

    if (!trimmedPath) {
      showLibraryPathError("Please enter a library folder path");
      inputLibraryPath.focus();
      return;
    }

    // Reject URLs upfront on client
    if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(trimmedPath)) {
      showLibraryPathError("URLs cannot be used as library paths. Please enter a local filesystem directory.");
      inputLibraryPath.focus();
      return;
    }

    hideLibraryPathError();

    if (btnApplyLibraryPath) btnApplyLibraryPath.disabled = true;
    if (btnChangeFolder) btnChangeFolder.disabled = true;

    try {
      const res = await fetch("/api/library", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: trimmedPath })
      });

      if (!res.ok) {
        let errMsg = `Failed to switch library (${res.status})`;
        try {
          const errJson = await res.json();
          if (errJson && errJson.error) errMsg = errJson.error;
        } catch {}
        showLibraryPathError(errMsg);
        return;
      }

      const data = await res.json();
      if (data.success) {
        showSuccess(`Manga folder updated: ${data.library_path}`);
        if (settingsLibraryPath) {
          settingsLibraryPath.textContent = data.library_path;
        }
        if (inputLibraryPath) {
          inputLibraryPath.value = data.library_path;
        }
        if (Array.isArray(data.pinned)) {
          pinnedSeriesSet = new Set(data.pinned);
        }
        await loadLibrary();
        closeAllModals();
      } else {
        showLibraryPathError(data.message || "Failed to switch library");
      }
    } catch (err) {
      showLibraryPathError(`Error switching manga folder: ${err.message}`);
    } finally {
      if (btnApplyLibraryPath) btnApplyLibraryPath.disabled = false;
      if (btnChangeFolder) btnChangeFolder.disabled = false;
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

      // Check if configured library directory exists
      if (data.library_exists === false) {
        allSeriesList = [];
        seriesGrid.innerHTML = "";
        if (pinnedGrid) pinnedGrid.innerHTML = "";
        if (pinnedSection) pinnedSection.classList.add("hidden");
        libraryEmpty.classList.add("hidden");
        if (libraryNoResults) libraryNoResults.classList.add("hidden");
        if (libraryUnavailable) {
          libraryUnavailable.classList.remove("hidden");
          if (unavailableFolderPath) {
            if (data.library_path) {
              unavailableFolderPath.textContent = data.library_path;
              unavailableFolderPath.classList.remove("hidden");
            } else {
              unavailableFolderPath.textContent = "";
              unavailableFolderPath.classList.add("hidden");
            }
          }
        }
        librarySubtitle.textContent = "Folder unavailable";
        return;
      }

      if (libraryUnavailable) {
        libraryUnavailable.classList.add("hidden");
      }

      if (data.library_path) {
        if (settingsLibraryPath) {
          settingsLibraryPath.textContent = data.library_path;
        }
        if (inputLibraryPath && !inputLibraryPath.matches(":focus")) {
          inputLibraryPath.value = data.library_path;
        }
      }

      allSeriesList = data.series || [];
      if (Array.isArray(data.pinned)) {
        pinnedSeriesSet = new Set(data.pinned);
      } else {
        try {
          const pinRes = await fetch("/api/pinned");
          if (pinRes.ok) {
            const pinData = await pinRes.json();
            if (Array.isArray(pinData.pinned)) {
              pinnedSeriesSet = new Set(pinData.pinned);
            }
          }
        } catch {}
      }

      allSeriesList.forEach((s) => {
        s.unreadCount = s.chapter_count || 0;
      });

      updateLibrarySortUI();
      // Render library immediately using returned series data
      renderLibrarySeries();

      // Concurrently resolve existing progress data for all series in background
      if (allSeriesList.length > 0) {
        allSeriesList.forEach((s) => {
          fetchSeriesProgressInfo(s.name, s.chapter_count)
            .then((prog) => {
              s.progressInfo = prog;
              if (prog && typeof prog.unreadCount === "number") {
                s.unreadCount = prog.unreadCount;
              }
              updateSeriesCardProgress(s.name, prog);
              if (librarySortCriterion === "unread") {
                renderLibrarySeries();
              }
            })
            .catch(() => {});
        });
      }
    } catch (err) {
      showError(`Failed to load library: ${err.message}`);
      librarySubtitle.textContent = "Could not connect to the backend server.";
    }
  }

  // Update a series card across library grids when its progress information resolves
  function updateSeriesCardProgress(seriesName, prog) {
    const cards = document.querySelectorAll(".series-card");
    cards.forEach((targetCard) => {
      if (targetCard.dataset.seriesName !== seriesName) return;

      const coverWrapper = targetCard.querySelector(".series-cover-wrapper");
      const content = targetCard.querySelector(".series-card-content");
      if (!content) return;

      if (prog && prog.hasProgress && prog.chapterName) {
        const percent = typeof prog.percentage === "number" ? prog.percentage : 0;
        const targetChapter = prog.chapterName;
        const readUrl = `#/read/${encodeURIComponent(seriesName)}/${encodeURIComponent(targetChapter)}`;

        // Update or add progress edge bar on cover
        if (coverWrapper) {
          let edge = coverWrapper.querySelector(".series-cover-progress");
          if (!edge) {
            edge = document.createElement("div");
            edge.className = "series-cover-progress";
            edge.setAttribute("aria-hidden", "true");
            edge.innerHTML = `<div class="series-cover-progress-fill" style="width: ${percent}%;"></div>`;
            coverWrapper.appendChild(edge);
          } else {
            const fill = edge.querySelector(".series-cover-progress-fill");
            if (fill) fill.style.width = `${percent}%`;
          }
        }

        // Update status text
        let statusEl = content.querySelector(".series-card-status");
        if (statusEl) {
          statusEl.className = "series-card-status";
          statusEl.textContent = targetChapter;
        }

        // Add or update continue link
        let continueLink = content.querySelector(".series-card-continue");
        if (!continueLink) {
          continueLink = document.createElement("a");
          continueLink.className = "series-card-continue";
          continueLink.setAttribute("href", readUrl);
          continueLink.setAttribute("title", `Continue reading ${targetChapter}`);
          continueLink.innerHTML = `
            <span class="continue-text">Continue reading</span>
            <span class="continue-arrow" aria-hidden="true">→</span>
          `;
          continueLink.addEventListener("click", (e) => {
            e.stopPropagation();
            window.location.hash = continueLink.getAttribute("href");
          });
          content.appendChild(continueLink);
        } else {
          continueLink.setAttribute("href", readUrl);
          continueLink.setAttribute("title", `Continue reading ${targetChapter}`);
        }
      } else {
        let statusEl = content.querySelector(".series-card-status");
        if (statusEl) {
          statusEl.className = "series-card-status status-unstarted";
          statusEl.textContent = "Not started";
        }
        const continueLink = content.querySelector(".series-card-continue");
        if (continueLink) {
          continueLink.remove();
        }
        if (coverWrapper) {
          const edge = coverWrapper.querySelector(".series-cover-progress");
          if (edge) edge.remove();
        }
      }
    });
  }

  function createSeriesCard(s, isPinned) {
    const card = document.createElement("div");
    card.className = "series-card";
    card.dataset.seriesName = s.name;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");

    const displayName = s.displayName || s.name;
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

    const pinBtnHtml = `
      <button type="button" class="btn-card-pin ${isPinned ? "pinned" : ""}" aria-label="${isPinned ? "Unpin manga" : "Pin manga"}" title="${isPinned ? "Unpin manga" : "Pin manga"}">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="12" y1="17" x2="12" y2="22"></line>
          <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.89A2 2 0 0 1 15 10.77V6a3 3 0 0 0-6 0v4.77a2 2 0 0 1-1.11 1.79l-1.78.89A2 2 0 0 0 5 15.24Z"></path>
        </svg>
      </button>
    `;

    const coverHtml = s.has_cover && s.cover_url
      ? `<div class="series-cover-wrapper">
           <img class="series-cover-img" src="${s.cover_url}" alt="${escapeHtml(displayName)} cover" loading="lazy" />
           ${pinBtnHtml}
           ${progressEdgeHtml}
         </div>`
      : `<div class="series-cover-wrapper series-cover-placeholder">
           <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
             <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
             <path d="M6 6h10"/>
             <path d="M6 10h10"/>
           </svg>
           ${pinBtnHtml}
           ${progressEdgeHtml}
         </div>`;

    card.innerHTML = `
      ${coverHtml}
      <div class="series-card-content">
        <div class="series-card-title" title="${escapeHtml(displayName)}">${escapeHtml(displayName)}</div>
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
          const pinBtn = wrapper.querySelector(".btn-card-pin");
          wrapper.innerHTML = `
            <svg class="placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
              <path d="M6 6h10"/>
              <path d="M6 10h10"/>
            </svg>
          `;
          if (pinBtn) wrapper.appendChild(pinBtn);
          if (progEdge) wrapper.appendChild(progEdge);
        }
      });
    }

    const pinBtn = card.querySelector(".btn-card-pin");
    if (pinBtn) {
      pinBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        togglePinSeries(s.name);
      });
      pinBtn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          togglePinSeries(s.name);
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
      if (e.target.closest(".series-card-continue") || e.target.closest(".btn-card-pin")) return;
      window.location.hash = `#/series/${encodeURIComponent(s.name)}`;
    });

    card.addEventListener("keydown", (e) => {
      if (e.target.closest(".series-card-continue") || e.target.closest(".btn-card-pin")) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        window.location.hash = `#/series/${encodeURIComponent(s.name)}`;
      }
    });

    return card;
  }

  function renderLibrarySeries() {
    seriesGrid.innerHTML = "";
    if (pinnedGrid) pinnedGrid.innerHTML = "";

    if (allSeriesList.length === 0) {
      librarySubtitle.textContent = "0 series";
      libraryEmpty.classList.remove("hidden");
      if (pinnedSection) pinnedSection.classList.add("hidden");
      if (libraryNoResults) libraryNoResults.classList.add("hidden");
      return;
    }

    libraryEmpty.classList.add("hidden");

    // Local filter by search query
    let filtered = allSeriesList;
    const query = librarySearchQuery.trim().toLowerCase();
    if (query) {
      filtered = allSeriesList.filter((s) => {
        const title = (s.displayName || s.name).toLowerCase();
        return title.includes(query) || s.name.toLowerCase().includes(query);
      });
    }

    // Local sort
    filtered = [...filtered].sort((a, b) => {
      let cmp = 0;
      if (librarySortCriterion === "chapters") {
        const aCount = a.chapter_count || 0;
        const bCount = b.chapter_count || 0;
        cmp = aCount - bCount;
      } else if (librarySortCriterion === "unread") {
        const aUnread = typeof a.unreadCount === "number" ? a.unreadCount : (a.chapter_count || 0);
        const bUnread = typeof b.unreadCount === "number" ? b.unreadCount : (b.chapter_count || 0);
        cmp = aUnread - bUnread;
      } else {
        // "name"
        const aTitle = a.displayName || a.name;
        const bTitle = b.displayName || b.name;
        cmp = aTitle.localeCompare(bTitle, undefined, { numeric: true, sensitivity: "base" });
      }

      if (librarySortDirection === "desc") {
        cmp = -cmp;
      }

      // Stable alphabetical fallback for ties
      if (cmp === 0 && librarySortCriterion !== "name") {
        const aTitle = a.displayName || a.name;
        const bTitle = b.displayName || b.name;
        return aTitle.localeCompare(bTitle, undefined, { numeric: true, sensitivity: "base" });
      }

      return cmp;
    });

    // Partition into pinned and unpinned lists
    const pinnedList = filtered.filter((s) => pinnedSeriesSet.has(s.name));
    const unpinnedList = filtered.filter((s) => !pinnedSeriesSet.has(s.name));

    // Update metadata subtitle: quiet, natural casing (e.g. "12 series")
    const totalCount = allSeriesList.length;
    if (query) {
      librarySubtitle.textContent = `${filtered.length} of ${totalCount} ${totalCount === 1 ? "series" : "series"}`;
    } else {
      librarySubtitle.textContent = `${totalCount} ${totalCount === 1 ? "series" : "series"}`;
    }

    // Show/hide no results state
    if (filtered.length === 0 && query) {
      if (pinnedSection) pinnedSection.classList.add("hidden");
      if (libraryNoResults) {
        libraryNoResults.classList.remove("hidden");
        const querySpan = document.getElementById("no-results-query");
        if (querySpan) querySpan.textContent = librarySearchQuery;

        // If query looks like a remote URL or identifier, offer direct action
        const existingPrompt = libraryNoResults.querySelector(".search-remote-prompt");
        if (existingPrompt) existingPrompt.remove();

        const isRemoteQuery =
          query.includes("weebcentral.com") ||
          query.startsWith("remote:weebcentral:") ||
          query.includes("nhentai.net") ||
          query.startsWith("remote:nhentai:");
        if (isRemoteQuery) {
          const promptDiv = document.createElement("div");
          promptDiv.className = "search-remote-prompt";
          promptDiv.style.marginTop = "14px";
          const openRemoteBtn = document.createElement("button");
          openRemoteBtn.type = "button";
          openRemoteBtn.className = "btn btn-secondary btn-sm";
          openRemoteBtn.textContent = "Open Remote Series";
          openRemoteBtn.addEventListener("click", () => {
            resolveAndOpenRemote(librarySearchQuery);
          });
          promptDiv.appendChild(openRemoteBtn);
          libraryNoResults.appendChild(promptDiv);
        }
      }
      return;
    }

    if (libraryNoResults) {
      libraryNoResults.classList.add("hidden");
      const existingPrompt = libraryNoResults.querySelector(".search-remote-prompt");
      if (existingPrompt) existingPrompt.remove();
    }

    // Render pinned section
    if (pinnedSection && pinnedGrid) {
      if (pinnedList.length > 0) {
        pinnedSection.classList.remove("hidden");
        if (pinnedSectionCount) {
          pinnedSectionCount.textContent = pinnedList.length;
        }
        pinnedList.forEach((s) => {
          pinnedGrid.appendChild(createSeriesCard(s, true));
        });
      } else {
        pinnedSection.classList.add("hidden");
      }
    }

    // Render unpinned cards in normal series grid
    unpinnedList.forEach((s) => {
      seriesGrid.appendChild(createSeriesCard(s, false));
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
    const isRemote = isRemoteSeries(seriesName);
    switchView("chapters");

    // Hide metadata editing for remote series (read-only from provider)
    if (btnEditMetadata) {
      btnEditMetadata.classList.toggle("hidden", isRemote);
    }

    seriesTitle.textContent = isRemote ? "Loading remote series..." : seriesName;
    seriesMeta.textContent = isRemote ? "Loading remote chapters..." : "Loading chapters...";
    chaptersList.innerHTML = "";
    chaptersEmpty.classList.add("hidden");

    if (headerSeriesTitle) {
      headerSeriesTitle.textContent = isRemote ? "Remote Series" : seriesName;
      headerSeriesTitle.title = `Scroll to top`;
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

      if (!chaptersRes.ok) {
        let errMsg = `HTTP error ${chaptersRes.status}`;
        try {
          const errData = await chaptersRes.json();
          if (errData && errData.error) errMsg = errData.error;
        } catch {}
        throw new Error(errMsg);
      }
      const data = await chaptersRes.json();

      if (data && data.title) {
        seriesTitle.textContent = data.title;
        if (headerSeriesTitle) {
          headerSeriesTitle.textContent = data.title;
          headerSeriesTitle.title = `Scroll ${data.title} to top`;
        }
      }

      currentSeries = (isRemote && data && data.series) ? data.series : seriesName;
      if (isRemote) {
        const canonicalId = (data && data.series) ? data.series : seriesName;
        const sTitle = (data && data.title) ? data.title : "";
        let pageCount = undefined;
        if (data && Array.isArray(data.chapters) && data.chapters.length === 1 && typeof data.chapters[0].image_count === "number" && data.chapters[0].image_count > 0) {
          pageCount = data.chapters[0].image_count;
        }
        saveRecentRemoteSeries(canonicalId, sTitle, data ? data.url : "", { pageCount, provider: data ? data.provider : undefined });
        if (window.location.hash !== `#/series/${encodeURIComponent(canonicalId)}`) {
          history.replaceState(null, "", `#/series/${encodeURIComponent(canonicalId)}`);
        }
      }

      currentSeriesBookmarks = new Set(readerData.bookmarks || []);
      currentSeriesProgress = readerData.progress || {};
      currentSeriesCompleted = new Set([...(readerData.completed || []), ...currentSeriesCompleted]);
      currentSeriesUnread = new Set(readerData.unread || []);
      for (const comp of currentSeriesCompleted) {
        currentSeriesUnread.delete(comp);
      }
      currentSeriesLastRead = readerData.last_read || null;

      renderSeriesMetadata(readerData);

      const rawChapters = data.chapters || [];
      const seenIds = new Set();
      const chapters = [];
      for (const ch of rawChapters) {
        const id = ch.name || ch.id;
        if (id && !seenIds.has(id)) {
          seenIds.add(id);
          chapters.push(ch);
        }
      }

      chaptersList.innerHTML = "";

      if (chapters.length === 0) {
        seriesMeta.textContent = "0 chapters";
        chaptersEmpty.classList.remove("hidden");
        updatePinButtons();
        updateResumeReadingButton();
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

      currentSeriesChapters = chapters;
      currentSeriesProgressMap = chapterProgressMap;
      updateChapterOrderUI();
      updatePinButtons();
      renderSeriesChaptersList();
      updateResumeReadingButton();
    } catch (err) {
      showError(`Failed to load chapters: ${err.message}`);
      seriesMeta.textContent = "Error loading chapters.";
    }
  }

  function renderSeriesChaptersList() {
    if (!chaptersList) return;
    chaptersList.innerHTML = "";
    if (!currentSeriesChapters || currentSeriesChapters.length === 0) return;

    let sortedChapters;
    const isRemote = isRemoteSeries(currentSeries);
    if (isRemote) {
      // Provider returns chapters in natural reading order (ascending).
      // Preserve provider's sequence, and reverse it when user requests descending.
      sortedChapters = seriesChapterOrder === "desc"
        ? [...currentSeriesChapters].reverse()
        : [...currentSeriesChapters];
    } else {
      const naturalCompare = (a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
      sortedChapters = [...currentSeriesChapters].sort((a, b) => {
        const cmp = naturalCompare(a.name, b.name);
        return seriesChapterOrder === "desc" ? -cmp : cmp;
      });
    }

    sortedChapters.forEach((ch) => {
      const item = document.createElement("div");
      item.className = "chapter-item";
      item.setAttribute("role", "button");
      item.setAttribute("tabindex", "0");

      const isBookmarked = currentSeriesBookmarks.has(ch.name);
      const isDone = isChapterCompleted(ch);
      if (isDone) {
        item.classList.add("chapter-completed");
      }

      const hasProgress = currentSeriesProgressMap.has(ch.name);
      const progressPct = hasProgress ? currentSeriesProgressMap.get(ch.name) : null;
      let progressText = "";
      if (isDone) {
        progressText = "Read";
      } else if (hasProgress && progressPct != null) {
        progressText = `${progressPct}%`;
      }

      const pagesText = ch.image_count > 0
        ? `${ch.image_count} ${ch.image_count === 1 ? "page" : "pages"}`
        : (ch.date ? escapeHtml(ch.date) : "");

      const readToggleBtnHtml = `
        <button type="button" class="btn-chapter-read-toggle ${isDone ? "completed" : ""}" title="${isDone ? "Mark as Unread" : "Mark as Read"}" aria-label="${isDone ? "Mark " + escapeHtml(ch.title || ch.name) + " as unread" : "Mark " + escapeHtml(ch.title || ch.name) + " as read"}">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            ${isDone ? '<polyline points="20 6 9 17 4 12"></polyline>' : '<circle cx="12" cy="12" r="9"></circle>'}
          </svg>
        </button>
      `;

      item.innerHTML = `
        <div class="chapter-info">
          <button class="btn-chapter-bookmark ${isBookmarked ? "bookmarked" : ""}" title="${isBookmarked ? "Remove bookmark" : "Bookmark chapter"}" aria-label="${isBookmarked ? "Remove bookmark" : "Bookmark chapter"}">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
            </svg>
          </button>
          <span class="chapter-title">${escapeHtml(ch.title || ch.name)}</span>
        </div>
        <div class="chapter-actions">
          <span class="chapter-progress">${progressText}</span>
          <span class="chapter-pages">${pagesText}</span>
          ${readToggleBtnHtml}
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="chapter-arrow">
            <path d="M9 18l6-6-6-6"/>
          </svg>
        </div>
      `;

      // Bookmark button click
      const bookmarkBtn = item.querySelector(".btn-chapter-bookmark");
      if (bookmarkBtn) {
        bookmarkBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          const willBookmark = !currentSeriesBookmarks.has(ch.name);
          const result = await toggleBookmark(currentSeries, ch.name, willBookmark);
          if (result) {
            loadChapters(currentSeries);
          }
        });
      }

      // Read/Unread button click
      const readToggleBtn = item.querySelector(".btn-chapter-read-toggle");
      if (readToggleBtn) {
        readToggleBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          const targetStatus = !isDone;
          await toggleChapterCompleted(currentSeries, ch.name, targetStatus);
        });
      }

      // Row click navigates to chapter reader
      item.addEventListener("click", (e) => {
        if (e.target.closest(".btn-chapter-bookmark") || e.target.closest(".btn-chapter-read-toggle")) return;
        window.location.hash = `#/read/${encodeURIComponent(currentSeries)}/${encodeURIComponent(ch.name)}`;
      });

      // Keyboard navigation (Enter or Space)
      item.addEventListener("keydown", (e) => {
        if (e.target.closest(".btn-chapter-bookmark") || e.target.closest(".btn-chapter-read-toggle")) return;
        if ((e.key === "Enter" || e.key === " ") && e.target === item) {
          e.preventDefault();
          window.location.hash = `#/read/${encodeURIComponent(currentSeries)}/${encodeURIComponent(ch.name)}`;
        }
      });

      chaptersList.appendChild(item);
    });
  }

  // 3. Load Real Vertical Scroll Reader View with Reading Progress, Bookmark & Navigation
  async function loadReader(seriesName, chapterName) {
    currentSeries = seriesName;
    currentChapter = chapterName;
    switchView("reader");
    resetReaderZoom();

    readerSeriesName.textContent = seriesName;
    readerChapterName.textContent = chapterName;
    readerContainer.innerHTML = "";
    readerFooter.classList.add("hidden");
    if (readerProgressContainer) readerProgressContainer.classList.add("hidden");
    if (readerEmpty) readerEmpty.classList.add("hidden");
    readerLoading.classList.remove("hidden");
    let hasTriggeredAutoComplete = false;

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

      if (!imagesRes.ok) {
        let errMsg = `HTTP error ${imagesRes.status}`;
        try {
          const errData = await imagesRes.json();
          if (errData && errData.error) errMsg = errData.error;
        } catch {}
        throw new Error(errMsg);
      }
      const data = await imagesRes.json();

      if (chaptersData && chaptersData.title) {
        readerSeriesName.textContent = chaptersData.title;
      }
      const currentChObj = (chaptersData.chapters || []).find((c) => c.name === chapterName);
      if (currentChObj && currentChObj.title) {
        readerChapterName.textContent = currentChObj.title;
      }

      currentSeriesBookmarks = new Set(readerData.bookmarks || []);
      currentSeriesProgress = readerData.progress || {};
      currentSeriesCompleted = new Set(readerData.completed || []);
      currentSeriesUnread = new Set(readerData.unread || []);
      currentSeriesLastRead = readerData.last_read || chapterName;

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

        imgEl.onerror = () => {
          imgEl.classList.add("image-load-failed");
          let retryBtn = pageDiv.querySelector(".reader-image-retry");
          if (!retryBtn) {
            retryBtn = document.createElement("button");
            retryBtn.type = "button";
            retryBtn.className = "reader-image-retry";
            retryBtn.innerHTML = `
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M23 4v6h-6M1 20v-6h6"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
              </svg>
              <span>Failed to load page. Click to retry</span>
            `;
            retryBtn.addEventListener("click", () => {
              retryBtn.remove();
              imgEl.classList.remove("image-load-failed");
              const sep = img.url.includes("?") ? "&" : "?";
              imgEl.src = `${img.url}${sep}_retry=${Date.now()}`;
            });
            pageDiv.appendChild(retryBtn);
          }
        };

        imgEl.onload = () => {
          imgEl.classList.remove("image-load-failed");
          const retryBtn = pageDiv.querySelector(".reader-image-retry");
          if (retryBtn) retryBtn.remove();
        };

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

      // If the saved page being restored is the final page, merely opening/restoring the saved position
      // must NOT count as newly completing the chapter. Active reading navigation must trigger it.
      const isRestoringFinalPage = (targetPage !== null && initialPageIndex === images.length && images.length > 0);
      let canAutoComplete = !isRestoringFinalPage;

      function completeCurrentChapter() {
        if (!canAutoComplete || hasTriggeredAutoComplete) return;
        hasTriggeredAutoComplete = true;
        const chBase = chapterName.replace(/\.(cbz|cbr|zip|tar)$/i, "");
        const isAlreadyCompleted = currentSeriesCompleted.has(chapterName) || currentSeriesCompleted.has(chBase);
        const isExplicitUnread = currentSeriesUnread.has(chapterName) || currentSeriesUnread.has(chBase);

        if (!isAlreadyCompleted || isExplicitUnread) {
          // Immediately update in-memory state consistently
          currentSeriesCompleted.add(chapterName);
          currentSeriesCompleted.add(chBase);
          currentSeriesUnread.delete(chapterName);
          currentSeriesUnread.delete(chBase);
          if (currentSeriesProgressMap) {
            currentSeriesProgressMap.set(chapterName, 100);
            currentSeriesProgressMap.set(chBase, 100);
          }

          // Persist the completed status and clear the conflicting unread override
          const completeEndpoint = isRemoteSeries(seriesName) ? "/api/remote/complete" : "/api/complete";
          fetch(completeEndpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              series: seriesName,
              chapter: chapterName,
              completed: true
            })
          }).then((r) => r.ok ? r.json() : null).then((data) => {
            if (data && data.success) {
              if (Array.isArray(data.completed_chapters)) {
                currentSeriesCompleted = new Set(data.completed_chapters);
              }
              if (Array.isArray(data.unread_chapters)) {
                currentSeriesUnread = new Set(data.unread_chapters);
              }
            }
          }).catch((err) => {
            console.warn("Failed to persist chapter completion:", err);
          });
        }
      }

      activeReaderComplete = completeCurrentChapter;
      activeReaderSuppressAutoComplete = () => {
        canAutoComplete = false;
        hasTriggeredAutoComplete = true;
      };

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

            // Visiting or scrolling to earlier pages enables completion upon returning to the final page
            if (activeIndex < images.length) {
              canAutoComplete = true;
              hasTriggeredAutoComplete = false;
            }

            // Auto-complete chapter when reader reaches the final page during active reading
            if (activeIndex === images.length && images.length > 0) {
              completeCurrentChapter();
            }
          }

          if (filename && filename !== currentVisibleImage) {
            currentVisibleImage = filename;
            currentSeriesLastRead = chapterName;

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
              }).then((r) => r.ok ? r.json() : null).then((data) => {
                if (data && data.last_read) {
                  currentSeriesLastRead = data.last_read;
                }
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
      if (readerEmpty) readerEmpty.classList.remove("hidden");
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
      librarySortCriterion = e.target.value;
      saveLibrarySortPreference();
      renderLibrarySeries();
    });
  }

  if (librarySortDir) {
    librarySortDir.addEventListener("click", () => {
      librarySortDirection = librarySortDirection === "asc" ? "desc" : "asc";
      updateLibrarySortUI();
      saveLibrarySortPreference();
      renderLibrarySeries();
    });
  }

  if (btnChapterOrder) {
    btnChapterOrder.addEventListener("click", () => {
      seriesChapterOrder = seriesChapterOrder === "asc" ? "desc" : "asc";
      try {
        localStorage.setItem("local_manga_chapter_order", seriesChapterOrder);
      } catch {}
      updateChapterOrderUI();
      renderSeriesChaptersList();
    });
  }

  if (headerBackLink) {
    headerBackLink.addEventListener("click", () => {
      window.location.hash = "#/";
    });
  }

  // Reader Back Buttons
  async function navigateBackToChapters() {
    if (isFullscreenActive()) {
      await exitFullscreen();
    }
    if (currentSeries) {
      window.location.hash = `#/series/${encodeURIComponent(currentSeries)}`;
    } else {
      window.location.hash = "#/";
    }
  }

  btnReaderBack.addEventListener("click", () => {
    navigateBackToChapters();
  });
  btnReaderBottomBack.addEventListener("click", () => {
    if (typeof activeReaderComplete === "function") {
      activeReaderComplete();
    }
    navigateBackToChapters();
  });

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
    btnReaderFooterNext.addEventListener("click", () => {
      if (typeof activeReaderComplete === "function") {
        activeReaderComplete();
      }
      navigateToChapter(currentNextChapter);
    });
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

  // Reader Page Screenshot Saving
  let isSavingScreenshot = false;

  function getActiveVisiblePageInfo() {
    if (!currentChapterImages || currentChapterImages.length === 0) return null;

    const pageElements = Array.from(readerContainer.querySelectorAll(".reader-page"));
    if (pageElements.length === 0) {
      return {
        filename: currentVisibleImage || currentChapterImages[0].filename,
        index: 1
      };
    }

    const viewportCenter = window.innerHeight / 2;
    let bestPage = null;
    let minDistance = Infinity;

    for (const pageEl of pageElements) {
      const rect = pageEl.getBoundingClientRect();
      if (rect.bottom > 0 && rect.top < window.innerHeight) {
        const pageCenter = rect.top + rect.height / 2;
        const dist = Math.abs(pageCenter - viewportCenter);
        if (dist < minDistance) {
          minDistance = dist;
          bestPage = pageEl;
        }
      }
    }

    const targetFilename = bestPage ? bestPage.dataset.filename : (currentVisibleImage || currentChapterImages[0].filename);
    const targetIdx = currentChapterImages.findIndex((img) => img.filename === targetFilename) + 1;

    return {
      filename: targetFilename,
      index: targetIdx > 0 ? targetIdx : 1
    };
  }

  async function saveCurrentPageScreenshot() {
    if (isSavingScreenshot) return;
    if (!currentSeries || !currentChapter) return;

    const pageInfo = getActiveVisiblePageInfo();
    if (!pageInfo) {
      showError("No page available to save");
      return;
    }

    isSavingScreenshot = true;
    try {
      const res = await fetch("/api/screenshot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          series: currentSeries,
          chapter: currentChapter,
          page: pageInfo.filename,
          page_index: pageInfo.index,
          series_title: readerSeriesName ? readerSeriesName.textContent.trim() : "",
          chapter_title: readerChapterName ? readerChapterName.textContent.trim() : ""
        })
      });

      const data = await res.json().catch(() => null);
      if (!res.ok || !data || !data.success) {
        const msg = (data && data.error) ? data.error : `HTTP error ${res.status}`;
        showError(`Failed to save screenshot: ${msg}`);
        return;
      }

      showSuccess(`Saved ${data.filename || "screenshot"}`);
    } catch (err) {
      showError(`Failed to save screenshot: ${err.message}`);
    } finally {
      isSavingScreenshot = false;
    }
  }

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

    // Toggle Keyboard Shortcuts Overlay (global shortcut: Shift + / or ?)
    const isShortcutsShortcut = (
      e.key === "?" ||
      (e.shiftKey && (e.key === "/" || e.code === "Slash"))
    );

    if (isShortcutsShortcut) {
      e.preventDefault();
      toggleShortcutsModal();
      return;
    }

    // Modal trap / suppression: do not handle background shortcuts when modal is open
    if (modalShortcuts && !modalShortcuts.classList.contains("hidden")) {
      if (e.key === "Tab") {
        const focusables = Array.from(modalShortcuts.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ));
        if (focusables.length > 0) {
          const first = focusables[0];
          const last = focusables[focusables.length - 1];
          if (e.shiftKey && (document.activeElement === first || !modalShortcuts.contains(document.activeElement))) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && (document.activeElement === last || !modalShortcuts.contains(document.activeElement))) {
            e.preventDefault();
            first.focus();
          }
        }
      }
      return;
    }

    if (modalOverlay && !modalOverlay.classList.contains("hidden")) {
      return;
    }

    // Only active when Reader View is open
    if (viewReader.classList.contains("hidden")) {
      return;
    }

    const isZoomIn = (
      (e.key === "=" || e.key === "+") ||
      e.key === "Add" ||
      e.code === "Equal" ||
      e.code === "NumpadAdd" ||
      e.code === "NumpadEqual" ||
      e.keyCode === 187 ||
      e.keyCode === 61 ||
      e.keyCode === 107 ||
      e.which === 187 ||
      e.which === 61 ||
      e.which === 107
    );
    const isZoomOut = (
      (e.key === "-" || e.key === "_") ||
      e.key === "Subtract" ||
      e.code === "Minus" ||
      e.code === "NumpadSubtract" ||
      e.keyCode === 189 ||
      e.keyCode === 173 ||
      e.keyCode === 109 ||
      e.which === 189 ||
      e.which === 173 ||
      e.which === 109
    );
    const isZoomReset = (
      !e.shiftKey &&
      (
        e.key === "0" ||
        e.code === "Digit0" ||
        e.code === "Numpad0" ||
        e.keyCode === 48 ||
        e.keyCode === 96 ||
        e.which === 48 ||
        e.which === 96
      )
    );

    if (isZoomIn) {
      e.preventDefault();
      changeReaderZoom(10);
    } else if (isZoomOut) {
      e.preventDefault();
      changeReaderZoom(-10);
    } else if (isZoomReset) {
      e.preventDefault();
      resetReaderZoom(true);
    } else if (e.shiftKey && (e.key === "R" || e.key === "r")) {
      e.preventDefault();
      if (!currentSeries || !currentChapter) return;
      const isDone = isChapterCompleted(currentChapter);
      toggleChapterCompleted(currentSeries, currentChapter, !isDone);
    } else if (e.shiftKey && (e.key === "S" || e.key === "s" || e.code === "KeyS")) {
      e.preventDefault();
      const nextStyle = currentReadingStyle === "spaced" ? "seamless" : "spaced";
      applyReadingStyle(nextStyle, true);
    } else if (!e.shiftKey && (e.key === "s" || e.key === "S")) {
      e.preventDefault();
      saveCurrentPageScreenshot();
    } else if (e.shiftKey && e.key === "ArrowUp") {
      e.preventDefault();
      stopHeldArrowScroll();
      window.scrollTo({ top: 0, behavior: "instant" });
    } else if (e.shiftKey && e.key === "ArrowDown") {
      e.preventDefault();
      stopHeldArrowScroll();
      const maxScroll = Math.max(
        document.documentElement.scrollHeight,
        document.body.scrollHeight
      );
      window.scrollTo({ top: maxScroll, behavior: "instant" });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (e.repeat) {
        startHeldArrowScroll("ArrowUp");
      } else {
        stopHeldArrowScroll();
        const scrollDistance = Math.round(window.innerHeight * 0.75);
        window.scrollBy({ top: -scrollDistance, behavior: "smooth" });
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (e.repeat) {
        startHeldArrowScroll("ArrowDown");
      } else {
        stopHeldArrowScroll();
        const scrollDistance = Math.round(window.innerHeight * 0.75);
        window.scrollBy({ top: scrollDistance, behavior: "smooth" });
      }
    } else if (e.key === "ArrowLeft") {
      stopHeldArrowScroll();
      if (currentPrevChapter) {
        e.preventDefault();
        navigateToChapter(currentPrevChapter);
      }
    } else if (e.key === "ArrowRight") {
      stopHeldArrowScroll();
      if (currentNextChapter) {
        e.preventDefault();
        navigateToChapter(currentNextChapter);
      }
    } else if (e.key === "f" || e.key === "F") {
      stopHeldArrowScroll();
      e.preventDefault();
      toggleFullscreen();
    } else if (e.key === "b" || e.key === "B") {
      stopHeldArrowScroll();
      e.preventDefault();
      btnReaderBookmark.click();
    }
  });

  window.addEventListener("keyup", (e) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      if (heldArrowKey === e.key) {
        stopHeldArrowScroll();
      }
    }
  });

  window.addEventListener("blur", stopHeldArrowScroll);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stopHeldArrowScroll();
    }
  });

  // Series Action Bar Event Listeners
  if (btnPinSeries) {
    btnPinSeries.addEventListener("click", () => {
      if (currentSeries) {
        togglePinSeries(currentSeries);
      }
    });
  }

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

  // Change library folder buttons & editable path form
  if (btnChangeFolder) {
    btnChangeFolder.addEventListener("click", changeMangaFolder);
  }
  if (btnReconnectFolder) {
    btnReconnectFolder.addEventListener("click", changeMangaFolder);
  }
  if (formLibraryPath) {
    formLibraryPath.addEventListener("submit", (e) => {
      e.preventDefault();
      applyManualLibraryPath();
    });
  }
  if (btnApplyLibraryPath) {
    btnApplyLibraryPath.addEventListener("click", (e) => {
      e.preventDefault();
      applyManualLibraryPath();
    });
  }
  if (inputLibraryPath) {
    inputLibraryPath.addEventListener("input", () => {
      hideLibraryPathError();
    });
    inputLibraryPath.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        applyManualLibraryPath();
      }
    });
  }

  // Profile Header Control & Dropdown Events
  if (headerProfileBtn) {
    headerProfileBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleProfileDropdown();
    });
  }

  if (dropdownItemProfile) {
    dropdownItemProfile.addEventListener("click", (e) => {
      e.stopPropagation();
      openProfileModal();
    });
  }

  if (dropdownItemSettings) {
    dropdownItemSettings.addEventListener("click", (e) => {
      e.stopPropagation();
      openSettingsModal();
    });
  }

  if (btnOpenRemote) {
    btnOpenRemote.addEventListener("click", (e) => {
      e.stopPropagation();
      openRemoteModal();
    });
  }

  if (dropdownItemRemote) {
    dropdownItemRemote.addEventListener("click", (e) => {
      e.stopPropagation();
      openRemoteModal();
    });
  }

  if (dropdownItemShortcuts) {
    dropdownItemShortcuts.addEventListener("click", (e) => {
      e.stopPropagation();
      openShortcutsModal();
    });
  }

  // Modal Backdrop & Close Events
  if (modalOverlay) {
    modalOverlay.addEventListener("click", () => {
      closeAllModals();
    });
  }

  if (modalShortcuts) {
    modalShortcuts.addEventListener("click", (e) => {
      e.stopPropagation();
    });
  }

  if (btnCloseShortcutsModal) {
    btnCloseShortcutsModal.addEventListener("click", closeAllModals);
  }
  if (btnCloseShortcuts) {
    btnCloseShortcuts.addEventListener("click", closeAllModals);
  }

  if (btnCloseProfileModal) {
    btnCloseProfileModal.addEventListener("click", closeAllModals);
  }
  if (btnCancelProfile) {
    btnCancelProfile.addEventListener("click", closeAllModals);
  }
  if (btnSaveProfile) {
    btnSaveProfile.addEventListener("click", saveProfile);
  }

  if (btnCloseSettingsModal) {
    btnCloseSettingsModal.addEventListener("click", closeAllModals);
  }
  if (btnCloseSettings) {
    btnCloseSettings.addEventListener("click", closeAllModals);
  }

  if (remoteFormatsToggle) {
    remoteFormatsToggle.addEventListener("click", (e) => {
      e.preventDefault();
      toggleFormatsDisclosure();
    });
  }

  if (btnCloseRemoteModal) {
    btnCloseRemoteModal.addEventListener("click", closeAllModals);
  }
  if (btnCancelRemote) {
    btnCancelRemote.addEventListener("click", closeAllModals);
  }
  if (btnLoadRemote) {
    btnLoadRemote.addEventListener("click", () => {
      if (remoteUrlInput) resolveAndOpenRemote(remoteUrlInput.value);
    });
  }
  if (formRemoteSeries) {
    formRemoteSeries.addEventListener("submit", (e) => {
      e.preventDefault();
      if (remoteUrlInput) resolveAndOpenRemote(remoteUrlInput.value);
    });
  }
  if (remoteUrlInput) {
    remoteUrlInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        resolveAndOpenRemote(remoteUrlInput.value);
      }
    });
  }
  if (btnClearRemoteRecent) {
    btnClearRemoteRecent.addEventListener("click", clearAllRecentRemoteSeries);
  }

  // Profile Avatar Upload & Removal
  if (profileAvatarInput) {
    profileAvatarInput.addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      if (!file.type.startsWith("image/")) {
        if (profileModalError) {
          profileModalError.textContent = "Please select a valid image file.";
          profileModalError.classList.remove("hidden");
        }
        return;
      }

      const reader = new FileReader();
      reader.onload = (loadEvent) => {
        pendingAvatarBase64 = loadEvent.target.result;
        pendingRemoveAvatar = false;
        if (profileModalAvatarImg) {
          profileModalAvatarImg.src = pendingAvatarBase64;
          profileModalAvatarImg.classList.remove("hidden");
        }
        if (profileModalAvatarDefault) {
          profileModalAvatarDefault.classList.add("hidden");
        }
        if (btnRemoveAvatar) {
          btnRemoveAvatar.classList.remove("hidden");
        }
        if (profileModalError) {
          profileModalError.textContent = "";
          profileModalError.classList.add("hidden");
        }
      };
      reader.onerror = () => {
        if (profileModalError) {
          profileModalError.textContent = "Failed to read image file.";
          profileModalError.classList.remove("hidden");
        }
      };
      reader.readAsDataURL(file);
    });
  }

  if (btnRemoveAvatar) {
    btnRemoveAvatar.addEventListener("click", () => {
      pendingAvatarBase64 = null;
      pendingRemoveAvatar = true;
      if (profileAvatarInput) profileAvatarInput.value = "";
      if (profileModalAvatarImg) {
        profileModalAvatarImg.src = "";
        profileModalAvatarImg.classList.add("hidden");
      }
      if (profileModalAvatarDefault) {
        profileModalAvatarDefault.classList.remove("hidden");
      }
      btnRemoveAvatar.classList.add("hidden");
    });
  }

  // Click outside to close dropdown
  document.addEventListener("click", (e) => {
    if (profileDropdown && !profileDropdown.classList.contains("hidden")) {
      if (!profileDropdown.contains(e.target) && !headerProfileBtn.contains(e.target)) {
        toggleProfileDropdown(false);
      }
    }
  });

  // Escape key to dismiss dropdown or modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (profileDropdown && !profileDropdown.classList.contains("hidden")) {
        toggleProfileDropdown(false);
      } else if ((modalOverlay && !modalOverlay.classList.contains("hidden")) || (modalShortcuts && !modalShortcuts.classList.contains("hidden"))) {
        closeAllModals();
      }
    }
  });

  // Settings Theme Option Listeners
  document.querySelectorAll("#settings-theme-group .settings-option-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const val = btn.getAttribute("data-theme-val");
      if (val) updateTheme(val);
    });
  });

  // Check if server specified a startup route (e.g. CLI remote URL)
  async function checkStartupRoute() {
    if (window.location.hash && window.location.hash !== "#/" && window.location.hash !== "#") return;
    try {
      const res = await fetch("/api/status");
      if (res.ok) {
        const data = await res.json();
        if (data && data.startup_url && (!window.location.hash || window.location.hash === "#/" || window.location.hash === "#")) {
          const hashIdx = data.startup_url.indexOf("#");
          if (hashIdx !== -1) {
            window.location.hash = data.startup_url.slice(hashIdx);
          }
        }
      }
    } catch {}
  }

  // Expose helpers for external inspection and test harness
  if (typeof window !== "undefined") {
    window.KEYBOARD_SHORTCUTS = KEYBOARD_SHORTCUTS;
    window.openShortcutsModal = openShortcutsModal;
    window.closeShortcutsModal = closeShortcutsModal;
    window.toggleShortcutsModal = toggleShortcutsModal;
    window.renderShortcutsOverlay = renderShortcutsOverlay;
    window.applyManualLibraryPath = applyManualLibraryPath;
    window.showLibraryPathError = showLibraryPathError;
    window.hideLibraryPathError = hideLibraryPathError;
  }

  // Initial load
  updateLibrarySortUI();
  updateChapterOrderUI();
  loadSettings();
  loadProfile();
  loadSupportedProviders();
  checkStartupRoute();
  handleRoute();
});
