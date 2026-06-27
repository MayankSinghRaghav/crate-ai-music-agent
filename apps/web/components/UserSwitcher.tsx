"use client";

import type { User } from "@/lib/types";

function initials(displayName: string) {
  return displayName
    .split(" (")[0]
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function personaLabel(displayName: string) {
  const m = displayName.match(/\(([^)]+)\)/);
  return m ? m[1] : "";
}

export function UserSwitcher({
  users,
  selectedId,
  onSelect,
}: {
  users: User[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {users.map((u) => {
        const active = u.id === selectedId;
        return (
          <button
            key={u.id}
            onClick={() => onSelect(u.id)}
            title={u.persona ?? undefined}
            className={`group flex items-center gap-2.5 rounded-full border px-2.5 py-1.5 text-left transition ${
              active
                ? "border-spotify-green bg-spotify-green/10"
                : "border-spotify-border bg-spotify-surface hover:border-spotify-muted"
            }`}
          >
            <span
              className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold ${
                active
                  ? "bg-spotify-green text-black"
                  : "bg-spotify-elevated text-spotify-subtle group-hover:text-white"
              }`}
            >
              {initials(u.display_name)}
            </span>
            <span className="pr-1.5 leading-tight">
              <span className="block text-sm font-medium">
                {u.display_name.split(" (")[0]}
              </span>
              <span className="block text-[11px] text-spotify-muted">
                {personaLabel(u.display_name)}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
