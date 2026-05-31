"use client";

// ChatPanel — slide-over right aside, 360px wide, z-10 absolute.
// Grid rows: header (auto) / messages (1fr, scrollable, auto-scroll on
// append) / input form (auto).
// SEND uses bg-purple (locked CSS token).
// Closes via the × in the header (writes setChatOpen(false) to Zustand).

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useStore } from "@/store";
import { useChat } from "@/hooks/useChat";
import ChatMessage from "./ChatMessage";

export default function ChatPanel() {
  const { messages, send, pending } = useChat();
  const setChatOpen = useStore((s) => s.setChatOpen);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, pending]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || pending) return;
    setInput("");
    await send(text);
  }

  return (
    <aside className="h-full grid grid-rows-[auto_1fr_auto] border-l border-border bg-bg-surface">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <h2 className="text-text-secondary text-xs font-mono uppercase tracking-wide">
          AI Assistant
        </h2>
        <button
          type="button"
          onClick={() => setChatOpen(false)}
          aria-label="Close chat"
          className="text-text-muted hover:text-text-primary font-mono text-sm px-1"
        >
          ×
        </button>
      </div>
      <div ref={scrollRef} className="overflow-y-auto p-2 flex flex-col gap-2">
        {messages.length === 0 && !pending && (
          <p className="text-text-muted text-xs font-mono text-center mt-4">
            Ask FinAlly about your portfolio.
          </p>
        )}
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        {pending && (
          <div
            className="text-text-muted text-sm font-mono italic"
            role="status"
            aria-live="polite"
          >
            Thinking…
          </div>
        )}
      </div>
      <form
        onSubmit={handleSubmit}
        className="border-t border-border p-2 flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={pending}
          placeholder="Ask FinAlly..."
          aria-label="Message"
          maxLength={2000}
          className="flex-1 bg-bg-base border border-border rounded px-2 py-1 text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-primary disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={pending || !input.trim()}
          className="bg-purple text-text-primary font-bold rounded px-3 py-1 text-sm disabled:opacity-50"
        >
          SEND
        </button>
      </form>
    </aside>
  );
}
