import Link from "next/link";
import {
  IconDeals,
  IconRecipes,
  IconLists,
  IconCompare,
} from "@/components/icons";

const NAV = [
  {
    href: "/deals",
    label: "Deals",
    Icon: IconDeals,
    color: "text-emerald-400",
  },
  {
    href: "/recipes",
    label: "Recipes",
    Icon: IconRecipes,
    color: "text-amber-400",
  },
  { href: "/lists", label: "Lists", Icon: IconLists, color: "text-blue-400" },
  {
    href: "/compare",
    label: "Compare",
    Icon: IconCompare,
    color: "text-red-400",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-12 p-8">
      <div className="text-center">
        <h1 className="text-5xl font-black tracking-tight">
          korb<span className="text-red-500">.guru</span>
        </h1>
        <p className="mt-3 text-lg text-white/50">
          Smart grocery shopping. Better cooking.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 w-full max-w-sm">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="group flex flex-col items-center gap-3 rounded-2xl bg-white/[0.04] border border-white/[0.08] p-6 transition-all hover:bg-white/[0.08] hover:-translate-y-0.5"
          >
            <div className={`${item.color}`}>
              <item.Icon className="w-8 h-8" />
            </div>
            <span className="font-semibold text-white/80">{item.label}</span>
          </Link>
        ))}
      </div>

      <p className="text-sm text-white/20">
        5 Retailers · 102k+ Products · 3.5k Recipes
      </p>
    </main>
  );
}
