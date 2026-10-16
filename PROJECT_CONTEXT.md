# PROJECT_CONTEXT.md: Local Manga & Manhwa Reader (`{ index }`)

Technical documentation of current codebase architecture, implementation, storage, network APIs, security models, platform integrations, and operational procedures as of version 2.0.0.

---

## 1. Project Overview & Identity

### Name & Identity
- **Application Name**: `{ index }` (Local Manga & Manhwa Reader).
- **Favicon Artwork**: Japanese calligraphic **本** (hon / book / source) emblem with white strokes and a thick black sumi-e ink outline on a transparent canvas (`static/index-mark.svg`). Configured with explicit `color-scheme: light dark` to prevent Safari from adding synthetic white background squares.
- **Browser Tab Title**: `{ index }`.
- **Current Version**: `v2.0.0` (remote manga reading, provider architecture, SSRF security, CLI remote launching, and polished UI).

### Core Purpose & Problem Solved
Desktop and web-based comic/manga readers often require heavy database engines, cloud accounts, proprietary libraries, or invasive file re-organizations. `{ index }` is a zero-dependency, local-first web server and client built entirely with the Python 3 standard library and vanilla HTML5 / CSS3 / ES6 JavaScript.

The application serves two primary workflows without compromising simplicity or security:
1. **Local Library Reading**: Reads manga and manhwa directly from standard local directories and `.cbz` / `.zip` archives without extraction to disk, database migrations, or mutating user files.
2. **Remote Stream Reading**: Resolves and streams manga/manhwa chapters and galleries directly from authorized online providers (e.g., WeebCentral, nhentai) into the identical reading interface with connection-level SSRF defense, LRU/TTL chapter caching, and isolated reading state persistence.

### Core Design Principles & Constraints
1. **Zero External Dependencies**:
   - Backend requires standard Python 3.10+ only (`http.server`, `urllib`, `json`, `pathlib`, `zipfile`, `socket`, `ssl`, `ipaddress`, `argparse`). No `pip install`, `requirements.txt`, or binary wheels.
   - Frontend requires vanilla ES6+ JavaScript, modern CSS3 custom properties, and semantic HTML5. No Node.js build pipelines (`npm`, `vite`, `webpack`, `react`, etc.).
2. **Non-Destructive Operations**:
   - Local collections are strictly read-only. Covers, hero backgrounds, and pages are read directly from existing files. Reading state, bookmarks, and metadata are saved in `.reader/reader_data.json` alongside series, never modifying images or archive files.
3. **Decoupled Application State**:
   - Application configuration (`settings.json`), user profiles (`profile.json`, `avatar.jpg`), and remote reading progress (`remote_reader_data.json`) are stored outside the git repository and outside manga collections in OS-standard application directories.
4. **Reused Reader Interface**:
   - Remote manga streams use the exact same continuous vertical reader, segmented timeline, keyboard navigation, reading style toggle, bookmarks, and progress tracking as local manga.
5. **Defense-in-Depth Security**:
   - Local server binds strictly to localhost loopback (`127.0.0.1`).
   - Outbound remote requests use connection-level socket validation, blocking private/loopback/cloud-metadata IPs before TLS negotiation, enforcing HTTPS-only schemes, strict hostname allowlists, hop-limited redirect validation, and binary magic-byte image verification.

---

## 2. Architecture & System Components

### High-Level System Architecture

```
+----------------------------------------------------------------------------------------------------+
|                                         Browser Client                                             |
|                                                                                                    |
|  index.html / style.css                                                                            |
|  ├── Editorial Dark Shell (Header: [ { index } ] [ User Profile v ] )                              |
|  ├── View 1: Library View (Search, Unified Sort, Series Grid, Cover Thumbnails, "Remote" Button)   |
|  ├── View 2: Series View (Hero Backdrop, Cover Thumbnail, Metadata Display, Chapter List)         |
|  ├── View 3: Reader View (Sticky Header, Continuous Strip, Bottom Segmented Timeline)              |
|  ├── Modal 1: User Profile & Library Switcher Dialog                                               |
|  ├── Modal 2: Series Metadata Editor (Local series only)                                           |
|  └── Modal 3: Open Remote Manga Dialog (URL input, Supported Providers Disclosure, Recents List)    |
|                                                                                                    |
|  app.js                                                                                            |
|  ├── Hash Router (#/, #/series/:name, #/read/:name/:chapter)                                       |
|  ├── IntersectionObserver Page Tracker (Debounced progress persistence & auto-scroll resume)       |
|  ├── Recents Manager (localStorage: local_manga_recent_remote, max 8 items)                        |
|  └── Dual-Mode Client (Transparently routes between local and remote series identifiers)           |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  | HTTP REST API & Static Asset Requests
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                Python 3 Standard Library Server                                    |
|                                         (server.py)                                                |
|                                                                                                    |
|  MangaRequestHandler (ThreadingHTTPServer, BaseHTTPRequestHandler)                                 |
|  ├── Security Dispatcher (Path traversal checks, safe child validation, ZIP Slip checks)           |
|  ├── Static Asset Server (/index.html, /style.css, /app.js, /index-mark.svg)                       |
|  ├── Local API Router (/api/series, /api/library, /api/settings, /api/profile, etc.)               |
|  └── Remote API Router & Dual-Mode Proxy (/api/remote/*, transparent /api/* delegation)           |
+------------------------------------+-----------------------------------+---------------------------+
                                     |                                   |
              Local Manga Pipeline   v            Remote Manga Pipeline  v
+---------------------------------------------+ +----------------------------------------------------+
|            MangaLibrary Model               | |              RemoteReaderService                   |
|                                             | |             (providers/service.py)                 |
| ├── Filesystem Scanner (Dirs & Archives)    | | ├── Provider Registry (providers/registry.py)     |
| ├── In-Memory Zip Streaming (zipfile)       | | │   ├── WeebCentralProvider (weebcentral.py)       |
| ├── Natural Numerical Sorter                | | │   ├── NhentaiProvider (nhentai.py)               |
| ├── Fallback Resolvers (Cover / Backdrop)   | | │   └── MockProvider (mock.py, testing)            |
| └── Atomic JSON Writer (.reader_data.json)  | | ├── ChapterPageCache (providers/cache.py LRU/TTL)  |
+---------------------+-----------------------+ | ├── Secure Proxy & Streamer (image-proxy)          |
                      |                         | └── SSRF Security Transport (providers/security.py)|
                      v                         +------------------------+---------------------------+
+---------------------------------------------+                          |
|         Local Filesystem & Storage          |                          v HTTPS (Allowed Domains Only)
|                                             | +----------------------------------------------------+
| 1. Manga Library (Any local folder)         | |                 Remote Upstream                    |
|    Manga/                                   | |                                                    |
|    └── Series Name/                         | | • WeebCentral (weebcentral.com & image CDNs)       |
|        ├── Chapter 01/ (Images: 01.jpg)     | | • nhentai (nhentai.net & i*.nhentai.net CDNs)      |
|        ├── Chapter 02.cbz (ZIP Stream)      | +----------------------------------------------------+
|        └── .reader/reader_data.json         |
|                                             |
| 2. Decoupled Application Config             |
|    ~/Library/Application Support/           |
|    LocalMangaReader/                        |
|    ├── settings.json (Theme & Library path) |
|    ├── profile.json (User display name)     |
|    ├── avatar.jpg (User avatar image)       |
|    └── remote_reader_data.json              |
|        (Remote progress, bookmarks, styles) |
+---------------------------------------------+
```

### Communication & Data Flow

