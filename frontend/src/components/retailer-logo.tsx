const RETAILERS: Record<string, { bg: string; text: string; label: string }> = {
  migros: { bg: "bg-[#ff6600]", text: "text-white", label: "M" },
  coop: { bg: "bg-[#e3000f]", text: "text-white", label: "C" },
  aldi: { bg: "bg-[#00457c]", text: "text-white", label: "A" },
  denner: { bg: "bg-[#ffcc00]", text: "text-[#333]", label: "D" },
  lidl: { bg: "bg-[#0050aa]", text: "text-[#fff200]", label: "L" },
};

export function RetailerLogo({
  retailer,
  size = "md",
}: {
  retailer: string;
  size?: "sm" | "md" | "lg";
}) {
  const key = retailer.toLowerCase();
  const info = RETAILERS[key] ?? {
    bg: "bg-white/10",
    text: "text-white/60",
    label: retailer.charAt(0).toUpperCase(),
  };
  const sizeClass =
    size === "sm"
      ? "w-6 h-6 text-[10px]"
      : size === "lg"
        ? "w-10 h-10 text-base"
        : "w-8 h-8 text-xs";

  return (
    <div
      className={`${info.bg} ${sizeClass} rounded-full flex items-center justify-center flex-shrink-0 mr-1`}
    >
      <span className={`${info.text} font-bold leading-none`}>
        {info.label}
      </span>
    </div>
  );
}

export function RetailerName({ retailer }: { retailer: string }) {
  const colors: Record<string, string> = {
    migros: "text-[#ff6600]",
    coop: "text-[#e3000f]",
    aldi: "text-[#00457c]",
    denner: "text-[#ffcc00]",
    lidl: "text-[#0050aa]",
  };
  return (
    <span
      className={`font-bold uppercase text-xs tracking-wider ${colors[retailer.toLowerCase()] ?? "text-white/50"}`}
    >
      {retailer}
    </span>
  );
}
