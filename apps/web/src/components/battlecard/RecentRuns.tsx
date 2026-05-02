"use client";

export function RecentRuns({
  runs,
  activeRunId,
  onSelect,
}: {
  runs: Array<Record<string, unknown>>;
  activeRunId?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-panel">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Recent Runs</h3>
      <div className="space-y-2">
        {runs.length === 0 ? (
          <p className="text-sm text-slate-500">No runs yet.</p>
        ) : (
          runs.map((run) => {
            const id = String(run.id ?? "");
            const competitor = String(run.competitor_name ?? "Unknown");
            const status = String(run.status ?? "queued");
            const active = id === activeRunId;
            return (
              <button
                key={id}
                onClick={() => onSelect(id)}
                className={`w-full rounded-lg border p-2 text-left transition ${
                  active ? "border-blue-300 bg-blue-50" : "border-slate-200 hover:bg-slate-50"
                }`}
              >
                <div className="text-sm font-medium text-slate-800">{competitor}</div>
                <div className="text-xs uppercase tracking-wide text-slate-500">{status}</div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