1. **Local Library Flow**:
   - User browses to `#/`: `app.js` requests `GET /api/series`.
   - `server.py` queries `MangaLibrary.list_series()`, scanning top-level folders in the active library.
   - User clicks a series (`#/series/<name>`): `app.js` fetches `GET /api/chapters?series=<name>` and `GET /api/reader-data?series=<name>`.
   - User opens a chapter (`#/read/<name>/<chapter>`): `app.js` fetches `GET /api/images?series=<name>&chapter=<chapter>`.
   - Pages render in the vertical DOM. As pages scroll past `IntersectionObserver`, `POST /api/progress` updates `<Series>/.reader/reader_data.json` atomically.

2. **Remote Manga Flow**:
   - User enters a URL in the Remote modal or launches `python3 server.py <url>`:
     - URL is checked against `default_registry.find_for_url(url)`.
     - `RemoteReaderService.resolve_series(url)` calls the matching provider's `get_series()` via `SecureHttpClient`.
     - Normalizes series metadata and constructs a canonical identifier: `remote:<provider_id>:<series_id>`.
     - Browser navigates to `#/series/remote%3A<provider_id>%3A<series_id>`.
   - Series Detail View:
     - `app.js` calls `GET /api/chapters?series=remote:...` and `GET /api/reader-data?series=remote:...`.
     - Server intercepts `is_remote_series(series)` and delegates directly to `remote_service.get_chapters()` and `remote_service.get_reader_data()`.
     - Cover image loads via `GET /api/cover?series=remote:...`, proxying through `remote_service.get_cover()`.
     - Metadata editing is automatically hidden in the UI (remote metadata is read-only).
   - Reader View:
     - `app.js` calls `GET /api/images?series=remote:...&chapter=<chapter_id>`.
     - `remote_service.get_chapter_pages()` checks `ChapterPageCache`. On a cache miss, it calls `provider.get_chapter_pages()`, caches the result, and returns page items with proxied URLs:
       `/api/remote/image-proxy?url=<quoted_cdn_url>&provider=<provider_id>`.
     - Browser streams images from the proxy endpoint. `server.py` validates the target URL and provider allowlist, checks magic bytes via `detect_image_format()`, and streams binary bytes with correct MIME type.
     - Progress (`POST /api/progress`), bookmarks (`POST /api/bookmark`), and style (`POST /api/style`) are stored in `remote_reader_data.json` keyed by `remote:<provider_id>:<series_id>`.

---

## 3. Technology Stack & Design Invariants

### Runtime & Core Stack
- **Backend Language**: Python 3.10+ (Standard Library only).
- **Core Standard Library Modules**:
  - `http.server.ThreadingHTTPServer`: Multi-threaded HTTP server preventing image streaming from blocking concurrent requests.
  - `http.server.BaseHTTPRequestHandler`: Low-level request dispatching and routing.
  - `http.client.HTTPSConnection`: Base connection class subclassed for socket-level SSRF defense.
  - `socket` & `ssl`: Direct IP connection and post-connect peer validation with TLS SNI wrapping.
  - `ipaddress`: Strict RFC IP classification against private, loopback, and metadata ranges.
  - `html.parser.HTMLParser`: Subclassed by `MiniHTMLTreeParser` for zero-dependency DOM tree generation.
  - `zipfile`: Direct in-memory streaming of `.cbz` and `.zip` archives.
  - `pathlib.Path`: Filesystem path manipulation and safe child traversal guardrails.
  - `json`: Atomic persistence of configuration and metadata.
  - `urllib.parse`: URL parsing, parameter extraction, and percent-encoding.
  - `argparse`: Command-line interface argument parsing.
- **Frontend Stack**:
  - Semantic HTML5, CSS3 with custom variables, and vanilla ES6+ JavaScript.
  - External Web Fonts: *Cormorant Garamond* (Editorial Serif headings) and *Inter* (Clean sans-serif UI).
  - No build tools, package managers, or frameworks.

### Invariants That Must Be Preserved
1. **Never Add Third-Party Dependencies**: No `requests`, `urllib3`, `BeautifulSoup`, `Pillow`, `Flask`, `FastAPI`, `npm`, or `pip` requirements.
2. **Never Write Into Manga Archives or Alter Media Files**: `.cbz` and `.zip` files must remain strictly untouched.
3. **Localhost Loopback Only**: The server must bind only to `127.0.0.1`. Never bind by default to `0.0.0.0`.
4. **Isolate User State From Code**: Never write user configuration, avatars, or reader data into the git working tree.
5. **Preserve CLI Non-Persistence**: CLI `--dir` overrides the library for that execution session only and must never overwrite `settings.json`.
6. **Dark Editorial Aesthetic**: Dark-mode only. Both Crimson (`#E53935`) and Kuromi (`#9B7EDB`) themes must share the neutral dark `#0E0E0E` foundation.
7. **Transparent Favicon**: The calligraphic **本** favicon (`static/index-mark.svg`) must retain transparent canvas and `color-scheme: light dark` declarations.

---

## 4. Complete Project File Structure

```text
local-manga-reader/
├── README.md                     # User documentation, quick-start guide, CLI reference
├── PROJECT_CONTEXT.md            # Comprehensive technical architecture, API, and developer guide
├── main.py                       # CLI entry point delegating directly to server.py
├── server.py                     # Core server, MangaLibrary model, API handlers, CLI runner
│
├── providers/                    # Remote manga provider subsystem package
│   ├── __init__.py               # Package exports (models, registry, cache, security, service)
│   ├── base.py                   # Normalized models (RemotePage, RemoteChapter, RemoteSeries, BaseProvider)
│   ├── cache.py                  # Thread-safe LRU/TTL ChapterPageCache with capacity bounds
│   ├── mock.py                   # MockProvider for offline verification and testing
│   ├── nhentai.py                # NhentaiProvider implementation (API v2 & HTML scraper)
│   ├── registry.py               # Thread-safe ProviderRegistry and URL resolution helpers
│   ├── security.py               # Connection-level SSRF protection, SecureHttpClient, IP filters
│   ├── service.py                # RemoteReaderService integrating providers with reader endpoints
│   └── weebcentral.py            # WeebCentralProvider implementation (HTMX & HTML scraper)
│
├── static/                       # Web client assets served by server.py
│   ├── index.html                # Single-page application markup shell and modals
│   ├── style.css                 # Editorial typography, themes (Crimson/Kuromi), modal styling
│   ├── app.js                    # SPA router, reader rendering, IntersectionObserver, remote modal
│   └── index-mark.svg            # Favicon: Stylized calligraphic 本 with transparent backing
│
├── assets/                       # Repository preview media and screenshots
│   ├── background.gif
│   ├── demo.gif
│   ├── library.png
│   ├── reader.png
│   └── series.png
│
├── start-mac.command             # Double-clickable macOS launcher script (Finder / Safari integration)
├── start-linux.sh                # Linux shell launcher (zenity/kdialog/CLI folder picker, browser launch)
├── start-windows.bat             # Windows batch launcher (PowerShell folder picker, browser launch)
│
└── tests/                        # Automated test suite package (427 tests across 11 modules)
    ├── __init__.py               # Test package initialization
    ├── test_server.py            # 129 tests: Server, MangaLibrary, archives, user profile, themes, launchers
    ├── test_remote_providers.py  # 61 tests: Cache LRU/TTL, connection-level SSRF, registry, models, security
    ├── test_remote_reader.py     # 41 tests: Remote reader flow, progress, bookmarks, cache, local independence
    ├── test_weebcentral_provider.py # 39 tests: WeebCentral HTML parsing, chapter titles, service integration
    ├── test_nhentai_provider.py  # 36 tests: nhentai API/HTML parsing, ordered pages, format maps, security
    ├── test_remote_ui_integration.py # 27 tests: UI contracts, HTML escaping, mock sockets, series switching
    ├── test_keyboard_shortcuts.py # 25 tests: Overlay cleanup, registry integrity, reader shortcuts, context styling
    ├── test_reading_state_semantics.py # 22 tests: Chapter completion semantics, unread preservation, state persistence
    ├── test_editable_library_path.py # 20 tests: Editable library path field, server validation, error handling, pin isolation
    ├── test_per_library_pins.py  # 14 tests: Per-library pin scoping, legacy migration, CLI --dir isolation
    └── test_cli_remote_url.py    # 13 tests: CLI remote URL argument handling, startup routing, error sanitization
```

