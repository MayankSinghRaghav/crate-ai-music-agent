"use client";

export function ComfortDial({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  const pct = Math.round(value * 100);
  const mode =
    value <= 0.33 ? "Comfort" : value >= 0.66 ? "Curiosity" : "Balanced";

  return (
    <div className="rounded-xl border border-spotify-border bg-spotify-surface p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <span className="text-sm font-medium text-spotify-subtle">
          Comfort <span className="text-spotify-muted">↔</span> Curiosity
        </span>
        <span className="text-sm font-semibold text-spotify-green">{mode}</span>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="crate-dial w-full"
        style={{ ["--fill" as string]: `${pct}%` }}
        aria-label="Comfort to Curiosity dial"
      />
      <div className="mt-2 flex justify-between text-[11px] text-spotify-muted">
        <span>more of what you love</span>
        <span>a real stretch</span>
      </div>
    </div>
  );
}
