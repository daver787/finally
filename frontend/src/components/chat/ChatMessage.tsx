"use client";

// ChatMessage — one row in the chat history. User messages right-aligned with
// a subtle bg; assistant messages left-aligned and rendered as Markdown so the
// model's **bold**, bullet lists, and GFM tables display formatted (rather than
// as raw markdown source). Assistant messages with executed actions render
// inline TradeChip elements after the message body.

import clsx from "clsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { TradeChipSuccess, TradeChipError } from "./TradeChip";
import type { StoredChatMessage } from "@/lib/types";

// Markdown element overrides tuned for the dark, dense terminal aesthetic.
// Compact spacing keeps the chat panel readable without large vertical gaps.
const markdownComponents: Components = {
  p: ({ children }) => <p className="my-1 first:mt-0 last:mb-0">{children}</p>,
  strong: ({ children }) => (
    <strong className="font-bold text-text-primary">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => (
    <ul className="my-1 ml-4 list-disc space-y-0.5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-1 ml-4 list-decimal space-y-0.5">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-snug">{children}</li>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue underline hover:text-accent"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-bg-elevated px-1 py-0.5 text-[0.85em] text-accent">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-1 overflow-x-auto rounded bg-bg-elevated p-2 text-xs">
      {children}
    </pre>
  ),
  h1: ({ children }) => (
    <h1 className="mb-1 mt-2 text-sm font-bold text-text-primary first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-1 mt-2 text-sm font-bold text-text-primary first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1 mt-2 text-sm font-semibold text-text-primary first:mt-0">
      {children}
    </h3>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-1 border-l-2 border-border pl-2 text-text-muted">
      {children}
    </blockquote>
  ),
  table: ({ children }) => (
    <div className="my-1 overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead>{children}</thead>,
  th: ({ children }) => (
    <th className="border border-border px-1.5 py-0.5 text-left font-semibold text-text-primary">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-border px-1.5 py-0.5">{children}</td>
  ),
  hr: () => <hr className="my-2 border-border" />,
};

export default function ChatMessage({
  message,
}: {
  message: StoredChatMessage;
}) {
  const isUser = message.role === "user";
  return (
    <div
      className={clsx("flex flex-col", isUser ? "items-end" : "items-start")}
    >
      <div
        className={clsx(
          "max-w-[85%] rounded px-2 py-1.5 text-sm font-mono",
          isUser
            ? "bg-bg-elevated text-text-primary whitespace-pre-wrap"
            : "text-text-secondary",
        )}
      >
        {isUser ? (
          message.content
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {message.content}
          </ReactMarkdown>
        )}
      </div>
      {!isUser && message.actions && (
        <div className="mt-1 flex flex-wrap gap-1">
          {(message.actions.trades ?? []).map((t, i) => (
            <TradeChipSuccess key={`s-${i}`} trade={t} />
          ))}
          {(message.actions.errors ?? []).map((e, i) => (
            <TradeChipError key={`e-${i}`} err={e} />
          ))}
          {(message.actions.watchlist_changes ?? []).map((w, i) => (
            <span
              key={`w-${i}`}
              className="inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded border border-accent/40 bg-accent/10 text-accent"
            >
              <span className="font-bold">{w.action.toUpperCase()}</span>
              <span>{w.ticker}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
