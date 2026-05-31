import { test, expect } from '@playwright/test';

/**
 * E2E-04 (buy) + E2E-05 (sell) — manual trade flow.
 *
 * Buys 1 AAPL, asserts the synchronous success toast, the new positions-table
 * row, and that cash is no longer the $10,000.00 seed; then sells it back and
 * asserts the SELL toast. A fresh DB per compose run guarantees the buy starts
 * from $10k and the sell finds the just-bought share.
 *
 * Selectors are the verified locators from 05-RESEARCH:
 *   - ticker input:   getByLabel('Ticker')                   (TradeBar.tsx)
 *   - quantity input: getByLabel('Quantity')                 (TradeBar.tsx)
 *   - BUY / SELL:     getByRole('button', { name: ... })     (TradeBar.tsx)
 *   - toast:          getByRole('status')  `BUY 1 AAPL @ $…`  (TradeBar.tsx)
 *   - positions row:  page.locator('td', { hasText: 'AAPL' }) (PositionsTable.tsx)
 *   - cash value:     the span immediately after the `Cash` label (Header.tsx)
 *   - connection dot: getByLabel('Connection connected')     (Header.tsx)
 *
 * The connection dot is awaited first so a live price exists for the instant
 * market-order fill (RESEARCH Pitfall 2). The toast is the synchronous success
 * signal; the positions row and cash change ride the background portfolio poll,
 * so they rely on the config's generous 10s expect timeout (RESEARCH Pitfall 4).
 * The positions <td> selector is MEDIUM-confidence (positional) — if it ever
 * flakes it is the single fallback candidate for a targeted data-testid; none is
 * added preemptively (frontend is locked).
 *
 * Web-first assertions only — no waitForTimeout (RESEARCH anti-patterns).
 */

test('buy then sell updates cash and positions', async ({ page }) => {
  await page.goto('/');

  // Wait for the SSE handshake so the cache holds a live AAPL price to fill at.
  await expect(page.getByLabel('Connection connected')).toBeVisible();

  // --- Buy 1 AAPL (E2E-04) ---
  await page.getByLabel('Ticker').fill('AAPL');
  await page.getByLabel('Quantity').fill('1');
  await page.getByRole('button', { name: 'BUY' }).click();

  // Toast confirms the fill synchronously (e.g. "BUY 1 AAPL @ $190.12").
  await expect(page.getByRole('status')).toContainText('BUY 1 AAPL');

  // The new position appears as an AAPL row in the positions table.
  await expect(page.locator('td', { hasText: 'AAPL' })).toBeVisible();

  // Cash dropped below the seed. Scope to the Cash value specifically: a market
  // buy is roughly value-neutral on the Portfolio *total* (cash converts to
  // position value at the same price), so the total stays ≈ $10,000.00 and only
  // Cash falls. The cash value is the <span> immediately following the `Cash`
  // header label, so assert that span no longer reads the $10,000.00 seed.
  const cashValue = page.getByText('Cash').locator('xpath=following-sibling::span[1]');
  await expect(cashValue).not.toHaveText('$10,000.00');

  // --- Sell it back (E2E-05) ---
  await page.getByLabel('Ticker').fill('AAPL');
  await page.getByLabel('Quantity').fill('1');
  await page.getByRole('button', { name: 'SELL' }).click();

  await expect(page.getByRole('status')).toContainText('SELL 1 AAPL');
});