---

## 5. Local Manga Reading Subsystem

### Directory Structure & Chapter Discovery
The local library scans top-level directories inside the configured manga folder:
- **Series**: Every top-level non-hidden subdirectory represents a series.
- **Directory Chapters**: Any subfolder containing images (e.g. `Chapter 01/`, `001 - The Beginning/`).
- **Archive Chapters**: `.cbz` and `.zip` files (case-insensitive). Members are indexed without extracting to disk.
- **Image Formats**: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.avif`, `.bmp`.
- **Natural Numerical Sorting**: All series, chapters, and image filenames are sorted using natural numerical order (`natural_sort_key`), ensuring `10.jpg` follows `9.jpg` rather than `1.jpg`.

### Fallback Hierarchies for Media
- **Cover Image Resolution** (`GET /api/cover?series=<name>`):
  1. `<Series>/cover.jpg` (or `.jpeg`)
  2. First image of the first naturally sorted chapter (directory or archive)
  3. Returns `404 Not Found` if empty (UI renders dark typography placeholder)
- **Hero Background Resolution** (`GET /api/background?series=<name>`):
  1. `<Series>/background.jpg` (or `.jpeg`)
  2. `<Series>/cover.jpg` (or `.jpeg`)
  3. First image of first naturally sorted chapter
  4. Returns `404 Not Found` if no images exist (hero backdrop remains transparent)

### Local Data Persistence (`reader_data.json`)
Stored per series in `<Series>/.reader/reader_data.json`:
- Created automatically on first progress update, bookmark, or style change.
- Writes are atomic (`reader_data.json.tmp` written and replaced via `Path.replace()`).
- Contains:
  - `progress`: `{"Chapter 01": "015.jpg"}`
  - `bookmarks`: `["Chapter 01", "Chapter 02.cbz"]`
  - `reader.style`: `"spaced"` or `"seamless"`
  - `summary`, `author`, `links`: Optional series metadata.

---

## 6. Remote Manga Reading Subsystem

### Provider Architecture & Models (`providers/base.py`)
All remote sources implement `BaseProvider` and produce standardized dataclasses:
- **`RemotePage`**: `index` (int), `url` (str), `headers` (dict, e.g. Referer), `byte_size` (optional int).
- **`RemoteChapter`**: `id` (str), `title` (str), `chapter_number` (optional float), `url` (str), `date` (optional str), `pages` (list of `RemotePage`), `metadata` (dict).
- **`RemoteSeries`**: `id` (str), `title` (str), `url` (str), `cover_url` (optional str), `backdrop_url` (optional str), `description` (optional str), `author` (optional str), `status` (optional str), `chapters` (list of `RemoteChapter`), `metadata` (dict).
- **`BaseProvider` Interface**:
  - `id`: Unique string identifier (e.g. `"weebcentral"`, `"nhentai"`).
  - `name`: Human-readable display name.
  - `allowed_domains`: Tuple of authorized hostnames/wildcards for outbound network calls.
  - `supported_url_types`: String label for UI disclosure (e.g. `"Series URL"`, `"Gallery URL"`).
  - `url_pattern`: Example pattern string for UI display.
  - `is_public`: Boolean determining whether the provider is exposed in the UI.
  - `can_handle_url(url: str) -> bool`: Checks URL compatibility.
  - `get_series(url_or_id: str) -> RemoteSeries`: Fetches series metadata and chapters.
  - `get_chapter_pages(chapter_url_or_id: str) -> List[RemotePage]`: Fetches pages for a chapter.
  - `get_image(url: str, headers: Optional[dict] = None) -> bytes`: Streams image bytes via `SecureHttpClient`.

### Provider Registry (`providers/registry.py`)
- Thread-safe registry (`ProviderRegistry`) managing active providers.
- Global `default_registry` initialized with registered providers: `WeebCentralProvider`, `NhentaiProvider`, and `MockProvider`.
- `find_for_url(url)` iterates through registered providers and delegates to `can_handle_url(url)`.

### Chapter Page Cache (`providers/cache.py`)
In-memory `ChapterPageCache` with thread-safe `RLock` preventing repeated upstream requests:
- **Capacity Limits**:
  - `max_entries`: 100 chapters.
  - `max_total_pages`: 10,000 pages total across all cached chapters.
  - `max_metadata_size`: 10 MB total metadata bytes.
  - `ttl_seconds`: 3,600 seconds (1 hour).
- **Eviction & Safety**:
  - Strict LRU eviction when any capacity limit is exceeded.
  - Expired entries are pruned on access.
  - Defensive deep copying on both `set()` and `get()` prevents callers from mutating cache entries.

### Image Proxy & Delivery (`/api/remote/image-proxy`)
Remote image URLs are never loaded directly by the browser to prevent CORS issues, referer leakage, and client-side IP exposure:
- Images are proxied through `/api/remote/image-proxy?url=<quoted_url>&provider=<provider_id>`.
- `RemoteReaderService.stream_page_image()` validates the URL against the provider's domain allowlist and SSRF policy.
- Response payload is validated with `detect_image_format()` magic bytes. If non-image content (such as an HTML challenge page or error) is received, the proxy rejects it with `400 Bad Request`.
- Sets security headers: `X-Content-Type-Options: nosniff`, `Cache-Control: public, max-age=86400`.

### Remote State Persistence (`remote_reader_data.json`)
Remote reading progress, bookmarks, and style preferences are stored in the decoupled user configuration directory:
- macOS: `~/Library/Application Support/LocalMangaReader/remote_reader_data.json`
- Linux: `~/.config/LocalMangaReader/remote_reader_data.json` (or `$XDG_CONFIG_HOME`)
- Windows: `%LOCALAPPDATA%\LocalMangaReader\remote_reader_data.json`
- Storage Key: Canonical series identifier `remote:<provider_id>:<series_id>` (e.g. `remote:weebcentral:01J76XY8CM99`, `remote:nhentai:686216`).
- Atomically written via `.tmp` file and replaced.

---

## 7. Current Remote Providers

### 1. WeebCentral (`providers/weebcentral.py`)
- **Provider ID**: `weebcentral`
- **Display Name**: WeebCentral
- **Supported URL Types**: Series URL (`weebcentral.com/series/…`)
- **Accepted URL Formats**:
  - Full Series URL: `https://weebcentral.com/series/{series_id}/{slug}` or `https://weebcentral.com/series/{series_id}`
  - Chapter URL: `https://weebcentral.com/chapters/{chapter_id}` (recognized by `can_handle_url`)
  - Canonical Identifier: `remote:weebcentral:{series_id}`
  - Raw Series ID (e.g. `01J76XY8CM99`)
- **Allowed Outbound Domains**:
  - `weebcentral.com`, `*.weebcentral.com`
  - `*.lastation.us`, `*.lowee.us`, `*.planeptune.us`, `*.leanbox.us`
  - `*.compsci88.com`, `*.skylandcdn.com`
