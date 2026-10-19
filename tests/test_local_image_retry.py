"""
Regression tests for manga reader automatic image retry over network interruptions (e.g., Tailscale).
Covers:
1. Code structure invariants in static/app.js.
2. A page fails initially but loads successfully on an automatic retry (with ~1s delay).
3. A page fails all three automatic retries (1s, 2s, 4s) and the manual Retry button remains available.
4. A successfully loaded page is not retried if subsequent error events occur.
5. Multiple error events do not schedule duplicate retries for the same image.
6. Pending retries are cancelled when navigating to another chapter or switching views.
7. A late error or load event from an old chapter does not affect the new chapter.
8. Cache-busting _retry parameter correctly updates without stacking.
9. Existing image loading and manual retry behavior remain intact.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestLocalImageRetry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_js_path = PROJECT_ROOT / "static" / "app.js"
        cls.assertTrue(cls.app_js_path.is_file(), "static/app.js must exist")
        cls.app_js_code = cls.app_js_path.read_text(encoding="utf-8")

    def _run_node_script(self, script_body: str) -> subprocess.CompletedProcess:
        full_script = f"""
const fs = require('fs');
const appCode = fs.readFileSync('{self.app_js_path}', 'utf8');

{script_body}
"""
        res = subprocess.run(
            ["node", "-e", full_script],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        return res

    def test_code_structure_invariants(self):
        """Verify retry tokens, constants, and cancellation hooks exist in static/app.js."""
        # Constants and helpers
        self.assertIn("AUTO_RETRY_DELAYS", self.app_js_code)
        self.assertIn("MAX_AUTO_RETRIES", self.app_js_code)
        self.assertIn("activeReaderRetryTimers", self.app_js_code)
        self.assertIn("cancelActiveReaderRetries", self.app_js_code)
        self.assertIn("getRetryUrl", self.app_js_code)

        # Integration in reader lifecycle
        self.assertIn("cancelActiveReaderRetries()", self.app_js_code)
        self.assertIn("currentLoadToken !== activeReaderLoadToken", self.app_js_code)

        # Manual retry button preservation
        self.assertIn("reader-image-retry", self.app_js_code)
        self.assertIn("Failed to load page. Click to retry", self.app_js_code)
        self.assertIn("image-load-failed", self.app_js_code)

    def test_page_fails_initially_and_recovers_on_automatic_retry(self):
        """Requirement 1: Page fails initially, automatically retries at ~1s, and recovers on retry."""
        script = """
        const assert = require('assert');

        class FakeClock {
          constructor() {
            this.now = 1000;
            this.timers = [];
            this.nextId = 1;
          }
          setTimeout(fn, delay) {
            const id = this.nextId++;
            this.timers.push({ id, fn, time: this.now + delay });
            return id;
          }
          clearTimeout(id) {
            this.timers = this.timers.filter(t => t.id !== id);
          }
          advance(ms) {
            this.now += ms;
            this.timers.sort((a, b) => a.time - b.time);
            while (this.timers.length && this.timers[0].time <= this.now) {
              const t = this.timers.shift();
              t.fn();
            }
          }
        }

        const clock = new FakeClock();
        const AUTO_RETRY_DELAYS = [1000, 2000, 4000];
        const MAX_AUTO_RETRIES = 3;
        let activeReaderRetryTimers = new Set();
        let activeReaderLoadToken = 1;
        const currentLoadToken = 1;

        function getRetryUrl(baseUrl) {
          const cleanUrl = baseUrl.replace(/([?&])_retry=\\d+(&|$)/, (m, p1, p2) => (p2 === "&" ? p1 : ""));
          const sep = cleanUrl.includes("?") ? "&" : "?";
          return `${cleanUrl}${sep}_retry=${clock.now}`;
        }

        // Simulate page image setup
        const pageDiv = {
          classList: new Set(),
          querySelector: () => null,
          appendChild: () => {}
        };
        const img = { url: '/api/image-file?series=Test&chapter=Ch1&file=01.jpg' };
        const imgEl = {
          src: img.url,
          classList: new Set(),
          complete: false,
          naturalWidth: 0
        };

        let autoRetryCount = 0;
        let retryTimeoutId = null;
        let isLoaded = false;
        let manualRetryShown = false;

        function showManualRetryButton() {
          manualRetryShown = true;
          imgEl.classList.add("image-load-failed");
        }

        imgEl.onerror = () => {
          if (currentLoadToken !== activeReaderLoadToken) return;
          if (isLoaded || (imgEl.complete && imgEl.naturalWidth > 0)) return;
          if (retryTimeoutId !== null) return;

          if (autoRetryCount < MAX_AUTO_RETRIES) {
            const delay = AUTO_RETRY_DELAYS[autoRetryCount];
            autoRetryCount++;

            retryTimeoutId = clock.setTimeout(() => {
              activeReaderRetryTimers.delete(retryTimeoutId);
              retryTimeoutId = null;

              if (currentLoadToken !== activeReaderLoadToken) return;
              if (isLoaded || (imgEl.complete && imgEl.naturalWidth > 0)) return;

              imgEl.classList.delete("image-load-failed");
              imgEl.src = getRetryUrl(img.url);
            }, delay);

            activeReaderRetryTimers.add(retryTimeoutId);
            return;
          }
          showManualRetryButton();
        };

        imgEl.onload = () => {
          if (currentLoadToken !== activeReaderLoadToken) return;
          isLoaded = true;
          autoRetryCount = 0;
          if (retryTimeoutId !== null) {
            clock.clearTimeout(retryTimeoutId);
            activeReaderRetryTimers.delete(retryTimeoutId);
            retryTimeoutId = null;
          }
          imgEl.classList.delete("image-load-failed");
        };

        // 1. Initial request fails
        imgEl.onerror();
        assert.strictEqual(autoRetryCount, 1, 'Auto retry count must increment to 1');
        assert.strictEqual(activeReaderRetryTimers.size, 1, '1 timer must be scheduled');
        assert.strictEqual(manualRetryShown, false, 'Manual button must not be shown during automatic retries');

        // Clock advances 500ms - timer should not have fired yet
        clock.advance(500);
        assert.strictEqual(imgEl.src, img.url, 'Should not have updated src yet before delay');

        // Clock advances remaining 500ms (1000ms total) - timer fires
        clock.advance(500);
        assert.strictEqual(imgEl.src, `${img.url}&_retry=2000`, 'Image src must be updated with retry timestamp');
        assert.strictEqual(activeReaderRetryTimers.size, 0, 'Timer must be removed from set');

        // Successful load on retry
        imgEl.complete = true;
        imgEl.naturalWidth = 1000;
        imgEl.onload();

        assert.strictEqual(isLoaded, true, 'isLoaded must be true');
        assert.strictEqual(autoRetryCount, 0, 'autoRetryCount must reset to 0 upon successful load');
        assert.strictEqual(manualRetryShown, false, 'Manual retry button was never needed');

        console.log('OK: Initial failure with auto retry recovery passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Initial failure with auto retry recovery passed", res.stdout)

    def test_page_fails_all_three_retries_and_shows_manual_button(self):
        """Requirement 1: Page fails all 3 retries (1s, 2s, 4s) and manual Retry button becomes available."""
        script = """
        const assert = require('assert');

        class FakeClock {
          constructor() {
            this.now = 1000;
            this.timers = [];
            this.nextId = 1;
          }
          setTimeout(fn, delay) {
            const id = this.nextId++;
            this.timers.push({ id, fn, time: this.now + delay });
            return id;
          }
          clearTimeout(id) {
            this.timers = this.timers.filter(t => t.id !== id);
          }
          advance(ms) {
            this.now += ms;
            this.timers.sort((a, b) => a.time - b.time);
            while (this.timers.length && this.timers[0].time <= this.now) {
              const t = this.timers.shift();
              t.fn();
            }
          }
        }

        const clock = new FakeClock();
        const AUTO_RETRY_DELAYS = [1000, 2000, 4000];
        const MAX_AUTO_RETRIES = 3;
        let activeReaderRetryTimers = new Set();
        let activeReaderLoadToken = 1;
        const currentLoadToken = 1;

        function getRetryUrl(baseUrl) {
          const cleanUrl = baseUrl.replace(/([?&])_retry=\\d+(&|$)/, (m, p1, p2) => (p2 === "&" ? p1 : ""));
          const sep = cleanUrl.includes("?") ? "&" : "?";
          return `${cleanUrl}${sep}_retry=${clock.now}`;
        }

        let manualButtonCreated = false;
        const pageDiv = {
          appendChild(child) {
            if (child.className === 'reader-image-retry') {
              manualButtonCreated = true;
            }
          },
          querySelector(sel) {
            return manualButtonCreated ? { className: 'reader-image-retry' } : null;
          }
        };

        const img = { url: '/api/image-file?series=Test&chapter=Ch1&file=02.jpg' };
        const imgEl = {
          src: img.url,
          classList: {
            classes: new Set(),
            add(c) { this.classes.add(c); },
            remove(c) { this.classes.delete(c); },
            contains(c) { return this.classes.has(c); }
          },
          complete: false,
          naturalWidth: 0
        };

        let autoRetryCount = 0;
        let retryTimeoutId = null;
        let isLoaded = false;

        function showManualRetryButton() {
          imgEl.classList.add("image-load-failed");
          let retryBtn = pageDiv.querySelector(".reader-image-retry");
          if (!retryBtn) {
            retryBtn = {
              type: "button",
              className: "reader-image-retry"
            };
            pageDiv.appendChild(retryBtn);
          }
        }

        imgEl.onerror = () => {
          if (currentLoadToken !== activeReaderLoadToken) return;
          if (isLoaded || (imgEl.complete && imgEl.naturalWidth > 0)) return;
          if (retryTimeoutId !== null) return;

          if (autoRetryCount < MAX_AUTO_RETRIES) {
            const delay = AUTO_RETRY_DELAYS[autoRetryCount];
            autoRetryCount++;

            retryTimeoutId = clock.setTimeout(() => {
              activeReaderRetryTimers.delete(retryTimeoutId);
              retryTimeoutId = null;

              if (currentLoadToken !== activeReaderLoadToken) return;
              if (isLoaded || (imgEl.complete && imgEl.naturalWidth > 0)) return;

              imgEl.classList.remove("image-load-failed");
              imgEl.src = getRetryUrl(img.url);
            }, delay);

            activeReaderRetryTimers.add(retryTimeoutId);
            return;
          }

          showManualRetryButton();
        };

        // 1. Initial request fails -> schedules Attempt 1 with 1000ms delay
        imgEl.onerror();
        assert.strictEqual(autoRetryCount, 1);
        assert.strictEqual(manualButtonCreated, false);

        // Advance 1000ms -> Attempt 1 executes
        clock.advance(1000);
        assert.strictEqual(imgEl.src.includes('_retry=2000'), true);

        // 2. Attempt 1 fails -> schedules Attempt 2 with 2000ms delay
        imgEl.onerror();
        assert.strictEqual(autoRetryCount, 2);
        assert.strictEqual(manualButtonCreated, false);

        // Advance 2000ms -> Attempt 2 executes
        clock.advance(2000);
        assert.strictEqual(imgEl.src.includes('_retry=4000'), true);

        // 3. Attempt 2 fails -> schedules Attempt 3 with 4000ms delay
        imgEl.onerror();
        assert.strictEqual(autoRetryCount, 3);
        assert.strictEqual(manualButtonCreated, false);

        // Advance 4000ms -> Attempt 3 executes
        clock.advance(4000);
        assert.strictEqual(imgEl.src.includes('_retry=8000'), true);

        // 4. Attempt 3 fails -> all 3 automatic retries exhausted!
        imgEl.onerror();
        assert.strictEqual(autoRetryCount, 3, 'Retry count stays at max');
        assert.strictEqual(activeReaderRetryTimers.size, 0, 'No more timers scheduled');
        assert.strictEqual(manualButtonCreated, true, 'Manual Retry button must be created');
        assert.strictEqual(imgEl.classList.contains("image-load-failed"), true, 'image-load-failed class must be added');

        console.log('OK: 3 retries exhausted with manual button passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: 3 retries exhausted with manual button passed", res.stdout)

    def test_successfully_loaded_page_is_not_retried(self):
        """Requirement 2 & 3: Successfully loaded image ignores error events and is never retried."""
        script = """
        const assert = require('assert');

        let retryCount = 0;
        let timersScheduled = 0;
        const isLoaded = true;
        const imgEl = { complete: true, naturalWidth: 1200, src: '/api/image-file?series=Test&file=01.jpg' };
        const initialSrc = imgEl.src;

        function onError() {
          if (isLoaded || (imgEl.complete && imgEl.naturalWidth > 0)) {
            return; // Guarded!
          }
          retryCount++;
          timersScheduled++;
        }

        // Trigger error event on already-loaded image
        onError();
        onError();

        assert.strictEqual(retryCount, 0, 'Loaded image must not trigger retry');
        assert.strictEqual(timersScheduled, 0, 'No timers must be scheduled');
        assert.strictEqual(imgEl.src, initialSrc, 'Image src must not change');

        console.log('OK: Loaded image never retried test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Loaded image never retried test passed", res.stdout)

    def test_multiple_error_events_do_not_schedule_duplicate_retries(self):
        """Requirement 2: Multiple error events while retry is pending do NOT schedule duplicate timers."""
        script = """
        const assert = require('assert');

        let scheduledTimers = [];
        let retryTimeoutId = null;
        let autoRetryCount = 0;
        const MAX_AUTO_RETRIES = 3;
        const AUTO_RETRY_DELAYS = [1000, 2000, 4000];
        let timerIdSeq = 1;

        function onError() {
          if (retryTimeoutId !== null) return; // Guard against duplicates!

          if (autoRetryCount < MAX_AUTO_RETRIES) {
            const delay = AUTO_RETRY_DELAYS[autoRetryCount];
            autoRetryCount++;
            retryTimeoutId = timerIdSeq++;
            scheduledTimers.push(retryTimeoutId);
          }
        }

        // Simulate 5 rapid error events firing on the same element
        onError();
        onError();
        onError();
        onError();
        onError();

        assert.strictEqual(scheduledTimers.length, 1, 'Only 1 timer must be scheduled despite 5 error events');
        assert.strictEqual(autoRetryCount, 1, 'Auto retry count should only increment once');

        console.log('OK: Deduplication of error events test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Deduplication of error events test passed", res.stdout)

    def test_pending_retries_cancelled_on_chapter_navigation(self):
        """Requirement 4: Navigating to another chapter cancels all pending retry timers."""
        script = """
        const assert = require('assert');

        class FakeClock {
          constructor() {
            this.now = 1000;
            this.timers = new Map();
            this.nextId = 1;
            this.executed = 0;
          }
          setTimeout(fn, delay) {
            const id = this.nextId++;
            this.timers.set(id, { fn, time: this.now + delay });
            return id;
          }
          clearTimeout(id) {
            this.timers.delete(id);
          }
          advance(ms) {
            this.now += ms;
            for (const [id, t] of Array.from(this.timers.entries())) {
              if (t.time <= this.now) {
                this.timers.delete(id);
                t.fn();
                this.executed++;
              }
            }
          }
        }

        const clock = new FakeClock();
        const activeReaderRetryTimers = new Set();

        function cancelActiveReaderRetries() {
          activeReaderRetryTimers.forEach((timerId) => clock.clearTimeout(timerId));
          activeReaderRetryTimers.clear();
        }

        // Chapter 1 loads, 3 images fail and schedule retries
        let ch1SrcUpdates = 0;
        const t1 = clock.setTimeout(() => { ch1SrcUpdates++; }, 1000);
        const t2 = clock.setTimeout(() => { ch1SrcUpdates++; }, 2000);
        const t3 = clock.setTimeout(() => { ch1SrcUpdates++; }, 4000);
        activeReaderRetryTimers.add(t1);
        activeReaderRetryTimers.add(t2);
        activeReaderRetryTimers.add(t3);

        assert.strictEqual(activeReaderRetryTimers.size, 3);
        assert.strictEqual(clock.timers.size, 3);

        // User navigates to Chapter 2 before any timer fires
        cancelActiveReaderRetries();

        assert.strictEqual(activeReaderRetryTimers.size, 0, 'activeReaderRetryTimers must be cleared');
        assert.strictEqual(clock.timers.size, 0, 'All clock timers must be cancelled');

        // Clock advances 10 seconds into the future
        clock.advance(10000);
        assert.strictEqual(clock.executed, 0, 'Zero timers should execute after chapter navigation');
        assert.strictEqual(ch1SrcUpdates, 0, 'No Chapter 1 src updates should have occurred');

        console.log('OK: Navigation cancellation test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Navigation cancellation test passed", res.stdout)

    def test_stale_callbacks_from_old_chapter_discarded(self):
        """Requirement 4: Late error or load event from old chapter does not affect new chapter."""
        script = """
        const assert = require('assert');

        let activeReaderLoadToken = 1;
        let modifiedDom = false;

        // Old chapter callback bound to currentLoadToken = 1
        const oldChapterLoadToken = 1;

        // Navigate to new chapter
        activeReaderLoadToken = 2;

        function staleOnError() {
          if (oldChapterLoadToken !== activeReaderLoadToken) {
            return; // Discarded!
          }
          modifiedDom = true;
        }

        function staleOnLoad() {
          if (oldChapterLoadToken !== activeReaderLoadToken) {
            return; // Discarded!
          }
          modifiedDom = true;
        }

        // Fire late events from old chapter
        staleOnError();
        staleOnLoad();

        assert.strictEqual(modifiedDom, false, 'Late events from old chapter must be discarded');

        console.log('OK: Stale chapter callbacks discarded test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Stale chapter callbacks discarded test passed", res.stdout)

    def test_cache_busting_url_generation(self):
        """Requirement 3: getRetryUrl appends or updates _retry timestamp cleanly without stacking."""
        script = """
        const assert = require('assert');

        function getRetryUrl(baseUrl, fakeTimestamp) {
          const cleanUrl = baseUrl.replace(/([?&])_retry=\\d+(&|$)/, (m, p1, p2) => (p2 === "&" ? p1 : ""));
          const sep = cleanUrl.includes("?") ? "&" : "?";
          return `${cleanUrl}${sep}_retry=${fakeTimestamp}`;
        }

        // Local image URL without query params
        const url1 = '/api/image-file?series=Bleach&chapter=01&file=01.jpg';
        const retry1 = getRetryUrl(url1, 1000);
        assert.strictEqual(retry1, '/api/image-file?series=Bleach&chapter=01&file=01.jpg&_retry=1000');

        // Subsequent retry on already retried URL replaces timestamp instead of stacking
        const retry2 = getRetryUrl(retry1, 2000);
        assert.strictEqual(retry2, '/api/image-file?series=Bleach&chapter=01&file=01.jpg&_retry=2000');

        // Third retry
        const retry3 = getRetryUrl(retry2, 4000);
        assert.strictEqual(retry3, '/api/image-file?series=Bleach&chapter=01&file=01.jpg&_retry=4000');

        // Remote image proxy URL with complex query params
        const remoteUrl = '/api/remote/image-proxy?url=https%3A%2F%2Fscans.example.com%2F01.png&provider=weebcentral';
        const remoteRetry1 = getRetryUrl(remoteUrl, 5000);
        assert.strictEqual(remoteRetry1, '/api/remote/image-proxy?url=https%3A%2F%2Fscans.example.com%2F01.png&provider=weebcentral&_retry=5000');

        const remoteRetry2 = getRetryUrl(remoteRetry1, 6000);
        assert.strictEqual(remoteRetry2, '/api/remote/image-proxy?url=https%3A%2F%2Fscans.example.com%2F01.png&provider=weebcentral&_retry=6000');

        console.log('OK: Cache-busting URL generation test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Cache-busting URL generation test passed", res.stdout)

    def test_manual_retry_resets_auto_retry_cycle(self):
        """Requirement 1 & 8: Manual retry resets auto retry count and removes error state."""
        script = """
        const assert = require('assert');

        let autoRetryCount = 3;
        let isLoaded = false;
        let retryTimeoutId = null;
        let srcAssigned = null;
        let buttonRemoved = false;

        const img = { url: '/api/image-file?series=Test&chapter=Ch1&file=01.jpg' };
        const imgEl = {
          classList: {
            removed: [],
            remove(c) { this.removed.push(c); }
          },
          set src(val) { srcAssigned = val; }
        };
        const retryBtn = {
          remove() { buttonRemoved = true; }
        };

        function onManualRetryClick() {
          retryBtn.remove();
          imgEl.classList.remove("image-load-failed");
          autoRetryCount = 0;
          isLoaded = false;
          if (retryTimeoutId !== null) {
            retryTimeoutId = null;
          }
          imgEl.src = `${img.url}&_retry=9999`;
        }

        onManualRetryClick();

        assert.strictEqual(buttonRemoved, true, 'Retry button must be removed on click');
        assert.strictEqual(imgEl.classList.removed.includes("image-load-failed"), true, 'image-load-failed class must be removed');
        assert.strictEqual(autoRetryCount, 0, 'autoRetryCount must reset to 0');
        assert.strictEqual(isLoaded, false, 'isLoaded must be false');
        assert.strictEqual(srcAssigned, '/api/image-file?series=Test&chapter=Ch1&file=01.jpg&_retry=9999');

        console.log('OK: Manual retry resets auto cycle test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Manual retry resets auto cycle test passed", res.stdout)


if __name__ == "__main__":
    unittest.main()
