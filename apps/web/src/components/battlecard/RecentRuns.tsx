"use client";

import { RefreshCw, Trash2 } from "lucide-react";

import type { RecentRun } from "@/lib/api";

export function RecentRuns({
  runs,
  activeRunId,
  onSelect,
  onRefresh,
  onDelete,
}: {
  runs: RecentRun[];
  activeRunId?: string;
  onSelect: (id: string) => void;
  onRefresh: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  function formatUpdatedAt(value: string) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "Updated recently";
    }

    return `Updated ${date.toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    })}`;
  }

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/80 p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Recent Runs</h3>
      <div className="space-y-2">
        {runs.length === 0 ? (
          <p className="text-sm text-slate-500">No runs yet.</p>
        ) : (
          runs.map((run) => {
            const id = run.id;
            const competitor = run.competitor_name || "Unknown";
            const status = run.status || "queued";
            const active = id === activeRunId;
            return (
              <div
                key={id}
                className={`group rounded-lg border p-2 transition ${
                  active ? "border-blue-300 bg-blue-50" : "border-slate-200 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-start gap-2">
                  <button type="button" onClick={() => onSelect(id)} className="min-w-0 flex-1 text-left">
                    <div className="min-w-0 break-words text-sm font-medium text-slate-800">{competitor}</div>
                    <div className="mt-0.5 text-xs uppercase tracking-wide text-slate-500">{status}</div>
                    <div className="mt-1 text-[11px] text-slate-400">{formatUpdatedAt(run.updated_at)}</div>
                  </button>
                  <div className="flex shrink-0 items-center gap-1 opacity-100 transition sm:opacity-0 sm:group-hover:opacity-100">
                    <button
                      type="button"
                      onClick={() => onRefresh(id)}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:text-slate-900"
                      aria-label={`Refresh ${competitor}`}
                      title="Refresh"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(id)}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 transition hover:border-red-300 hover:text-red-600"
                      aria-label={`Delete ${competitor}`}
                      title="Delete"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