- **Implementation Characteristics**:
  - Zero-dependency parsing using `MiniHTMLTreeParser` (built on `html.parser.HTMLParser`).
  - Series metadata extracted from OpenGraph meta tags and semantic HTML (`og:title`, `og:image`, `og:description`, `<h1>`, `#manga-summary`).
  - Chapters: extracts all `/chapters/` links. Supports HTMX dynamic loading by requesting `/series/{series_id}/full-chapter-list` when present.
  - Chapter Titles: cleans extraneous UI badges such as "Last Read" and excludes `<time>` ISO timestamps while preserving legitimate titles (e.g. "Chapter 105.5: Extra Story").
  - Chapter Ordering: natural sorting by parsed float chapter numbers (e.g. 0 for Prologue, 1.5 for decimals).
  - Chapter Pages: extracts image tags from `#chapter-images`. If empty, queries the HTMX dynamic endpoint `/chapters/{chapter_id}/images`.
  - Filters out branding assets, tracking pixels, logos, and avatars.
  - Sends standard browser request headers with `Referer: https://weebcentral.com/`.

### 2. nhentai (`providers/nhentai.py`)
- **Provider ID**: `nhentai`
- **Display Name**: nhentai
- **Supported URL Types**: Gallery URL (`nhentai.net/g/…`)
- **Accepted URL Formats**:
  - Gallery URL: `https://nhentai.net/g/{gallery_id}/` or `/g/{gallery_id}`
  - API URLs: `https://nhentai.net/api/gallery/{gallery_id}` or `https://nhentai.net/api/v2/galleries/{gallery_id}`
  - Page View URL: `https://nhentai.net/g/{gallery_id}/{page_number}/`
  - Canonical Identifier: `remote:nhentai:{gallery_id}` (numeric ID required)
- **Allowed Outbound Domains (Strict 14-Host Allowlist)**:
  - `nhentai.net` (HTML pages and API)
  - `i.nhentai.net`, `i1.nhentai.net`, `i2.nhentai.net`, `i3.nhentai.net`, `i4.nhentai.net`, `i5.nhentai.net`, `i7.nhentai.net` (Page image CDNs)
  - `t.nhentai.net`, `t1.nhentai.net`, `t2.nhentai.net`, `t3.nhentai.net`, `t4.nhentai.net`, `t5.nhentai.net`, `t7.nhentai.net` (Thumbnail CDNs)
- **Implementation Characteristics**:
  - Multi-tier retrieval strategy:
    1. Primary: Official public API v2 endpoint `/api/v2/galleries/{gallery_id}`.
    2. Fallback: Gallery HTML page `/g/{gallery_id}/`, extracting embedded `window._gallery` JSON script or parsing DOM nodes.
  - Data Mapping: A gallery is normalized into a `RemoteSeries` containing exactly one `RemoteChapter` (with `id = gallery_id` and `chapter_number = None`).
  - Image Format Mapping: maps API format shorthand (`j` -> `.jpg`, `p` -> `.png`, `g` -> `.gif`, `w` -> `.webp`).
  - Full-resolution page image URL: `https://i.nhentai.net/galleries/{media_id}/{page_index}.{ext}`.
  - Cover image URL: `https://t.nhentai.net/galleries/{media_id}/cover.{ext}`.
  - Metadata: preserves artists, tags, characters, parodies, languages, categories, and alternate Japanese titles.
  - Defensive error handling: distinguishes 404 Not Found from 403/503 Cloudflare rate limits.

### 3. Mock Provider (`providers/mock.py`)
- **Provider ID**: `mock`
- **Visibility**: `is_public = False` (hidden from UI supported provider list).
- Provides in-memory test fixtures (`sololeveling`, `chainsawman`, `onepiece`) allowing full end-to-end integration testing in zero-network environments.

---

## 8. Frontend Client Architecture

### Views & Client Routing (`window.location.hash`)
The frontend is a single-page application governed by hash changes (`hashchange` event):
- `#/`: **Library View**. Displays local series grid, instant search filter, unified sort controls (Name, Chapters, Unread), profile avatar, and "Remote" launch button.
- `#/series/<series_name>`: **Series View**. Displays atmospheric hero backdrop, cover thumbnail, series metadata, order toggle (Ascending / Descending), and chapter listing with progress indicators. Works identically for local and remote series.
- `#/read/<series_name>/<chapter_name>`: **Reader View**. Continuous vertical reader, sticky header, previous/next chapter navigation, fullscreen toggle, reading mode switch, and interactive progress timeline.

### Remote Manga UI (`#modal-remote`)
- Triggered via the **Remote** button in the library header or **Open Remote Manga** in the profile dropdown.
- **URL Input**: Paste any supported series, chapter, gallery URL, or canonical `remote:...` identifier.
- **Supported Formats Disclosure**: Collapsible accordion populated dynamically from `/api/remote/providers`. Shows registered public providers (WeebCentral, nhentai) with name, URL type, and format patterns.
- **Recent Remote Series**:
  - Saved in browser `localStorage` under `local_manga_recent_remote` (up to 8 items).
  - Displays series title, provider badge (e.g. "WeebCentral", "nhentai"), and total page count when available.
  - Internal technical strings (e.g. `remote:weebcentral:...`) are never displayed as titles.
  - Each entry has an **Open** button and a **Remove** button. A **Clear All** button wipes the list.
- **Error Handling**: Displays descriptive inline error banners for invalid URLs, unsupported hosts, SSRF blocks, or network failures without alert popups.

### Theme Engine (Crimson & Kuromi)
The design is dark-mode only, sharing an identical neutral foundation (`#0E0E0E`):
- **Crimson Theme** (`data-theme="crimson"`):
  - Primary Accent: `#E53935` (Crimson red)
  - Hover Accent: `#FF4D4D`
- **Kuromi Theme** (`data-theme="kuromi"`):
  - Primary Accent: `#9B7EDB` (Kuromi purple)
  - Hover Accent: `#B19AE8`
- Persisted on the server in `settings.json` and applied to `document.documentElement` (`<html data-theme="...">`).

---

## 9. Reader Engine & Interaction

### Page Rendering & Layout Modes
Images are loaded lazily in reading order inside `.reader-page` containers:
- **Spaced Mode** (`mode-spaced`): Adds 20px vertical margins and subtle rounded borders between pages. Designed for traditional Japanese manga.
- **Seamless Mode** (`mode-seamless`): Removes all gaps, margins, paddings, and borders (`gap: 0 !important`). Images touch edge-to-edge for an unbroken webtoon / manhwa strip.
- Preference is saved per series (both local and remote) and persists across sessions.

### Progress Tracking Mechanics
- Real-time page visibility is tracked using `IntersectionObserver` with `threshold: 0.1` and root margin `-10% 0px -40% 0px`.
- As a page enters the focal zone, the reading position is updated in memory and debounced (400ms) before sending `POST /api/progress`.
- On opening a chapter, the reader automatically smooth-scrolls to the last read page.

### Segmented Timeline
- Fixed at the bottom of the viewport (`.reader-progress-container`).
- Renders up to 80 proportional bars.
- Segments update dynamically: `.past`, `.current` (with accent glow), and `.future`.
- Hovering shows page tooltips; clicking any segment immediately scrolls to that page.

### Keyboard Shortcuts

| Key | Action |
| :--- | :--- |
| `Left Arrow` | Navigate to previous chapter |
| `Right Arrow` | Navigate to next chapter |
| `Up Arrow` | Scroll up smoothly through the current chapter (hold for continuous scrolling) |
| `Down Arrow` | Scroll down smoothly through the current chapter (hold for continuous scrolling) |
| `Shift + Up Arrow` | Jump to the top of the chapter |
| `Shift + Down Arrow` | Jump to the bottom of the chapter |
| `F` | Toggle fullscreen mode |
| `B` | Toggle chapter bookmark |
| `Shift + R` | Toggle chapter Read / Unread status |
| `Shift + S` | Toggle Spaced / Seamless reading mode |
| `S` | Save currently displayed page screenshot |
| `=` | Zoom in manga pages by 10% (50%–300% range, temporary) |
| `-` | Zoom out manga pages by 10% (50%–300% range, temporary) |
| `0` | Reset zoom to 100% (temporary) |
| `Shift + /` / `?` | Toggle keyboard shortcuts reference overlay (global across library, series, reader) |
| `Escape` | Exit fullscreen / close modal / return to series view |

