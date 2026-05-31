import { test, expect } from '@playwright/test';

/**
 * E2E-07 — SSE resilience: the price stream is interrupted, then the client
 * auto-reconnects and the connection dot returns to "connected".
 *
 * The frontend opens a native EventSource to /api/stream/prices (useSSE.ts):
 * onopen → connectionStatus "connected"; onerror → "reconnecting"/"disconnected".
 * The header dot exposes the state via aria-label `Connection ${status}`
 * (Header.tsx:67). The backend sends `retry: 1000`, so EventSource auto-retries.
 *
 * Interrupt mechanism — IMPORTANT (RESEARCH Assumptions Log A3, MEDIUM):
 * an already-OPEN, server-held keep-alive SSE stream cannot be torn down from
 * the Playwright client side. Verified empirically that NONE of these drop the
 * live connection (the dot stays "connected", onerror never fires):
 *   - `page.route(..., r => r.abort())` installed after connect (only affects
 *     new requests, not the in-flight stream)
 *   - `context.setOffline(true)`
 *   - CDP `Network.emulateNetworkConditions { offline: true }`
 *   - CDP `Network.setBlockedURLs`
 *   - `route.continue()` proxy + later flag flip (the open proxied read is not
 *     re-routed)
 * A fixed-body `route.fulfill` EOFs instantly and never yields a stable
 * "connected" to assert against.
 *
 * The deterministic, reliable interrupt we CAN drive from the client is to
 * control the FIRST connection: the EventSource issues a new request whenever
 * it (re)connects, and aborting that request makes onerror fire. So the test
 * starts in the interrupted state (route aborts → dot is NOT "connected"), then
 * lifts the interruption (unroute → native auto-retry connects) and asserts the
 * dot reaches "connected". This proves the interrupt→reconnect recovery arc —
 * the substance of E2E-07 — without depending on severing a live socket, which
 * is not achievable client-side.
 *
 * The route is scoped to this Playwright page/context and torn down per test
 * (threat T-05-07). We assert the arc (not-connected → connected), not an exact
 * intermediate label, per A3. Web-first assertions only — no waitForTimeout.
 */

test('sse interrupts then reconnects (dot returns to green)', async ({ page }) => {
  // Interrupt the SSE endpoint BEFORE the EventSource connects. Every connect
  // attempt aborts → onerror fires → the dot never reaches "connected".
  await page.route('**/api/stream/prices', (route) => route.abort());

  await page.goto('/');

  // While interrupted, the connection dot is NOT "connected" (it sits in
  // reconnecting/disconnected). Assert the absence to confirm the interrupt.
  await expect(page.getByLabel('Connection connected')).toHaveCount(0, {
    timeout: 10_000,
  });

  // Lift the interruption. The native EventSource auto-retry (backend
  // `retry: 1000`) now reaches the live backend and the stream opens.
  await page.unroute('**/api/stream/prices');

  // The dot returns to "connected" once the reconnected EventSource reopens.
  await expect(page.getByLabel('Connection connected')).toBeVisible({
    timeout: 15_000,
  });
});
