"use client";

// Next.js App Router error boundary — catches any render/runtime error below
// the root layout and offers a reset instead of a white screen.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <p className="text-sm text-spotify-subtle">
        {error.message || "An unexpected error occurred."}
      </p>
      <button
        onClick={reset}
        className="rounded-full bg-spotify-green px-4 py-2 text-sm font-semibold text-black transition hover:bg-spotify-greenDark"
      >
        Try again
      </button>
    </main>
  );
}
