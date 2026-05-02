"use client";

import { Check, ChevronDown, Copy, ExternalLink, PhoneCall } from "lucide-react";
import React, { useMemo, useState } from "react";

type SourceItem = {
  url?: string;
  title?: string;
};

type SectionItem = {
  claim?: string;
  citations?: string[];
};

type Summary = {
  key_insight?: string;
  confidence_label?: string;
  confidence_score?: number;
  source_count?: number;
  generated_in_seconds?: number | null;
};

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <button
      type="button"
      onClick={onCopy}
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-900"
      title={copied ? "Copied" : "Copy"}
      aria-label={copied ? "Copied" : "Copy"}
    >
      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
    </button>
  );
}

function citationLabels(item: SectionItem, sourceIndexByUrl: Map<string, number>) {
  return ((item.citations ?? []) as string[])
    .map((url) => ({ url, index: sourceIndexByUrl.get(url) }))
    .filter((entry) => typeof entry.index === "number") as Array<{ url: string; index: number }>;
}

function CitationBadges({
  item,
  sourceIndexByUrl,
  onOpenSource,
}: {
  item: SectionItem;
  sourceIndexByUrl: Map<string, number>;
  onOpenSource: (url: string) => void;
}) {
  const labels = citationLabels(item, sourceIndexByUrl);
  if (!labels.length) {
    return null;
  }

  return (
    <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
      {labels.map(({ url, index }) => (
        <button
          key={url}
          type="button"
          onClick={() => onOpenSource(url)}
          title={url}
          className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-0.5 font-medium text-slate-600 hover:border-slate-300 hover:bg-slate-50"
        >
          S{index}
        </button>
      ))}
    </div>
  );
}

function SummaryBar({
  competitor,
  summary,
  sources,
  liveMode,
  onToggle,
}: {
  competitor: string;
  summary?: Summary;
  sources: SourceItem[];
  liveMode: boolean;
  onToggle: () => void;
}) {
  const generated = summary?.generated_in_seconds ? `${summary.generated_in_seconds}s` : "-";
  const sourceCount = summary?.source_count ?? sources.length;
  const confidence = summary?.confidence_label ?? "Low confidence";

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 xl:flex-row xl:items-center xl:justify-between">
      <div className="grid gap-2 sm:grid-cols-4 xl:flex xl:items-center xl:gap-4">
        <div className="font-medium text-slate-900">{competitor}</div>
        <div><span className="font-medium text-slate-700">Sources</span> {sourceCount}</div>
        <div><span className="font-medium text-slate-700">Confidence</span> {confidence}</div>
        <div><span className="font-medium text-slate-700">Generated</span> {generated}</div>
      </div>
      <button
        type="button"
        onClick={onToggle}
        className={`inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold ${
          liveMode
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : "border-slate-200 bg-white text-slate-700"
        }`}
      >
        <PhoneCall className="h-3.5 w-3.5" />
        Live Call Mode {liveMode ? "ON" : "OFF"}
      </button>
    </div>
  );
}

function KeyInsight({ summary }: { summary?: Summary }) {
  const insight = summary?.key_insight || "Competitive angle is still being assembled from available evidence.";
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-800">Key insight</p>
      <p className="mt-1 text-lg font-semibold leading-7 text-slate-950">{insight}</p>
    </div>
  );
}

function isEmptyClaim(item?: SectionItem) {
  return !item?.claim || item.claim === "Not enough public data found.";
}

function usefulItems(items?: SectionItem[], limit = 3) {
  return (items ?? []).filter((item) => !isEmptyClaim(item)).slice(0, limit);
}