### Keyboard Shortcuts Reference Overlay
The application provides an interactive, modal keyboard shortcuts cheat-sheet overlay (`#shortcutsModal`):
- **Invocation**: Openable globally from any view (library, series detail, and reader) via `Shift + /` or `?`, or through the "Keyboard Shortcuts" item in the top-right profile dropdown.
- **Single Source of Truth**: Rendered dynamically from the `KEYBOARD_SHORTCUTS` registry in `static/app.js`, organized strictly into three functional reader categories:
  1. **Reader navigation**: Previous/next chapter navigation (`Left Arrow`, `Right Arrow`), smooth vertical scrolling (`Up Arrow`, `Down Arrow`), and top/bottom chapter jumps (`Shift + Up Arrow`, `Shift + Down Arrow`).
  2. **Reading controls**: Fullscreen toggle (`F`), chapter bookmark (`B`), read/unread toggle (`Shift + R`), and spaced/seamless layout toggle (`Shift + S`).
  3. **Zoom and screenshots**: Temporary zoom in (`=`), zoom out (`-`), zoom reset (`0`), and page screenshot capture (`S`).
- **Cleaned Registry Structure**: The redundant General navigation category and its entries (`toggle-shortcuts`, `dismiss-modal`, `activate-item`) have been eliminated from both the registry and overlay UI. No red active-context highlighting or category emphasis remains for general navigation.
- **Context-Aware Visual Feedback**:
  - In the reader view, the active category header is subtly highlighted with the active theme's accent color (Crimson red or Kuromi purple).
  - In non-reader views (library and series detail), shortcuts render in the neutral dark palette.
- **Dismissal & Accessibility**:
  - Closed via `Escape` key, clicking the close button (`.btn-close`), or clicking outside the modal dialog onto the backdrop overlay.
  - Traps and handles focus cleanly, preserving underlying view state on close.

> **Temporary Manga Reader Zoom Rules**:
> - Zoom range: **50% to 300%** with a **100%** default, adjusting in 10 percentage point steps.
> - Affects only manga page images within `.reader-container` via the `--reader-zoom` CSS custom property, preserving image aspect ratio and horizontal panning access.
> - Controls, header, footer, and timeline remain unscaled and fully functional.
> - Preserves current zoom level across entering/exiting fullscreen and toggling Spaced/Seamless reading modes.
> - Strictly temporary and in-memory: resets to 100% on opening any chapter, navigating between chapters, or exiting reader view. Never persisted to `localStorage`, `reader_data.json`, or server configuration.

---

## 10. Reading State & Data Storage Reference

### Storage Locations by Platform

| Component | macOS | Linux | Windows |
| :--- | :--- | :--- | :--- |
| **Settings** (`settings.json`) | `~/Library/Application Support/LocalMangaReader/settings.json` | `~/.config/LocalMangaReader/settings.json` | `%LOCALAPPDATA%\LocalMangaReader\settings.json` |
| **User Profile** (`profile.json`) | `~/Library/Application Support/LocalMangaReader/profile.json` | `~/.config/LocalMangaReader/profile.json` | `%LOCALAPPDATA%\LocalMangaReader\profile.json` |
| **User Avatar** (`avatar.jpg`) | `~/Library/Application Support/LocalMangaReader/avatar.jpg` | `~/.config/LocalMangaReader/avatar.jpg` | `%LOCALAPPDATA%\LocalMangaReader\avatar.jpg` |
| **Remote State** (`remote_reader_data.json`) | `~/Library/Application Support/LocalMangaReader/remote_reader_data.json` | `~/.config/LocalMangaReader/remote_reader_data.json` | `%LOCALAPPDATA%\LocalMangaReader\remote_reader_data.json` |
| **Local State** (`reader_data.json`) | `<Manga_Library>/<Series>/.reader/reader_data.json` | `<Manga_Library>/<Series>/.reader/reader_data.json` | `<Manga_Library>/<Series>/.reader/reader_data.json` |
| **Recent Remotes** (`localStorage`) | Browser LocalStorage (`local_manga_recent_remote`) | Browser LocalStorage (`local_manga_recent_remote`) | Browser LocalStorage (`local_manga_recent_remote`) |

### Per-Library Pin Persistence (`pinned_by_library`)
Pinned series are persisted independently for each manga library in `settings.json` under the `pinned_by_library` dictionary:
- **Canonical Key Architecture**: Keys in `pinned_by_library` are canonical, normalized absolute filesystem paths computed via `Path.expanduser().resolve()`. This ensures consistent lookup regardless of redundant separators, relative path markers (`.`, `..`), or platform path differences.
- **Data Model**:
  ```json
  {
    "theme": "crimson",
    "library_path": "/Users/user/Manga",
    "pinned_by_library": {
      "/Users/user/Manga": ["Berserk", "Vinland Saga"],
      "/Volumes/External/Archive": ["Chainsaw Man"]
    }
  }
  ```
- **Backward-Compatible Idempotent Migration**:
  - Legacy configurations storing a global `"pinned": [...]` list are automatically migrated on startup.
  - If a default library path is configured, the legacy pins are mapped to `pinned_by_library[canonical_library_path]` and the top-level `"pinned"` key is safely retired from disk.
  - If no default library is configured at startup, the legacy `"pinned"` key is preserved without destructive data loss.
  - The migration is strictly idempotent: subsequent startups or reloads never re-migrate, duplicate, or overwrite pins.
  - Unrelated settings (theme, library path, window state) are preserved intact.
- **Collection Isolation**:
  - Pinning or unpinning in Library A modifies only Library A's pin list.
  - Switching to Library B loads only Library B's pin list; an empty pin list for one library never modifies or clears other libraries.
  - The frontend derives the Pinned section strictly from series physically present in the active collection (`allSeriesList`). Non-local or stale pins are never rendered in the UI.
- **CLI `--dir` Temporary Override Invariant**:
  - Launching the server with `--dir <path>` activates a temporary library override for that execution session only.
  - Pin and unpin operations performed during that session are scoped to `pinned_by_library[canonical_temp_path]`.
  - The saved default `library_path` in `settings.json` is strictly protected and never modified by temporary `--dir` operations.

### Editable Library Path & Switching Mechanics
The application provides an editable filesystem path input in the Settings modal (`#modal-settings`):
- **User Interface**: Contains a text input (`#input-library-path`), an explicit Apply button (`#btn-apply-library-path`), and an inline error display (`#library-path-error`), alongside the existing native folder browsing control (`#btn-change-folder`).
- **Interaction Flow**:
  1. Opening Settings populates `#input-library-path` with the currently active library's full filesystem path and clears any prior error.
  2. The user can type, paste, or edit the path and apply it via the Apply button or by pressing `Enter`.
  3. The client disables submit controls during request flight to prevent duplicate submissions.
  4. On success: refreshes the library view, updates displayed path indicators, loads the target library's scoped pins, closes the modal, and shows a success notification.
  5. On error: displays a clear inline error message near the input, keeps the modal open for correction, and preserves the active library and saved settings intact.
- **Server Validation & Security**:
  - Reject URLs upfront (protocols like `http://`, `https://`, `ftp://` are rejected with HTTP 400).
  - Paths are normalized via `canonicalize_library_path()` (`Path(p).expanduser().resolve()`), handling tildes, relative segments (`..`, `.`), redundant slashes, and spaces.
  - Rejects missing paths with descriptive "Directory does not exist" messages.
  - Rejects file paths with "Path is a file, not a directory" messages.
  - Gracefully handles inaccessible paths (`PermissionError`) and filesystem errors without leaking internal tracebacks.
  - Switches `MangaRequestHandler.library` in memory and updates persisted `library_path` in `settings.json` only after validation succeeds.
