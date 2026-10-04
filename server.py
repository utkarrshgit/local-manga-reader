#!/usr/bin/env python3
"""
Local Manga & Manhwa Reader - Core Server (Phase 1)
Zero external dependencies; uses only Python standard library.
"""

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import zipfile
from http import HTTPStatus
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote, quote

DEFAULT_PORT = 8000


def get_config_dir() -> Path:
    """Returns directory where configuration and profile data are stored."""
    if os.environ.get("LOCAL_MANGA_CONFIG_DIR"):
        return Path(os.environ["LOCAL_MANGA_CONFIG_DIR"])
    if os.environ.get("LOCAL_MANGA_CONFIG_FILE"):
        return Path(os.environ["LOCAL_MANGA_CONFIG_FILE"]).parent
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local"))
        return Path(local_app_data) / "LocalMangaReader"
    if sys.platform.startswith("linux"):
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return Path(xdg_config_home) / "LocalMangaReader"
    return Path(os.path.expanduser("~/Library/Application Support/LocalMangaReader"))


def get_settings_file_path() -> Path:
    """Returns path to the application settings configuration file (settings.json)."""
    if os.environ.get("LOCAL_MANGA_SETTINGS_FILE"):
        return Path(os.environ["LOCAL_MANGA_SETTINGS_FILE"])
    if os.environ.get("LOCAL_MANGA_CONFIG_FILE"):
        p = Path(os.environ["LOCAL_MANGA_CONFIG_FILE"])
        if p.name == "settings.json":
            return p
        if p.name != "library_path":
            return p
        return p.parent / "settings.json"
    return get_config_dir() / "settings.json"


def get_legacy_config_file_path() -> Path:
    """Returns path to the legacy standalone library_path file outside the git repository."""
    if os.environ.get("LOCAL_MANGA_LEGACY_CONFIG_FILE"):
        return Path(os.environ["LOCAL_MANGA_LEGACY_CONFIG_FILE"])
    if os.environ.get("LOCAL_MANGA_CONFIG_FILE"):
        p = Path(os.environ["LOCAL_MANGA_CONFIG_FILE"])
        if p.name == "library_path":
            return p
        return p.parent / "library_path"
    return get_config_dir() / "library_path"


def get_config_file_path() -> Path:
    """Returns path to the primary settings file (settings.json). Kept for backwards compatibility."""
    return get_settings_file_path()


def get_profile_file_path() -> Path:
    """Returns path to the profile configuration file."""
    return get_config_dir() / "profile.json"


def get_avatar_file_path() -> Path:
    """Returns path to the user profile avatar image file."""
    return get_config_dir() / "avatar.jpg"


