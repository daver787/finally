import { api, ApiError } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("api client", () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it("posts a buy trade with the correct payload", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      jsonResponse({ cash_balance: 100, positions: [] }),
    );
    await api.trade({ ticker: "aapl", quantity: 10, side: "buy" });

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/portfolio/trade",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ ticker: "AAPL", quantity: 10, side: "buy" }),
      }),
    );
  });

  it("uppercases the ticker when adding to the watchlist", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse([]));
    await api.addWatchlistTicker("nvda");

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/watchlist",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ ticker: "NVDA" }),
      }),
    );
  });

  it("posts the chat message body", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      jsonResponse({ message: "ok" }),
    );
    await api.chat("buy 1 AAPL");

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "buy 1 AAPL" }),
      }),
    );
  });

  it("throws an ApiError carrying the server detail message", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      jsonResponse({ detail: "Insufficient cash" }, 400),
    );

    await expect(
      api.trade({ ticker: "AAPL", quantity: 999, side: "buy" }),
    ).rejects.toThrow("Insufficient cash");
  });

  it("ApiError exposes the HTTP status", async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      jsonResponse({ detail: "Not found" }, 404),
    );

    await expect(api.getPortfolio()).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
    });
    expect(ApiError).toBeDefined();
  });
});
