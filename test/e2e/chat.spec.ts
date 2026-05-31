import { test, expect } from '@playwright/test';

/**
 * E2E-06 — AI chat (deterministic mock) with inline trade chip.
 *
 * The harness runs the app service with LLM_MOCK=true (set in 05-01), so the
 * backend returns a fixed MOCK_RESPONSE (chat.py): the message
 * "I've reviewed your portfolio. I'll pick up 1 share of AAPL to demonstrate
 * trade execution." plus a single buy-1-AAPL trade that auto-executes against
 * the seeded $10k cash. No OPENROUTER_API_KEY is needed or referenced — the
 * mock path never calls OpenRouter (threat T-05-06).
 *
 * The ChatPanel is conditionally rendered (Header "Ask FinAlly" toggles a
 * Zustand flag that TradingTerminal observes), so the toggle MUST be clicked
 * before interacting with the message input (RESEARCH Pitfall 3).
 *
 * Selectors are the verified accessibility/text locators:
 *   - getByRole('button',{name:'Ask FinAlly'})  Header.tsx:62
 *   - getByLabel('Message')                      ChatPanel.tsx:77
 *   - getByRole('button',{name:'SEND'})          ChatPanel.tsx:81-87
 *   - mock reply text                            chat.py MOCK_RESPONSE (regex)
 *   - inline trade chip BUY ... AAAPL            TradeChip.tsx TradeChipSuccess
 *
 * Web-first assertions only — no waitForTimeout. The inline-chip locator is
 * MEDIUM confidence (text-based); if it ever flakes it is the single candidate
 * for a targeted data-testid (NOT added preemptively; frontend is locked).
 */

test('ai chat (mock) shows response + inline trade chip', async ({ page }) => {
  await page.goto('/');

  // Mount the ChatPanel — it is conditionally rendered (Pitfall 3).
  await page.getByRole('button', { name: 'Ask FinAlly' }).click();

  // Send a message; the mock reply is deterministic under LLM_MOCK=true.
  await page.getByLabel('Message').fill('Analyze my portfolio');
  await page.getByRole('button', { name: 'SEND' }).click();

  // The fixed mock reply text is rendered verbatim by the assistant message.
  await expect(page.getByText(/pick up 1 share of AAPL/)).toBeVisible();

  // The auto-executed buy renders an inline TradeChipSuccess pill containing
  // both "BUY" and "AAPL". Filter a span on both texts and assert the first.
  const tradeChip = page
    .locator('span', { hasText: 'AAPL' })
    .filter({ hasText: 'BUY' });
  await expect(tradeChip.first()).toBeVisible();
});
