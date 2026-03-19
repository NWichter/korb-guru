"use client";

import { useEffect, useState, useCallback } from "react";
import { IconRecipes, IconHeart, IconX } from "@/components/icons";
import { SkeletonSwipeCard, SkeletonList } from "@/components/skeleton";
import { ErrorBoundary } from "@/components/error-boundary";

interface Recipe {
  id: string;
  name?: string;
  title?: string;
  type: string;
  cost: string;
  time_minutes: number;
  image_url?: string | null;
}

const TYPE_EMOJIS: Record<string, string> = {
  protein: "🥩",
  veggie: "🥗",
  carb: "🍚",
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

function RecipesContent() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [recommended, setRecommended] = useState<Recipe[]>([]);
  const [current, setCurrent] = useState(0);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [swipeCount, setSwipeCount] = useState(0);
  const [mode, setMode] = useState<"discover" | "search">("discover");

  const loadDiscover = useCallback(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/v1/recipes/discover?limit=20`)
      .then((r) => r.json())
      .then((data) => {
        const items = data.recipes ?? data ?? [];
        if (items.length > 0) {
          setRecipes(items);
          setCurrent(0);
          return;
        }
        // Fallback to plain list if discover returns empty
        return fetch(`${API_BASE}/api/v1/recipes?limit=20`)
          .then((r) => r.json())
          .then((data) => {
            setRecipes(data.recipes ?? data ?? []);
            setCurrent(0);
          });
      })
      .catch(() => {
        fetch(`${API_BASE}/api/v1/recipes?limit=20`)
          .then((r) => r.json())
          .then((data) => {
            setRecipes(data.recipes ?? data ?? []);
            setCurrent(0);
          })
          .catch(() => setRecipes([]));
      })
      .finally(() => setLoading(false));
  }, []);

  const loadRecommendations = useCallback(() => {
    fetch(`${API_BASE}/api/v1/recipes/recommendations?limit=5`)
      .then((r) => r.json())
      .then((data) => setRecommended(data.recipes ?? data ?? []))
      .catch(() => setRecommended([]));
  }, []);

  const search = (q: string) => {
    setLoading(true);
    setMode("search");
    const params = new URLSearchParams({ limit: "20" });
    if (q) params.set("q", q);
    fetch(`${API_BASE}/api/v1/recipes/search?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setRecipes(data.recipes ?? data ?? []);
        setCurrent(0);
      })
      .catch(() => setRecipes([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDiscover();
    loadRecommendations();
  }, [loadDiscover, loadRecommendations]);

  const swipe = async (recipeId: string, action: "like" | "dislike") => {
    try {
      await fetch(`${API_BASE}/api/v1/recipes/${recipeId}/swipe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
    } catch {
      /* ignore */
    }
    const newCount = swipeCount + 1;
    setSwipeCount(newCount);
    setCurrent((c) => c + 1);
    // Refresh recommendations every 3 swipes
    if (newCount % 3 === 0) loadRecommendations();
  };

  const recipe = recipes[current];

  return (
    <>
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => {
            setMode("discover");
            loadDiscover();
          }}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
            mode === "discover"
              ? "bg-red-600 text-white shadow-lg shadow-red-600/25"
              : "bg-white/[0.04] border border-white/[0.08] text-white/60"
          }`}
        >
          Discover
        </button>
        <button
          onClick={() => setMode("search")}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
            mode === "search"
              ? "bg-red-600 text-white shadow-lg shadow-red-600/25"
              : "bg-white/[0.04] border border-white/[0.08] text-white/60"
          }`}
        >
          Search
        </button>
      </div>

      {mode === "search" && (
        <input
          type="text"
          placeholder="Search recipes..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search(query)}
          className="w-full mb-4 px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08] focus:border-red-500 focus:outline-none transition"
        />
      )}

      {loading ? (
        <SkeletonSwipeCard />
      ) : !recipe ? (
        <div className="text-center text-white/40 mt-8">
          <p className="mb-2">No more recipes to discover.</p>
          <button
            onClick={loadDiscover}
            className="text-red-400 hover:text-red-300 text-sm"
          >
            Load more
          </button>
        </div>
      ) : (
        <div className="bg-white/[0.04] border border-white/[0.08] rounded-2xl overflow-hidden text-center transition-all">
          {recipe.image_url ? (
            <div className="h-44 overflow-hidden">
              <img
                src={recipe.image_url}
                alt={recipe.title ?? recipe.name ?? ""}
                className="w-full h-full object-cover"
              />
            </div>
          ) : (
            <div className="h-32 bg-gradient-to-br from-white/[0.06] to-white/[0.02] flex items-center justify-center">
              <span className="text-6xl">{TYPE_EMOJIS[recipe.type] ?? "🍽️"}</span>
            </div>
          )}
          <div className="p-6">
          <h2 className="text-2xl font-bold mb-2">{recipe.title ?? recipe.name}</h2>
          <div className="flex justify-center gap-3 text-sm text-white/40 mb-6">
            <span className="px-2.5 py-1 rounded-full bg-white/[0.06] capitalize">{TYPE_EMOJIS[recipe.type] ?? "🍽️"} {recipe.type}</span>
            <span className="px-2.5 py-1 rounded-full bg-white/[0.06]">⏱️ {recipe.time_minutes} min</span>
            <span className="px-2.5 py-1 rounded-full bg-white/[0.06]">💰 CHF {recipe.cost}</span>
          </div>
          <div className="flex gap-4 justify-center">
            <button
              onClick={() => swipe(recipe.id, "dislike")}
              className="w-16 h-16 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center hover:bg-red-500/20 transition"
            >
              <IconX className="w-7 h-7" />
            </button>
            <button
              onClick={() => swipe(recipe.id, "like")}
              className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center hover:bg-emerald-500/20 transition"
            >
              <IconHeart className="w-7 h-7" />
            </button>
          </div>
          <p className="mt-4 text-xs text-white/20">
            {current + 1} / {recipes.length} · {swipeCount} swipes total
          </p>
          </div>
        </div>
      )}

      {/* Recommendations section */}
      {recommended.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm font-semibold text-white/60 mb-3">
            Recommended for you
          </h3>
          <div className="space-y-2">
            {recommended.map((r) => (
              <div
                key={r.id}
                className="flex items-center justify-between rounded-xl bg-white/[0.04] border border-white/[0.08] p-3 hover:bg-white/[0.06] transition"
              >
                <div>
                  <p className="font-semibold text-sm">{r.title ?? r.name}</p>
                  <p className="text-xs text-white/30 capitalize">
                    {r.type} · {r.time_minutes} min
                  </p>
                </div>
                <span className="text-xs text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">
                  Match
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

export default function RecipesPage() {
  return (
    <main className="min-h-screen p-6 max-w-md mx-auto">
      <h1 className="text-3xl font-bold mb-6 flex items-center gap-3">
        <IconRecipes className="w-8 h-8 text-amber-400" />
        Recipes
      </h1>
      <ErrorBoundary>
        <RecipesContent />
      </ErrorBoundary>
    </main>
  );
}