function buildDisplayPayload(payload: any, sources: SourceItem[]) {
  const sections = payload?.sections || {};
  const weaknesses = usefulItems(sections.weaknesses_risks, 3);
  const strengths = usefulItems(sections.strengths, 3);
  const pricing = usefulItems(sections.pricing_posture, 2);
  const talk = usefulItems(sections.sales_talk_track_objection_handling, 3);

  const fallbackHowToBeat = weaknesses.length
    ? weaknesses.map((item) => ({
        claim: `Use this pressure point: ${item.claim}`,
        citations: item.citations ?? [],
      }))
    : strengths.map((item) => ({
        claim: `Position Blostem's speed and support against: ${item.claim}`,
        citations: item.citations ?? [],
      }));

  const fallbackTalkTrack = talk.length
    ? talk
    : (weaknesses.length ? weaknesses : pricing).map((item) => ({
        claim: `"${item.claim}"`,
        citations: item.citations ?? [],
      }));

  const fallbackWin = weaknesses.length
    ? weaknesses.map((item) => ({
        claim: `Teams that care about speed, pricing clarity, support, or flexibility around: ${item.claim}`,
        citations: item.citations ?? [],
      }))
    : strengths.slice(0, 2).map((item) => ({
        claim: `Deals where Blostem can simplify the buyer's path versus: ${item.claim}`,
        citations: item.citations ?? [],
      }));

  const fallbackLose = [
    {
      claim: "Large enterprises already deeply embedded in the competitor ecosystem.",
      citations: [],
    },
  ];

  return {
    summary: payload.summary ?? {
      key_insight:
        weaknesses[0]?.claim ??
        strengths[0]?.claim ??
        "Switch to Deep Research to inspect the available competitor evidence.",
      confidence_label: sources.length >= 8 ? "Medium confidence" : "Low confidence",
      source_count: sources.length,
      generated_in_seconds: null,
    },
    howToBeat: usefulItems(payload.how_to_beat, 4).length ? usefulItems(payload.how_to_beat, 4) : fallbackHowToBeat,
    talkTrack: usefulItems(payload.talk_track, 3).length ? usefulItems(payload.talk_track, 3) : fallbackTalkTrack,
    dealGuidance: payload.deal_guidance ?? {
      when_we_win: fallbackWin.slice(0, 3),
      when_we_lose: fallbackLose,
    },
  };
}

