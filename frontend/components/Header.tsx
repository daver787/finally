"use client";

import type { ConnectionStatus } from "@/lib/types";
import { fmtMoney } from "@/lib/format";

interface HeaderProps {
  totalValue: number;
  cashBalance: number;
  totalPnl: number;
  status: ConnectionStatus;
  chatOpen: boolean;
  onToggleChat: () => void;
}

const STATUS_META: Record<
  ConnectionStatus,
  { color: string; label: string; pulse: boolean }
> = {
  connected: { color: "var(--up)", label: "LIVE", pulse: true },
  reconnecting: { color: "var(--accent)", label: "SYNCING", pulse: true },
  disconnected: { color: "var(--down)", label: "OFFLINE", pulse: false },
};

export function Header({
  totalValue,
  cashBalance,
  totalPnl,
  status,
  chatOpen,
  onToggleChat,
}: HeaderProps) {
  const meta = STATUS_META[status];
  const pnlColor =
    totalPnl > 0 ? "var(--up)" : totalPnl < 0 ? "var(--down)" : "var(--ink-dim)";

  return (
    <header
      className="flex items-center justify-between px-4 h-14 shrink-0"
      style={{
        borderBottom: "1px solid var(--border)",
        background:
          "linear-gradient(180deg, rgba(19,26,38,0.9), rgba(13,17,23,0.9))",
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center w-9 h-9 rounded"
          style={{
            background:
              "linear-gradient(135deg, var(--accent), var(--purple))",
            boxShadow: "0 0 18px rgba(236,173,10,0.3)",
          }}
        >
          <span
            className="font-extrabold text-base"
            style={{ color: "#0a0e16" }}
          >
            F
          </span>
        </div>
        <div className="leading-tight">
          <div className="flex items-baseline gap-1.5">
            <span className="text-base font-extrabold tracking-tight">
              FinAlly
            </span>
            <span
              className="text-[10px] font-semibold tracking-[0.22em] tnum"
              style={{ color: "var(--accent)" }}
            >
              v1.0
            </span>
          </div>
          <div
            className="text-[10px] tracking-[0.18em] uppercase"
            style={{ color: "var(--ink-faint)" }}
          >
            AI Trading Workstation
          </div>
        </div>
      </div>

      {/* Center — total portfolio value */}
      <div className="flex items-center gap-7">
        <Stat
          label="Portfolio Value"
          value={fmtMoney(totalValue)}
          big
          valueColor="var(--ink)"
        />
        <div
          className="h-8 w-px"
          style={{ background: "var(--border)" }}
        />
        <Stat
          label="Unrealized P&L"
          value={fmtMoney(totalPnl, { sign: true })}
          valueColor={pnlColor}
        />
        <div
          className="h-8 w-px"
          style={{ background: "var(--border)" }}
        />
        <Stat
          label="Cash"
          value={fmtMoney(cashBalance)}
          valueColor="var(--blue)"
          testId="cash-balance"
        />
      </div>

      {/* Right — connection + chat toggle */}
      <div className="flex items-center gap-3">
        <div
          className="flex items-center gap-2 px-2.5 py-1.5 rounded"
          style={{
            background: "var(--bg-base)",
            border: "1px solid var(--border)",
          }}
        >
          <span
            data-testid="connection-status"
            data-status={status}
            className={meta.pulse ? "dot-pulse" : ""}
            style={{
              width: 8,
              height: 8,
              borderRadius: 999,
              background: meta.color,
              color: meta.color,
              display: "inline-block",
              boxShadow: `0 0 8px ${meta.color}`,
            }}
            aria-label={`Connection: ${meta.label}`}
          />
          <span
            className="text-[10px] font-bold tracking-[0.14em] tnum"
            style={{ color: meta.color }}
          >
            {meta.label}
          </span>
        </div>

        <button
          data-testid="chat-toggle"
          onClick={onToggleChat}
          className="btn flex items-center gap-2 px-3 py-1.5 text-xs"
          style={{
            background: chatOpen ? "var(--purple)" : "var(--bg-elevated)",
            border: "1px solid var(--border-bright)",
            color: "var(--ink)",
          }}
        >
          <span
            style={{ width: 7, height: 7, borderRadius: 999, background: "var(--accent)", display: "inline-block" }}
          />
          AI COPILOT
        </button>
      </div>
    </header>
  );
}

function Stat({
  label,
  value,
  valueColor,
  big,
  testId,
}: {
  label: string;
  value: string;
  valueColor: string;
  big?: boolean;
  testId?: string;
}) {
  return (
    <div className="text-right leading-tight">
      <div
        className="text-[9px] tracking-[0.16em] uppercase"
        style={{ color: "var(--ink-faint)" }}
      >
        {label}
      </div>
      <div
        data-testid={testId}
        className={`tnum font-bold ${big ? "text-xl" : "text-sm"}`}
        style={{ color: valueColor }}
      >
        {value}
      </div>
    </div>
  );
}
