"use client";

import { useEffect, useState } from "react";
import { IconCart } from "@/components/icons";

interface MealPlan {
  id: string;
  date: string;
  meals: { type: string; recipe_name: string }[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function MealsPage() {
  const [plans, setPlans] = useState<MealPlan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/meal-plans`)
      .then((r) => r.json())
      .then((data) => setPlans(Array.isArray(data) ? data : []))
      .catch(() => setPlans([]))
      .finally(() => setLoading(false));
  }, []);

  const generateList = async (planId: string) => {
    try {
      await fetch(
        `${API_BASE}/api/v1/meal-plans/${planId}/generate-grocery-list`,
        {
          method: "POST",
        },
      );
      alert("Grocery list generated!");
    } catch {
      alert("Failed to generate list");
    }
  };

  return (
    <main className="min-h-screen p-6 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 flex items-center gap-3">
        <IconCart className="w-8 h-8 text-violet-400" />
        Meal Plans
      </h1>

      {loading ? (
        <p className="text-white/40">Loading...</p>
      ) : plans.length === 0 ? (
        <div className="text-center text-white/40 mt-12">
          <div className="w-20 h-20 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mx-auto mb-4">
            <IconCart className="w-10 h-10 text-violet-400" />
          </div>
          <p className="font-semibold text-white/60 mb-2">No meal plans yet</p>
          <p className="text-sm">
            Create a weekly plan to auto-generate shopping lists from your
            favorite recipes.
          </p>

          <div className="mt-8 grid grid-cols-7 gap-2">
            {DAYS.map((day) => (
              <div
                key={day}
                className="bg-white/[0.04] border border-white/[0.08] rounded-xl p-3 text-center"
              >
                <p className="text-xs font-semibold text-white/60 mb-2">
                  {day}
                </p>
                <div className="space-y-1">
                  <div className="h-6 rounded bg-white/[0.04] border border-dashed border-white/[0.08]" />
                  <div className="h-6 rounded bg-white/[0.04] border border-dashed border-white/[0.08]" />
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs text-white/20 mt-4">
            Swipe recipes you like, then build your week here.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className="bg-white/[0.04] border border-white/[0.08] rounded-xl p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <p className="font-semibold">{plan.date}</p>
                <button
                  onClick={() => generateList(plan.id)}
                  className="text-xs bg-red-600/20 text-red-400 px-3 py-1 rounded-full hover:bg-red-600/30 transition"
                >
                  Generate list
                </button>
              </div>
              <div className="space-y-1">
                {plan.meals?.map((meal, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-sm text-white/60"
                  >
                    <span className="text-xs text-white/30 w-16 capitalize">
                      {meal.type}
                    </span>
                    <span>{meal.recipe_name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
