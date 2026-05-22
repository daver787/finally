import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/components/ChatPanel";
import type { ChatMessage } from "@/lib/types";

function renderPanel(overrides: Partial<Parameters<typeof ChatPanel>[0]> = {}) {
  const props = {
    open: true,
    messages: [] as ChatMessage[],
    busy: false,
    onSend: jest.fn(),
    onClose: jest.fn(),
    ...overrides,
  };
  render(<ChatPanel {...props} />);
  return props;
}

describe("ChatPanel", () => {
  it("renders nothing when closed", () => {
    renderPanel({ open: false });
    expect(screen.queryByTestId("chat-input")).not.toBeInTheDocument();
  });

  it("renders the message input and send button when open", () => {
    renderPanel();
    expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    expect(screen.getByTestId("chat-send-button")).toBeInTheDocument();
  });

  it("calls onSend with the trimmed draft when Send is clicked", async () => {
    const user = userEvent.setup();
    const { onSend } = renderPanel();
    await user.type(screen.getByTestId("chat-input"), "  buy 5 NVDA  ");
    await user.click(screen.getByTestId("chat-send-button"));
    expect(onSend).toHaveBeenCalledWith("buy 5 NVDA");
  });

  it("clears the input after sending", async () => {
    const user = userEvent.setup();
    renderPanel();
    const input = screen.getByTestId("chat-input");
    await user.type(input, "hello");
    await user.click(screen.getByTestId("chat-send-button"));
    expect(input).toHaveValue("");
  });

  it("submits on Enter without Shift", async () => {
    const user = userEvent.setup();
    const { onSend } = renderPanel();
    await user.type(screen.getByTestId("chat-input"), "analyze risk{Enter}");
    expect(onSend).toHaveBeenCalledWith("analyze risk");
  });

  it("does not send while busy", async () => {
    const user = userEvent.setup();
    const { onSend } = renderPanel({ busy: true });
    const input = screen.getByTestId("chat-input");
    // textarea is disabled while busy; clicking send must not fire onSend
    expect(input).toBeDisabled();
    await user.click(screen.getByTestId("chat-send-button"));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows the loading indicator while busy", () => {
    renderPanel({ busy: true });
    expect(screen.getByText(/thinking/i)).toBeInTheDocument();
  });

  it("renders user and assistant message bubbles", () => {
    const messages: ChatMessage[] = [
      { id: "1", role: "user", content: "Buy 1 AAPL" },
      {
        id: "2",
        role: "assistant",
        content: "Done — bought 1 share.",
        trades: [{ ticker: "AAPL", side: "buy", quantity: 1, price: 190 }],
      },
    ];
    renderPanel({ messages });
    const bubbles = screen.getAllByTestId("chat-message");
    expect(bubbles).toHaveLength(2);
    expect(bubbles[0]).toHaveAttribute("data-role", "user");
    expect(bubbles[1]).toHaveAttribute("data-role", "assistant");
  });

  it("renders inline trade chips for assistant trade executions", () => {
    const messages: ChatMessage[] = [
      {
        id: "2",
        role: "assistant",
        content: "Executed your trade.",
        trades: [{ ticker: "AAPL", side: "buy", quantity: 1, price: 190 }],
      },
    ];
    renderPanel({ messages });
    const chips = screen.getAllByTestId("chat-trade-chip");
    expect(chips).toHaveLength(1);
    expect(chips[0]).toHaveTextContent("Bought 1 AAPL");
  });

  it("renders suggested prompts in the empty state", () => {
    renderPanel({ messages: [] });
    expect(
      screen.getByText(/Ask FinAlly to analyze your portfolio/i),
    ).toBeInTheDocument();
  });
});
