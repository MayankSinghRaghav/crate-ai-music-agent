export function Logo({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden>
        <rect width="26" height="26" rx="7" fill="#1DB954" />
        <circle cx="13" cy="13" r="6.5" fill="#0A0A0A" />
        <circle cx="13" cy="13" r="1.7" fill="#1DB954" />
        <path
          d="M6 19.5 L20 19.5"
          stroke="#0A0A0A"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
      <span className="text-lg font-bold tracking-tight">Crate</span>
    </div>
  );
}
