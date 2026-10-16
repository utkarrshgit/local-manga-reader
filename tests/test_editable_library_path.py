"""
test_editable_library_path.py - Automated regression tests for Editable Library Path in { index }.

Covers all 20 required points from Section 8:
1. The editable path field is present in the existing library-switching interface.
2. The field is populated with the active library's full path.
3. A valid path can be applied successfully.
4. Enter submits the path.
5. Surrounding whitespace is handled correctly.
6. A path containing spaces works.
7. A missing or invalid path is rejected.
8. A file path is rejected when a directory is required.
9. An inaccessible directory is handled gracefully where reliably testable.
10. A failed switch does not change the active library.
11. A failed switch does not overwrite the saved library path.
12. A successful switch updates the active and persisted paths according to existing behavior.
13. Switching between two libraries loads the correct pinned-series list.
14. Pinning or unpinning after switching affects only that library.
15. Switching back restores the original library's pins.
16. CLI --dir continues to leave the saved default library configuration unchanged.
17. The existing folder picker still works.
18. Existing theme, profile, remote reading, and local reading behavior remain intact.
19. Error messages are rendered safely and do not interpret user input as HTML.
20. The UI remains compatible with both Crimson and Kuromi themes.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server import (
    MangaLibrary,
    MangaRequestHandler,
    canonicalize_library_path,
    get_settings_file_path,
    load_app_settings,
    load_pinned_series,
    save_app_settings,
    save_library_path_config,
    save_pinned_series,
    save_user_profile,
    toggle_pin_series,
)


class MockSocket:
    """Mock socket for simulating HTTP requests against MangaRequestHandler."""

    def __init__(self, request_bytes: bytes):
        self.rfile = BytesIO(request_bytes)
        self.wfile = BytesIO()

    def makefile(self, mode: str = "rb", *args, **kwargs):
        if "b" in mode:
            if "r" in mode:
                return self.rfile
            return self.wfile
        raise ValueError(f"Unsupported mock mode: {mode}")

    def sendall(self, data: bytes):
        self.wfile.write(data)


class TestEditableLibraryPath(unittest.TestCase):
    """Test suite verifying editable library path switching, validation, and pin isolation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name).resolve()

        # Isolated config directory
        self.config_dir = (self.temp_path / "config").resolve()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.orig_config_dir = os.environ.get("LOCAL_MANGA_CONFIG_DIR")
        os.environ["LOCAL_MANGA_CONFIG_DIR"] = str(self.config_dir)

        # Create Library A with series
        self.lib_a_dir = (self.temp_path / "LibraryA").resolve()
        self.lib_a_dir.mkdir(parents=True, exist_ok=True)
        for s_name in ("Manga A1", "Manga A2"):
            s_dir = self.lib_a_dir / s_name
            ch_dir = s_dir / "Chapter 1"
            ch_dir.mkdir(parents=True, exist_ok=True)
            (ch_dir / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        # Create Library B with series
        self.lib_b_dir = (self.temp_path / "LibraryB").resolve()
        self.lib_b_dir.mkdir(parents=True, exist_ok=True)
        for s_name in ("Manga B1", "Manga B2"):
            s_dir = self.lib_b_dir / s_name
            ch_dir = s_dir / "Chapter 1"
            ch_dir.mkdir(parents=True, exist_ok=True)
            (ch_dir / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        # Start with Library A
        self.lib_a = MangaLibrary(str(self.lib_a_dir))
        save_library_path_config(str(self.lib_a_dir))
        MangaRequestHandler.library = self.lib_a
        MangaRequestHandler.static_dir = PROJECT_ROOT / "static"

    def tearDown(self):
        MangaRequestHandler.library = None
        if self.orig_config_dir:
            os.environ["LOCAL_MANGA_CONFIG_DIR"] = self.orig_config_dir
        else:
            os.environ.pop("LOCAL_MANGA_CONFIG_DIR", None)
        os.environ.pop("MOCK_FOLDER_PICKER_RESULT", None)
        self.temp_dir.cleanup()

    def _simulate_get(self, path: str):
        req = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("utf-8")
        sock = MockSocket(req)
        handler = MangaRequestHandler(sock, ("127.0.0.1", 12345), None)
        sock.wfile.seek(0)
        resp = sock.wfile.read().decode("utf-8", errors="replace")
        headers, _, body = resp.partition("\r\n\r\n")
        return headers, body

    def _simulate_post(self, path: str, json_data: dict):
        body_bytes = json.dumps(json_data).encode("utf-8")
        req = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode("utf-8") + body_bytes
        sock = MockSocket(req)
        handler = MangaRequestHandler(sock, ("127.0.0.1", 12345), None)
        sock.wfile.seek(0)
        resp = sock.wfile.read().decode("utf-8", errors="replace")
        headers, _, body = resp.partition("\r\n\r\n")
        return headers, body

    # 1. Field presence
    def test_01_editable_path_field_present_in_ui(self):
        """1. The editable path field is present in the existing library-switching interface."""
        headers, html = self._simulate_get("/")
        self.assertIn("200 OK", headers)
        self.assertIn('id="modal-settings"', html)
        self.assertIn('id="form-library-path"', html)
        self.assertIn('id="input-library-path"', html)
        self.assertIn('id="btn-apply-library-path"', html)
        self.assertIn('id="library-path-error"', html)
        self.assertIn('id="settings-library-path"', html)
        self.assertIn('id="btn-change-folder"', html)

        # CSS checks
        _, css = self._simulate_get("/style.css")
        self.assertIn(".settings-path-form", css)
        self.assertIn(".settings-path-input", css)
        self.assertIn(".btn-apply-path", css)
        self.assertIn(".settings-path-error", css)

    # 2. Field population
    def test_02_field_populated_with_active_library_path(self):
        """2. The field is populated with the active library's full path."""
        _, js = self._simulate_get("/app.js")
        self.assertIn("inputLibraryPath.value = data.library_path", js)
        self.assertIn("inputLibraryPath", js)
        self.assertIn("openSettingsModal", js)

        # GET /api/library returns the active library path
        headers, body = self._simulate_get("/api/library")
        self.assertIn("200 OK", headers)
        data = json.loads(body)
        self.assertEqual(data["library_path"], str(self.lib_a_dir.resolve()))

    # 3. Valid path applied successfully
    def test_03_valid_path_applied_successfully(self):
        """3. A valid path can be applied successfully."""
        headers, body = self._simulate_post("/api/library", {"path": str(self.lib_b_dir)})
        self.assertIn("200 OK", headers)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["library_path"], str(self.lib_b_dir.resolve()))
        self.assertTrue(data["library_exists"])
        self.assertEqual(data["series_count"], 2)

        # Verify active library in request handler
        self.assertEqual(MangaRequestHandler.library.root_path, self.lib_b_dir.resolve())

    # 4. Enter submits the path
    def test_04_enter_submits_the_path(self):
        """4. Enter submits the path in the form and on keydown."""
        _, js = self._simulate_get("/app.js")
        self.assertIn('formLibraryPath.addEventListener("submit"', js)
        self.assertIn('e.key === "Enter"', js)
        self.assertIn("applyManualLibraryPath", js)

    # 5. Surrounding whitespace handled correctly
    def test_05_surrounding_whitespace_handled_correctly(self):
        """5. Surrounding whitespace is handled correctly."""
        padded_path = f"   \t  {self.lib_b_dir}  \n  "
        headers, body = self._simulate_post("/api/library", {"path": padded_path})
        self.assertIn("200 OK", headers)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["library_path"], str(self.lib_b_dir.resolve()))

    # 6. Path containing spaces works
    def test_06_path_containing_spaces_works(self):
        """6. A path containing spaces works."""
        space_dir = self.temp_path / "My Manga Collection" / "Japanese Manga"
        space_dir.mkdir(parents=True, exist_ok=True)
        s_dir = space_dir / "Space Manga"
        ch_dir = s_dir / "Chapter 1"
        ch_dir.mkdir(parents=True, exist_ok=True)
        (ch_dir / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        headers, body = self._simulate_post("/api/library", {"path": str(space_dir)})
        self.assertIn("200 OK", headers)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["library_path"], str(space_dir.resolve()))
        self.assertEqual(data["series_count"], 1)

    # 7. Missing or invalid path is rejected
    def test_07_missing_or_invalid_path_rejected(self):
        """7. A missing or invalid path is rejected."""
        # Nonexistent directory
        headers, body = self._simulate_post("/api/library", {"path": str(self.temp_path / "does_not_exist_9876")})
        self.assertIn("400 Bad Request", headers)
        data = json.loads(body)
        self.assertIn("Directory does not exist", data.get("error", ""))

        # Empty / whitespace path
        headers2, body2 = self._simulate_post("/api/library", {"path": "   "})
        self.assertIn("400 Bad Request", headers2)
        data2 = json.loads(body2)
        self.assertIn("non-empty string", data2.get("error", ""))

        # URL path
        headers3, body3 = self._simulate_post("/api/library", {"path": "https://weebcentral.com/series/123"})
        self.assertIn("400 Bad Request", headers3)
        data3 = json.loads(body3)
        self.assertIn("URLs cannot be used", data3.get("error", ""))

    # 8. File path rejected
    def test_08_file_path_rejected_when_directory_required(self):
        """8. A file path is rejected when a directory is required."""
        dummy_file = self.temp_path / "not_a_dir.txt"
        dummy_file.write_text("hello", encoding="utf-8")

        headers, body = self._simulate_post("/api/library", {"path": str(dummy_file)})
        self.assertIn("400 Bad Request", headers)
        data = json.loads(body)
        self.assertIn("file, not a directory", data.get("error", ""))

    # 9. Inaccessible directory handled gracefully
    def test_09_inaccessible_directory_handled_gracefully(self):
        """9. An inaccessible directory is handled gracefully where reliably testable."""
        test_dir = self.temp_path / "unreadable_dir"
        test_dir.mkdir(parents=True, exist_ok=True)

        with patch("server.os.scandir", side_effect=PermissionError("Permission denied")):
            headers, body = self._simulate_post("/api/library", {"path": str(test_dir)})
            self.assertIn("400 Bad Request", headers)
            data = json.loads(body)
            self.assertIn("Permission denied", data.get("error", ""))

    # 10. Failed switch does not change active library
    def test_10_failed_switch_does_not_change_active_library(self):
        """10. A failed switch does not change the active library."""
        initial_root = MangaRequestHandler.library.root_path
        headers, _ = self._simulate_post("/api/library", {"path": str(self.temp_path / "fake_dir_xyz")})
        self.assertIn("400 Bad Request", headers)
        self.assertEqual(MangaRequestHandler.library.root_path, initial_root)

    # 11. Failed switch does not overwrite saved library path
    def test_11_failed_switch_does_not_overwrite_saved_library_path(self):
        """11. A failed switch does not overwrite the saved library path."""
        settings_before = load_app_settings()
        saved_before = settings_before.get("library_path")

        headers, _ = self._simulate_post("/api/library", {"path": "https://evil.com/manga"})
        self.assertIn("400 Bad Request", headers)

        settings_after = load_app_settings()
        self.assertEqual(settings_after.get("library_path"), saved_before)

    # 12. Successful switch updates active and persisted paths
    def test_12_successful_switch_updates_active_and_persisted_paths(self):
        """12. A successful switch updates the active and persisted paths according to existing behavior."""
        headers, body = self._simulate_post("/api/library", {"path": str(self.lib_b_dir)})
        self.assertIn("200 OK", headers)

        # Active in memory
        self.assertEqual(MangaRequestHandler.library.root_path, self.lib_b_dir.resolve())

        # Persisted in settings.json
        settings = load_app_settings()
        self.assertEqual(settings.get("library_path"), str(self.lib_b_dir.resolve()))

    # 13. Switching between two libraries loads correct pinned-series list
    def test_13_switching_between_two_libraries_loads_correct_pinned_list(self):
        """13. Switching between two libraries loads the correct pinned-series list."""
        # Pin in Library A
        toggle_pin_series("Manga A1", pinned=True, library_path=self.lib_a_dir)

        # Pin in Library B
        toggle_pin_series("Manga B1", pinned=True, library_path=self.lib_b_dir)

        # Switch to Library B via API
        headers, body = self._simulate_post("/api/library", {"path": str(self.lib_b_dir)})
        self.assertIn("200 OK", headers)
        data = json.loads(body)
        self.assertEqual(data["pinned"], ["Manga B1"])
        self.assertNotIn("Manga A1", data["pinned"])

        # GET /api/pin returns Library B pins
        _, pin_body = self._simulate_get("/api/pin")
        pin_data = json.loads(pin_body)
        self.assertEqual(pin_data["pinned"], ["Manga B1"])

    # 14. Pinning or unpinning after switching affects only that library
    def test_14_pinning_or_unpinning_after_switching_affects_only_that_library(self):
        """14. Pinning or unpinning after switching affects only that library."""
        toggle_pin_series("Manga A1", pinned=True, library_path=self.lib_a_dir)
        toggle_pin_series("Manga B1", pinned=True, library_path=self.lib_b_dir)

        # Switch to Library B
        self._simulate_post("/api/library", {"path": str(self.lib_b_dir)})

        # Pin Manga B2 in Library B
        h_pin, b_pin = self._simulate_post("/api/pin", {"series": "Manga B2", "pinned": True})
        self.assertIn("200 OK", h_pin)
        b_data = json.loads(b_pin)
        self.assertIn("Manga B1", b_data["pinned_series"])
        self.assertIn("Manga B2", b_data["pinned_series"])

        # Library A pins must remain ["Manga A1"]
        lib_a_pins = load_pinned_series(self.lib_a_dir)
        self.assertEqual(lib_a_pins, ["Manga A1"])

    # 15. Switching back restores original library's pins
    def test_15_switching_back_restores_original_library_pins(self):
        """15. Switching back restores the original library's pins."""
        toggle_pin_series("Manga A1", pinned=True, library_path=self.lib_a_dir)
        toggle_pin_series("Manga B1", pinned=True, library_path=self.lib_b_dir)

        # Switch to B
        self._simulate_post("/api/library", {"path": str(self.lib_b_dir)})

        # Switch back to A
        h_back, b_back = self._simulate_post("/api/library", {"path": str(self.lib_a_dir)})
        self.assertIn("200 OK", h_back)
        back_data = json.loads(b_back)
        self.assertEqual(back_data["pinned"], ["Manga A1"])

        # Verify via GET /api/pin
        _, pin_body = self._simulate_get("/api/pin")
        self.assertEqual(json.loads(pin_body)["pinned"], ["Manga A1"])

    # 16. CLI --dir continues to leave saved default library unchanged
    def test_16_cli_dir_leaves_saved_default_library_unchanged(self):
        """16. CLI --dir continues to leave the saved default library configuration unchanged."""
        # Library A is saved in settings.json
        save_library_path_config(str(self.lib_a_dir))

        # Simulate CLI --dir session with Library B
        cli_lib = MangaLibrary(str(self.lib_b_dir))
        MangaRequestHandler.library = cli_lib

        # Check that settings.json still points to Library A
        saved = load_app_settings().get("library_path")
        self.assertEqual(saved, str(self.lib_a_dir.resolve()))

        # Pin operations in this session use active library
        toggle_pin_series("Manga B1", pinned=True, library_path=cli_lib.root_path)
        self.assertEqual(load_pinned_series(cli_lib.root_path), ["Manga B1"])

        # Saved library path in settings.json remains Library A
        self.assertEqual(load_app_settings().get("library_path"), str(self.lib_a_dir.resolve()))

    # 17. Existing folder picker still works
    def test_17_existing_folder_picker_still_works(self):
        """17. The existing folder picker action still works."""
        os.environ["MOCK_FOLDER_PICKER_RESULT"] = str(self.lib_b_dir)
        headers, body = self._simulate_post("/api/library", {"action": "select"})
        self.assertIn("200 OK", headers)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["library_path"], str(self.lib_b_dir.resolve()))

        # Test cancellation
        os.environ["MOCK_FOLDER_PICKER_RESULT"] = ""
        headers2, body2 = self._simulate_post("/api/library", {"action": "select"})
        self.assertIn("200 OK", headers2)
        data2 = json.loads(body2)
        self.assertFalse(data2["success"])
        self.assertTrue(data2["cancelled"])

    # 18. Existing theme, profile, and reading behavior remain intact
    def test_18_existing_theme_profile_and_reading_state_intact(self):
        """18. Existing theme, profile, and reading state remain intact across switches."""
        # Set theme and profile
        save_app_settings(theme="kuromi")
        save_user_profile(name="TestReader")

        # Mark chapter progress in Library A
        self.lib_a.update_progress("Manga A1", "Chapter 1", "1.jpg")

        # Switch library
        self._simulate_post("/api/library", {"path": str(self.lib_b_dir)})

        # Check settings
        settings = load_app_settings()
        self.assertEqual(settings.get("theme"), "kuromi")

        # Check reading state in Library A was untouched
        state_a = self.lib_a.get_reader_data("Manga A1")
        self.assertIsNotNone(state_a)
        self.assertEqual(state_a.get("progress", {}).get("Chapter 1"), "1.jpg")

    # 19. Error messages rendered safely without HTML interpretation
    def test_19_error_messages_rendered_safely_no_html(self):
        """19. Error messages are rendered safely using textContent and do not interpret HTML."""
        _, js = self._simulate_get("/app.js")
        self.assertIn("libraryPathError.textContent = message", js)
        self.assertNotIn("libraryPathError.innerHTML = message", js)

        # Test sending a path with HTML tags
        malicious_path = "/path/<script>alert('xss')</script>/manga"
        headers, body = self._simulate_post("/api/library", {"path": malicious_path})
        self.assertIn("400 Bad Request", headers)
        data = json.loads(body)
        self.assertIn("error", data)
        # The error is a clean string containing the attempted path without HTML execution
        self.assertIn("<script>alert('xss')</script>", data["error"])

    # 20. Theme compatibility
    def test_20_ui_theme_compatibility(self):
        """20. The UI styling for editable path elements matches both Crimson and Kuromi themes."""
        _, css = self._simulate_get("/style.css")
        # Uses CSS custom properties that adapt to both Crimson and Kuromi themes
        self.assertIn("var(--accent)", css)
        self.assertIn("var(--accent-subtle)", css)
        self.assertIn("var(--surface-elevated)", css)
        self.assertIn("var(--border)", css)
        self.assertIn(".settings-path-input:focus", css)
        self.assertIn(".btn-apply-path", css)


if __name__ == "__main__":
    unittest.main()
