import { Page, Locator, expect } from '@playwright/test';

/**
 * Shared helpers for the FinAlly E2E suite.
 *
 * The frontend exposes a data-testid contract (see test/README.md). Helpers
 * prefer those testids but fall back to text/role selectors so the suite stays
 * resilient if a testid is missing.
 *
 * NOTE: All button clicks use { force: true } because the SSE price stream
 * causes constant React re-renders of the TradeBar and WatchlistAdd components,
 * which makes their buttons flicker in/out of the DOM. force: true bypasses
 * Playwright's stability check while still delivering a real native click.
 */

/** Parse a currency-formatted string like "$10,000.00" or "-$1,234.5" into a number. */
export function parseMoney(text: string | null): number {
  if (!text) return NaN;
  const cleaned = text.replace(/[^0-9.\-]/g, '');
  return parseFloat(cleaned);
}

/** First locator from a list of candidates that resolves to a visible element. */
async function firstVisible(page: Page, selectors: string[]): Promise<Locator | null> {
  for (const sel of selectors) {
    const loc = page.locator(sel).first();
    if (await loc.count()) {
      try {
        if (await loc.isVisible()) return loc;
      } catch {
        // element detached between count and isVisible — skip
      }
    }
  }
  return null;
}

/** Wait for the app shell to be interactive (watchlist populated). */
export async function waitForAppReady(page: Page): Promise<void> {
  const watchlist = page.locator('[data-testid="watchlist"]');
  if (await watchlist.count()) {
    await watchlist.first().waitFor({ state: 'visible', timeout: 20000 });
  }
  // Wait for at least one ticker row to render.
  await expect
    .poll(async () => await watchlistRows(page).count(), { timeout: 20000 })
    .toBeGreaterThan(0);
}

/** All watchlist ticker rows. */
export function watchlistRows(page: Page): Locator {
  return page.locator('[data-testid="watchlist-row"]');
}

/** A single watchlist row by ticker symbol. */
export function watchlistRow(page: Page, ticker: string): Locator {
  return page
    .locator(`[data-testid="watchlist-row"][data-ticker="${ticker}"]`)
    .or(page.locator('[data-testid="watchlist-row"]', { hasText: ticker }));
}

/** All position rows in the positions table. */
export function positionRows(page: Page): Locator {
  return page.locator('[data-testid="position-row"]');
}

/** A single position row by ticker symbol. */
export function positionRow(page: Page, ticker: string): Locator {
  return page
    .locator(`[data-testid="position-row"][data-ticker="${ticker}"]`)
    .or(page.locator('[data-testid="position-row"]', { hasText: ticker }));
}

/** Read the cash balance from the header. */
export async function getCashBalance(page: Page): Promise<number> {
  const el = await firstVisible(page, [
    '[data-testid="cash-balance"]',
  ]);
  if (!el) throw new Error('cash-balance element not found');
  return parseMoney(await el.textContent());
}

/** Read the total portfolio value from the header. */
export async function getTotalValue(page: Page): Promise<number> {
  const el = await firstVisible(page, [
    '[data-testid="total-value"]',
  ]);
  if (!el) throw new Error('total-value element not found');
  return parseMoney(await el.textContent());
}

/** Execute a trade through the trade bar. side = 'buy' | 'sell'. */
export async function executeTrade(
  page: Page,
  ticker: string,
  quantity: number | string,
  side: 'buy' | 'sell'
): Promise<void> {
  const tickerInput = page.locator('[data-testid="trade-ticker-input"]');
  const qtyInput = page.locator('[data-testid="trade-quantity-input"]');
  const button = page.locator(
    side === 'buy'
      ? '[data-testid="trade-buy-button"]'
      : '[data-testid="trade-sell-button"]'
  );

  await tickerInput.fill('');
  await tickerInput.fill(ticker);
  await qtyInput.fill('');
  await qtyInput.fill(String(quantity));
  // force: true bypasses stability check — buttons re-render on every SSE tick
  await button.click({ force: true });
}

/** Add a ticker to the watchlist via the add-ticker input. */
export async function addToWatchlist(page: Page, ticker: string): Promise<void> {
  const input = page.locator('[data-testid="watchlist-add-input"]');
  await input.fill('');
  await input.fill(ticker);
  const button = page.locator('[data-testid="watchlist-add-button"]');
  if (await button.count()) {
    // force: true bypasses stability check — button re-renders on every SSE tick
    await button.click({ force: true });
  } else {
    await input.press('Enter');
  }
}

/** Remove a ticker from the watchlist via that row's remove button. */
export async function removeFromWatchlist(page: Page, ticker: string): Promise<void> {
  const row = watchlistRow(page, ticker);
  await row.first().waitFor({ state: 'visible', timeout: 10000 });
  const removeBtn = row.locator('[data-testid="watchlist-remove-button"]');
  if (await removeBtn.count()) {
    await removeBtn.first().click({ force: true });
  } else {
    // Fallback: hover then click any button in the row.
    await row.first().hover();
    await row.locator('button').first().click({ force: true });
  }
}

/** Open the AI chat panel if it is collapsible and currently closed. */
export async function openChatPanel(page: Page): Promise<Locator> {
  const panel = page.locator('[data-testid="chat-panel"]');
  const toggle = page.locator('[data-testid="chat-toggle"]');

  if ((await panel.count()) && (await panel.first().isVisible())) {
    return panel.first();
  }
  if (await toggle.count()) {
    // force: true — toggle button also re-renders on SSE ticks
    await toggle.first().click({ force: true });
    await panel.first().waitFor({ state: 'visible', timeout: 10000 });
    return panel.first();
  }
  // No explicit toggle — assume the panel is always present.
  await panel.first().waitFor({ state: 'visible', timeout: 10000 });
  return panel.first();
}
