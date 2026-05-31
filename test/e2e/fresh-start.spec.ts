import { test, expect } from '@playwright/test';

/**
 * E2E-02 — Fresh start smoke test.
 *
 * Proves the full stack comes up against a freshly seeded DB ($10k / 10 tickers)
 * and renders live data. Selectors are the verified accessibility/text locators
 * from 05-RESEARCH (Header.tsx aria-label / WatchlistRow.tsx). The connection dot
 * is asserted with a web-first assertion (never instantly) because the SSE
 * handshake completes asynchronously after onopen (RESEARCH Pitfall 2).
 */

test('fresh start: watchlist, $10k, streaming', async ({ page }) => {
  await page.goto('/');

  // A seeded ticker renders as a bold ticker cell in the watchlist.
  await expect(page.getByText('AAPL', { exact: true })).toBeVisible();

  // The $10,000.00 cash seed is shown in the header (toLocaleString format).
  // On a fresh DB both Portfolio total and Cash read $10,000.00, so the text
  // resolves to two header spans — assert at least one is present rather than
  // tripping strict mode on a single-element locator.
  await expect(page.getByText('$10,000.00').first()).toBeVisible();

  // The connection dot reaches "connected" once EventSource.onopen fires
  // (aria-label `Connection connected`). Auto-retried, not asserted instantly.
  await expect(page.getByLabel('Connection connected')).toBeVisible();
});

test('prices stream', async ({ page }) => {
  await page.goto('/');

  // Wait for the SSE handshake before sampling a price.
  await expect(page.getByLabel('Connection connected')).toBeVisible();

  // The AAPL row's price is the 2nd span (span0 = ticker, span1 = price).
  const aaplRow = page.locator('div.group', { hasText: 'AAPL' });
  const priceCell = aaplRow.locator('span').nth(1);

  // Sample the rendered price, then poll until it differs. Never assert an exact
  // value — the GBM simulator is random. SSE pushes every ~500ms; 10s is ample.
  const first = await priceCell.innerText();
  await expect
    .poll(async () => priceCell.innerText(), { timeout: 10_000 })
    .not.toBe(first);
});
