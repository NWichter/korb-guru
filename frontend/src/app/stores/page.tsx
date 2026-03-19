"use client";

import { useEffect, useState, useRef } from "react";
import { IconSearch } from "@/components/icons";

interface Store {
  id: string;
  name: string;
  retailer?: string;
  brand?: string;
  address: string;
  lat?: number;
  lng?: number;
  latitude?: number;
  longitude?: number;
  rating?: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

const RETAILER_COLORS: Record<string, string> = {
  migros: "#ff6600",
  coop: "#e3000f",
  aldi: "#00457c",
  denner: "#ffcc00",
  lidl: "#0050aa",
};

export default function StoresPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);
  const [mapLoaded, setMapLoaded] = useState(false);
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<unknown>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/stores`)
      .then((r) => r.json())
      .then((data) => setStores(Array.isArray(data) ? data : []))
      .catch(() => setStores([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (stores.length === 0 || mapLoaded) return;

    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload = () => {
      if (!mapRef.current || mapInstanceRef.current) return;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const L = (window as any).L;
      const map = L.map(mapRef.current).setView([47.3769, 8.5417], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(map);

      stores.forEach((store) => {
        const storeLat = store.lat ?? store.latitude;
        const storeLng = store.lng ?? store.longitude;
        if (!storeLat || !storeLng) return;
        const retailer = store.retailer ?? store.brand ?? "";
        const color = RETAILER_COLORS[retailer.toLowerCase()] ?? "#888";
        const marker = L.circleMarker([storeLat, storeLng], {
          radius: 8,
          fillColor: color,
          color: "#fff",
          weight: 2,
          opacity: 1,
          fillOpacity: 0.8,
        }).addTo(map);
        marker.bindPopup(
          `<b>${store.name}</b><br/>${retailer}<br/>${store.address ?? ""}${
            store.rating ? `<br/>⭐ ${store.rating}` : ""
          }`,
        );
      });

      mapInstanceRef.current = map;
      setMapLoaded(true);
    };
    document.head.appendChild(script);
  }, [stores, mapLoaded]);

  return (
    <main className="min-h-screen">
      <div className="p-6 max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-4 flex items-center gap-3">
          <IconSearch className="w-8 h-8 text-blue-400" />
          Stores
        </h1>
        <p className="text-white/40 text-sm mb-4">
          {loading
            ? "Loading stores..."
            : `${stores.length} stores in Zurich region`}
        </p>
      </div>

      <div
        ref={mapRef}
        className="w-full h-[60vh] bg-gray-900"
        style={{ minHeight: 400 }}
      />

      {!loading && stores.length > 0 && (
        <div className="p-6 max-w-2xl mx-auto">
          <div className="flex flex-wrap gap-3 mb-4">
            {Object.entries(RETAILER_COLORS).map(([name, color]) => (
              <div
                key={name}
                className="flex items-center gap-2 text-sm text-white/60"
              >
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <span className="capitalize">{name}</span>
              </div>
            ))}
          </div>

          <div className="space-y-2 max-h-60 overflow-y-auto">
            {stores.map((store) => (
              <div
                key={store.id}
                className="flex items-center gap-3 rounded-xl bg-white/[0.04] border border-white/[0.08] p-3"
              >
                <div
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: RETAILER_COLORS[(store.retailer ?? store.brand ?? "").toLowerCase()] ?? "#888" }}
                />
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm truncate">{store.name}</p>
                  <p className="text-xs text-white/40 capitalize truncate">
                    {store.address}
                  </p>
                </div>
                {store.rating && (
                  <span className="text-xs text-amber-400">
                    ⭐ {store.rating}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
