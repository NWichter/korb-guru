"use client";

import { useEffect, useState } from "react";
import { IconDeals } from "@/components/icons";
import { SkeletonList } from "@/components/skeleton";
import { ErrorBoundary } from "@/components/error-boundary";
import { RetailerLogo } from "@/components/retailer-logo";

interface Product {
  id: string;
  name: string;
  retailer: string;
  price: number;
  discount_pct: number;
  category: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const RETAILERS = ["all", "migros", "coop", "aldi", "denner", "lidl"];

function DealsContent() {
  const [products, setProducts] = useState<Product[]>([]);
  const [recommended, setRecommended] = useState<Product[]>([]);
  const [retailer, setRetailer] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "20" });
    if (retailer !== "all") params.set("retailer", retailer);

    fetch(`${API_BASE}/api/v1/products/deals?${params}`)
      .then((r) => r.json())
      .then((data) => setProducts(data.products ?? data ?? []))
      .catch(() => setProducts([]))
      .finally(() => setLoading(false));
  }, [retailer]);

  // Load personalized recommendations
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/products/recommended?limit=5`)
      .then((r) => r.json())
      .then((data) => setRecommended(data.products ?? data ?? []))
      .catch(() => setRecommended([]));
  }, []);

  const sendFeedback = async (productId: string, positive: boolean) => {
    try {
      await fetch(`${API_BASE}/api/v1/products/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, positive }),
      });
    } catch {
      /* ignore */
    }
  };

  return (
    <>
      <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
        {RETAILERS.map((r) => (
          <button
            key={r}
            onClick={() => setRetailer(r)}
            className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all duration-200 ${
              retailer === r
                ? "bg-red-600 text-white shadow-lg shadow-red-600/25"
                : "bg-white/[0.04] border border-white/[0.08] text-white/60 hover:bg-white/[0.08]"
            }`}
          >
            {r === "all" ? "All" : r.charAt(0).toUpperCase() + r.slice(1)}
          </button>
        ))}
      </div>

      {/* Personalized recommendations */}
      {recommended.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-white/60 mb-3">
            Recommended for you
          </h3>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {recommended.map((p) => (
              <div
                key={p.id}
                className="min-w-[160px] rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3 flex-shrink-0"
              >
                <p className="font-semibold text-sm truncate">{p.name}</p>
                <p className="text-xs text-white/40 capitalize">{p.retailer}</p>
                <p className="text-sm font-bold text-emerald-400 mt-1">
                  CHF {p.price?.toFixed(2)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <SkeletonList count={6} />
      ) : products.length === 0 ? (
        <p className="text-white/40 text-center mt-12">No deals found.</p>
      ) : (
        <div className="space-y-3">
          {products.map((p) => (
            <div
              key={p.id}
              className="flex items-center gap-5 rounded-xl bg-white/[0.04] border border-white/[0.08] p-4 transition-all duration-300 hover:bg-white/[0.06] hover:-translate-y-0.5"
            >
              <RetailerLogo retailer={p.retailer} size="sm" />
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate">{p.name}</p>
                <p className="text-sm text-white/40 capitalize">{p.retailer}</p>
              </div>
              <div className="text-right flex-shrink-0 ml-2">
                <p className="text-lg font-bold text-red-400 font-mono whitespace-nowrap">
                  CHF {p.price?.toFixed(2)}
                </p>
                {p.discount_pct > 0 && (
                  <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">
                    -{p.discount_pct}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export default function DealsPage() {
  return (
    <main className="min-h-screen p-6 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 flex items-center gap-3">
        <IconDeals className="w-8 h-8 text-emerald-400" />
        Weekly Deals
      </h1>
      <ErrorBoundary>
        <DealsContent />
      </ErrorBoundary>
    </main>
  );
}