function ActionList({
  title,
  eyebrow,
  items,
  sourceIndexByUrl,
  onOpenSource,
  tone = "slate",
  copyable = false,
  compact = false,
}: {
  title: string;
  eyebrow: string;
  items: SectionItem[];
  sourceIndexByUrl: Map<string, number>;
  onOpenSource: (url: string) => void;
  tone?: "slate" | "rose" | "emerald" | "indigo";
  copyable?: boolean;
  compact?: boolean;
}) {
  const styles = {
    slate: "border-slate-200 bg-white text-slate-700",
    rose: "border-rose-200 bg-rose-50 text-rose-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    indigo: "border-indigo-200 bg-indigo-50 text-indigo-700",
  };
  const safeItems = items.length ? items : [{ claim: "Not enough public data found.", citations: [] }];

  return (
    <section className={`rounded-lg border p-4 ${styles[tone]}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em]">{eyebrow}</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">{title}</h3>
        </div>
        {copyable ? <CopyButton value={safeItems.map((item) => item.claim ?? "").filter(Boolean).join("\n")} /> : null}
      </div>
      <ul className={`${compact ? "mt-2 space-y-2" : "mt-3 space-y-2"} text-sm text-slate-800`}>
        {safeItems.map((item, idx) => (
          <li key={`${title}-${idx}`} className="rounded-lg border border-white/80 bg-white/85 p-3">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1 font-medium leading-5">{item.claim ?? "Not enough public data found."}</div>
              {copyable ? <CopyButton value={item.claim ?? ""} /> : null}
            </div>
            <CitationBadges item={item} sourceIndexByUrl={sourceIndexByUrl} onOpenSource={onOpenSource} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function DealGuidance({
  guidance,
  sourceIndexByUrl,
  onOpenSource,
  compact = false,
}: {
  guidance?: { when_we_win?: SectionItem[]; when_we_lose?: SectionItem[] };
  sourceIndexByUrl: Map<string, number>;
  onOpenSource: (url: string) => void;
  compact?: boolean;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Deal guidance</p>
      <h3 className="mt-1 text-lg font-semibold text-slate-950">When to use this card</h3>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <ActionList title="When we win" eyebrow="Use" items={guidance?.when_we_win ?? []} sourceIndexByUrl={sourceIndexByUrl} onOpenSource={onOpenSource} tone="emerald" compact={compact} />
        <ActionList title="When we lose" eyebrow="Watch" items={guidance?.when_we_lose ?? []} sourceIndexByUrl={sourceIndexByUrl} onOpenSource={onOpenSource} tone="rose" compact={compact} />
      </div>
    </section>
  );
}

const SECTION_STYLES: Record<string, { shell: string; accent: string; eyebrow: string }> = {
  weaknesses_risks: { shell: "border-rose-200 bg-rose-50/80", accent: "text-rose-700", eyebrow: "Risk" },
  strengths: { shell: "border-emerald-200 bg-emerald-50/80", accent: "text-emerald-700", eyebrow: "Win themes" },
  competitor_overview: { shell: "border-sky-200 bg-sky-50/80", accent: "text-sky-700", eyebrow: "Overview" },
  positioning: { shell: "border-cyan-200 bg-cyan-50/80", accent: "text-cyan-700", eyebrow: "Messaging" },
  pricing_posture: { shell: "border-amber-200 bg-amber-50/80", accent: "text-amber-800", eyebrow: "Commercial" },
  recent_launches_announcements: { shell: "border-violet-200 bg-violet-50/80", accent: "text-violet-700", eyebrow: "Momentum" },
  customer_sentiment: { shell: "border-slate-200 bg-slate-50/80", accent: "text-slate-700", eyebrow: "Voice of customer" },
  sales_talk_track_objection_handling: { shell: "border-indigo-200 bg-indigo-50/80", accent: "text-indigo-700", eyebrow: "Objections" },
};

function SectionCard({
  sectionKey,
  title,
  items,
  sourceIndexByUrl,
  onOpenSource,
}: {
  sectionKey: string;
  title: string;
  items: SectionItem[];
  sourceIndexByUrl: Map<string, number>;
  onOpenSource: (url: string) => void;
}) {
  const theme = SECTION_STYLES[sectionKey] || { shell: "border-slate-200 bg-white", accent: "text-slate-700", eyebrow: "Section" };
  const safeItems = items.length ? items : [{ claim: "Not enough public data found.", citations: [] }];

  return (
    <div className={`rounded-lg border p-4 shadow-sm ${theme.shell}`}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${theme.accent}`}>{theme.eyebrow}</p>
          <h4 className="text-sm font-semibold text-slate-800">{title}</h4>
        </div>
        <div className="rounded-full bg-white/80 px-2 py-1 text-[11px] font-medium text-slate-500">{safeItems.length} items</div>
      </div>
      <ul className="space-y-3 text-sm text-slate-700">
        {safeItems.map((item, idx) => (
          <li key={`${sectionKey}-${idx}`} className="rounded-lg border border-white/70 bg-white/80 p-3">
            <div className="flex items-start gap-3">
              <span className={`mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-semibold ${theme.accent}`}>
                {idx + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-medium text-slate-900">{item.claim ?? "Not enough public data found."}</div>
                <CitationBadges item={item} sourceIndexByUrl={sourceIndexByUrl} onOpenSource={onOpenSource} />
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SourcesDrawer({ sources, openSourceUrl }: { sources: SourceItem[]; openSourceUrl?: string | null }) {
  return (
    <details className="rounded-lg border border-slate-200 bg-white">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-slate-800">
        Sources
        <ChevronDown className="h-4 w-4 text-slate-500" />
      </summary>
      <div className="grid gap-2 border-t border-slate-100 p-4 md:grid-cols-2">
        {sources.length === 0 ? (
          <p className="text-sm text-slate-500">Not enough public data found.</p>
        ) : (
          sources.map((source, idx) => {
            const url = String(source.url ?? "");
            const title = String(source.title ?? url);
            const active = openSourceUrl === url;
            return (
              <a
                key={`${url}-${idx}`}
                href={url}
                target="_blank"
                rel="noreferrer"
                className={`rounded-lg border p-3 text-sm hover:bg-slate-50 ${active ? "border-indigo-300 bg-indigo-50" : "border-slate-100"}`}
              >
                <div className="flex items-start justify-between gap-2 font-medium text-slate-800">
                  <span>S{idx + 1} - {title}</span>
                  <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                </div>
                <div className="mt-1 truncate text-xs text-slate-500">{url}</div>
              </a>
            );
          })
        )}
      </div>
    </details>
  );
}

function SourceModal({
  source,
  index,
  onClose,
}: {
  source?: SourceItem;
  index?: number;
  onClose: () => void;
}) {
  if (!source) {
    return null;
  }
  const url = String(source.url ?? "");
  const title = String(source.title ?? url);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-4 shadow-xl" onClick={(event) => event.stopPropagation()}>
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Source S{index}</div>
        <h3 className="mt-1 text-base font-semibold text-slate-950">{title}</h3>
        <p className="mt-2 break-all text-sm text-slate-600">{url}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Close
          </button>
          <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800">
            Open <ExternalLink className="h-4 w-4" />
          </a>
        </div>
      </div>
    </div>
  );
}

export function BattlecardCards({ payload }: { payload?: any; events?: any[] }) {
  const [liveMode, setLiveMode] = useState(true);
  const [openSourceUrl, setOpenSourceUrl] = useState<string | null>(null);
  const sources = (payload?.sources || []) as SourceItem[];
  const sourceIndexByUrl = useMemo(() => {
    const map = new Map<string, number>();
    sources.forEach((source, idx) => {
      if (source?.url) {
        map.set(source.url, idx + 1);
      }
    });
    return map;
  }, [sources]);
  const sourceByUrl = useMemo(() => new Map(sources.map((source, idx) => [String(source.url ?? ""), { source, index: idx + 1 }])), [sources]);
  const activeSource = openSourceUrl ? sourceByUrl.get(openSourceUrl) : undefined;

  if (!payload) {
    return (
      <div className="animate-rise rounded-lg border border-slate-200 bg-white/95 p-6 shadow-panel">
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">Battlecard Output</h3>
        <p className="text-sm text-slate-500">Run in progress. Sections will appear when generation finishes.</p>
      </div>
    );
  }

  const sectionTitles: Record<string, string> = {
    weaknesses_risks: "Weaknesses / risks",
    strengths: "Strengths",
    competitor_overview: "Competitor overview",
    positioning: "Positioning",
    pricing_posture: "Pricing posture",
    recent_launches_announcements: "Recent launches / announcements",
    customer_sentiment: "Customer sentiment",
    sales_talk_track_objection_handling: "Objection handling",
  };

  const sections = payload.sections || {};
  const display = buildDisplayPayload(payload, sources);

  return (
    <div className="space-y-4">
      <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Sales-ready battlecard</p>
            <h2 className="mt-1 text-2xl font-semibold text-slate-950">{payload.competitor_name}</h2>
          </div>
        </div>

        <SummaryBar
          competitor={String(payload.competitor_name ?? "Competitor")}
          summary={display.summary}
          sources={sources}
          liveMode={liveMode}
          onToggle={() => setLiveMode((value) => !value)}
        />

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-4">
            <KeyInsight summary={display.summary} />
            <ActionList title="How to Beat" eyebrow="Positioning weapons" items={display.howToBeat as SectionItem[]} sourceIndexByUrl={sourceIndexByUrl} onOpenSource={setOpenSourceUrl} tone="rose" copyable compact={liveMode} />
            <DealGuidance guidance={display.dealGuidance} sourceIndexByUrl={sourceIndexByUrl} onOpenSource={setOpenSourceUrl} compact={liveMode} />
          </div>
          <div className="xl:sticky xl:top-4 xl:self-start">
            <ActionList title="Talk Track" eyebrow="Use on calls" items={display.talkTrack as SectionItem[]} sourceIndexByUrl={sourceIndexByUrl} onOpenSource={setOpenSourceUrl} tone="indigo" copyable compact={liveMode} />
          </div>
        </div>

        {!liveMode ? (
          <details open className="rounded-lg border border-slate-200 bg-slate-50">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-slate-800">
              Deep research
              <ChevronDown className="h-4 w-4 text-slate-500" />
            </summary>
            <div className="grid gap-4 border-t border-slate-100 p-4 md:grid-cols-2">
              {Object.keys(sectionTitles).map((key) => (
                <SectionCard
                  key={key}
                  sectionKey={key}
                  title={sectionTitles[key]}
                  items={(sections[key] || []) as SectionItem[]}
                  sourceIndexByUrl={sourceIndexByUrl}
                  onOpenSource={setOpenSourceUrl}
                />
              ))}
            </div>
          </details>
        ) : null}

        {!liveMode ? <SourcesDrawer sources={sources} openSourceUrl={openSourceUrl} /> : null}
      </div>
      <SourceModal source={activeSource?.source} index={activeSource?.index} onClose={() => setOpenSourceUrl(null)} />
    </div>
  );
}