- **Per-Library Pin Scoping**:
  - On a successful switch, `POST /api/library` returns the newly active library's pins from `pinned_by_library`.
  - Pins are never merged across collections; returning to a previous library restores its isolated pins.

### Environment Overrides for Testing
Configuration and state locations can be overridden via environment variables:
- `LOCAL_MANGA_CONFIG_DIR`: Sets base configuration directory.
- `LOCAL_MANGA_SETTINGS_FILE`: Explicit path to `settings.json`.
- `LOCAL_MANGA_CONFIG_FILE`: Legacy override alias.
- `LOCAL_MANGA_LAUNCHER`: Set to `1` by shell launchers to prevent duplicate browser launches.

---

## 11. CLI & Application Launch Behavior

### CLI Commands & Arguments
The server can be started using either `python3 server.py` or `python3 main.py`:

```bash
# Standard startup using saved library
python3 server.py

# Open a remote manga series or gallery directly in the reader on startup
python3 server.py "https://nhentai.net/g/686216/"
python3 main.py "https://weebcentral.com/series/01J76XY8CM99/chainsaw-man"

# Directly open via canonical identifier
python3 server.py "remote:weebcentral:01J76XY8CM99"

# Temporarily inspect another local manga folder (does NOT overwrite saved settings)
python3 server.py --dir /Volumes/External/Manga

# Bind to a custom port
python3 server.py --port 9000

# View all options
python3 server.py --help
```

### CLI Arguments Reference
- `url` (optional positional argument): Supported remote manga/manhwa URL or canonical identifier (`remote:<provider>:<id>`).
  - Pre-validated by `RemoteReaderService` before server startup.
  - If invalid, unsupported, or SSRF-blocked: writes a clean, sanitized error to `stderr` and exits immediately with code `1`. Sensitive query parameters are never leaked.
  - If valid: sets `startup_url` on the server and automatically opens the browser to `http://localhost:<port>/#/series/<quoted_target>`.
- `--dir`, `-d`: Sets the manga library directory for that session only.
- `--port`, `-p`: Port to bind HTTP server (default: `8000`).

### Platform Launch Scripts
- **macOS** (`start-mac.command`):
  - Double-clickable Finder launcher.
  - Inspects command-line arguments: if a remote URL or `remote:...` identifier is passed, sets `TARGET_OPEN_URL`.
  - Sets `LOCAL_MANGA_LAUNCHER=1` so `server.py` does not trigger a duplicate browser opening.
  - Starts `python3 server.py --port $PORT "$@"` in background with `cleanup()` trap.
  - Polls `http://localhost:$PORT/api/status` for readiness (every 250ms, up to 10s).
  - Opens Safari to `TARGET_OPEN_URL` using `open -a Safari`.
- **Linux** (`start-linux.sh`):
  - Checks for Python 3 (`python3` or `python`).
  - Parses arguments for remote URLs to configure `TARGET_OPEN_URL`.
  - Polls `/api/status` for readiness.
  - Opens default desktop browser (`xdg-open`, `gio`, or browser binaries).
- **Windows** (`start-windows.bat`):
  - Finds Python (`python` or `py -3`).
  - Launches background PowerShell poller on `/api/status` to launch the default browser.
  - Runs `server.py` in the foreground.

---

## 12. Comprehensive API Reference

### 1. General & System Endpoints

