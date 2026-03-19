"use client";

import { useState } from "react";
import { IconCompare } from "@/components/icons";
import { SkeletonList } from "@/components/skeleton";
import { ErrorBoundary } from "@/components/error-boundary";
import { RetailerLogo } from "@/components/retailer-logo";

interface RetailerPrice {
  retailer: string;
  name: string;
  price: number;
  discount_pct: number | null;
}

interface Comparison {
  product_name: string;
  retailers: RetailerPrice[];
}

const RETAILER_COLORS: Record<string, string> = {
  migros: "text-orange-400",
  coop: "text-red-400",
  aldi: "text-blue-400",
  denner: "text-yellow-400",
  lidl: "text-sky-400",
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

function CompareContent() {
  const [query, setQuery] = useState("");
  const [comparisons, setComparisons] = useState<Comparison[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [askAnswer, setAskAnswer] = useState("");
  const [askLoading, setAskLoading] = useState(false);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    setAskAnswer("");
    try {
      const params = new URLSearchParams({ q: query, limit: "10" });
      const res = await fetch(`${API_BASE}/api/v1/products/compare?${params}`);
      const data = await res.json();
      const comps: Comparison[] = data.comparisons ?? [];
      // Filter out "other" retailer
      const filtered = comps.map((c) => ({
        ...c,
        retailers: c.retailers.filter(
          (r) => r.retailer.toLowerCase() !== "other",
        ),
      })).filter((c) => c.retailers.length > 0);
      setComparisons(filtered);
    } catch {
      setComparisons([]);
    } finally {
      setLoading(false);
    }
  };

  const askAboutProduct = async () => {
    if (!query.trim()) return;
    setAskLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/products/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });
      const data = await res.json();
      setAskAnswer(data.answer ?? data.response ?? JSON.stringify(data));
    } catch {
      setAskAnswer("Could not get an answer right now.");
    } finally {
      setAskLoading(false);
    }
  };

  return (
    <>
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          placeholder="e.g. Milk, Butter, Bread..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          className="flex-1 px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08] focus:border-red-500 focus:outline-none transition"
        />
        <button
          onClick={search}
          disabled={loading}
          className="px-5 py-3 rounded-xl bg-red-600 font-semibold hover:bg-red-500 transition-all disabled:opacity-50 shadow-lg shadow-red-600/25"
        >
          Compare
        </button>
        <button
          onClick={askAboutProduct}
          disabled={askLoading || !query.trim()}
          className="px-4 py-3 rounded-xl bg-white/[0.06] border border-white/[0.08] font-semibold hover:bg-white/[0.1] transition-all disabled:opacity-40 text-sm"
        >
          Ask AI
        </button>
      </div>

      {askAnswer && (
        <div className="mb-6 p-4 rounded-xl bg-violet-500/10 border border-violet-500/20 text-sm text-white/80 whitespace-pre-wrap">
          <p className="text-xs text-violet-400 font-semibold mb-1">
            AI Answer
          </p>
          {askAnswer}
        </div>
      )}

      {loading ? (
        <SkeletonList count={5} />
      ) : !searched ? (
        <p className="text-white/40 text-center mt-12">
          Search for a product to compare prices across retailers.
        </p>
      ) : comparisons.length === 0 ? (
        <p className="text-white/40 text-center">No results found.</p>
      ) : (
        <div className="space-y-6">
          {comparisons.map((comp, ci) => (
            <div
              key={ci}
              className="rounded-2xl bg-white/[0.03] border border-white/[0.08] overflow-hidden"
            >
              <div className="px-5 pt-4 pb-2">
                <h3 className="font-bold text-white/90 capitalize">
                  {comp.product_name}
                </h3>
                <p className="text-xs text-white/30">
                  {comp.retailers.length} retailers compared
                </p>
              </div>
              <div className="px-3 pb-3 space-y-1.5">
                {comp.retailers
                  .sort((a, b) => a.price - b.price)
                  .map((r, i) => (
                    <div
                      key={i}
                      className={`flex items-center gap-5 rounded-xl px-4 py-3 transition-all ${
                        i === 0
                          ? "bg-emerald-500/10 border border-emerald-500/20"
                          : "bg-white/[0.03] border border-white/[0.04]"
                      }`}
                    >
                      <RetailerLogo retailer={r.retailer} size="sm" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-xs font-bold uppercase tracking-wider ${
                              RETAILER_COLORS[r.retailer.toLowerCase()] ??
                              "text-white/50"
                            }`}
                          >
                            {r.retailer}
                          </span>
                          {i === 0 && (
                            <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded-full font-semibold">
                              Cheapest
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-white/60 truncate mt-0.5">
                          {r.name}
                        </p>
                      </div>
                      <div className="text-right flex-shrink-0 ml-3">
                        <p className="text-lg font-bold font-mono">
                          CHF {r.price?.toFixed(2)}
                        </p>
                        {r.discount_pct != null && r.discount_pct > 0 && (
                          <span className="text-xs text-red-400 font-semibold">
                            -{r.discount_pct}%
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export default function ComparePage() {
  return (
    <main className="min-h-screen p-6 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 flex items-center gap-3">
        <IconCompare className="w-8 h-8 text-red-400" />
        Price Comparison
      </h1>
      <ErrorBoundary>
        <CompareContent />
      </ErrorBoundary>
    </main>
  );
}
