"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  IconDeals,
  IconRecipes,
  IconLists,
  IconCompare,
  IconCart,
  IconSearch,
  IconChat,
} from "./icons";

const NAV_ITEMS = [
  { href: "/deals", label: "Deals", Icon: IconDeals },
  { href: "/recipes", label: "Recipes", Icon: IconRecipes },
  { href: "/chat", label: "Chat", Icon: IconChat },
  { href: "/lists", label: "Lists", Icon: IconLists },
  { href: "/compare", label: "Compare", Icon: IconCompare },
  { href: "/stores", label: "Stores", Icon: IconSearch },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-white/[0.06] bg-gray-950/90 backdrop-blur-xl">
      <div className="max-w-2xl mx-auto flex justify-around py-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-0.5 px-3 py-1.5 transition ${
                active ? "text-red-500" : "text-white/30 hover:text-white/60"
              }`}
            >
              <item.Icon className="w-5 h-5" />
              <span className="text-[10px] font-semibold">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export function TopBar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-gray-950/90 backdrop-blur-xl">
      <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-red-600 flex items-center justify-center">
            <IconCart className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-bold text-sm tracking-tight">
            korb<span className="text-red-500">.guru</span>
          </span>
        </Link>
        <Link
          href="/chat"
          className="text-xs bg-red-600/20 text-red-400 px-3 py-1.5 rounded-full hover:bg-red-600/30 transition font-semibold"
        >
          Ask AI
        </Link>
      </div>
    </header>
  );
}
