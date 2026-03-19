"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { ErrorBoundary } from "@/components/error-boundary";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

function ChatContent() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        'Hi! I\'m your shopping assistant. Ask me anything — e.g. "Find the cheapest pasta" or "What\'s on sale at Migros this week?"',
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const query = input.trim();
    if (!query || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setLoading(true);

    try {
      const res = await fetch(
        `${API_BASE}/api/v1/products/search?q=${encodeURIComponent(query)}&limit=5`,
      );
      const data = await res.json();
      const products = data.products ?? data ?? [];

      let reply: string;
      if (products.length === 0) {
        reply = `I couldn't find any products matching "${query}". Try a different search term.`;
      } else {
        const lines = products.map(
          (
            p: {
              name: string;
              retailer: string;
              price: number;
              discount_pct: number;
            },
            i: number,
          ) =>
            `${i + 1}. **${p.name}** — CHF ${p.price?.toFixed(2)} at ${p.retailer}${p.discount_pct > 0 ? ` (-${p.discount_pct}%)` : ""}`,
        );
        reply = `Here's what I found:\n\n${lines.join("\n")}\n\nThe cheapest option is #1. Want me to add it to your shopping list?`;
      }

      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I couldn't reach the backend. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100dvh-3.25rem)] max-w-2xl mx-auto">
      <div className="flex-1 overflow-y-auto space-y-4 p-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-red-600 text-white rounded-br-sm"
                  : "bg-white/[0.06] border border-white/[0.08] text-white/80 rounded-bl-sm"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-ol:my-1 prose-li:my-0.5 prose-strong:text-white">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white/[0.06] border border-white/[0.08] rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex gap-1">
                <div
                  className="w-2 h-2 rounded-full bg-white/30 animate-bounce"
                  style={{ animationDelay: "0ms" }}
                />
                <div
                  className="w-2 h-2 rounded-full bg-white/30 animate-bounce"
                  style={{ animationDelay: "150ms" }}
                />
                <div
                  className="w-2 h-2 rounded-full bg-white/30 animate-bounce"
                  style={{ animationDelay: "300ms" }}
                />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="p-4 pb-20 border-t border-white/[0.06]">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask about products, prices, recipes..."
            className="flex-1 px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08] focus:border-red-500 focus:outline-none transition text-sm"
            disabled={loading}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="px-5 py-3 rounded-xl bg-red-600 font-semibold hover:bg-red-500 transition-all disabled:opacity-40 text-sm"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <main className="max-w-2xl mx-auto -mb-20">
      <ErrorBoundary>
        <ChatContent />
      </ErrorBoundary>
    </main>
  );
}
