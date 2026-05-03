"use client";

import { CheckCircle2, Loader2 } from "lucide-react";

import type { PipelineEvent, RunStatus } from "@/types/battlecard";

const STAGES: Array<{ id: RunStatus; label: string }> = [
  { id: "queued", label: "Queued" },
  { id: "resolving_domain", label: "Finding sources" },
  { id: "crawling", label: "Crawling pages" },
  { id: "extracting", label: "Extracting signals" },
  { id: "generating", label: "Generating battlecard" },
  { id: "rendering", label: "Rendering markdown" },
  { id: "exporting", label: "Exporting PDF" },
  { id: "completed", label: "Completed" },
];

export function ProgressState({ status, events }: { status: RunStatus; events: PipelineEvent[] }) {
  const eventByStage = new Map(events.map((e) => [e.stage, e]));

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/80 p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Pipeline Progress</h3>
      <div className="space-y-2">
        {STAGES.map((stage) => {
          const event = eventByStage.get(stage.id);
          const active = status === stage.id;
          const complete =
            event?.progress === 100 ||
            status === "completed" ||
            STAGES.findIndex((s) => s.id === status) > STAGES.findIndex((s) => s.id === stage.id);

          return (
            <div key={stage.id} className="rounded-lg border border-slate-100 bg-slate-50 p-2">
              <div className="mb-1 flex items-center justify-between text-sm">
                <div className="flex items-center gap-2 font-medium text-slate-800">
                  {complete ? (
                    <CheckCircle2 className="h-4 w-4 text-accent" />
                  ) : active ? (
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  ) : (
                    <span className="h-4 w-4 rounded-full border border-slate-300" />
                  )}
                  <span>{stage.label}</span>
                </div>
                <span className="text-xs text-slate-500">{event?.progress ?? (complete ? 100 : 0)}%</span>
              </div>
              <progress
                className="h-2 w-full overflow-hidden rounded-full [&::-webkit-progress-bar]:rounded-full [&::-webkit-progress-bar]:bg-slate-200 [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-gradient-to-r [&::-webkit-progress-value]:from-blue-500 [&::-webkit-progress-value]:via-sky-500 [&::-webkit-progress-value]:to-emerald-500"
                max={100}
                value={event?.progress ?? (complete ? 100 : 0)}
              />
              {event?.message ? <p className="mt-1 text-xs text-slate-500">{event.message}</p> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
