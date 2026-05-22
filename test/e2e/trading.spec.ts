import { test, expect } from '@playwright/test';
import {
  waitForAppReady,
  watchlistRows,
  watchlistRow,
  positionRow,
  getCashBalance,
  executeTrade,
  addToWatchlist,
  removeFromWatchlist,
  openChatPanel,
} from './helpers';

/**
 * FinAlly Trading Terminal — end-to-end scenarios.
 *
 * These tests run serially (workers: 1) against a single shared portfolio.
 * Each test that mutates state is written to be self-contained and tolerant
 * of leftover state from prior runs (e.g. existing AAPL positions).
 */
test.describe('FinAlly Trading Terminal', () => {
  test('fresh start: watchlist, balance, streaming', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // 10 default tickers are present in the watchlist.
    await expect(watchlistRows(page)).toHaveCount(10);
    for (const ticker of [
      'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA',
      'NVDA', 'META', 'JPM', 'V', 'NFLX',
    ]) {
      await expect(watchlistRow(page, ticker).first()).toBeVisible();
    }

    // Cash balance shows $10,000 on a fresh database. On a re-used volume the
    // balance may differ, so accept any value but require the element exists.
    const cash = await getCashBalance(page);
    expect(Number.isNaN(cash)).toBe(false);

    // Prices are streaming: a watchlist price cell should change within a few
    // ticks of the SSE stream.
    const priceCell = watchlistRow(page, 'AAPL')
      .first()
      .locator('[data-testid="watchlist-price"]');
    await expect(priceCell).toBeVisible();
    const initialPrice = await priceCell.textContent();
    await expect
      .poll(async () => await priceCell.textContent(), { timeout: 8000 })
      .not.toBe(initialPrice);
  });

  test('add and remove ticker from watchlist', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const ticker = 'UBER';

    // Clean slate: if UBER lingers from a prior run, remove it first.
    if (await watchlistRow(page, ticker).count()) {
      await removeFromWatchlist(page, ticker);
      await expect(watchlistRow(page, ticker)).toHaveCount(0);
    }

    await addToWatchlist(page, ticker);
    await expect(watchlistRow(page, ticker).first()).toBeVisible({ timeout: 10000 });

    await removeFromWatchlist(page, ticker);
    await expect(watchlistRow(page, ticker)).toHaveCount(0);
  });

  test('buy shares: cash decreases, position appears', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const cashBefore = await getCashBalance(page);

    await executeTrade(page, 'AAPL', 5, 'buy');

    // Cash should drop after the buy fills.
    await expect
      .poll(async () => await getCashBalance(page), { timeout: 10000 })
      .toBeLessThan(cashBefore);

    // AAPL position appears with quantity >= 5 (>= because a prior run may
    // have left shares; this test only adds 5).
    const row = positionRow(page, 'AAPL');
    await expect(row.first()).toBeVisible({ timeout: 10000 });
    const qtyCell = row.first().locator('[data-testid="position-qty"]');
    await expect
      .poll(
        async () => {
          const txt = await qtyCell.textContent();
          return parseFloat((txt || '').replace(/[^0-9.\-]/g, ''));
        },
        { timeout: 10000 }
      )
      .toBeGreaterThanOrEqual(5);
  });

  test('sell shares: cash increases, position updates', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Ensure a known starting quantity by buying 5 first.
    await executeTrade(page, 'AAPL', 5, 'buy');
    const qtyCell = positionRow(page, 'AAPL')
      .first()
      .locator('[data-testid="position-qty"]');
    await expect(qtyCell).toBeVisible({ timeout: 10000 });

    const readQty = async () => {
      const txt = await qtyCell.textContent();
      return parseFloat((txt || '').replace(/[^0-9.\-]/g, ''));
    };
    await expect.poll(readQty, { timeout: 10000 }).toBeGreaterThanOrEqual(5);
    const qtyBeforeSell = await readQty();

    const cashBeforeSell = await getCashBalance(page);

    await executeTrade(page, 'AAPL', 2, 'sell');

    // Cash increases after the sell fills.
    await expect
      .poll(async () => await getCashBalance(page), { timeout: 10000 })
      .toBeGreaterThan(cashBeforeSell);

    // Quantity drops by exactly 2.
    await expect
      .poll(readQty, { timeout: 10000 })
      .toBeCloseTo(qtyBeforeSell - 2, 4);
  });

  test('insufficient cash: error shown', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    await executeTrade(page, 'AAPL', 1000000, 'buy');

    // The trade bar surfaces a validation error rather than filling.
    const feedback = page.locator('[data-testid="trade-feedback"]');
    await expect(feedback).toBeVisible({ timeout: 10000 });
    await expect(feedback).toContainText(/insufficient|not enough|cash|fail|error/i);
  });

  test('portfolio heatmap renders with positions', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Guarantee at least one position so the heatmap has data to draw.
    await executeTrade(page, 'AAPL', 1, 'buy');
    await expect(positionRow(page, 'AAPL').first()).toBeVisible({ timeout: 10000 });

    const heatmap = page.locator('[data-testid="portfolio-heatmap"]');
    await expect(heatmap).toBeVisible({ timeout: 10000 });

    // Recharts Treemap renders <rect> elements inside an <svg>.
    const rects = heatmap.locator('svg rect');
    await expect
      .poll(async () => await rects.count(), { timeout: 10000 })
      .toBeGreaterThan(0);
  });

  test('P&L chart has data points', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // A trade triggers an immediate portfolio snapshot, ensuring chart data.
    await executeTrade(page, 'AAPL', 1, 'buy');

    const chart = page.locator('[data-testid="pnl-chart"]');
    await expect(chart).toBeVisible({ timeout: 10000 });

    // Chart libraries draw an <svg> or <canvas>; require one to be present
    // with rendered drawing primitives (path/line/rect) once data arrives.
    const svgOrCanvas = chart.locator('svg, canvas');
    await expect(svgOrCanvas.first()).toBeVisible({ timeout: 10000 });
    await expect
      .poll(
        async () => {
          const paths = await chart.locator('svg path, svg line, svg circle').count();
          const canvases = await chart.locator('canvas').count();
          return paths + canvases;
        },
        { timeout: 10000 }
      )
      .toBeGreaterThan(0);
  });

  test('AI chat: send message, see response and trade execution', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    await openChatPanel(page);

    const input = page.locator('[data-testid="chat-input"]');
    await expect(input).toBeVisible({ timeout: 10000 });
    await input.fill('analyze my portfolio');

    const sendBtn = page.locator('[data-testid="chat-send-button"]');
    if (await sendBtn.count()) {
      await sendBtn.click();
    } else {
      await input.press('Enter');
    }

    // The user's message appears in the conversation.
    await expect(
      page.locator('[data-testid="chat-message"]', { hasText: 'analyze my portfolio' })
    ).toBeVisible({ timeout: 10000 });

    // The mocked LLM response appears (LLM_MOCK=true gives a fixed reply).
    await expect(
      page.locator('[data-testid="chat-message"]', {
        hasText: /reviewed your portfolio/i,
      })
    ).toBeVisible({ timeout: 15000 });

    // The mock executes a 1-share AAPL buy, surfaced as an inline chip.
    const chip = page.locator('[data-testid="chat-trade-chip"]');
    if (await chip.count()) {
      await expect(chip.first()).toBeVisible({ timeout: 10000 });
      await expect(chip.first()).toContainText(/AAPL/i);
    } else {
      // Fallback: the executed trade should at least show AAPL in chat.
      await expect(
        page.locator('[data-testid="chat-message"]', { hasText: /AAPL/i }).first()
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test('SSE connection status shows green', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const status = page.locator('[data-testid="connection-status"]');
    await expect(status).toBeVisible({ timeout: 10000 });

    // Prefer the explicit data-status attribute; fall back to color classes.
    await expect
      .poll(
        async () => {
          const attr = await status.getAttribute('data-status');
          if (attr) return attr;
          const cls = (await status.getAttribute('class')) || '';
          if (/green|connected/i.test(cls)) return 'connected';
          return 'unknown';
        },
        { timeout: 10000 }
      )
      .toBe('connected');
  });
});
