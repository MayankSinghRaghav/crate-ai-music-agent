import Link from "next/link";

/**
 * App logo — the official Spotify glyph next to the "Spotify" wordmark.
 * Rendered as a link so clicking it always returns to the landing page ("/"),
 * i.e. Today's Dig, from wherever the user currently is.
 */
export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link
      href="/"
      aria-label="Spotify — go to home"
      className={`group flex items-center gap-2 rounded-full outline-none transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-spotify-green focus-visible:ring-offset-2 focus-visible:ring-offset-spotify-black ${className}`}
    >
      <svg
        viewBox="0 0 24 24"
        role="img"
        aria-hidden
        className="h-7 w-7 shrink-0 transition-transform duration-200 group-hover:scale-110 group-active:scale-95"
      >
        <path
          fill="#1DB954"
          d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.18-.899-.54-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.021-.12-1.141-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.18-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.42 1.56-.301.421-1.02.599-1.561.3z"
        />
      </svg>
      <span className="text-lg font-bold tracking-tight">Spotify</span>
    </Link>
  );
}
