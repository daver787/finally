import { render, screen } from "@testing-library/react";
import { Header } from "@/components/Header";

function renderHeader(overrides: Partial<Parameters<typeof Header>[0]> = {}) {
  const props = {
    totalValue: 12345.67,
    cashBalance: 8000,
    totalPnl: 250.5,
    status: "connected" as const,
    chatOpen: false,
    onToggleChat: jest.fn(),
    ...overrides,
  };
  render(<Header {...props} />);
  return props;
}

describe("Header", () => {
  it("renders the cash balance", () => {
    renderHeader({ cashBalance: 8000 });
    expect(screen.getByTestId("cash-balance")).toHaveTextContent("$8,000.00");
  });

  it("renders portfolio value and unrealized P&L", () => {
    renderHeader({ totalValue: 12345.67, totalPnl: 250.5 });
    expect(screen.getByText("$12,345.67")).toBeInTheDocument();
    expect(screen.getByText("+$250.50")).toBeInTheDocument();
  });

  it("reflects connection status on the status indicator", () => {
    renderHeader({ status: "connected" });
    expect(screen.getByTestId("connection-status")).toHaveAttribute(
      "data-status",
      "connected",
    );
  });

  it("shows reconnecting status", () => {
    renderHeader({ status: "reconnecting" });
    expect(screen.getByTestId("connection-status")).toHaveAttribute(
      "data-status",
      "reconnecting",
    );
    expect(screen.getByText("SYNCING")).toBeInTheDocument();
  });

  it("shows disconnected status", () => {
    renderHeader({ status: "disconnected" });
    expect(screen.getByTestId("connection-status")).toHaveAttribute(
      "data-status",
      "disconnected",
    );
    expect(screen.getByText("OFFLINE")).toBeInTheDocument();
  });

  it("invokes onToggleChat when the copilot button is clicked", () => {
    const { onToggleChat } = renderHeader();
    screen.getByTestId("chat-toggle").click();
    expect(onToggleChat).toHaveBeenCalledTimes(1);
  });
});
