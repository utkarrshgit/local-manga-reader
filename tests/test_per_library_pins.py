"""
test_per_library_pins.py - Automated regression tests for Per-Library Pinned Series persistence.

Verifies:
1. Pinning a series in Library A does not pin it in Library B.
2. Pinning a series in Library B does not alter Library A's pins.
3. Unpinning in one library does not affect another library.
4. Switching libraries returns the correct pinned list.
5. An empty pin list is isolated to its own library.
6. A series not present in the active library is not displayed in its Pinned section.
7. Relative and normalized equivalent library paths resolve to the same pin configuration where applicable.
8. Legacy global pins migrate safely to the default library.
9. Migration does not duplicate or overwrite pins on subsequent startups.
10. Existing unrelated settings remain intact during migration.
11. Temporary --dir usage does not overwrite the saved default library configuration.
12. Temporary-library pin operations are associated with the correct library.
13. Existing pin-related APIs continue to behave correctly.
14. Existing library switching and local manga reading behavior remain unchanged.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from http import HTTPStatus
from io import BytesIO
from pathlib import Path

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


class TestPerLibraryPinPersistence(unittest.TestCase):
    """Regression test suite for per-library pin persistence and library isolation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Isolated config directory outside git repository
        self.config_dir = self.temp_path / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.orig_config_dir = os.environ.get("LOCAL_MANGA_CONFIG_DIR")
        os.environ["LOCAL_MANGA_CONFIG_DIR"] = str(self.config_dir)

        # Create Library A with 3 series
        self.lib_a_dir = self.temp_path / "LibraryA"
        self.lib_a_dir.mkdir(parents=True, exist_ok=True)
        for s_name in ("Manga A1", "Manga A2", "Manga A3"):
            s_dir = self.lib_a_dir / s_name
            ch_dir = s_dir / "Chapter 1"
            ch_dir.mkdir(parents=True, exist_ok=True)
            (ch_dir / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        # Create Library B with 3 series
        self.lib_b_dir = self.temp_path / "LibraryB"
        self.lib_b_dir.mkdir(parents=True, exist_ok=True)
        for s_name in ("Manga B1", "Manga B2", "Manga B3"):
            s_dir = self.lib_b_dir / s_name
            ch_dir = s_dir / "Chapter 1"
            ch_dir.mkdir(parents=True, exist_ok=True)
            (ch_dir / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        self.library_a = MangaLibrary(str(self.lib_a_dir))
        self.library_b = MangaLibrary(str(self.lib_b_dir))

        # Default handler setup
        MangaRequestHandler.library = self.library_a
        MangaRequestHandler.static_dir = PROJECT_ROOT / "static"

    def tearDown(self):
        MangaRequestHandler.library = None
        if self.orig_config_dir is not None:
            os.environ["LOCAL_MANGA_CONFIG_DIR"] = self.orig_config_dir
        else:
            os.environ.pop("LOCAL_MANGA_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def _simulate_request(self, method: str, path: str, body: dict | None = None, handler_library: MangaLibrary | None = None) -> tuple[str, bytes]:
        req_bytes = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n".encode("utf-8")
        if body is not None:
            raw_body = json.dumps(body).encode("utf-8")
            req_bytes += f"Content-Type: application/json\r\nContent-Length: {len(raw_body)}\r\n\r\n".encode("utf-8") + raw_body
        else:
            req_bytes += b"\r\n"

        sock = MockSocket(req_bytes)

        class CustomHandler(MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

            def log_message(self, format, *args):
                pass

        CustomHandler.library = handler_library if handler_library is not None else MangaRequestHandler.library
        CustomHandler.static_dir = PROJECT_ROOT / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        resp = sock.wfile.read()
        split_idx = resp.find(b"\r\n\r\n")
        headers = resp[:split_idx].decode("utf-8", errors="replace")
        content = resp[split_idx + 4:]
        return headers, content

    # 1. Pinning a series in Library A does not pin it in Library B.
    def test_1_pinning_in_library_a_does_not_pin_in_library_b(self):
        toggle_pin_series("Manga A1", True, library_path=self.lib_a_dir)
        pinned_a = load_pinned_series(self.lib_a_dir)
        pinned_b = load_pinned_series(self.lib_b_dir)

        self.assertIn("Manga A1", pinned_a)
        self.assertNotIn("Manga A1", pinned_b)
        self.assertEqual(pinned_b, [])

    # 2. Pinning a series in Library B does not alter Library A's pins.
    def test_2_pinning_in_library_b_does_not_alter_library_a_pins(self):
        toggle_pin_series("Manga A1", True, library_path=self.lib_a_dir)
        toggle_pin_series("Manga B1", True, library_path=self.lib_b_dir)
        toggle_pin_series("Manga B2", True, library_path=self.lib_b_dir)

        pinned_a = load_pinned_series(self.lib_a_dir)
        pinned_b = load_pinned_series(self.lib_b_dir)

        self.assertEqual(pinned_a, ["Manga A1"])
        self.assertEqual(pinned_b, ["Manga B1", "Manga B2"])

    # 3. Unpinning in one library does not affect another library.
    def test_3_unpinning_in_one_library_does_not_affect_another(self):
        toggle_pin_series("Manga A1", True, library_path=self.lib_a_dir)
        toggle_pin_series("Manga B1", True, library_path=self.lib_b_dir)

        # Unpin Manga A1 in Library A
        is_pinned, updated = toggle_pin_series("Manga A1", False, library_path=self.lib_a_dir)
        self.assertFalse(is_pinned)
        self.assertEqual(updated, [])

        # Library A is empty, Library B is still intact
        self.assertEqual(load_pinned_series(self.lib_a_dir), [])
        self.assertEqual(load_pinned_series(self.lib_b_dir), ["Manga B1"])

    # 4. Switching libraries returns the correct pinned list.
    def test_4_switching_libraries_returns_correct_pinned_list(self):
        # Configure initial default library as Library A
        save_library_path_config(str(self.lib_a_dir))
        toggle_pin_series("Manga A1", True, library_path=self.lib_a_dir)
        toggle_pin_series("Manga B2", True, library_path=self.lib_b_dir)

        # Verify Library A pins via GET /api/pinned
        MangaRequestHandler.library = self.library_a
        h, b = self._simulate_request("GET", "/api/pinned")
        self.assertIn("200 OK", h)
        data = json.loads(b.decode("utf-8"))
        self.assertEqual(data["pinned"], ["Manga A1"])

        # Switch to Library B via POST /api/library
        h_switch, b_switch = self._simulate_request("POST", "/api/library", {"path": str(self.lib_b_dir)})
        self.assertIn("200 OK", h_switch)
        switch_data = json.loads(b_switch.decode("utf-8"))
        self.assertTrue(switch_data["success"])
        self.assertEqual(switch_data["pinned"], ["Manga B2"])

        # Subsequent GET /api/series uses Library B's pins
        h_series, b_series = self._simulate_request("GET", "/api/series")
        self.assertIn("200 OK", h_series)
        series_data = json.loads(b_series.decode("utf-8"))
        self.assertEqual(series_data["pinned"], ["Manga B2"])

        # Switch back to Library A
        h_switch2, b_switch2 = self._simulate_request("POST", "/api/library", {"path": str(self.lib_a_dir)})
        self.assertIn("200 OK", h_switch2)
        switch2_data = json.loads(b_switch2.decode("utf-8"))
        self.assertEqual(switch2_data["pinned"], ["Manga A1"])

    # 5. An empty pin list is isolated to its own library.
    def test_5_empty_pin_list_isolated_to_own_library(self):
        toggle_pin_series("Manga A1", True, library_path=self.lib_a_dir)
        save_pinned_series([], library_path=self.lib_b_dir)

        self.assertEqual(load_pinned_series(self.lib_a_dir), ["Manga A1"])
        self.assertEqual(load_pinned_series(self.lib_b_dir), [])

    # 6. A series not present in the active library is not displayed in its Pinned section.
    def test_6_series_not_present_in_active_library_not_displayed(self):
        # Library A contains Manga A1, A2, A3.
        # Pin "Manga B1" under Library A artificially or from previous state
        save_pinned_series(["Manga A1", "NonExistentSeries", "Manga B1"], library_path=self.lib_a_dir)

        # GET /api/series returns scanned series
        MangaRequestHandler.library = self.library_a
        h, b = self._simulate_request("GET", "/api/series")
        data = json.loads(b.decode("utf-8"))
        scanned_names = {s["name"] for s in data["series"]}

        # Active library series list contains only actual series in Library A
        self.assertIn("Manga A1", scanned_names)
        self.assertNotIn("NonExistentSeries", scanned_names)
        self.assertNotIn("Manga B1", scanned_names)

        # Verify frontend filtering contract via Node.js
        node_script = f"""
        const scannedSeries = {json.dumps(data["series"])};
        const pinnedList = {json.dumps(data["pinned"])};
        const pinnedSeriesSet = new Set(pinnedList);

        // Frontend partitioning logic from renderLibrarySeries()
        const displayedPinned = scannedSeries.filter(s => pinnedSeriesSet.has(s.name));
        const displayedPinnedNames = displayedPinned.map(s => s.name);

        if (displayedPinnedNames.includes("NonExistentSeries")) process.exit(1);
        if (displayedPinnedNames.includes("Manga B1")) process.exit(2);
        if (!displayedPinnedNames.includes("Manga A1")) process.exit(3);
        console.log("PINNED_ISOLATION_CONTRACT_PASSED");
        """
        result = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Node contract failed: {result.stderr}")
        self.assertIn("PINNED_ISOLATION_CONTRACT_PASSED", result.stdout)

    # 7. Relative and normalized equivalent library paths resolve to the same pin configuration where applicable.
    def test_7_relative_and_normalized_equivalent_paths_resolve_identically(self):
        canon_a = canonicalize_library_path(self.lib_a_dir)

        # Variants of Library A path
        variant_redundant = str(self.lib_a_dir / ".." / self.lib_a_dir.name)
        variant_dots = str(self.lib_a_dir) + "/./"
        variant_trailing = str(self.lib_a_dir) + "/"

        self.assertEqual(canonicalize_library_path(variant_redundant), canon_a)
        self.assertEqual(canonicalize_library_path(variant_dots), canon_a)
        self.assertEqual(canonicalize_library_path(variant_trailing), canon_a)

        # Pinning using variant path resolves to same entry
        toggle_pin_series("Manga A2", True, library_path=variant_redundant)
        self.assertEqual(load_pinned_series(self.lib_a_dir), ["Manga A2"])
        self.assertEqual(load_pinned_series(variant_dots), ["Manga A2"])
        self.assertEqual(load_pinned_series(variant_trailing), ["Manga A2"])

    # 8. Legacy global pins migrate safely to the default library.
    def test_8_legacy_global_pins_migrate_safely_to_default_library(self):
        settings_file = get_settings_file_path()
        legacy_payload = {
            "theme": "kuromi",
            "library_path": str(self.lib_a_dir),
            "pinned": ["Legacy Manga 1", "Legacy Manga 2"],
        }
        settings_file.write_text(json.dumps(legacy_payload, indent=2), encoding="utf-8")

        # Loading settings triggers migration
        settings = load_app_settings()

        # Legacy global 'pinned' list is removed from settings root
        self.assertNotIn("pinned", settings)
        self.assertIn("pinned_by_library", settings)

        # Migrated pins exist under Library A canonical key
        canon_a = canonicalize_library_path(self.lib_a_dir)
        self.assertEqual(settings["pinned_by_library"].get(canon_a), ["Legacy Manga 1", "Legacy Manga 2"])

        # Also readable via load_pinned_series()
        self.assertEqual(load_pinned_series(self.lib_a_dir), ["Legacy Manga 1", "Legacy Manga 2"])

        # Inspect raw disk content
        raw_disk = json.loads(settings_file.read_text(encoding="utf-8"))
        self.assertNotIn("pinned", raw_disk)
        self.assertEqual(raw_disk["pinned_by_library"][canon_a], ["Legacy Manga 1", "Legacy Manga 2"])

    # 9. Migration does not duplicate or overwrite pins on subsequent startups.
    def test_9_migration_idempotent_no_duplicate_or_overwrite_on_subsequent_startups(self):
        settings_file = get_settings_file_path()
        legacy_payload = {
            "theme": "crimson",
            "library_path": str(self.lib_a_dir),
            "pinned": ["Series Alpha"],
        }
        settings_file.write_text(json.dumps(legacy_payload, indent=2), encoding="utf-8")

        # Initial load triggers migration
        load_app_settings()

        # Add pin to Library B
        toggle_pin_series("Series Beta", True, library_path=self.lib_b_dir)

        # Subsequent loads do NOT re-migrate or overwrite Library B
        settings_reload1 = load_app_settings()
        settings_reload2 = load_app_settings()

        canon_a = canonicalize_library_path(self.lib_a_dir)
        canon_b = canonicalize_library_path(self.lib_b_dir)

        self.assertEqual(settings_reload2["pinned_by_library"][canon_a], ["Series Alpha"])
        self.assertEqual(settings_reload2["pinned_by_library"][canon_b], ["Series Beta"])
        self.assertNotIn("pinned", settings_reload2)

    # 10. Existing unrelated settings remain intact during migration.
    def test_10_unrelated_settings_intact_during_migration(self):
        settings_file = get_settings_file_path()
        payload = {
            "theme": "kuromi",
            "library_path": str(self.lib_a_dir),
            "pinned": ["Series P"],
            "custom_ui_zoom": 120,
            "display_language": "en-US",
        }
        settings_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        migrated = load_app_settings()
        self.assertEqual(migrated["theme"], "kuromi")
        self.assertEqual(migrated["library_path"], str(self.lib_a_dir))
        self.assertEqual(migrated["custom_ui_zoom"], 120)
        self.assertEqual(migrated["display_language"], "en-US")

        # Raw disk inspection
        raw = json.loads(settings_file.read_text(encoding="utf-8"))
        self.assertEqual(raw["custom_ui_zoom"], 120)
        self.assertEqual(raw["display_language"], "en-US")

    # 11. Temporary --dir usage does not overwrite the saved default library configuration.
    def test_11_cli_dir_does_not_overwrite_saved_default_library(self):
        # Save Library A as default
        save_library_path_config(str(self.lib_a_dir))
        self.assertEqual(load_app_settings().get("library_path"), str(self.lib_a_dir))

        # Simulate CLI --dir override with Library B
        temp_cli_library = MangaLibrary(str(self.lib_b_dir))
        MangaRequestHandler.library = temp_cli_library

        # Execute pin operation against temporary library
        h, b = self._simulate_request("POST", "/api/pin", {"series": "Manga B1", "pinned": True}, handler_library=temp_cli_library)
        self.assertIn("200 OK", h)

        # Default library in settings.json MUST NOT be altered
        settings = load_app_settings()
        self.assertEqual(settings.get("library_path"), str(self.lib_a_dir))

    # 12. Temporary-library pin operations are associated with the correct library.
    def test_12_temporary_library_pins_associated_with_correct_library(self):
        save_library_path_config(str(self.lib_a_dir))
        toggle_pin_series("Manga A1", True, library_path=self.lib_a_dir)

        # Simulate session with --dir Library B
        temp_cli_library = MangaLibrary(str(self.lib_b_dir))
        MangaRequestHandler.library = temp_cli_library

        # Pin Manga B2 via API in temporary session
        h, b = self._simulate_request("POST", "/api/pin", {"series": "Manga B2", "pinned": True}, handler_library=temp_cli_library)
        self.assertIn("200 OK", h)
        res = json.loads(b.decode("utf-8"))
        self.assertEqual(res["pinned_series"], ["Manga B2"])

        # Check persistence: Library B has Manga B2, Library A has Manga A1
        self.assertEqual(load_pinned_series(self.lib_b_dir), ["Manga B2"])
        self.assertEqual(load_pinned_series(self.lib_a_dir), ["Manga A1"])

    # 13. Existing pin-related APIs continue to behave correctly.
    def test_13_existing_pin_apis_behave_correctly(self):
        MangaRequestHandler.library = self.library_a

        # Bad request: missing body
        h, b = self._simulate_request("POST", "/api/pin", None)
        self.assertIn("400 Bad Request", h)

        # Bad request: missing series
        h, b = self._simulate_request("POST", "/api/pin", {"pinned": True})
        self.assertIn("400 Bad Request", h)

        # Bad request: non-boolean pinned
        h, b = self._simulate_request("POST", "/api/pin", {"series": "Manga A1", "pinned": "true"})
        self.assertIn("400 Bad Request", h)

        # Valid pin
        h, b = self._simulate_request("POST", "/api/pin", {"series": "Manga A1", "pinned": True})
        self.assertIn("200 OK", h)
        data = json.loads(b.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertTrue(data["pinned"])
        self.assertEqual(data["pinned_series"], ["Manga A1"])

        # GET /api/pin
        h, b = self._simulate_request("GET", "/api/pin")
        self.assertIn("200 OK", h)
        self.assertEqual(json.loads(b.decode("utf-8"))["pinned"], ["Manga A1"])

        # GET /api/pinned
        h, b = self._simulate_request("GET", "/api/pinned")
        self.assertIn("200 OK", h)
        self.assertEqual(json.loads(b.decode("utf-8"))["pinned"], ["Manga A1"])

        # Valid unpin
        h, b = self._simulate_request("POST", "/api/pin", {"series": "Manga A1", "pinned": False})
        self.assertIn("200 OK", h)
        self.assertFalse(json.loads(b.decode("utf-8"))["pinned"])

    # 14. Existing library switching and local manga reading behavior remain unchanged.
    def test_14_existing_library_switching_and_reading_behavior_unchanged(self):
        # 1. Switch to Library A and list chapters
        self._simulate_request("POST", "/api/library", {"path": str(self.lib_a_dir)})
        h_ch, b_ch = self._simulate_request("GET", "/api/chapters?series=Manga%20A1")
        self.assertIn("200 OK", h_ch)
        ch_data = json.loads(b_ch.decode("utf-8"))
        self.assertEqual(ch_data["chapter_count"], 1)

        # 2. List images in chapter
        h_img, b_img = self._simulate_request("GET", "/api/images?series=Manga%20A1&chapter=Chapter%201")
        self.assertIn("200 OK", h_img)
        img_data = json.loads(b_img.decode("utf-8"))
        self.assertEqual(img_data["image_count"], 1)

        # 3. Switch to Library B and list chapters
        self._simulate_request("POST", "/api/library", {"path": str(self.lib_b_dir)})
        h_ch_b, b_ch_b = self._simulate_request("GET", "/api/chapters?series=Manga%20B1")
        self.assertIn("200 OK", h_ch_b)
        ch_b_data = json.loads(b_ch_b.decode("utf-8"))
        self.assertEqual(ch_b_data["chapter_count"], 1)


if __name__ == "__main__":
    unittest.main()
