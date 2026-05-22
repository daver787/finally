import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TradeBar } from "@/components/TradeBar";

describe("TradeBar", () => {
  it("calls onTrade with a buy payload when the Buy button is clicked", async () => {
    const user = userEvent.setup();
    const onTrade = jest.fn().mockResolvedValue(undefined);
    render(<TradeBar defaultTicker={null} onTrade={onTrade} />);

    await user.type(screen.getByTestId("trade-ticker-input"), "aapl");
    await user.type(screen.getByTestId("trade-quantity-input"), "10");
    await user.click(screen.getByTestId("trade-buy-button"));

    expect(onTrade).toHaveBeenCalledWith("AAPL", 10, "buy");
  });

  it("calls onTrade with a sell payload when the Sell button is clicked", async () => {
    const user = userEvent.setup();
    const onTrade = jest.fn().mockResolvedValue(undefined);
    render(<TradeBar defaultTicker={null} onTrade={onTrade} />);

    await user.type(screen.getByTestId("trade-ticker-input"), "nvda");
    await user.type(screen.getByTestId("trade-quantity-input"), "2.5");
    await user.click(screen.getByTestId("trade-sell-button"));

    expect(onTrade).toHaveBeenCalledWith("NVDA", 2.5, "sell");
  });

  it("shows a success message after a trade resolves", async () => {
    const user = userEvent.setup();
    const onTrade = jest.fn().mockResolvedValue(undefined);
    render(<TradeBar defaultTicker="AAPL" onTrade={onTrade} />);

    await user.type(screen.getByTestId("trade-quantity-input"), "3");
    await user.click(screen.getByTestId("trade-buy-button"));

    await waitFor(() => {
      expect(screen.getByTestId("trade-feedback")).toHaveTextContent(
        "Bought 3 AAPL",
      );
    });
  });

  it("shows the error message when a trade rejects", async () => {
    const user = userEvent.setup();
    const onTrade = jest
      .fn()
      .mockRejectedValue(new Error("Insufficient cash"));
    render(<TradeBar defaultTicker="AAPL" onTrade={onTrade} />);

    await user.type(screen.getByTestId("trade-quantity-input"), "999");
    await user.click(screen.getByTestId("trade-buy-button"));

    await waitFor(() => {
      expect(screen.getByTestId("trade-feedback")).toHaveTextContent(
        "Insufficient cash",
      );
    });
  });

  it("rejects an empty ticker without calling onTrade", async () => {
    const user = userEvent.setup();
    const onTrade = jest.fn().mockResolvedValue(undefined);
    render(<TradeBar defaultTicker={null} onTrade={onTrade} />);

    await user.type(screen.getByTestId("trade-quantity-input"), "5");
    await user.click(screen.getByTestId("trade-buy-button"));

    expect(onTrade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-feedback")).toHaveTextContent(
      /ticker symbol/i,
    );
  });

  it("rejects a non-positive quantity without calling onTrade", async () => {
    const user = userEvent.setup();
    const onTrade = jest.fn().mockResolvedValue(undefined);
    render(<TradeBar defaultTicker="AAPL" onTrade={onTrade} />);

    await user.type(screen.getByTestId("trade-quantity-input"), "0");
    await user.click(screen.getByTestId("trade-buy-button"));

    expect(onTrade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-feedback")).toHaveTextContent(
      /positive quantity/i,
    );
  });

  it("prefills the ticker from defaultTicker", () => {
    render(<TradeBar defaultTicker="TSLA" onTrade={jest.fn()} />);
    expect(screen.getByTestId("trade-ticker-input")).toHaveValue("TSLA");
  });
});
