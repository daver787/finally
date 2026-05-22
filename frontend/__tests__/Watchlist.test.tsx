import { render, screen } from "@testing-library/react";
import { Watchlist } from "@/components/Watchlist";
import type {
  Direction,
  PricePoint,
  PriceSnapshot,
  WatchlistItem,
} from "@/lib/types";

const ITEMS: WatchlistItem[] = [
  { ticker: "AAPL", price: 190.12, prev_price: 189.0, change_pct: 0.59 },
  { ticker: "TSLA", price: 240.5, prev_price: 245.0, change_pct: -1.84 },
];

function renderWatchlist(
  overrides: Partial<Parameters<typeof Watchlist>[0]> = {},
) {
  const props = {
    items: ITEMS,
    prices: {} as Record<string, PriceSnapshot>,
    history: {} as Record<string, PricePoint[]>,
    lastChanged: {} as Record<string, Direction>,
    selected: null,
    onSelect: jest.fn(),
    onRemove: jest.fn(),
    ...overrides,
  };
  render(<Watchlist {...props} />);
  return props;
}

describe("Watchlist", () => {
  it("renders one row per watchlist item", () => {
    renderWatchlist();
    const rows = screen.getAllByTestId("watchlist-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute("data-ticker", "AAPL");
    expect(rows[1]).toHaveAttribute("data-ticker", "TSLA");
  });

  it("renders ticker symbols and prices from the REST snapshot", () => {
    renderWatchlist();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    const prices = screen.getAllByTestId("watchlist-price");
    expect(prices[0]).toHaveTextContent("190.12");
    expect(prices[1]).toHaveTextContent("240.50");
  });

  it("prefers live SSE prices over the REST snapshot when present", () => {
    renderWatchlist({
      prices: {
        AAPL: {
          ticker: "AAPL",
          price: 201.99,
          previousPrice: 190.12,
          changePct: 6.24,
          direction: "up",
          timestamp: 1,
        },
      },
    });
    const prices = screen.getAllByTestId("watchlist-price");
    expect(prices[0]).toHaveTextContent("201.99");
  });

  it("applies the flash-green class when a ticker ticks up", () => {
    renderWatchlist({
      prices: {
        AAPL: {
          ticker: "AAPL",
          price: 191,
          previousPrice: 190,
          changePct: 0.53,
          direction: "up",
          timestamp: 1,
        },
      },
      lastChanged: { AAPL: "up" },
    });
    const rows = screen.getAllByTestId("watchlist-row");
    expect(rows[0]).toHaveClass("flash-green");
  });

  it("applies the flash-red class when a ticker ticks down", () => {
    renderWatchlist({
      prices: {
        TSLA: {
          ticker: "TSLA",
          price: 239,
          previousPrice: 240.5,
          changePct: -0.62,
          direction: "down",
          timestamp: 1,
        },
      },
      lastChanged: { TSLA: "down" },
    });
    const rows = screen.getAllByTestId("watchlist-row");
    expect(rows[1]).toHaveClass("flash-red");
  });

  it("removes the flash class after the timeout elapses", () => {
    jest.useFakeTimers();
    try {
      renderWatchlist({
        prices: {
          AAPL: {
            ticker: "AAPL",
            price: 191,
            previousPrice: 190,
            changePct: 0.53,
            direction: "up",
            timestamp: 1,
          },
        },
        lastChanged: { AAPL: "up" },
      });
      const row = screen.getAllByTestId("watchlist-row")[0];
      expect(row).toHaveClass("flash-green");
      jest.advanceTimersByTime(600);
      expect(row).not.toHaveClass("flash-green");
    } finally {
      jest.useRealTimers();
    }
  });

  it("calls onSelect with the ticker when a row is clicked", () => {
    const { onSelect } = renderWatchlist();
    screen.getAllByTestId("watchlist-row")[1].click();
    expect(onSelect).toHaveBeenCalledWith("TSLA");
  });

  it("calls onRemove without selecting when the remove button is clicked", () => {
    const { onSelect, onRemove } = renderWatchlist();
    screen.getAllByTestId("watchlist-remove-btn")[0].click();
    expect(onRemove).toHaveBeenCalledWith("AAPL");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("shows an empty state when there are no items", () => {
    renderWatchlist({ items: [] });
    expect(screen.getByText(/No symbols/i)).toBeInTheDocument();
    expect(screen.queryAllByTestId("watchlist-row")).toHaveLength(0);
  });
});
