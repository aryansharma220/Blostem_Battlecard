"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BattlecardCards } from "./BattlecardCards";

export function BattlecardViewer({ markdown, payload, events, mode }: { markdown?: string | null; payload?: any; events?: any[]; mode?: "live" | "deep" }) {
  // Prefer structured payload when available
  if (payload) {
    return <BattlecardCards payload={payload} events={events} initialMode={mode ?? (payload?.summary?.mode === "deep" ? "deep" : "live")} />;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white/95 p-6 shadow-panel animate-rise">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">Battlecard Output</h3>
      {markdown ? (
        <article className="prose prose-slate max-w-none prose-headings:font-semibold prose-li:my-1">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
        </article>
      ) : (
        <p className="text-sm text-slate-500">Run in progress. Sections will appear when generation finishes.</p>
      )}
    </div>
  );
}