| Method | Endpoint | Description | Request Body | Response Payload |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/status` | Server readiness check & startup state | None | `{ "status": "online", "app": "Local Manga Reader (Phase 6)", "library_path": "...", "library_exists": bool, "startup_url": str\|null, "endpoints": [...] }` |
| `GET` | `/api/settings` | Retrieve theme settings | None | `{ "theme": "crimson"\|"kuromi", "library_path": "..." }` |
| `POST` | `/api/settings` | Update theme preference | `{"theme": "crimson"\|"kuromi"}` | `{ "success": true, "theme": "..." }` |
| `GET` | `/api/library` | Active local library status & pins | None | `{ "library_path": str\|null, "library_exists": bool, "series_count": int, "pinned": [...] }` |
| `POST` | `/api/library` | Switch active local library | `{"action": "select"}` or `{"path": "/..."}` | `{ "success": true, "library_path": "...", "library_exists": bool, "series_count": int, "pinned": [...] }` |
| `GET` | `/api/profile` | Retrieve local user profile | None | `{ "name": str, "has_avatar": bool, "avatar_url": str\|null }` |
| `POST` | `/api/profile` | Update profile name or avatar | `{"name": str, "avatar": "data:image/...", "remove_avatar": bool}` | Updated profile object |
| `GET` | `/api/pin`, `/api/pinned` | Retrieve pinned series for active library | None | `{ "pinned": ["Series A", ...] }` |
| `POST` | `/api/pin` | Pin or unpin series in active library | `{"series": "...", "pinned": bool}` (optional bool) | `{ "success": true, "pinned": bool, "pinned_series": [...] }` |
| `POST` | `/api/screenshot` | Save manga page screenshot | `{"series": "...", "chapter": "...", "image": "...", "provider": "..."}` | `{ "success": true, "path": "...", "filename": "..." }` |

### 2. Remote Reading Endpoints (`/api/remote/*`)

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/remote/providers` | None | Returns list of registered public providers, URL types, and pattern examples. |
| `GET` | `/api/remote/resolve` | `url=<target_url>` | Resolves a remote URL into provider ID, series ID, canonical identifier, and normalized series metadata. |
| `GET` | `/api/remote/series` | `url=<url>` or `series=<id>&provider=<p>` | Retrieves series metadata and chapter listing for a remote series. |
| `GET` | `/api/remote/chapters` | `series=<id>&provider=<p>` | Retrieves chapter list for a remote series. |
| `GET` | `/api/remote/images` | `series=<id>&chapter=<ch>&provider=<p>` | Retrieves reader-formatted image items with proxied image URLs. |
| `GET` | `/api/remote/image-proxy` | `url=<cdn_url>&provider=<p>` | Streams verified remote page image with magic byte validation and cache headers. |
| `GET` | `/api/remote/cover` | `series=<series_identifier>` | Streams cover image for a remote series. |
| `GET` | `/api/remote/background` | `series=<series_identifier>` | Streams hero background image for a remote series (falls back to cover). |
| `GET` | `/api/remote/reader-data` | `series=<series_identifier>` | Returns remote progress, bookmarks, and style preference. |
| `POST` | `/api/remote/progress` | Body: `{"series": "...", "chapter": "...", "image": "..."}` | Updates reading progress for a remote series. |
| `POST` | `/api/remote/bookmark` | Body: `{"series": "...", "chapter": "...", "bookmarked": bool}` | Toggles bookmark for a remote chapter. |
| `POST` | `/api/remote/style` | Body: `{"series": "...", "style": "spaced"\|"seamless"}` | Updates reading style for a remote series. |
| `POST` | `/api/remote/completed` | Body: `{"series": "...", "chapter": "...", "completed": bool}` | Toggles chapter Read/Unread state for remote series. |

### 3. Dual-Mode Unified Endpoints
The following endpoints accept either local series names (e.g. `Berserk`) or remote identifiers (`remote:weebcentral:01J76XY8CM99` / `https://...`). The server automatically detects remote series via `is_remote_series()`:

| Method | Endpoint | Local Behavior | Remote Behavior |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/chapters?series=...` | Scans folders and `.cbz`/`.zip` archives | Queries `RemoteReaderService.get_chapters()` |
| `GET` | `/api/images?series=...&chapter=...` | Lists images in folder/archive | Queries `RemoteReaderService.get_chapter_images_for_reader()` |
| `GET` | `/api/cover?series=...` | Resolves `cover.jpg` -> first chapter image | Proxies remote cover -> first page image |
| `GET` | `/api/background?series=...` | Resolves `background.jpg` -> cover -> first image | Proxies backdrop -> cover -> first page image |
| `GET` | `/api/reader-data?series=...` | Reads `<Series>/.reader/reader_data.json` | Reads `remote_reader_data.json` |
| `POST` | `/api/progress` | Writes to local `reader_data.json` | Writes to global `remote_reader_data.json` |
| `POST` | `/api/bookmark` | Writes to local `reader_data.json` | Writes to global `remote_reader_data.json` |
| `POST` | `/api/style` | Writes to local `reader_data.json` | Writes to global `remote_reader_data.json` |
| `POST` | `/api/completed` | Writes to local `reader_data.json` | Writes to global `remote_reader_data.json` |
| `POST` | `/api/cover` | Uploads `<Series>/cover.jpg` | **Rejected with 400 Bad Request** (remote metadata is read-only) |
| `POST` | `/api/background` | Uploads `<Series>/background.jpg` | **Rejected with 400 Bad Request** (remote metadata is read-only) |

---

## 13. Security Architecture & Threat Model

### Local Request Security
1. **Localhost Binding**: HTTP server binds strictly to `127.0.0.1`.
2. **Path Traversal Guardrails**: `MangaLibrary._is_safe_child()` verifies candidate paths resolve strictly inside `root_path`. Directory traversal markers (`..`, leading slashes, Windows drive letters) are rejected.
3. **ZIP Slip Protection**: Archive extraction inspects every `ZipInfo.filename` using `is_safe_archive_member()`, rejecting paths with `..`, root slashes, or device markers.
4. **Static File Confinement**: Static file dispatcher verifies resolved file paths remain inside `static/`.

### Remote Outbound Security (`providers/security.py`)
1. **HTTPS Enforcement**: Only `https://` URLs are permitted. Schemes such as `http://`, `file://`, `ftp://`, `gopher://`, or `data:` raise `InvalidSchemeError`.
2. **Provider Domain Allowlists**: Hostnames are strictly matched against each provider's `allowed_domains`. Wildcard prefixes (e.g. `*.weebcentral.com`, `*.lastation.us`) require full subdomain boundaries; prefix or suffix spoofing (e.g. `evilweebcentral.com`, `weebcentral.com.attacker.com`) is rejected.
3. **Connection-Level Socket SSRF Defense (`SSRFProtectedHTTPSConnection`)**:
   - Outbound connections subclass `http.client.HTTPSConnection` to manage raw socket creation directly.
   - Hostnames are resolved via `socket.getaddrinfo`.
   - Every candidate IP is validated against strict RFC blocklists before connection:
     - IPv4: Loopback (`127.0.0.0/8`), Private (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), Link-Local / Cloud Metadata (`169.254.0.0/16` - protects AWS `169.254.169.254`, GCP, Azure metadata services), Carrier-Grade NAT (`100.64.0.0/10`), Documentation (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), Multicast (`224.0.0.0/4`), Reserved (`240.0.0.0/4`), Broadcast (`255.255.255.255/32`).
     - IPv6: Loopback (`::1/128`), Unspecified (`::/128`), Link-Local (`fe80::/10`), Unique Local (`fc00::/7`), Documentation (`2001:db8::/32`), Multicast (`ff00::/8`), IPv4-mapped/translated (`::ffff:0:0:0/96`, `64:ff9b::/96`).
   - The raw socket connects directly to the pre-approved IP.
   - Immediately post-connect, `sock.getpeername()` is re-verified on the active socket.
   - The verified socket is passed to `ssl_context.wrap_socket` with `server_hostname=self.host`.
   - Preserves TLS Server Name Indication (SNI) and certificate validation (`check_hostname=True`, `verify_mode=ssl.CERT_REQUIRED`).
   - Prevents Time-of-Check to Time-of-Use (TOCTOU) DNS rebinding attacks completely without secondary DNS queries.
4. **Redirect Guardrails**: Automatic HTTP redirects are disabled. Every redirect destination is validated against the HTTPS scheme and provider allowlist. Enforces hop limits (default max 5) and loop detection.
5. **Image Proxy Magic Byte Verification**: All proxied image streams must match binary magic bytes for JPEG, PNG, WebP, GIF, AVIF, or BMP via `detect_image_format()`. Non-image payloads (e.g. HTML challenge pages) are rejected with `400 Bad Request`.

---

## 14. Testing Suite & Verification Procedures

### Test Suite Structure
The test suite consists of **427 automated tests** organized across 11 modules:

| Test Module | Tests | Focus Area |
| :--- | :--- | :--- |
| `tests/test_server.py` | 129 | Core HTTP server, `MangaLibrary`, natural sorting, archive discovery (`.cbz`/`.zip`), user profile, appearance/themes, library resolution, platform launchers, pin API, and screenshot saving. |
| `tests/test_remote_providers.py` | 61 | `ChapterPageCache` LRU/TTL bounds and counter accounting, connection-level SSRF transport, `MockProvider`, `ProviderRegistry`, normalized models, security IP/domain validation. |
| `tests/test_remote_reader.py` | 41 | End-to-end remote reader flow, progress/bookmark/style persistence, cache hit/miss behavior, graceful error handling, local reading regression independence. |
| `tests/test_weebcentral_provider.py` | 39 | WeebCentral HTML parsing, chapter title cleaning (excluding 'Last Read' badges and `<time>` tags), dynamic image endpoint fallback, service and HTTP integration. |
| `tests/test_nhentai_provider.py` | 36 | nhentai API v2 & HTML scraper, ordered page generation, format mapping, domain allowlist enforcement, regression safety. |
| `tests/test_remote_ui_integration.py` | 27 | UI contracts, DOM safety, HTML escaping of untrusted titles, mock socket HTTP simulation, switching between local and remote series. |
| `tests/test_keyboard_shortcuts.py` | 25 | Overlay cleanup (General navigation removal), registry integrity, context highlighting, reader shortcuts (`=`, `-`, `0`, `Shift+R`, `S`), continuous held-arrow scrolling, reader header layout. |
| `tests/test_reading_state_semantics.py` | 22 | Explicit vs natural chapter completion semantics, unread preservation during navigation and progress updates, local and remote state persistence. |
| `tests/test_editable_library_path.py` | 20 | Editable library path UI, server validation, URL and file rejection, permission error handling, pin list isolation across switches, and theme compatibility. |
| `tests/test_per_library_pins.py` | 14 | Scoped per-library pins, canonical path normalization, safe idempotent legacy migration, CLI `--dir` isolation, UI switching isolation, relative/equivalent path resolution. |
| `tests/test_cli_remote_url.py` | 13 | CLI remote URL argument handling, startup routing, error sanitization, launcher suppression of duplicate browser opens. |

### Running the Test Suite

```bash
# Run the entire test suite (all 427 tests)
python3 -m unittest discover -s tests -p "test_*.py" -v

# Run a specific test module
python3 -m unittest tests.test_editable_library_path
python3 -m unittest tests.test_per_library_pins
python3 -m unittest tests.test_keyboard_shortcuts
python3 -m unittest tests.test_reading_state_semantics
python3 -m unittest tests.test_cli_remote_url
python3 -m unittest tests.test_weebcentral_provider
python3 -m unittest tests.test_nhentai_provider

# Alternatively, run a test module by file path
python3 -m unittest tests/test_editable_library_path.py
python3 -m unittest tests/test_per_library_pins.py
python3 -m unittest tests/test_server.py
python3 -m unittest tests/test_keyboard_shortcuts.py

# Validate client JavaScript syntax
node -c static/app.js

# Validate shell launcher script syntax
bash -n start-mac.command
bash -n start-linux.sh
```

### Smoke Test Procedures
1. **Local Reading Verification**:
   - Start server: `python3 server.py --dir /path/to/test_manga`.
   - Open `http://localhost:8000`. Verify series list loads.
   - Open a folder chapter and an archive chapter (`.cbz`/`.zip`).
   - Scroll through pages; verify bottom timeline updates; refresh and confirm auto-resume.
2. **Remote Reading Verification**:
   - Click "Remote" button in library view.
   - Paste a WeebCentral or nhentai URL (e.g. `https://nhentai.net/g/686216/`).
   - Confirm series view loads with title, cover, and chapter list.
   - Open chapter; verify images stream via `/api/remote/image-proxy`.
   - Toggle bookmark (`B`) and style (`S`); confirm state persists on reload.
3. **CLI Direct Launch Verification**:
   - Run `python3 server.py "https://nhentai.net/g/686216/"`.
   - Verify server boots and browser navigates directly to `#/series/remote%3Anhentai%3A686216`.

---

## 15. Implementation Status Matrix

### Implemented & Fully Verified
- [x] Zero-dependency Python 3 backend and vanilla ES6 frontend.
- [x] Natural numerical sorting for series, chapters, and image filenames.
- [x] Directory chapters + `.cbz` and `.zip` archive chapters with in-memory streaming.
- [x] Continuous vertical reader with Spaced and Seamless modes (`Shift + S`).
- [x] Segmented bottom progress timeline with hover preview and jump navigation.
- [x] Auto-resuming reading progress via `IntersectionObserver`.
- [x] Chapter bookmarking (`B`) and series reading style preferences.
- [x] Read/Unread chapter completion toggle (`Shift + R`) with explicit unread persistence.
- [x] Page screenshot capture (`S`) saving full-resolution images to `<Library>/Screenshots/<Series>/`.
- [x] Temporary reader zoom (`=`, `-`, `0` reset) across 50% to 300% range without persistent storage mutation.
- [x] Smooth continuous scrolling via held Up/Down arrow keys.
- [x] Fixed translucent reader header with backdrop blur and Chapters button navigation.
- [x] Per-library pinned series scoped by canonical path (`pinned_by_library`) with idempotent legacy migration and CLI `--dir` isolation.
- [x] Editable library path field in Settings modal with server validation, error handling, and per-library pin isolation.
- [x] Keyboard shortcuts reference overlay (`Shift + /` / `?`) with context-aware reader categories (Reader navigation, Reading controls, Zoom/screenshot) and clean dismissal.
- [x] Viewport-centered series page header title with responsive truncation.
- [x] Cover and hero background fallback hierarchies.
- [x] Editorial dark UI with Crimson and Kuromi dual themes.
- [x] Local user profiles (display name and avatar image upload).
- [x] Remote provider architecture and thread-safe registry.
- [x] Connection-level SSRF protection (`SSRFProtectedHTTPSConnection`) with RFC IP filtering.
- [x] Thread-safe LRU/TTL `ChapterPageCache` with capacity limits.
- [x] WeebCentral provider with HTMX full chapter list parsing and cleaned chapter titles.
- [x] nhentai provider with API v2 support, embedded JSON fallback, and gallery normalization.
- [x] Secure image proxy with magic byte format validation.
- [x] Decoupled remote state persistence (`remote_reader_data.json`).
- [x] Remote browsing modal with collapsible provider disclosure and recent series manager.
- [x] CLI remote URL launch support with automatic browser opening.
- [x] Cross-platform launcher scripts (`start-mac.command`, `start-linux.sh`, `start-windows.bat`).
- [x] Complete test suite with 427 passing unit and integration tests across 11 modules.

### Source-Dependent / Live Network Limitations
- **Live Upstream Site Availability**: WeebCentral and nhentai providers connect to live third-party websites. Changes to upstream markup or anti-bot Cloudflare challenges (HTTP 403 / 503) can block requests during live execution, even though unit tests pass with offline fixtures.
- **Third-Party Rate Limits**: Rapidly navigating across multiple remote chapters may trigger upstream CDN throttling.

### Intentionally Deferred / Excluded
- **No Multi-User Accounts or Passwords**: The app is designed strictly for single-user localhost loopback execution.
- **No Light Mode**: The application aesthetic is permanently dark-editorial by design.
- **No Deep Directory Nesting**: Scanning is restricted to 2 hierarchy levels (`<Root>/<Series>/<Chapter>`).
- **No Remote Series Metadata Editing**: Remote series metadata is read-only from the upstream provider. Cover and background uploads are rejected for remote series.

---

## 16. Known Limitations, Edge Cases & Operational Notes

1. **Safari Fullscreen Scroll Restoration**:
   When exiting fullscreen in Safari (macOS / WebKit), Safari's internal layout restoration can reset the scroll position to where you were before entering fullscreen mode. Chrome, Edge, and Firefox preserve the position properly. Complex browser-event interception workarounds have been deliberately avoided to maintain codebase simplicity and prevent event loop regressions.
2. **Upstream Cloudflare Protection**:
   If an upstream provider (such as nhentai or WeebCentral) activates strict Cloudflare challenge pages (e.g. Under Attack Mode), requests will return HTTP 403 or 503. The server catches these and returns clean error messages rather than hanging.
3. **WeebCentral Dynamic Images**:
   WeebCentral occasionally serves chapter pages via a secondary HTMX endpoint `/chapters/{id}/images`. The provider automatically detects empty `#chapter-images` containers and falls back to requesting this dynamic fragment.
4. **nhentai Gallery Representation**:
   An nhentai gallery is modeled as a single `RemoteSeries` containing 1 `RemoteChapter`. Opening the series detail view shows this single chapter, which immediately opens into the reader.
5. **Recent Remote Series Storage**:
   Recent remote items are stored in the user's browser `localStorage` (`local_manga_recent_remote`). Clearing browser site data will reset the recent series list in the modal (though server-side reading progress and bookmarks in `remote_reader_data.json` are retained).
6. **Safari Favicon Caching**:
   Safari aggressively caches favicons in `~/Library/Safari/Favicon Cache`. If a modified favicon does not display, clearing that folder and restarting Safari resolves the issue.
7. **Archive File Corruption**:
   Corrupt `.cbz` or `.zip` archives are safely caught by `zipfile.BadZipFile`, returning an empty list (`[]`) and displaying a disabled state in the UI rather than crashing the server.

---

## 17. Guidelines & Safety Rules for Future Development

When extending or maintaining this project, future developers and coding agents **must follow these rules**:

1. **Preserve Zero-Dependency Invariant**:
   Never add external Python packages or npm libraries. All code must remain compatible with Python 3.10+ standard library and modern native browser APIs.
2. **Follow Provider Contract & Security Controls**:
   Any new remote provider must subclass `BaseProvider`, define `allowed_domains`, implement `can_handle_url`, `get_series`, `get_chapter_pages`, and route image requests through `SecureHttpClient` with SSRF protection.
3. **Isolate Remote State**:
   Never store remote provider state inside the local manga library. Remote progress, bookmarks, and styles must be managed through `RemoteReaderService` and stored in `remote_reader_data.json`.
4. **Protect Local Reading Independence**:
   Changes to remote reading must never regress local folder or archive reading. Run `python3 -m unittest tests.test_server` and `python3 -m unittest tests.test_remote_reader` after any modifications.
5. **Always Sanitize User & Remote Strings**:
   Remote titles, chapter names, authors, and synopses are untrusted external data. Use `textContent` or escape HTML before inserting into the DOM to prevent XSS.
6. **Maintain Complete Test Coverage**:
   Any new endpoint, provider, or CLI feature must include regression tests. Ensure all 427 tests pass before finishing any task:
   ```bash
   python3 -m unittest discover -s tests -p "test_*.py" -v
   ```
