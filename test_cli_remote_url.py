"""
test_cli_remote_url.py - Automated tests for CLI remote manga URL support.

Verifies:
1. Normal startup without arguments preserves existing behavior.
2. Passing supported remote URLs (nhentai, WeebCentral, mock) resolves and constructs correct reader URL.
3. Passing canonical remote identifiers (remote:<provider>:<id>) works seamlessly.
4. Passing invalid or unsupported URLs exits cleanly with non-zero status and clear, sanitized error.
5. SSRF and security policy violations are rejected before server startup.
6. Sensitive query parameters are not leaked in CLI error output.
7. /api/status endpoint exposes startup_url when configured.
8. main.py delegates to server.py correctly.
9. Browser opening is triggered when run directly and suppressed when under a launcher.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import server
from providers import default_registry
from providers.mock import MockProvider


class TestCLIRemoteURLSupport(unittest.TestCase):
    """Test suite for CLI remote URL argument handling and startup routing."""

    def setUp(self) -> None:
        if "mock" not in default_registry:
            default_registry.register(MockProvider())

    def test_main_no_arguments_preserves_normal_startup(self) -> None:
        """With no URL argument, target_open_url should be None and run_server called normally."""
        with patch.object(sys, "argv", ["server.py"]), \
             patch("server.run_server") as mock_run_server:
            server.main()
            mock_run_server.assert_called_once()
            _, kwargs = mock_run_server.call_args
            self.assertIsNone(kwargs.get("target_open_url"))

    def test_main_with_valid_nhentai_url(self) -> None:
        """A valid nhentai gallery URL should resolve to the canonical nhentai reader route."""
        test_url = "https://nhentai.net/g/686216/"
        with patch.object(sys, "argv", ["server.py", test_url]), \
             patch("server.run_server") as mock_run_server:
            server.main()
            mock_run_server.assert_called_once()
            _, kwargs = mock_run_server.call_args
            target = kwargs.get("target_open_url")
            self.assertIsNotNone(target)
            self.assertIn("8000/#/series/remote%3Anhentai%3A686216", target)

    def test_main_with_custom_port_and_url(self) -> None:
        """Custom port and remote URL should be reflected in the reader startup URL."""
        test_url = "https://nhentai.net/g/686216/"
        with patch.object(sys, "argv", ["server.py", "--port", "9090", test_url]), \
             patch("server.run_server") as mock_run_server:
            server.main()
            mock_run_server.assert_called_once()
            _, kwargs = mock_run_server.call_args
            self.assertEqual(kwargs.get("port"), 9090)
            target = kwargs.get("target_open_url")
            self.assertIn("http://localhost:9090/#/series/remote%3Anhentai%3A686216", target)

    def test_main_with_weebcentral_url(self) -> None:
        """A valid WeebCentral series URL should resolve to the canonical weebcentral reader route."""
        test_url = "https://weebcentral.com/series/01J76XY8CM99/chainsaw-man"
        with patch.object(sys, "argv", ["server.py", test_url]), \
             patch("server.run_server") as mock_run_server:
            server.main()
            mock_run_server.assert_called_once()
            _, kwargs = mock_run_server.call_args
            target = kwargs.get("target_open_url")
            self.assertIsNotNone(target)
            self.assertIn("8000/#/series/remote%3Aweebcentral%3A01J76XY8CM99", target)

    def test_main_with_canonical_remote_identifier(self) -> None:
        """Directly passing remote:<provider>:<id> on the CLI should be supported."""
        canonical = "remote:nhentai:177013"
        with patch.object(sys, "argv", ["server.py", canonical]), \
             patch("server.run_server") as mock_run_server:
            server.main()
            mock_run_server.assert_called_once()
            _, kwargs = mock_run_server.call_args
            target = kwargs.get("target_open_url")
            self.assertIn("remote%3Anhentai%3A177013", target)

    def test_main_with_unsupported_provider_exits_with_error(self) -> None:
        """Passing a URL for an unsupported domain should exit non-zero and print a clean error."""
        unsupported = "https://example.com/manga/test"
        stderr_capture = io.StringIO()
        with patch.object(sys, "argv", ["server.py", unsupported]), \
             patch("sys.stderr", stderr_capture), \
             self.assertRaises(SystemExit) as cm:
            server.main()
        self.assertEqual(cm.exception.code, 1)
        err = stderr_capture.getvalue()
        self.assertIn("Error: Invalid or unsupported remote manga URL", err)
        self.assertIn("example.com", err)

    def test_main_with_disallowed_scheme_exits_with_error(self) -> None:
        """Insecure HTTP URLs should be rejected by the security policy and exit non-zero."""
        insecure = "http://weebcentral.com/series/01J76XY8CM99"
        stderr_capture = io.StringIO()
        with patch.object(sys, "argv", ["server.py", insecure]), \
             patch("sys.stderr", stderr_capture), \
             self.assertRaises(SystemExit) as cm:
            server.main()
        self.assertEqual(cm.exception.code, 1)
        err = stderr_capture.getvalue()
        self.assertIn("Error: Invalid or unsupported remote manga URL", err)

    def test_main_with_ssrf_attempt_exits_with_error(self) -> None:
        """Internal IP addresses should be rejected without starting the server."""
        ssrf_url = "https://127.0.0.1/admin"
        stderr_capture = io.StringIO()
        with patch.object(sys, "argv", ["server.py", ssrf_url]), \
             patch("sys.stderr", stderr_capture), \
             self.assertRaises(SystemExit) as cm:
            server.main()
        self.assertEqual(cm.exception.code, 1)

    def test_sensitive_query_parameters_are_not_logged_in_host_error(self) -> None:
        """Query parameters containing sensitive tokens should not be reflected in host info."""
        sensitive_url = "https://evil.com/leak?auth_token=super_secret_key_12345"
        stderr_capture = io.StringIO()
        with patch.object(sys, "argv", ["server.py", sensitive_url]), \
             patch("sys.stderr", stderr_capture), \
             self.assertRaises(SystemExit):
            server.main()
        err = stderr_capture.getvalue()
        self.assertNotIn("super_secret_key_12345", err)
        self.assertIn("evil.com", err)

    def test_main_py_delegation(self) -> None:
        """main.py should invoke server.main()."""
        import main as main_entry
        with patch.object(sys, "argv", ["main.py"]), \
             patch("server.run_server") as mock_run_server:
            main_entry.main()
            mock_run_server.assert_called_once()

    def test_run_server_opens_browser_when_not_in_launcher(self) -> None:
        """When target_open_url is supplied and not running from launcher, webbrowser.open is spawned."""
        fake_url = "http://localhost:8000/#/series/remote%3Anhentai%3A123"
        with patch.dict(os.environ, {}, clear=True), \
             patch("webbrowser.open") as mock_wb_open, \
             patch("server.ThreadingHTTPServer") as mock_http_server:
            # Make serve_forever raise KeyboardInterrupt to exit immediately
            instance = mock_http_server.return_value
            instance.serve_forever.side_effect = KeyboardInterrupt
            server.run_server(target_open_url=fake_url)
            # Give daemon thread a brief moment to run
            import time
            time.sleep(0.05)
            mock_wb_open.assert_called_with(fake_url)

    def test_run_server_suppresses_browser_when_in_launcher(self) -> None:
        """When LOCAL_MANGA_LAUNCHER is set, server.py should not call webbrowser.open."""
        fake_url = "http://localhost:8000/#/series/remote%3Anhentai%3A123"
        with patch.dict(os.environ, {"LOCAL_MANGA_LAUNCHER": "1"}), \
             patch("webbrowser.open") as mock_wb_open, \
             patch("server.ThreadingHTTPServer") as mock_http_server:
            instance = mock_http_server.return_value
            instance.serve_forever.side_effect = KeyboardInterrupt
            server.run_server(target_open_url=fake_url)
            import time
            time.sleep(0.05)
            mock_wb_open.assert_not_called()

    def test_api_status_includes_startup_url(self) -> None:
        """The /api/status endpoint should include the startup_url property."""
        from test_remote_ui_integration import MockSocket
        server.MangaRequestHandler.startup_url = "http://localhost:8000/#/series/remote%3Anhentai%3A686216"
        server.MangaRequestHandler.library = server.MangaLibrary(None)
        server.MangaRequestHandler.static_dir = server.Path(__file__).parent / "static"

        req = b"GET /api/status HTTP/1.1\r\nHost: localhost\r\n\r\n"
        sock = MockSocket(req)
        handler = server.MangaRequestHandler(sock, ("127.0.0.1", 12345), None)

        sock.wfile.seek(0)
        raw_res = sock.wfile.read().decode("utf-8")
        headers_part, body_part = raw_res.split("\r\n\r\n", 1)
        self.assertIn("200 OK", headers_part)
        data = server.json.loads(body_part)
        self.assertEqual(data.get("startup_url"), "http://localhost:8000/#/series/remote%3Anhentai%3A686216")

        # Cleanup
        server.MangaRequestHandler.startup_url = None


if __name__ == "__main__":
    unittest.main()
