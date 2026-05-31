import { test, expect } from '@playwright/test';

/**
 * E2E-03 — Watchlist add / remove.
 *
 * Drives the real add-ticker form and the hover-gated remove control against a
 * freshly seeded DB. PYPL is deliberately NOT one of the 10 seed tickers
 * (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX), so the add is
 * always a genuine insert and the remove unambiguously drops the cell to zero.
 *
 * Selectors are the verified locators from 05-RESEARCH:
 *   - add input:   getByPlaceholder('Add ticker…')          (WatchlistPanel.tsx)
 *   - add submit:  getByRole('button', { name: '+' })        (WatchlistPanel.tsx)
 *   - row:         div.group with hasText 'PYPL'             (WatchlistRow.tsx)
 *   - remove ×:    getByLabel('Remove PYPL'), hover-gated    (WatchlistRow.tsx)
 *   - ticker cell: getByText('PYPL', { exact: true })        (WatchlistRow.tsx)
 *
 * Web-first assertions only — no waitForTimeout (RESEARCH anti-patterns).
 */

test('add and remove a ticker', async ({ page }) => {
  await page.goto('/');

  // Add PYPL via the watchlist form and confirm the new cell renders.
  await page.getByPlaceholder('Add ticker…').fill('PYPL');
  await page.getByRole('button', { name: '+' }).click();
  await expect(page.getByText('PYPL', { exact: true })).toBeVisible();

  // The × control is revealed on hover, so hover the row before clicking it.
  const row = page.locator('div.group', { hasText: 'PYPL' });
  await row.hover();
  await page.getByLabel('Remove PYPL').click();

  // After removal the PYPL cell is gone entirely (count drops to 0).
  await expect(page.getByText('PYPL', { exact: true })).toHaveCount(0);
});