def load_user_profile() -> dict:
    """Loads user profile from config directory. Defaults to name='User', has_avatar=False."""
    profile_file = get_profile_file_path()
    avatar_file = get_avatar_file_path()
    name = "User"
    if profile_file.is_file():
        try:
            data = json.loads(profile_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                raw_name = data.get("name")
                if isinstance(raw_name, str) and raw_name.strip():
                    name = raw_name.strip()
        except Exception:
            pass

    has_avatar = avatar_file.is_file() and avatar_file.stat().st_size > 0
    return {
        "name": name,
        "has_avatar": has_avatar,
        "avatar_url": "/api/profile/avatar" if has_avatar else None
    }


def save_user_profile(name: str | None = None, avatar_bytes: bytes | None = None, remove_avatar: bool = False) -> dict:
    """Saves user profile (name, avatar) to config directory."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    profile_file = get_profile_file_path()
    avatar_file = get_avatar_file_path()

    current_profile = load_user_profile()
    if name is not None:
        cleaned_name = name.strip()
        new_name = cleaned_name if cleaned_name else "User"
    else:
        new_name = current_profile["name"]

    if remove_avatar:
        if avatar_file.is_file():
            try:
                avatar_file.unlink()
            except OSError:
                pass
    elif avatar_bytes:
        temp_avatar = config_dir / "avatar.jpg.tmp"
        try:
            temp_avatar.write_bytes(avatar_bytes)
            temp_avatar.replace(avatar_file)
        except Exception:
            if temp_avatar.is_file():
                try:
                    temp_avatar.unlink()
                except OSError:
                    pass

    temp_profile = config_dir / "profile.json.tmp"
    try:
        temp_profile.write_text(json.dumps({"name": new_name}, indent=2), encoding="utf-8")
        temp_profile.replace(profile_file)
    except Exception:
        if temp_profile.is_file():
            try:
                temp_profile.unlink()
            except OSError:
                pass

    return load_user_profile()


def load_app_settings() -> dict:
    """
    Loads application settings (theme, library_path, etc.) from settings.json.
    Automatically migrates legacy standalone library_path file into settings.json if present.
    """
    settings_file = get_settings_file_path()
    legacy_file = get_legacy_config_file_path()

    raw_data: dict = {}
    if settings_file.is_file():
        try:
            parsed = json.loads(settings_file.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                raw_data = parsed
        except Exception:
            raw_data = {}

    # Validate and normalize theme
    raw_theme = raw_data.get("theme")
    theme = raw_theme if raw_theme in ("crimson", "kuromi") else "crimson"

    # Extract library_path
    raw_lib = raw_data.get("library_path")
    library_path = raw_lib.strip() if isinstance(raw_lib, str) and raw_lib.strip() else None

    # Migration check: if settings.json does not contain library_path, check legacy standalone file
    if library_path is None and legacy_file.is_file():
        try:
            legacy_content = legacy_file.read_text(encoding="utf-8").strip()
            if legacy_content:
                # Prepare migration payload
                migration_payload: dict = {"theme": theme, "library_path": legacy_content}
                for k, v in raw_data.items():
                    if k not in ("appearance", "theme", "library_path"):
                        migration_payload[k] = v

                config_dir = settings_file.parent
                config_dir.mkdir(parents=True, exist_ok=True)
                temp_settings = config_dir / f"{settings_file.name}.tmp"
                try:
                    temp_settings.write_text(json.dumps(migration_payload, indent=2), encoding="utf-8")
                    temp_settings.replace(settings_file)
                    # Successful write! Remove old standalone library_path file
                    try:
                        legacy_file.unlink()
                    except OSError:
                        pass
                    library_path = legacy_content
                except Exception:
                    # Write failed: clean up temp file and do NOT remove legacy file
                    if temp_settings.is_file():
                        try:
                            temp_settings.unlink()
                        except OSError:
                            pass
                    # Return legacy_content in-memory so user does not lose configured library
                    library_path = legacy_content
        except Exception:
            pass

    result: dict = {"theme": theme}
    if library_path is not None:
        result["library_path"] = library_path

    # Preserve any other non-appearance keys
    for k, v in raw_data.items():
        if k not in ("appearance", "theme", "library_path"):
            result[k] = v

    return result


def save_app_settings(theme: str | None = None, library_path: str | None = None) -> dict:
    """Saves application settings (theme, library_path) to settings.json."""
    settings_file = get_settings_file_path()
    config_dir = settings_file.parent
    config_dir.mkdir(parents=True, exist_ok=True)

    current = load_app_settings()
    payload: dict = {}

    new_theme = current.get("theme", "crimson")
    if theme is not None and theme in ("crimson", "kuromi"):
        new_theme = theme
    payload["theme"] = new_theme

    if library_path is not None:
        cleaned_path = library_path.strip()
        if cleaned_path:
            payload["library_path"] = cleaned_path
    elif "library_path" in current and current["library_path"]:
        payload["library_path"] = current["library_path"]

    for k, v in current.items():
        if k not in ("appearance", "theme", "library_path"):
            payload[k] = v

    temp_settings = config_dir / f"{settings_file.name}.tmp"
    try:
        temp_settings.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_settings.replace(settings_file)
    except Exception:
        if temp_settings.is_file():
            try:
                temp_settings.unlink()
            except OSError:
                pass
        raise

    return load_app_settings()


def save_library_path_config(path_str: str) -> None:
    """Saves configured manga library directory to settings.json."""
    save_app_settings(library_path=path_str)


def load_saved_library_path() -> str | None:
    """Loads saved manga library directory from settings.json if available."""
    settings = load_app_settings()
    return settings.get("library_path")


def get_default_library_dir() -> str | None:
    """Resolves default library path via env override or saved config. Returns None if unconfigured."""
    if os.environ.get("MANGA_DIR"):
        return os.environ["MANGA_DIR"]
    saved = load_saved_library_path()
    if saved:
        return saved
    return None


DEFAULT_LIBRARY_DIR = get_default_library_dir()


def choose_folder_native(prompt: str = "Select your Manga library folder:") -> str | None:
    """
    Prompts user with native folder selection dialog (osascript on macOS, PowerShell on Windows).
    Supports MOCK_FOLDER_PICKER_RESULT environment variable for automated testing.
    """
    if "MOCK_FOLDER_PICKER_RESULT" in os.environ:
        val = os.environ["MOCK_FOLDER_PICKER_RESULT"].strip()
        return val if val else None

    if sys.platform == "win32":
        ps_cmd = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
            f"$f.Description = '{prompt}'; "
            "$f.ShowNewFolderButton = $true; "
            "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-STA", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=120
            )
            if proc.returncode == 0:
                chosen = proc.stdout.strip()
                return chosen if chosen else None
            return None
        except Exception:
            return None

    if sys.platform.startswith("linux"):
        if shutil.which("zenity"):
            try:
                proc = subprocess.run(
                    ["zenity", "--file-selection", "--directory", f"--title={prompt}"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if proc.returncode == 0:
                    chosen = proc.stdout.strip()
                    return chosen if chosen else None
                return None
            except Exception:
                pass
        if shutil.which("kdialog"):
            try:
                proc = subprocess.run(
                    ["kdialog", "--getexistingdirectory", os.path.expanduser("~"), f"--title={prompt}"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if proc.returncode == 0:
                    chosen = proc.stdout.strip()
                    return chosen if chosen else None
                return None
            except Exception:
                pass
        return None

    script = f'''
    tell application "System Events"
        activate
    end tell
    try
        set selectedFolder to choose folder with prompt "{prompt}"
        return POSIX path of selectedFolder
    on error number -128
        return ""
    end try
    '''
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120
        )
        if proc.returncode == 0:
            chosen = proc.stdout.strip()
            if chosen and chosen != "/":
                chosen = chosen.rstrip("/")
            return chosen if chosen else None
        return None
    except Exception:
        return None


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}
ARCHIVE_EXTENSIONS = {".cbz", ".zip"}

EXTENSION_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
    ".bmp": "image/bmp",
}


def is_safe_archive_member(name: str) -> bool:
    """
    Validates that an archive member name is safe and does not attempt path traversal.
    """
    if not name or not isinstance(name, str):
        return False
    clean = name.replace("\\", "/").strip()
    if clean.startswith("/") or clean.startswith("\\"):
        return False
    if len(clean) > 1 and clean[1] == ":":
        return False
    parts = clean.split("/")
    if any(part in ("..", ".") for part in parts):
        return False
    return True


def natural_sort_key(text: str):
    """
    Sort strings containing numbers naturally:
    e.g. ['1.jpg', '2.jpg', '10.jpg'] instead of ['1.jpg', '10.jpg', '2.jpg']
    """
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def is_valid_http_url(url: str) -> bool:
    """Validates that a URL is a valid HTTP or HTTPS URL."""
    if not isinstance(url, str):
        return False
    trimmed = url.strip()
    if not trimmed:
        return False
    try:
        parsed = urlparse(trimmed)
        return parsed.scheme.lower() in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


SUPPORTED_IMAGE_TYPES = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "avif": "image/avif",
    "bmp": "image/bmp",
}


def detect_image_format(data: bytes) -> str | None:
    """
    Detects supported image format from magic bytes.
    Returns format identifier ('jpeg', 'png', 'webp', 'gif', 'avif', 'bmp') or None if unsupported/invalid.
    """
    if not isinstance(data, (bytes, bytearray)) or len(data) < 12:
        return None

    # JPEG: starts with \xff\xd8\xff
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"

    # PNG: starts with \x89PNG\r\n\x1a\n
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"

    # WebP: starts with RIFF and bytes 8..12 are WEBP
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"

    # GIF: starts with GIF87a or GIF89a
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"

    # AVIF: bytes 4..8 are ftyp and bytes 8..12 are avif or avis
    if data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"):
        return "avif"

    # BMP: starts with BM and minimum header length
    if data.startswith(b"BM") and len(data) >= 14:
        return "bmp"

    return None


class MangaLibrary:
    """Manages filesystem scanning and resolution of manga series, chapters, and images."""

    def __init__(self, root_path: str | Path | None = None):
        self.root_path = Path(root_path).expanduser().resolve() if root_path else None

    def exists(self) -> bool:
        return bool(self.root_path and self.root_path.exists() and self.root_path.is_dir())

    def _is_safe_child(self, path: Path) -> bool:
        """Prevent directory traversal attacks."""
        if not self.root_path:
            return False
        try:
            resolved = path.resolve()
            return self.root_path in resolved.parents or resolved == self.root_path
        except (ValueError, RuntimeError):
            return False

    @staticmethod
    def _list_archive_images(archive_path: Path) -> list[str]:
        """
        Safely lists all supported image files in a CBZ or ZIP archive.
        Filters out directories, hidden/system files, unsupported extensions, and path traversal attempts.
        Sorts image filenames naturally.
        """
        if not archive_path.is_file():
            return []
        try:
            if not zipfile.is_zipfile(archive_path):
                return []
            with zipfile.ZipFile(archive_path, "r") as zf:
                valid_images = []
                for info in zf.infolist():
                    if info.is_dir() or info.filename.endswith("/"):
                        continue
                    filename = info.filename
                    if not is_safe_archive_member(filename):
                        continue
                    parts = filename.replace("\\", "/").split("/")
                    if any(part.startswith(".") or part == "__MACOSX" for part in parts):
                        continue
                    ext = Path(filename).suffix.lower()
                    if ext in IMAGE_EXTENSIONS:
                        base_name = Path(filename).name
                        valid_images.append(base_name)

                valid_images.sort(key=natural_sort_key)
                return valid_images
        except Exception:
            return []

    def _resolve_chapter_path(self, series_name: str, chapter_name: str) -> Path | None:
        """
        Resolves and validates a chapter path (directory or .cbz/.zip archive).
        Returns the safe Path object or None if invalid.
        """
        if not self.root_path or not series_name or not chapter_name:
            return None
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        # Check direct path
        chapter_path = series_dir / chapter_name
        if self._is_safe_child(chapter_path):
            if chapter_path.is_dir() and not chapter_path.name.startswith("."):
                return chapter_path
            if chapter_path.is_file() and chapter_path.suffix.lower() in ARCHIVE_EXTENSIONS and not chapter_path.name.startswith("."):
                return chapter_path

        # Fallback if chapter_name was passed without extension
        for ext in ARCHIVE_EXTENSIONS:
            candidate = series_dir / f"{chapter_name}{ext}"
            if self._is_safe_child(candidate) and candidate.is_file() and not candidate.name.startswith("."):
                return candidate

        return None

    def list_series(self) -> list:
        """
        Discovers all manga/manhwa series in the library root.
        Ignores hidden folders (starting with '.').
        """
        if not self.exists():
            return []

        series_list = []
        for entry in os.scandir(self.root_path):
            if entry.is_dir() and not entry.name.startswith("."):
                try:
                    chapter_count = sum(
                        1 for ch in os.scandir(entry.path)
                        if not ch.name.startswith(".") and (
                            ch.is_dir() or
                            (ch.is_file() and Path(ch.name).suffix.lower() in ARCHIVE_EXTENSIONS)
                        )
                    )
                except OSError:
                    chapter_count = 0

                has_cover = self.get_cover_source(entry.name) is not None
                series_list.append({
                    "name": entry.name,
                    "chapter_count": chapter_count,
                    "has_cover": has_cover,
                    "cover_url": f"/api/cover?series={quote(entry.name)}" if has_cover else None
                })

        series_list.sort(key=lambda s: natural_sort_key(s["name"]))
        return series_list

    def list_chapters(self, series_name: str) -> list:
        """
        Discovers and naturally sorts all chapters inside a series directory.
        Supports chapter subdirectories, .cbz files, and .zip files.
        Ignores hidden folders and files (starting with '.'), and unsupported loose files.
        """
        if not self.root_path:
            return []
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return []

        chapters = []
        for entry in os.scandir(series_dir):
            if entry.name.startswith("."):
                continue

            if entry.is_dir():
                try:
                    img_count = sum(
                        1 for f in os.scandir(entry.path)
                        if f.is_file() and not f.name.startswith(".") and Path(f.name).suffix.lower() in IMAGE_EXTENSIONS
                    )
                except OSError:
                    img_count = 0
                chapters.append({
                    "name": entry.name,
                    "image_count": img_count
                })
            elif entry.is_file():
                ext = Path(entry.name).suffix.lower()
                if ext in ARCHIVE_EXTENSIONS:
                    images = self._list_archive_images(Path(entry.path))
                    display_name = entry.name[:-len(ext)]
                    chapters.append({
                        "name": display_name,
                        "image_count": len(images)
                    })

        chapters.sort(key=lambda c: natural_sort_key(c["name"]))
        return chapters

    def list_images(self, series_name: str, chapter_name: str) -> list[str]:
        """
        Discovers and naturally sorts all images inside a chapter (directory or archive).
        """
        chapter_path = self._resolve_chapter_path(series_name, chapter_name)
        if not chapter_path:
            return []

        if chapter_path.is_dir():
            image_files = []
            try:
                for entry in os.scandir(chapter_path):
                    if entry.is_file() and not entry.name.startswith("."):
                        if Path(entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                            image_files.append(entry.name)
            except OSError:
                return []
            image_files.sort(key=natural_sort_key)
            return image_files

        if chapter_path.is_file() and chapter_path.suffix.lower() in ARCHIVE_EXTENSIONS:
            return self._list_archive_images(chapter_path)

        return []

    def get_image_path(self, series_name: str, chapter_name: str, file_name: str) -> Path | None:
        """Resolves the absolute path of an image securely for directory chapters."""
        chapter_path = self._resolve_chapter_path(series_name, chapter_name)
        if not chapter_path or not chapter_path.is_dir():
            return None
        target_path = chapter_path / file_name
        if not self._is_safe_child(target_path):
            return None
        if target_path.is_file() and target_path.suffix.lower() in IMAGE_EXTENSIONS:
            return target_path
        return None

    def get_chapter_image_info(self, series_name: str, chapter_name: str, file_name: str) -> tuple[str, Path, str, int, str] | None:
        """
        Resolves image information for either a directory chapter or archive chapter.
        Returns a tuple: (source_type, source_path, member_name_or_empty, file_size, mime_type)
        where source_type is "file" or "archive".
        Returns None if not found or invalid.
        """
        chapter_path = self._resolve_chapter_path(series_name, chapter_name)
        if not chapter_path:
            return None

        # 1. Directory chapter
        if chapter_path.is_dir():
            target_path = chapter_path / file_name
            if not self._is_safe_child(target_path):
                return None
            if target_path.is_file() and target_path.suffix.lower() in IMAGE_EXTENSIONS:
                mime_type, _ = mimetypes.guess_type(str(target_path))
                if not mime_type:
                    mime_type = EXTENSION_MIME_TYPES.get(target_path.suffix.lower(), "image/jpeg")
                return ("file", target_path, "", target_path.stat().st_size, mime_type)
            return None

        # 2. Archive chapter (.cbz or .zip)
        if chapter_path.is_file() and chapter_path.suffix.lower() in ARCHIVE_EXTENSIONS:
            if not is_safe_archive_member(file_name):
                return None
            try:
                if not zipfile.is_zipfile(chapter_path):
                    return None
                with zipfile.ZipFile(chapter_path, "r") as zf:
                    target_info = None
                    try:
                        info = zf.getinfo(file_name)
                        if not info.is_dir() and not info.filename.endswith("/"):
                            target_info = info
                    except KeyError:
                        pass

                    # Fallback to matching by basename
                    if not target_info:
                        for info in zf.infolist():
                            if info.is_dir() or info.filename.endswith("/"):
                                continue
                            if Path(info.filename).name == file_name:
                                target_info = info
                                break

                    if not target_info:
                        return None

                    if not is_safe_archive_member(target_info.filename):
                        return None

                    ext = Path(target_info.filename).suffix.lower()
                    if ext not in IMAGE_EXTENSIONS:
                        return None

                    mime_type, _ = mimetypes.guess_type(target_info.filename)
                    if not mime_type:
                        mime_type = EXTENSION_MIME_TYPES.get(ext, "image/jpeg")

                    return ("archive", chapter_path, target_info.filename, target_info.file_size, mime_type)
            except Exception:
                return None

        return None

    def get_cover_source(self, series_name: str) -> tuple[str, Path, str, int, str] | None:
        """
        Resolves the cover image source for a series.
        Priority:
        1. <series_dir>/cover.jpg (or .jpeg)
        2. First image of the first naturally sorted chapter (directory or archive)
        Returns None if no cover or chapter images exist.
        """
        if not self.root_path:
            return None
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        # Priority 1: <series_dir>/cover.jpg (or .jpeg)
        for cand_name in ("cover.jpg", "cover.jpeg"):
            candidate = series_dir / cand_name
            if candidate.is_file():
                mime_type = "image/jpeg"
                return ("file", candidate, "", candidate.stat().st_size, mime_type)

        # Priority 2: First image of the first naturally sorted chapter
        chapters = self.list_chapters(series_name)
        for ch in chapters:
            images = self.list_images(series_name, ch["name"])
            if images:
                first_img = images[0]
                img_info = self.get_chapter_image_info(series_name, ch["name"], first_img)
                if img_info:
                    return img_info

        return None

    def get_cover_path(self, series_name: str) -> Path | None:
        """
        Resolves the cover image path for a series if located directly on disk as a file.
        Preserves backward compatibility for callers expecting a Path.
        """
        if not self.root_path:
            return None
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        # Priority 1: <series_dir>/cover.jpg (or .jpeg)
        candidate = series_dir / "cover.jpg"
        if candidate.is_file():
            return candidate
        candidate_jpeg = series_dir / "cover.jpeg"
        if candidate_jpeg.is_file():
            return candidate_jpeg

        # Priority 2: First image of first chapter if chapter is a directory
        chapters = self.list_chapters(series_name)
        for ch in chapters:
            images = self.list_images(series_name, ch["name"])
            if images:
                first_img = images[0]
                img_path = self.get_image_path(series_name, ch["name"], first_img)
                if img_path and img_path.is_file():
                    return img_path

        return None

    def get_background_source(self, series_name: str) -> tuple[str, Path, str, int, str] | None:
        """
        Resolves the atmospheric background image source for a series hero.
        Priority:
        1. <series_dir>/background.jpg (or .jpeg)
        2. <series_dir>/cover.jpg (or .jpeg)
        3. First image of the first naturally sorted chapter (directory or archive)
        4. None if no image exists anywhere
        """
        if not self.root_path:
            return None
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        # Priority 1: <series_dir>/background.jpg (or .jpeg)
        for cand_name in ("background.jpg", "background.jpeg"):
            candidate = series_dir / cand_name
            if candidate.is_file():
                mime_type = "image/jpeg"
                return ("file", candidate, "", candidate.stat().st_size, mime_type)

        # Priority 2 & 3: Fallback to cover source (cover.jpg/jpeg, then first image of first chapter)
        return self.get_cover_source(series_name)

    def get_background_path(self, series_name: str) -> Path | None:
        """
        Resolves the atmospheric background image path for a series hero if located directly on disk as a file.
        Preserves backward compatibility.
        """
        if not self.root_path:
            return None
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        # Priority 1: <series_dir>/background.jpg (or .jpeg)
        bg_candidate = series_dir / "background.jpg"
        if bg_candidate.is_file():
            return bg_candidate
        bg_candidate_jpeg = series_dir / "background.jpeg"
        if bg_candidate_jpeg.is_file():
            return bg_candidate_jpeg

        # Priority 2: Fallback to <series_dir>/cover.jpg
        cover_candidate = self.get_cover_path(series_name)
        if cover_candidate and cover_candidate.is_file():
            return cover_candidate

        return None

    def has_background_file(self, series_name: str) -> bool:
        """Checks if a dedicated background.jpg (or .jpeg) exists for a series."""
        if not self.root_path:
            return False
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return False
        return (series_dir / "background.jpg").is_file() or (series_dir / "background.jpeg").is_file()

    def save_cover_image(self, series_name: str, image_bytes: bytes) -> bool:
        """
        Saves uploaded image bytes as <series_dir>/cover.jpg.
        Validates safety, format, and writes atomically.
        """
        if not self.root_path:
            return False
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return False

        if not detect_image_format(image_bytes):
            return False

        target_file = series_dir / "cover.jpg"
        if not self._is_safe_child(target_file):
            return False

        temp_file = series_dir / "cover.jpg.tmp"
        try:
            temp_file.write_bytes(image_bytes)
            temp_file.replace(target_file)
            jpeg_alt = series_dir / "cover.jpeg"
            if jpeg_alt.is_file():
                try:
                    jpeg_alt.unlink()
                except OSError:
                    pass
            return True
        except Exception:
            if temp_file.is_file():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            return False

    def save_background_image(self, series_name: str, image_bytes: bytes) -> bool:
        """
        Saves uploaded image bytes as <series_dir>/background.jpg.
        Validates safety, format, and writes atomically.
        """
        if not self.root_path:
            return False
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return False

        if not detect_image_format(image_bytes):
            return False

        target_file = series_dir / "background.jpg"
        if not self._is_safe_child(target_file):
            return False

        temp_file = series_dir / "background.jpg.tmp"
        try:
            temp_file.write_bytes(image_bytes)
            temp_file.replace(target_file)
            jpeg_alt = series_dir / "background.jpeg"
            if jpeg_alt.is_file():
                try:
                    jpeg_alt.unlink()
                except OSError:
                    pass
            return True
        except Exception:
            if temp_file.is_file():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            return False

    def remove_background_image(self, series_name: str) -> bool:
        """
        Removes <series_dir>/background.jpg (and .jpeg) so series falls back to cover.
        """
        if not self.root_path:
            return False
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return False

        for fname in ("background.jpg", "background.jpeg", "background.jpg.tmp", "background.jpeg.tmp"):
            fpath = series_dir / fname
            if fpath.is_file():
                try:
                    fpath.unlink()
                except OSError:
                    pass
        return True

    def get_reader_data(self, series_name: str) -> dict | None:
        """
        Retrieves reader data (bookmarks, progress, preferences, and summary) for a given series.
        Returns default dict if file does not exist or is malformed.
        Returns None if series_name is invalid or unsafe.
        """
        if not self.root_path:
            return None
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        default_data = {
            "progress": {},
            "bookmarks": [],
            "reader": {
                "style": "spaced"
            }
        }

        reader_file = series_dir / ".reader" / "reader_data.json"
        if not reader_file.is_file():
            return default_data

        try:
            content = reader_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                return default_data

            progress = data.get("progress")
            if not isinstance(progress, dict):
                progress = {}

            bookmarks = data.get("bookmarks")
            if not isinstance(bookmarks, list):
                bookmarks = []

            reader_meta = data.get("reader")
            style = "spaced"
            if isinstance(reader_meta, dict):
                raw_style = reader_meta.get("style")
                if raw_style in ("spaced", "seamless"):
                    style = raw_style

            # Normalize progress and bookmarks so both display names and archive filenames work seamlessly
            normalized_progress = {}
            for k, v in progress.items():
                if isinstance(k, str) and isinstance(v, str):
                    normalized_progress[k] = v
                    for ext in ARCHIVE_EXTENSIONS:
                        if k.lower().endswith(ext):
                            normalized_progress[k[:-len(ext)]] = v
                        elif (series_dir / f"{k}{ext}").is_file():
                            normalized_progress[f"{k}{ext}"] = v

            normalized_bookmarks = set()
            for b in bookmarks:
                if isinstance(b, str):
                    normalized_bookmarks.add(b)
                    for ext in ARCHIVE_EXTENSIONS:
                        if b.lower().endswith(ext):
                            normalized_bookmarks.add(b[:-len(ext)])
                        elif (series_dir / f"{b}{ext}").is_file():
                            normalized_bookmarks.add(f"{b}{ext}")

            result = {
                "progress": normalized_progress,
                "bookmarks": sorted(list(normalized_bookmarks), key=natural_sort_key),
                "reader": {
                    "style": style
                }
            }
            if isinstance(data.get("summary"), str):
                result["summary"] = data["summary"]
            if isinstance(data.get("author"), str):
                result["author"] = data["author"]
            if isinstance(data.get("links"), dict):
                clean_links = {}
                for k, v in data["links"].items():
                    if isinstance(k, str) and isinstance(v, str) and is_valid_http_url(v):
                        clean_links[k] = v
                result["links"] = clean_links
            return result
        except Exception:
            return default_data

    def save_reader_data(self, series_name: str, data: dict) -> bool:
        """
        Saves reader data for a series inside <Series>/.reader/reader_data.json.
        """
        if not self.root_path:
            return False
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return False

        reader_dir = series_dir / ".reader"
        reader_dir.mkdir(parents=True, exist_ok=True)
        reader_file = reader_dir / "reader_data.json"
        temp_file = reader_dir / "reader_data.json.tmp"

        reader_meta = data.get("reader", {})
        style = "spaced"
        if isinstance(reader_meta, dict):
            raw_style = reader_meta.get("style")
            if raw_style in ("spaced", "seamless"):
                style = raw_style

        clean_data = {
            "progress": data.get("progress", {}),
            "bookmarks": data.get("bookmarks", []),
            "reader": {
                "style": style
            }
        }
        if "summary" in data and isinstance(data["summary"], str):
            clean_data["summary"] = data["summary"]
        if "author" in data and isinstance(data["author"], str):
            clean_data["author"] = data["author"]
        if "links" in data and isinstance(data["links"], dict):
            clean_links = {}
            for k, v in data["links"].items():
                if isinstance(k, str) and isinstance(v, str) and is_valid_http_url(v):
                    clean_links[k] = v
            clean_data["links"] = clean_links

        try:
            temp_file.write_text(json.dumps(clean_data, indent=2), encoding="utf-8")
            temp_file.replace(reader_file)
            return True
        except Exception:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            return False

    def update_metadata(self, series_name: str, summary: str | None = None, author: str | None = None, links: dict | None = None) -> dict | None:
        """
        Updates series metadata (summary, author, links) in reader_data.json.
        Preserves progress, bookmarks, and reader settings.
        Returns the updated reader data dictionary on success, or None on error.
        """
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        data = self.get_reader_data(series_name)
        if data is None:
            return None

        if summary is not None:
            if not isinstance(summary, str):
                return None
            data["summary"] = summary

        if author is not None:
            if not isinstance(author, str):
                return None
            data["author"] = author

        if links is not None:
            if not isinstance(links, dict):
                return None
            validated_links = {}
            for label, url in links.items():
                if not isinstance(label, str) or not label.strip():
                    return None
                if not isinstance(url, str) or not is_valid_http_url(url):
                    return None
                validated_links[label.strip()] = url.strip()
            data["links"] = validated_links

        if self.save_reader_data(series_name, data):
            return data
        return None

    def update_reader_style(self, series_name: str, style: str) -> dict | None:
        """
        Updates the reader style preference ('spaced' or 'seamless') for a series.
        """
        if style not in ("spaced", "seamless"):
            return None

        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        data = self.get_reader_data(series_name)
        if data is None:
            return None

        data["reader"] = {"style": style}
        if self.save_reader_data(series_name, data):
            return data
        return None

    def update_progress(self, series_name: str, chapter_name: str, image_name: str) -> dict | None:
        """
        Updates the last read image for a chapter in a series.
        """
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        chapter_path = self._resolve_chapter_path(series_name, chapter_name)
        if not chapter_path:
            return None

        # Validate image filename (must not contain path separators)
        if not image_name or "/" in image_name or "\\" in image_name or ".." in image_name:
            return None

        data = self.get_reader_data(series_name)
        if data is None:
            return None

        data["progress"][chapter_name] = image_name
        for ext in ARCHIVE_EXTENSIONS:
            if chapter_name.lower().endswith(ext):
                data["progress"][chapter_name[:-len(ext)]] = image_name
            elif (series_dir / f"{chapter_name}{ext}").is_file():
                data["progress"][f"{chapter_name}{ext}"] = image_name

        if self.save_reader_data(series_name, data):
            return data
        return None

    def toggle_bookmark(self, series_name: str, chapter_name: str, bookmarked: bool | None = None) -> dict | None:
        """
        Adds, removes, or toggles bookmark for a chapter in a series.
        """
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        chapter_path = self._resolve_chapter_path(series_name, chapter_name)
        if not chapter_path:
            return None

        data = self.get_reader_data(series_name)
        if data is None:
            return None

        bookmarks = set(data.get("bookmarks", []))
        names_to_modify = {chapter_name}
        for ext in ARCHIVE_EXTENSIONS:
            if chapter_name.lower().endswith(ext):
                names_to_modify.add(chapter_name[:-len(ext)])
            elif (series_dir / f"{chapter_name}{ext}").is_file():
                names_to_modify.add(f"{chapter_name}{ext}")

        if bookmarked is None:
            is_currently_bookmarked = any(n in bookmarks for n in names_to_modify)
            if is_currently_bookmarked:
                bookmarks.difference_update(names_to_modify)
            else:
                bookmarks.update(names_to_modify)
        elif bookmarked:
            bookmarks.update(names_to_modify)
        else:
            bookmarks.difference_update(names_to_modify)

        data["bookmarks"] = sorted(list(bookmarks), key=natural_sort_key)
        if self.save_reader_data(series_name, data):
            return data
        return None


class MangaRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for serving manga API endpoints and static assets."""

    library: MangaLibrary
    static_dir: Path

    def _send_json(self, data, status: int = HTTPStatus.OK):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = HTTPStatus.NOT_FOUND):
        self._send_json({"error": message}, status=status)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Helper to get single query parameter
        def get_param(name: str):
            vals = query.get(name)
            return vals[0] if vals else None

        # 0. API: Application Settings (/api/settings)
        if path == "/api/settings":
            self._send_json(load_app_settings())
            return

        # 0b. API: User Profile endpoints (/api/profile and /api/profile/avatar)
        if path == "/api/profile":
            self._send_json(load_user_profile())
            return

        if path == "/api/profile/avatar":
            avatar_path = get_avatar_file_path()
            if not avatar_path.is_file() or avatar_path.stat().st_size == 0:
                self._send_error("Avatar not found", HTTPStatus.NOT_FOUND)
                return

            try:
                with open(avatar_path, "rb") as f:
                    header = f.read(32)
                fmt = detect_image_format(header)
                if fmt and fmt in SUPPORTED_IMAGE_TYPES:
                    mime_type = SUPPORTED_IMAGE_TYPES[fmt]
                else:
                    mime_type, _ = mimetypes.guess_type(str(avatar_path))
                    if not mime_type:
                        mime_type = "image/jpeg"

                file_size = avatar_path.stat().st_size
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()

                with open(avatar_path, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        # 0b. API: Get active library info (/api/library)
        if path == "/api/library":
            self._send_json({
                "library_path": str(self.library.root_path) if self.library.root_path else None,
                "library_exists": self.library.exists(),
                "series_count": len(self.library.list_series()) if self.library.exists() else 0
            })
            return

        # 1. API: List all series
        if path == "/api/series":
            series = self.library.list_series()
            self._send_json({
                "library_path": str(self.library.root_path) if self.library.root_path else None,
                "library_exists": self.library.exists(),
                "series_count": len(series),
                "series": series
            })
            return

        # 2. API: List chapters for a series (/api/chapters?series=...)
        if path == "/api/chapters":
            series_name = get_param("series")
            if not series_name:
                self._send_error("Missing required query parameter: 'series'", HTTPStatus.BAD_REQUEST)
                return

            chapters = self.library.list_chapters(series_name)
            self._send_json({
                "series": series_name,
                "chapter_count": len(chapters),
                "chapters": chapters
            })
            return

        # 3. API: List images in a chapter (/api/images?series=...&chapter=...)
        if path == "/api/images":
            series_name = get_param("series")
            chapter_name = get_param("chapter")
            if not series_name or not chapter_name:
                self._send_error("Missing required query parameters: 'series' and 'chapter'", HTTPStatus.BAD_REQUEST)
                return

            images = self.library.list_images(series_name, chapter_name)
            # Build image URLs for convenient frontend consumption
            image_items = [
                {
                    "filename": img,
                    "url": f"/api/image-file?series={quote(series_name)}&chapter={quote(chapter_name)}&file={quote(img)}"
                }
                for img in images
            ]
            self._send_json({
                "series": series_name,
                "chapter": chapter_name,
                "image_count": len(image_items),
                "images": image_items
            })
            return

        # 4. API: Serve single image file (/api/image-file?series=...&chapter=...&file=...)
        if path == "/api/image-file":
            series_name = get_param("series")
            chapter_name = get_param("chapter")
            file_name = get_param("file")

            if not series_name or not chapter_name or not file_name:
                self._send_error("Missing required query parameters: 'series', 'chapter', 'file'", HTTPStatus.BAD_REQUEST)
                return

            info = self.library.get_chapter_image_info(series_name, chapter_name, file_name)
            if not info:
                self._send_error(f"Image not found: {file_name}", HTTPStatus.NOT_FOUND)
                return

            source_type = info[0]
            if source_type == "file":
                _, image_path, _, file_size, mime_type = info
                try:
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()

                    with open(image_path, "rb") as f:
                        # Stream in 64KB chunks to keep memory usage minimal
                        while chunk := f.read(65536):
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            elif source_type == "archive":
                _, archive_path, member_name, file_size, mime_type = info
                try:
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", mime_type)
                        self.send_header("Content-Length", str(file_size))
                        self.send_header("Cache-Control", "public, max-age=86400")
                        self.end_headers()

                        with zf.open(member_name, "r") as f:
                            while chunk := f.read(65536):
                                self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception:
                    self._send_error(f"Failed to read image from archive: {file_name}", HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        # 5. API: Serve series cover image (/api/cover?series=...)
        if path == "/api/cover":
            series_name = get_param("series")
            if not series_name:
                self._send_error("Missing required query parameter: 'series'", HTTPStatus.BAD_REQUEST)
                return

            cover_info = self.library.get_cover_source(series_name)
            if not cover_info:
                self._send_error(f"Cover not found for series: {series_name}", HTTPStatus.NOT_FOUND)
                return

            source_type = cover_info[0]
            if source_type == "file":
                _, cover_path, _, file_size, mime_type = cover_info
                try:
                    with open(cover_path, "rb") as f:
                        header = f.read(32)
                    fmt = detect_image_format(header)
                    if fmt and fmt in SUPPORTED_IMAGE_TYPES:
                        mime_type = SUPPORTED_IMAGE_TYPES[fmt]
                    elif not mime_type:
                        mime_type, _ = mimetypes.guess_type(str(cover_path))
                        if not mime_type:
                            mime_type = "image/jpeg"

                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Expires", "0")
                    self.end_headers()

                    with open(cover_path, "rb") as f:
                        while chunk := f.read(65536):
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            elif source_type == "archive":
                _, archive_path, member_name, file_size, mime_type = cover_info
                try:
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        with zf.open(member_name, "r") as f:
                            header = f.read(32)
                        fmt = detect_image_format(header)
                        if fmt and fmt in SUPPORTED_IMAGE_TYPES:
                            mime_type = SUPPORTED_IMAGE_TYPES[fmt]

                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", mime_type)
                        self.send_header("Content-Length", str(file_size))
                        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                        self.send_header("Pragma", "no-cache")
                        self.send_header("Expires", "0")
                        self.end_headers()

                        with zf.open(member_name, "r") as f:
                            while chunk := f.read(65536):
                                self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception:
                    self._send_error(f"Failed to read cover from archive: {series_name}", HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        # 5b. API: Serve series background image (/api/background?series=...)
        if path == "/api/background":
            series_name = get_param("series")
            if not series_name:
                self._send_error("Missing required query parameter: 'series'", HTTPStatus.BAD_REQUEST)
                return

            bg_info = self.library.get_background_source(series_name)
            if not bg_info:
                self._send_error(f"Background not found for series: {series_name}", HTTPStatus.NOT_FOUND)
                return

            source_type = bg_info[0]
            if source_type == "file":
                _, bg_path, _, file_size, mime_type = bg_info
                try:
                    with open(bg_path, "rb") as f:
                        header = f.read(32)
                    fmt = detect_image_format(header)
                    if fmt and fmt in SUPPORTED_IMAGE_TYPES:
                        mime_type = SUPPORTED_IMAGE_TYPES[fmt]
                    elif not mime_type:
                        mime_type, _ = mimetypes.guess_type(str(bg_path))
                        if not mime_type:
                            mime_type = "image/jpeg"

                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Expires", "0")
                    self.end_headers()

                    with open(bg_path, "rb") as f:
                        while chunk := f.read(65536):
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            elif source_type == "archive":
                _, archive_path, member_name, file_size, mime_type = bg_info
                try:
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        with zf.open(member_name, "r") as f:
                            header = f.read(32)
                        fmt = detect_image_format(header)
                        if fmt and fmt in SUPPORTED_IMAGE_TYPES:
                            mime_type = SUPPORTED_IMAGE_TYPES[fmt]

                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", mime_type)
                        self.send_header("Content-Length", str(file_size))
                        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                        self.send_header("Pragma", "no-cache")
                        self.send_header("Expires", "0")
                        self.end_headers()

                        with zf.open(member_name, "r") as f:
                            while chunk := f.read(65536):
                                self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception:
                    self._send_error(f"Failed to read background from archive: {series_name}", HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        # 6. API: Get reader data (bookmarks, progress, preferences, metadata) for a series (/api/reader-data?series=...)
        if path in ("/api/reader-data", "/api/metadata"):
            series_name = get_param("series")
            if not series_name:
                self._send_error("Missing required query parameter: 'series'", HTTPStatus.BAD_REQUEST)
                return

            data = self.library.get_reader_data(series_name)
            if data is None:
                self._send_error(f"Series not found or invalid: {series_name}", HTTPStatus.NOT_FOUND)
                return

            self._send_json({
                "series": series_name,
                "summary": data.get("summary", ""),
                "author": data.get("author", ""),
                "links": data.get("links", {}),
                "has_cover": self.library.get_cover_source(series_name) is not None,
                "has_background": self.library.has_background_file(series_name),
                "progress": data["progress"],
                "bookmarks": data["bookmarks"],
                "reader": data["reader"]
            })
            return

        # 7. Static Assets (index.html, style.css, app.js)
        clean_path = path.lstrip("/")
        if clean_path.startswith("static/"):
            clean_path = clean_path[len("static/"):]
        if not clean_path:
            clean_path = "index.html"

        candidate_file = (self.static_dir / clean_path).resolve()
        # Verify candidate_file is strictly within static_dir
        if (self.static_dir in candidate_file.parents or candidate_file == self.static_dir) and candidate_file.is_file():
            mime_type, _ = mimetypes.guess_type(str(candidate_file))
            if not mime_type:
                mime_type = "text/plain"

            content_type = f"{mime_type}; charset=utf-8" if "text" in mime_type or "javascript" in mime_type or "json" in mime_type else mime_type
            data = candidate_file.read_bytes()

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return

        # 8. Status / Health Check endpoint
        if path == "/api/status":
            self._send_json({
                "status": "online",
                "app": "Local Manga Reader (Phase 6)",
                "library_path": str(self.library.root_path) if self.library.root_path else None,
                "library_exists": self.library.exists(),
                "endpoints": [
                    "/api/series",
                    "/api/chapters?series=<series_name>",
                    "/api/images?series=<series_name>&chapter=<chapter_name>",
                    "/api/image-file?series=<series_name>&chapter=<chapter_name>&file=<filename>",
                    "/api/cover?series=<series_name>",
                    "/api/reader-data?series=<series_name>",
                    "POST /api/progress",
                    "POST /api/bookmark",
                    "POST /api/style"
                ]
            })
            return

        # Default 404
        self._send_error("Endpoint not found", HTTPStatus.NOT_FOUND)

    def _read_json_body(self) -> dict | None:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                return None
            body_bytes = self.rfile.read(content_length)
            data = json.loads(body_bytes.decode("utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 0. API: Update user profile (/api/profile)
        if path == "/api/profile":
            content_type = self.headers.get("Content-Type", "")
            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                content_length = 0

            if content_length > 50 * 1024 * 1024:
                self._send_error("Payload too large (max 50MB)", HTTPStatus.BAD_REQUEST)
                return

            if "application/json" in content_type:
                body = self._read_json_body()
                if body is None:
                    self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                    return
                name = body.get("name")
                if name is not None and not isinstance(name, str):
                    self._send_error("Field 'name' must be a string", HTTPStatus.BAD_REQUEST)
                    return
                remove_avatar = bool(body.get("remove_avatar", False))
                avatar_bytes = None
                raw_b64 = body.get("avatar")
                if raw_b64 and isinstance(raw_b64, str):
                    try:
                        import base64
                        if "," in raw_b64:
                            raw_b64 = raw_b64.split(",", 1)[1]
                        avatar_bytes = base64.b64decode(raw_b64)
                    except Exception:
                        self._send_error("Invalid base64 avatar data", HTTPStatus.BAD_REQUEST)
                        return
                    if not detect_image_format(avatar_bytes):
                        self._send_error("Invalid or unsupported image file. Supported formats: JPEG, PNG, WebP, GIF, AVIF, BMP", HTTPStatus.BAD_REQUEST)
                        return

                profile = save_user_profile(name=name, avatar_bytes=avatar_bytes, remove_avatar=remove_avatar)
                self._send_json({"success": True, **profile})
                return
            else:
                self._send_error("Expected application/json Content-Type", HTTPStatus.BAD_REQUEST)
                return

        # 0b. API: Upload or remove user profile avatar directly (/api/profile/avatar)
        if path == "/api/profile/avatar":
            query = parse_qs(parsed.query)
            action = query.get("action", [None])[0]
            if action in ("remove", "delete"):
                profile = save_user_profile(remove_avatar=True)
                self._send_json({"success": True, **profile})
                return

            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                content_length = 0

            if content_length <= 0:
                self._send_error("Missing request body", HTTPStatus.BAD_REQUEST)
                return
            if content_length > 50 * 1024 * 1024:
                self._send_error("Payload too large (max 50MB)", HTTPStatus.BAD_REQUEST)
                return

            raw_body = self.rfile.read(content_length)
            content_type = self.headers.get("Content-Type", "")
            avatar_bytes = None
            if "application/json" in content_type:
                try:
                    import base64
                    json_data = json.loads(raw_body.decode("utf-8"))
                    raw_b64 = json_data.get("avatar", "")
                    if "," in raw_b64:
                        raw_b64 = raw_b64.split(",", 1)[1]
                    avatar_bytes = base64.b64decode(raw_b64)
                except Exception:
                    self._send_error("Invalid base64 avatar data", HTTPStatus.BAD_REQUEST)
                    return
            else:
                avatar_bytes = raw_body

            if not avatar_bytes or not detect_image_format(avatar_bytes):
                self._send_error("Invalid or unsupported image file. Supported formats: JPEG, PNG, WebP, GIF, AVIF, BMP", HTTPStatus.BAD_REQUEST)
                return

            profile = save_user_profile(avatar_bytes=avatar_bytes)
            self._send_json({"success": True, **profile})
            return

        # 0c. API: Update application settings (/api/settings)
        if path == "/api/settings":
            body = self._read_json_body()
            if body is None:
                self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                return

            theme = body.get("theme")
            if theme is None or theme not in ("crimson", "kuromi"):
                self._send_error("Invalid or missing theme value. Allowed: 'crimson', 'kuromi'", HTTPStatus.BAD_REQUEST)
                return

            updated = save_app_settings(theme=theme)
            self._send_json({"success": True, **updated})
            return

        # 1. API: Update reading progress (/api/progress)
        if path == "/api/progress":
            body = self._read_json_body()
            if not body:
                self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                return

            series = body.get("series")
            chapter = body.get("chapter")
            image = body.get("image")

            if not series or not chapter or not image:
                self._send_error("Missing required fields: 'series', 'chapter', 'image'", HTTPStatus.BAD_REQUEST)
                return

            data = self.library.update_progress(series, chapter, image)
            if data is None:
                self._send_error("Invalid series, chapter, or image filename", HTTPStatus.BAD_REQUEST)
                return

            self._send_json({
                "success": True,
                "series": series,
                "chapter": chapter,
                "progress": data["progress"],
                "bookmarks": data["bookmarks"],
                "reader": data["reader"]
            })
            return

        # 2. API: Toggle chapter bookmark (/api/bookmark)
        if path == "/api/bookmark":
            body = self._read_json_body()
            if not body:
                self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                return

            series = body.get("series")
            chapter = body.get("chapter")
            bookmarked = body.get("bookmarked")

            if not series or not chapter:
                self._send_error("Missing required fields: 'series', 'chapter'", HTTPStatus.BAD_REQUEST)
                return

            data = self.library.toggle_bookmark(series, chapter, bookmarked)
            if data is None:
                self._send_error("Invalid series or chapter name", HTTPStatus.BAD_REQUEST)
                return

            self._send_json({
                "success": True,
                "series": series,
                "chapter": chapter,
                "bookmarked": chapter in data["bookmarks"],
                "progress": data["progress"],
                "bookmarks": data["bookmarks"],
                "reader": data["reader"]
            })
            return

        # 3. API: Update reading style preference (/api/style)
        if path == "/api/style":
            body = self._read_json_body()
            if not body:
                self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                return

            series = body.get("series")
            style = body.get("style")

            if not series or not style:
                self._send_error("Missing required fields: 'series', 'style'", HTTPStatus.BAD_REQUEST)
                return

            if style not in ("spaced", "seamless"):
                self._send_error("Invalid style value. Allowed: 'spaced', 'seamless'", HTTPStatus.BAD_REQUEST)
                return

            data = self.library.update_reader_style(series, style)
            if data is None:
                self._send_error("Failed to update reader style (invalid series)", HTTPStatus.BAD_REQUEST)
                return

            self._send_json({
                "success": True,
                "series": series,
                "style": data["reader"]["style"],
                "progress": data["progress"],
                "bookmarks": data["bookmarks"],
                "reader": data["reader"]
            })
            return

        # 4. API: Unified reader data and metadata endpoint (/api/reader-data, /api/metadata)
        if path in ("/api/reader-data", "/api/metadata"):
            body = self._read_json_body()
            if not body:
                self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                return

            series = body.get("series")
            chapter = body.get("chapter")
            action = body.get("action")

            if not series:
                self._send_error("Missing required field: 'series'", HTTPStatus.BAD_REQUEST)
                return

            # Check if this is a metadata update action
            is_metadata_action = (
                action == "metadata" or
                path == "/api/metadata" or
                "metadata" in body or
                (action is None and chapter is None and ("summary" in body or "author" in body or "links" in body))
            )

            if is_metadata_action:
                meta_payload = body.get("metadata") if isinstance(body.get("metadata"), dict) else body

                summary = meta_payload.get("summary")
                author = meta_payload.get("author")
                links = meta_payload.get("links")

                if summary is not None and not isinstance(summary, str):
                    self._send_error("Field 'summary' must be a string", HTTPStatus.BAD_REQUEST)
                    return
                if author is not None and not isinstance(author, str):
                    self._send_error("Field 'author' must be a string", HTTPStatus.BAD_REQUEST)
                    return
                if links is not None:
                    if not isinstance(links, dict):
                        self._send_error("Field 'links' must be an object/dict", HTTPStatus.BAD_REQUEST)
                        return
                    for label, url in links.items():
                        if not isinstance(label, str) or not label.strip():
                            self._send_error("Link label must be a non-empty string", HTTPStatus.BAD_REQUEST)
                            return
                        if not isinstance(url, str) or not is_valid_http_url(url):
                            self._send_error(f"Invalid URL for link '{label}'. Must be a valid HTTP or HTTPS URL.", HTTPStatus.BAD_REQUEST)
                            return

                data = self.library.update_metadata(series, summary=summary, author=author, links=links)
                if data is None:
                    self._send_error("Failed to update metadata (invalid series or data)", HTTPStatus.BAD_REQUEST)
                    return

                self._send_json({
                    "success": True,
                    "series": series,
                    "summary": data.get("summary", ""),
                    "author": data.get("author", ""),
                    "links": data.get("links", {}),
                    "has_cover": self.library.get_cover_source(series) is not None,
                    "has_background": self.library.has_background_file(series),
                    "progress": data["progress"],
                    "bookmarks": data["bookmarks"],
                    "reader": data["reader"]
                })
                return

            if action == "style" or (action is None and "style" in body):
                style = body.get("style")
                if not style or style not in ("spaced", "seamless"):
                    self._send_error("Invalid or missing style value", HTTPStatus.BAD_REQUEST)
                    return
                data = self.library.update_reader_style(series, style)
            else:
                if not chapter:
                    self._send_error("Missing required field: 'chapter'", HTTPStatus.BAD_REQUEST)
                    return

                if action == "progress" or "image" in body:
                    image = body.get("image")
                    if not image:
                        self._send_error("Missing required field: 'image'", HTTPStatus.BAD_REQUEST)
                        return
                    data = self.library.update_progress(series, chapter, image)
                elif action == "bookmark" or "bookmarked" in body:
                    bookmarked = body.get("bookmarked")
                    data = self.library.toggle_bookmark(series, chapter, bookmarked)
                else:
                    self._send_error("Unrecognized action or missing payload in /api/reader-data", HTTPStatus.BAD_REQUEST)
                    return

            if data is None:
                self._send_error("Failed to update reader data (invalid input)", HTTPStatus.BAD_REQUEST)
                return

            self._send_json({
                "success": True,
                "series": series,
                "progress": data["progress"],
                "bookmarks": data["bookmarks"],
                "reader": data["reader"]
            })
            return

        # 5. API: Upload series cover image (/api/cover?series=...)
        if path == "/api/cover":
            query = parse_qs(parsed.query)
            series_name = query.get("series", [None])[0]
            content_type = self.headers.get("Content-Type", "")
            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                content_length = 0

            if content_length <= 0:
                self._send_error("Missing request body", HTTPStatus.BAD_REQUEST)
                return
            if content_length > 50 * 1024 * 1024:
                self._send_error("Payload too large (max 50MB)", HTTPStatus.BAD_REQUEST)
                return

            raw_body = self.rfile.read(content_length)
            image_bytes = None

            if "application/json" in content_type:
                try:
                    import base64
                    json_data = json.loads(raw_body.decode("utf-8"))
                    if not series_name:
                        series_name = json_data.get("series")
                    raw_b64 = json_data.get("image", "")
                    if "," in raw_b64:
                        raw_b64 = raw_b64.split(",", 1)[1]
                    image_bytes = base64.b64decode(raw_b64)
                except Exception:
                    self._send_error("Invalid JSON body or base64 image data", HTTPStatus.BAD_REQUEST)
                    return
            else:
                image_bytes = raw_body

            if not series_name:
                self._send_error("Missing required parameter: 'series'", HTTPStatus.BAD_REQUEST)
                return

            if not self.library.root_path:
                self._send_error("No library configured", HTTPStatus.BAD_REQUEST)
                return

            series_dir = self.library.root_path / series_name
            if not self.library._is_safe_child(series_dir) or not series_dir.is_dir():
                self._send_error("Invalid or nonexistent series", HTTPStatus.BAD_REQUEST)
                return

            if not image_bytes or not detect_image_format(image_bytes):
                self._send_error("Invalid or unsupported image file. Supported formats: JPEG, PNG, WebP, GIF, AVIF, BMP", HTTPStatus.BAD_REQUEST)
                return

            success = self.library.save_cover_image(series_name, image_bytes)
            if not success:
                self._send_error("Failed to save cover image", HTTPStatus.INTERNAL_SERVER_ERROR)
                return

            self._send_json({
                "success": True,
                "series": series_name,
                "cover_url": f"/api/cover?series={quote(series_name)}"
            })
            return

        # 6. API: Upload or remove series background image (/api/background?series=...)
        if path == "/api/background":
            query = parse_qs(parsed.query)
            series_name = query.get("series", [None])[0]
            action = query.get("action", [None])[0]
            content_type = self.headers.get("Content-Type", "")
            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                content_length = 0

            raw_body = b""
            json_data = None
            if content_length > 0:
                if content_length > 50 * 1024 * 1024:
                    self._send_error("Payload too large (max 50MB)", HTTPStatus.BAD_REQUEST)
                    return
                raw_body = self.rfile.read(content_length)
                if "application/json" in content_type:
                    try:
                        json_data = json.loads(raw_body.decode("utf-8"))
                        if not series_name:
                            series_name = json_data.get("series")
                        if not action:
                            action = json_data.get("action")
                    except Exception:
                        pass

            if not series_name:
                self._send_error("Missing required parameter: 'series'", HTTPStatus.BAD_REQUEST)
                return

            if not self.library.root_path:
                self._send_error("No library configured", HTTPStatus.BAD_REQUEST)
                return

            series_dir = self.library.root_path / series_name
            if not self.library._is_safe_child(series_dir) or not series_dir.is_dir():
                self._send_error("Invalid or nonexistent series", HTTPStatus.BAD_REQUEST)
                return

            if action in ("remove", "delete"):
                self.library.remove_background_image(series_name)
                self._send_json({
                    "success": True,
                    "series": series_name,
                    "action": "removed"
                })
                return

            image_bytes = None
            if json_data and json_data.get("image"):
                import base64
                try:
                    raw_b64 = json_data["image"]
                    if "," in raw_b64:
                        raw_b64 = raw_b64.split(",", 1)[1]
                    image_bytes = base64.b64decode(raw_b64)
                except Exception:
                    self._send_error("Invalid base64 image data", HTTPStatus.BAD_REQUEST)
                    return
            else:
                image_bytes = raw_body

            if not image_bytes or not detect_image_format(image_bytes):
                self._send_error("Invalid or unsupported image file. Supported formats: JPEG, PNG, WebP, GIF, AVIF, BMP", HTTPStatus.BAD_REQUEST)
                return

            success = self.library.save_background_image(series_name, image_bytes)
            if not success:
                self._send_error("Failed to save background image", HTTPStatus.INTERNAL_SERVER_ERROR)
                return

            self._send_json({
                "success": True,
                "series": series_name,
                "background_url": f"/api/background?series={quote(series_name)}"
            })
            return

        # 6. API: Change manga library directory (/api/library)
        if path == "/api/library":
            body = self._read_json_body()
            if not body:
                self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                return

            action = body.get("action")
            target_path_str = None

            if action == "select":
                chosen = choose_folder_native("Select your Manga library folder:")
                if not chosen:
                    self._send_json({
                        "success": False,
                        "cancelled": True,
                        "message": "Folder selection cancelled by user"
                    })
                    return
                target_path_str = chosen
            elif "path" in body:
                raw_path = body.get("path")
                if not isinstance(raw_path, str) or not raw_path.strip():
                    self._send_error("Field 'path' must be a non-empty string", HTTPStatus.BAD_REQUEST)
                    return
                target_path_str = raw_path.strip()
            else:
                self._send_error("Missing required field: 'action' or 'path'", HTTPStatus.BAD_REQUEST)
                return

            resolved_path = Path(target_path_str).expanduser().resolve()
            if not resolved_path.exists() or not resolved_path.is_dir():
                self._send_error(f"Selected path is not an existing directory: {resolved_path}", HTTPStatus.BAD_REQUEST)
                return

            # Update library in memory for all subsequent requests
            new_lib = MangaLibrary(str(resolved_path))
            MangaRequestHandler.library = new_lib

            # Persist to configuration file outside git repository
            save_library_path_config(str(resolved_path))

            self._send_json({
                "success": True,
                "library_path": str(resolved_path),
                "library_exists": True,
                "series_count": len(new_lib.list_series())
            })
            return

        self._send_error("Endpoint not found", HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        def get_param(name: str):
            vals = query.get(name)
            return vals[0] if vals else None

        if path == "/api/background":
            series_name = get_param("series")
            if not series_name:
                self._send_error("Missing required parameter: 'series'", HTTPStatus.BAD_REQUEST)
                return

            if not self.library.root_path:
                self._send_error("No library configured", HTTPStatus.BAD_REQUEST)
                return

            series_dir = self.library.root_path / series_name
            if not self.library._is_safe_child(series_dir) or not series_dir.is_dir():
                self._send_error("Invalid or nonexistent series", HTTPStatus.BAD_REQUEST)
                return

            self.library.remove_background_image(series_name)
            self._send_json({
                "success": True,
                "series": series_name,
                "action": "removed"
            })
            return

        if path == "/api/profile/avatar":
            profile = save_user_profile(remove_avatar=True)
            self._send_json({
                "success": True,
                "action": "removed",
                **profile
            })
            return

        self._send_error("Endpoint not found", HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """Custom concise logging format."""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def run_server(library_dir: str | None = None, port: int = DEFAULT_PORT):
    library = MangaLibrary(library_dir)
    print("=" * 60)
    print("  Local Manga & Manhwa Reader - Core Server (Phase 1)")
    print("=" * 60)
    print(f"Library Directory : {library.root_path if library.root_path else 'None (unconfigured)'}")
    print(f"Directory Exists  : {'Yes' if library.exists() else 'No (directory will be scanned once created or selected)'}")
    print(f"Server URL        : http://localhost:{port}")
    print("=" * 60)
    print("Available API endpoints:")
    print(f"  • Status check   : http://localhost:{port}/api/status")
    print(f"  • Series list    : http://localhost:{port}/api/series")
    print(f"  • Chapters list  : http://localhost:{port}/api/chapters?series=<series_name>")
    print(f"  • Images list    : http://localhost:{port}/api/images?series=<series_name>&chapter=<chapter_name>")
    print("=" * 60)
    print("Press Ctrl+C to stop the server.\n")

    MangaRequestHandler.library = library
    MangaRequestHandler.static_dir = Path(__file__).parent / "static"

    server = ThreadingHTTPServer(("127.0.0.1", port), MangaRequestHandler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        server.server_close()


def main():
    default_dir = get_default_library_dir()
    parser = argparse.ArgumentParser(
        description="Local web-based manga/manhwa reader server (Phase 1)"
    )
    parser.add_argument(
        "--dir", "-d",
        type=str,
        default=default_dir,
        help=f"Path to your manga library folder (default: {default_dir if default_dir else 'None (unconfigured)'})"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to bind the HTTP server to (default: {DEFAULT_PORT})"
    )
    args = parser.parse_args()
    run_server(library_dir=args.dir, port=args.port)


if __name__ == "__main__":
    main()
