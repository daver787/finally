"use client";

// WatchlistAdd — compact input row docked beneath the watchlist panel.

import { useState } from "react";

interface WatchlistAddProps {
  onAdd: (ticker: string) => Promise<void>;
}

export function WatchlistAdd({ onAdd }: WatchlistAddProps) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const sym = value.trim().toUpperCase();
    if (!sym) return;
    setBusy(true);
    setError(null);
    try {
      await onAdd(sym);
      setValue("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add ticker");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel panel-in shrink-0">
      <div className="flex items-center gap-2 px-3 py-2">
        <input
          data-testid="watchlist-add-input"
          value={value}
          onChange={(e) => {
            setValue(e.target.value.toUpperCase());
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          placeholder="ADD SYMBOL…"
          aria-label="Add ticker to watchlist"
          className="field flex-1 px-2.5 py-1.5 text-xs uppercase tracking-wide"
          disabled={busy}
        />
        <button
          data-testid="watchlist-add-button"
          onClick={submit}
          disabled={busy}
          className="btn px-3 py-1.5 text-xs"
          style={{ background: "var(--purple)", color: "var(--ink)" }}
        >
          {busy ? "…" : "ADD"}
        </button>
      </div>
      {error && (
        <div
          className="px-3 pb-2 text-[10px] tnum"
          style={{ color: "var(--down)" }}
        >
          ✕ {error}
        </div>
      )}
    </div>
  );
}
