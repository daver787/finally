import { render, screen, within } from "@testing-library/react";
import { PositionsTable } from "@/components/PositionsTable";
import type { Position } from "@/lib/types";

const POSITIONS: Position[] = [
  {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 150,
    current_price: 190,
    unrealized_pnl: 400,
    pnl_pct: 26.67,
  },
  {
    ticker: "TSLA",
    quantity: 5,
    avg_cost: 260,
    current_price: 240,
    unrealized_pnl: -100,
    pnl_pct: -7.69,
  },
  {
    ticker: "MSFT",
    quantity: 0,
    avg_cost: 300,
    current_price: 310,
    unrealized_pnl: 0,
    pnl_pct: 0,
  },
];

function renderTable(
  overrides: Partial<Parameters<typeof PositionsTable>[0]> = {},
) {
  const props = {
    positions: POSITIONS,
    getLivePrice: () => undefined,
    onSelect: jest.fn(),
    selected: null,
    ...overrides,
  };
  render(<PositionsTable {...props} />);
  return props;
}

describe("PositionsTable", () => {
  it("renders only positions with a non-zero quantity", () => {
    renderTable();
    const rows = screen.getAllByTestId("position-row");
    expect(rows).toHaveLength(2);
    expect(rows.map((r) => r.getAttribute("data-ticker"))).toEqual([
      "AAPL",
      "TSLA",
    ]);
  });

  it("computes a profitable position's unrealized P&L", () => {
    // (current_price - avg_cost) * quantity = (190 - 150) * 10 = +400
    renderTable();
    const row = screen
      .getAllByTestId("position-row")
      .find((r) => r.getAttribute("data-ticker") === "AAPL")!;
    expect(within(row).getByText("+$400.00")).toBeInTheDocument();
    expect(within(row).getByText("+26.67%")).toBeInTheDocument();
  });

  it("computes a losing position's unrealized P&L", () => {
    // (240 - 260) * 5 = -100
    renderTable();
    const row = screen
      .getAllByTestId("position-row")
      .find((r) => r.getAttribute("data-ticker") === "TSLA")!;
    expect(within(row).getByText("-$100.00")).toBeInTheDocument();
    expect(within(row).getByText("-7.69%")).toBeInTheDocument();
  });

  it("recomputes P&L from a live SSE price when available", () => {
    // live AAPL price 200 -> (200 - 150) * 10 = +500
    renderTable({
      getLivePrice: (t) => (t === "AAPL" ? 200 : undefined),
    });
    const row = screen
      .getAllByTestId("position-row")
      .find((r) => r.getAttribute("data-ticker") === "AAPL")!;
    expect(within(row).getByText("+$500.00")).toBeInTheDocument();
  });

  it("renders the quantity cell", () => {
    renderTable();
    const row = screen
      .getAllByTestId("position-row")
      .find((r) => r.getAttribute("data-ticker") === "AAPL")!;
    expect(within(row).getByTestId("position-qty")).toHaveTextContent("10");
  });

  it("calls onSelect with the ticker when a row is clicked", () => {
    const { onSelect } = renderTable();
    screen
      .getAllByTestId("position-row")
      .find((r) => r.getAttribute("data-ticker") === "TSLA")!
      .click();
    expect(onSelect).toHaveBeenCalledWith("TSLA");
  });

  it("shows an empty state when there are no open positions", () => {
    renderTable({ positions: [] });
    expect(screen.getByText(/No open positions/i)).toBeInTheDocument();
    expect(screen.queryAllByTestId("position-row")).toHaveLength(0);
  });
});
