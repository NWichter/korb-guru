"use client";

import { useEffect, useState } from "react";
import { IconLists, IconCart } from "@/components/icons";
import { SkeletonList } from "@/components/skeleton";
import { ErrorBoundary } from "@/components/error-boundary";

interface GroceryItem {
  id: string;
  ingredient_name: string;
  quantity: string | null;
  category: string;
  is_checked: boolean;
}

interface GroceryList {
  id: string;
  name: string;
  estimated_total: string;
  items: GroceryItem[];
}

const CATEGORY_ICONS: Record<string, string> = {
  dairy: "🧀",
  meat: "🥩",
  vegetables: "🥬",
  fruits: "🍎",
  bakery: "🍞",
  pasta: "🍝",
  pantry: "🫙",
  drinks: "🥤",
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

function ListsContent() {
  const [lists, setLists] = useState<GroceryList[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/grocery/lists`)
      .then((r) => r.json())
      .then((data) => setLists(Array.isArray(data) ? data : []))
      .catch(() => setLists([]))
      .finally(() => setLoading(false));
  }, []);

  const toggleItem = async (itemId: string) => {
    // Optimistic update
    setLists((prev) =>
      prev.map((list) => ({
        ...list,
        items: list.items.map((item) =>
          item.id === itemId ? { ...item, is_checked: !item.is_checked } : item,
        ),
      })),
    );
    // Find current state
    const item = lists.flatMap((l) => l.items).find((i) => i.id === itemId);
    if (!item) return;
    try {
      await fetch(`${API_BASE}/api/v1/grocery/items/${itemId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_checked: !item.is_checked }),
      });
    } catch {
      // Revert on error
      setLists((prev) =>
        prev.map((list) => ({
          ...list,
          items: list.items.map((i) =>
            i.id === itemId ? { ...i, is_checked: item.is_checked } : i,
          ),
        })),
      );
    }
  };

  if (loading) return <SkeletonList count={4} />;

  if (lists.length === 0) {
    return (
      <div className="text-center text-white/40 mt-12">
        <div className="w-20 h-20 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mx-auto mb-4">
          <IconCart className="w-10 h-10 text-blue-400" />
        </div>
        <p className="font-semibold text-white/60 mb-2">
          No shopping lists yet
        </p>
        <p className="text-sm">
          Create a list from a meal plan or add products manually.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {lists.map((list) => {
        const checked = list.items?.filter((i) => i.is_checked).length ?? 0;
        const total = list.items?.length ?? 0;
        const progress = total > 0 ? (checked / total) * 100 : 0;

        // Group items by category
        const grouped: Record<string, GroceryItem[]> = {};
        for (const item of list.items ?? []) {
          const cat = item.category || "Other";
          if (!grouped[cat]) grouped[cat] = [];
          grouped[cat].push(item);
        }

        return (
          <div
            key={list.id}
            className="rounded-2xl bg-white/[0.03] border border-white/[0.08] overflow-hidden"
          >
            {/* List header */}
            <div className="px-5 pt-5 pb-3">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-bold">{list.name}</h2>
                <span className="text-xs text-white/40 bg-white/[0.06] px-2.5 py-1 rounded-full">
                  {checked}/{total}
                </span>
              </div>
              {/* Progress bar */}
              <div className="w-full h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-red-500 to-red-400 rounded-full transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {/* Items grouped by category */}
            <div className="px-5 pb-4 space-y-4">
              {Object.entries(grouped).map(([category, items]) => (
                <div key={category}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">
                      {CATEGORY_ICONS[category.toLowerCase()] ?? "📦"}
                    </span>
                    <span className="text-xs font-semibold text-white/40 uppercase tracking-wider">
                      {category}
                    </span>
                  </div>
                  <div className="space-y-1">
                    {items.map((item) => (
                      <div
                        key={item.id}
                        onClick={() => toggleItem(item.id)}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all cursor-pointer ${
                          item.is_checked
                            ? "bg-white/[0.02]"
                            : "bg-white/[0.04] hover:bg-white/[0.06]"
                        }`}
                      >
                        <div
                          className={`w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                            item.is_checked
                              ? "bg-red-500 border-red-500"
                              : "border-white/20 hover:border-white/40"
                          }`}
                        >
                          {item.is_checked && (
                            <svg
                              className="w-3 h-3 text-white"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="3"
                              viewBox="0 0 24 24"
                            >
                              <path
                                d="M5 13l4 4L19 7"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                          )}
                        </div>
                        <span
                          className={`flex-1 text-sm transition-all ${
                            item.is_checked
                              ? "line-through text-white/25"
                              : "text-white/80"
                          }`}
                        >
                          {item.ingredient_name}
                        </span>
                        {item.quantity && (
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${
                              item.is_checked
                                ? "text-white/15 bg-white/[0.02]"
                                : "text-white/40 bg-white/[0.06]"
                            }`}
                          >
                            {item.quantity}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function ListsPage() {
  return (
    <main className="min-h-screen p-6 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 flex items-center gap-3">
        <IconLists className="w-8 h-8 text-blue-400" />
        Shopping Lists
      </h1>
      <ErrorBoundary>
        <ListsContent />
      </ErrorBoundary>
    </main>
  );
}
