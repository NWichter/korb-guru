export function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl bg-white/[0.04] border border-white/[0.06] p-4">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-4 w-32 rounded bg-white/[0.08]" />
          <div className="h-3 w-20 rounded bg-white/[0.06]" />
        </div>
        <div className="h-5 w-16 rounded bg-white/[0.08]" />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function SkeletonSwipeCard() {
  return (
    <div className="animate-pulse rounded-2xl bg-white/[0.04] border border-white/[0.08] p-6 text-center">
      <div className="h-7 w-48 rounded bg-white/[0.08] mx-auto mb-4" />
      <div className="flex justify-center gap-4 mb-6">
        <div className="h-4 w-16 rounded bg-white/[0.06]" />
        <div className="h-4 w-16 rounded bg-white/[0.06]" />
        <div className="h-4 w-16 rounded bg-white/[0.06]" />
      </div>
      <div className="flex gap-4 justify-center">
        <div className="w-16 h-16 rounded-full bg-white/[0.06]" />
        <div className="w-16 h-16 rounded-full bg-white/[0.06]" />
      </div>
    </div>
  );
}
