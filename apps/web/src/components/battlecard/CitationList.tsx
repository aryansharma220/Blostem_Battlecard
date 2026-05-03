"use client";

export function CitationList({ sources }: { sources: Array<Record<string, unknown>> }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-panel">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Sources</h3>
      <div className="space-y-2">
        {sources.length === 0 ? (
          <p className="text-sm text-slate-500">Not enough public data found.</p>
        ) : (
          sources.map((source, idx) => {
            const url = String(source.url ?? "");
            const title = String(source.title ?? url);
            return (
              <a
                key={`${url}-${idx}`}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="block rounded-lg border border-slate-100 p-2 text-sm hover:bg-slate-50"
              >
                <div className="font-medium text-slate-800">S{idx + 1} - {title}</div>
                <div className="mt-1 break-all text-xs text-slate-500">{url}</div>
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500">
                  {source.source_type ? <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-600">{String(source.source_type)}</span> : null}
                  {source.published_at ? <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-600">{String(source.published_at)}</span> : null}
                  {typeof source.score === "number" ? <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-600">score {Number(source.score).toFixed(2)}</span> : null}
                </div>
              </a>
            );
          })
        )}
      </div>
    </div>
  );
}
