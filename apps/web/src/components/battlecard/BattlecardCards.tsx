"use client";

import { Check, ChevronDown, Copy, ExternalLink, PhoneCall } from "lucide-react";
import React, { useMemo, useState } from "react";

type SourceItem = {
  url?: string;
  title?: string;
  snippet?: string;
  excerpt?: string;
  summary?: string;
};

type SectionItem = {
  claim?: string;
  citations?: string[];
};

type Summary = {
  key_insight?: string;
  confidence_label?: string;
  confidence_score?: number;
  confidence_explanation?: string;
  source_count?: number;
  generated_in_seconds?: number | null;
};

type ObjectionItem = {
  objection?: string;
  response?: string;
  citations?: string[];
};

type SourceLookup = Map<string, { source: SourceItem; index: number }>;

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

function trimSentence(value: string, maxWords = 8) {
  const words = value.replace(/\s+/g, " ").trim().split(" ").filter(Boolean);
  if (words.length <= maxWords) {
    return words.join(" ");
  }
  return `${words.slice(0, maxWords).join(" ")}...`;
}

function tightenInsight(insight: string) {
  const normalized = insight.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return { lead: "Competitive angle is still assembling", tail: "" };
  }

  const firstSplit = normalized.split(/[.?!]/)[0] ?? normalized;
  const concise = trimSentence(firstSplit, 14);
  const marker = concise.match(/( but | however | while | yet )/i);

  if (!marker || marker.index === undefined) {
    return { lead: concise, tail: "" };
  }

  const lead = concise.slice(0, marker.index).trim();
  const tail = concise.slice(marker.index).trim();
  return { lead, tail };
}

function CitationBadges({
  item,
  sourceIndexByUrl,
  sourceByUrl,
  onOpenSource,
}: {
  item: SectionItem;
  sourceIndexByUrl: Map<string, number>;
  sourceByUrl: SourceLookup;
  onOpenSource: (url: string) => void;
}) {
  const labels = citationLabels(item, sourceIndexByUrl);
  if (!labels.length) {
    return null;
  }

  return (
    <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
      {labels.map(({ url, index }) => {
        const linked = sourceByUrl.get(url)?.source;
        const hoverDetail = String(linked?.snippet ?? linked?.excerpt ?? linked?.summary ?? linked?.title ?? url);
        return (
          <div key={url} className="group relative">
            <button
              type="button"
              onClick={() => onOpenSource(url)}
              className="inline-flex items-center rounded-full border border-slate-300 bg-white px-2 py-0.5 font-semibold text-slate-700 hover:border-slate-400 hover:bg-slate-50"
              aria-label={`Open source ${index}`}
            >
              [S{index}]
            </button>
            <div className="pointer-events-none absolute left-0 top-full z-20 mt-1 hidden w-72 rounded-md border border-slate-200 bg-white p-2 text-[11px] text-slate-700 shadow-lg group-hover:block">
              <div className="font-semibold text-slate-900">S{index} · {String(sourceByUrl.get(url)?.source.title ?? "Source")}</div>
              <div className="mt-1 line-clamp-3 text-slate-600">{trimSentence(hoverDetail, 24)}</div>
            </div>
          </div>
        );
      })}
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
  const confidenceTitle = summary?.confidence_explanation ?? `Based on ${sourceCount} sources and available signal agreement.`;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-[13px] text-slate-700 xl:flex-row xl:items-center xl:justify-between">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-slate-950">{competitor}</span>
        <span className="text-slate-300">|</span>
        <span>{sourceCount} sources</span>
        <span className="text-slate-300">|</span>
        <span title={confidenceTitle}>{confidence}</span>
        <span className="text-slate-300">|</span>
        <span>Generated in {generated}</span>
      </div>
      <button
        type="button"
        onClick={onToggle}
        className={`inline-flex items-center justify-center gap-2 rounded-full border px-3 py-2 text-[12px] font-semibold tracking-wide ${
          liveMode
            ? "border-emerald-500 bg-emerald-100 text-emerald-800 shadow-sm"
            : "border-slate-200 bg-white text-slate-700"
        }`}
      >
        <PhoneCall className="h-3.5 w-3.5" />
        Live Mode {liveMode ? "ON" : "OFF"}
      </button>
    </div>
  );
}

function KeyInsight({ summary }: { summary?: Summary }) {
  const insight = summary?.key_insight || "Competitive angle is still being assembled from available evidence.";
  const compact = tightenInsight(insight);
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-900">Key insight</p>
      <p className="mt-1 truncate text-[21px] font-medium leading-8 text-slate-950" title={insight}>
        <strong>{compact.lead}</strong>
        {compact.tail ? <span className="font-medium"> {compact.tail}</span> : null}
      </p>
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
        claim: `Attack this pain point: ${item.claim}`,
        citations: item.citations ?? [],
      }))
    : strengths.map((item) => ({
        claim: `Do not mirror their breadth; sell Blostem speed against: ${item.claim}`,
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
      claim: "Deeply integrated users with high switching costs.",
      citations: [],
    },
    {
      claim: "Large enterprises already deeply embedded in the competitor ecosystem.",
      citations: [],
    },
    {
      claim: "Teams already optimized around the competitor's tooling.",
      citations: [],
    },
  ];

  const fallbackObjections = [
    {
      objection: `${payload.competitor_name ?? "The competitor"} feels safer.`,
      response: "Safe can become slow; Blostem wins when speed, support, and flexibility matter.",
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
      confidence_explanation: `Based on ${sources.length} sources and available agreement across extracted signals.`,
      source_count: sources.length,
      generated_in_seconds: null,
    },
    howToBeat: usefulItems(payload.how_to_beat, 4).length ? usefulItems(payload.how_to_beat, 4) : fallbackHowToBeat,
    talkTrack: usefulItems(payload.talk_track, 3).length ? usefulItems(payload.talk_track, 3) : fallbackTalkTrack,
    objectionHandling: (payload.objection_handling ?? fallbackObjections) as ObjectionItem[],
    dealGuidance: payload.deal_guidance ?? {
      when_we_win: fallbackWin.slice(0, 3),
      when_we_lose: fallbackLose,
    },
  };
}

function ObjectionHandling({
  items,
  sourceIndexByUrl,
  sourceByUrl,
  onOpenSource,
  compact = false,
}: {
  items: ObjectionItem[];
  sourceIndexByUrl: Map<string, number>;
  sourceByUrl: SourceLookup;
  onOpenSource: (url: string) => void;
  compact?: boolean;
}) {
  const safeItems = items.length ? items : [{ objection: "The competitor feels safer.", response: "Safe can become slow; Blostem wins on speed and support.", citations: [] }];
  return (
    <section className="rounded-lg border border-fuchsia-300 bg-fuchsia-50 p-5 text-fuchsia-800">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="inline-flex items-center gap-1 rounded-full border border-fuchsia-300 bg-white/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.2em] text-fuchsia-900">
            OBJECTION FLIP
          </p>
          <h3 className="mt-2 text-xl font-semibold text-slate-950">Objection Handling</h3>
        </div>
        <CopyButton value={safeItems.map((item) => `${item.objection}\n${item.response}`).join("\n\n")} />
      </div>
      <ul className={`${compact ? "mt-3 space-y-2.5" : "mt-4 space-y-3"} text-[15px] text-slate-800`}>
        {safeItems.map((item, idx) => (
          <li key={`objection-${idx}`} className="rounded-lg border border-white/80 bg-white/90 p-3.5">
            <div className="font-semibold text-slate-900">Objection: {item.objection ?? "Objection unavailable."}</div>
            <div className="mt-1 font-medium leading-6 text-fuchsia-900">{"->"} Flip: {item.response ?? "Response unavailable."}</div>
            <CitationBadges item={{ claim: item.response, citations: item.citations }} sourceIndexByUrl={sourceIndexByUrl} sourceByUrl={sourceByUrl} onOpenSource={onOpenSource} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function ActionList({
  title,
  eyebrow,
  items,
  sourceIndexByUrl,
  sourceByUrl,
  onOpenSource,
  tone = "slate",
  copyable = false,
  compact = false,
  cardClassName,
  listClassName,
  topLabel,
  copyAllLabel,
  allowItemCopy = true,
}: {
  title: string;
  eyebrow: string;
  items: SectionItem[];
  sourceIndexByUrl: Map<string, number>;
  sourceByUrl: SourceLookup;
  onOpenSource: (url: string) => void;
  tone?: "slate" | "rose" | "emerald" | "indigo";
  copyable?: boolean;
  compact?: boolean;
  cardClassName?: string;
  listClassName?: string;
  topLabel?: string;
  copyAllLabel?: string;
  allowItemCopy?: boolean;
}) {
  const styles = {
    slate: "border-slate-200 bg-white text-slate-700",
    rose: "border-rose-300 bg-rose-100/70 text-rose-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    indigo: "border-indigo-400 bg-indigo-100/70 text-indigo-900",
  };
  const safeItems = items.length ? items : [{ claim: "Not enough public data found.", citations: [] }];

  return (
    <section className={`rounded-lg border p-5 ${styles[tone]} ${cardClassName ?? ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          {topLabel ? <p className="mb-2 inline-flex rounded-full border border-white/70 bg-white/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-800">{topLabel}</p> : null}
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em]">{eyebrow}</p>
          <h3 className="mt-1 text-xl font-semibold text-slate-950">{title}</h3>
        </div>
        {copyable ? (
          <button
            type="button"
            onClick={async () => {
              await navigator.clipboard.writeText(safeItems.map((item) => item.claim ?? "").filter(Boolean).join("\n"));
            }}
            className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-[12px] font-semibold text-slate-800 hover:bg-slate-50"
          >
            <Copy className="h-3.5 w-3.5" /> {copyAllLabel ?? "Copy all"}
          </button>
        ) : null}
      </div>
      <ul className={`${compact ? "mt-3 space-y-2.5" : "mt-4 space-y-3"} text-[15px] text-slate-800 ${listClassName ?? ""}`}>
        {safeItems.map((item, idx) => (
          <li key={`${title}-${idx}`} className="rounded-lg border border-white/80 bg-white/85 p-3.5">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1 font-semibold leading-6">{item.claim ?? "Not enough public data found."}</div>
              {copyable && allowItemCopy ? <CopyButton value={item.claim ?? ""} /> : null}
            </div>
            <CitationBadges item={item} sourceIndexByUrl={sourceIndexByUrl} sourceByUrl={sourceByUrl} onOpenSource={onOpenSource} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function DealGuidance({
  guidance,
  sourceIndexByUrl,
  sourceByUrl,
  onOpenSource,
  compact = false,
}: {
  guidance?: { when_we_win?: SectionItem[]; when_we_lose?: SectionItem[] };
  sourceIndexByUrl: Map<string, number>;
  sourceByUrl: SourceLookup;
  onOpenSource: (url: string) => void;
  compact?: boolean;
}) {
  const wins = (guidance?.when_we_win ?? []).map((item) => ({ ...item, claim: trimSentence(String(item.claim ?? ""), 8) }));
  const losses = (guidance?.when_we_lose ?? []).map((item) => ({ ...item, claim: trimSentence(String(item.claim ?? ""), 8) }));

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Deal guidance</p>
      <h3 className="mt-1 text-xl font-semibold text-slate-950">When to use this card</h3>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <ActionList title="WE WIN WHEN" eyebrow="WIN" items={wins} sourceIndexByUrl={sourceIndexByUrl} sourceByUrl={sourceByUrl} onOpenSource={onOpenSource} tone="emerald" compact={compact} />
        <ActionList title="WE LOSE WHEN" eyebrow="LOSE" items={losses} sourceIndexByUrl={sourceIndexByUrl} sourceByUrl={sourceByUrl} onOpenSource={onOpenSource} tone="rose" compact={compact} />
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
  sourceByUrl,
  onOpenSource,
}: {
  sectionKey: string;
  title: string;
  items: SectionItem[];
  sourceIndexByUrl: Map<string, number>;
  sourceByUrl: SourceLookup;
  onOpenSource: (url: string) => void;
}) {
  const theme = SECTION_STYLES[sectionKey] || { shell: "border-slate-200 bg-white", accent: "text-slate-700", eyebrow: "Section" };
  const filteredItems = usefulItems(items, 3);
  const safeItems = filteredItems.length ? filteredItems : [{ claim: "Not enough public data found.", citations: [] }];

  return (
    <div className={`rounded-lg border p-4 shadow-sm ${theme.shell}`}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${theme.accent}`}>{theme.eyebrow}</p>
          <h4 className="text-sm font-semibold text-slate-800">{title}</h4>
        </div>
        <div className="rounded-full bg-white/80 px-2 py-1 text-[11px] font-medium text-slate-500">{safeItems.length} items</div>
      </div>
      <ul className="space-y-3 text-[14px] text-slate-700">
        {safeItems.map((item, idx) => (
          <li key={`${sectionKey}-${idx}`} className="rounded-lg border border-white/70 bg-white/80 p-3">
            <div className="flex items-start gap-3">
              <span className={`mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-semibold ${theme.accent}`}>
                {idx + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-semibold leading-6 text-slate-900">{item.claim ?? "Not enough public data found."}</div>
                <CitationBadges item={item} sourceIndexByUrl={sourceIndexByUrl} sourceByUrl={sourceByUrl} onOpenSource={onOpenSource} />
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DeepResearchAccordion({
  sections,
  sectionTitles,
  sourceIndexByUrl,
  sourceByUrl,
  onOpenSource,
}: {
  sections: Record<string, SectionItem[]>;
  sectionTitles: Record<string, string>;
  sourceIndexByUrl: Map<string, number>;
  sourceByUrl: SourceLookup;
  onOpenSource: (url: string) => void;
}) {
  const order = [
    "weaknesses_risks",
    "strengths",
    "pricing_posture",
    "customer_sentiment",
    "sales_talk_track_objection_handling",
  ];

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="px-1">
        <h3 className="text-sm font-semibold text-slate-900">Deep research</h3>
      </div>
      {order.map((key) => {
        const items = usefulItems((sections[key] || []) as SectionItem[], 3);
        if (!items.length) {
          return null;
        }
        const sectionName = sectionTitles[key] ?? key;
        const summary = `${items.length} key ${key.includes("weakness") ? "risks" : "signals"}`;

        return (
          <details key={key} className="rounded-lg border border-slate-200 bg-white" open={key === "weaknesses_risks"}>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-slate-800">
              <span>{sectionName}</span>
              <span className="text-xs font-medium text-slate-500">{summary}</span>
            </summary>
            <div className="border-t border-slate-100 p-3">
              <SectionCard
                sectionKey={key}
                title={sectionName}
                items={items}
                sourceIndexByUrl={sourceIndexByUrl}
                sourceByUrl={sourceByUrl}
                onOpenSource={onOpenSource}
              />
            </div>
          </details>
        );
      })}
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
      <div className="space-y-6 rounded-lg border border-slate-300 bg-white p-6 shadow-panel">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Sales-ready battlecard</p>
            <h2 className="mt-1 text-3xl font-semibold text-slate-950">{payload.competitor_name}</h2>
          </div>
        </div>

        <SummaryBar
          competitor={String(payload.competitor_name ?? "Competitor")}
          summary={display.summary}
          sources={sources}
          liveMode={liveMode}
          onToggle={() => setLiveMode((value) => !value)}
        />

        <div className="space-y-6">
          <div className="space-y-3">
            <KeyInsight summary={display.summary} />
          </div>

          <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
            <div className="grid gap-5 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
              <ActionList
                title="How to Beat"
                eyebrow="Positioning weapons"
                topLabel="PRIMARY LEVER"
                items={display.howToBeat as SectionItem[]}
                sourceIndexByUrl={sourceIndexByUrl}
                sourceByUrl={sourceByUrl}
                onOpenSource={setOpenSourceUrl}
                tone="rose"
                copyable
                compact={liveMode}
                cardClassName="border-2"
              />
              <div className="xl:sticky xl:top-4 xl:self-start">
                <ActionList
                  title="Talk Track"
                  eyebrow="Use this in call"
                  items={display.talkTrack as SectionItem[]}
                  sourceIndexByUrl={sourceIndexByUrl}
                  sourceByUrl={sourceByUrl}
                  onOpenSource={setOpenSourceUrl}
                  tone="indigo"
                  copyable
                  copyAllLabel="Copy ALL Talk Track"
                  allowItemCopy={false}
                  compact={liveMode}
                  cardClassName="border-2 shadow-md"
                  listClassName="text-[15px]"
                />
              </div>
            </div>
          </div>

          <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-4">
            <ObjectionHandling
              items={display.objectionHandling as ObjectionItem[]}
              sourceIndexByUrl={sourceIndexByUrl}
              sourceByUrl={sourceByUrl}
              onOpenSource={setOpenSourceUrl}
              compact={liveMode}
            />
            <DealGuidance guidance={display.dealGuidance} sourceIndexByUrl={sourceIndexByUrl} sourceByUrl={sourceByUrl} onOpenSource={setOpenSourceUrl} compact={liveMode} />
          </div>
        </div>

        {!liveMode ? (
          <DeepResearchAccordion
            sections={sections}
            sectionTitles={sectionTitles}
            sourceIndexByUrl={sourceIndexByUrl}
            sourceByUrl={sourceByUrl}
            onOpenSource={setOpenSourceUrl}
          />
        ) : null}

        {!liveMode ? <SourcesDrawer sources={sources} openSourceUrl={openSourceUrl} /> : null}
      </div>
      <SourceModal source={activeSource?.source} index={activeSource?.index} onClose={() => setOpenSourceUrl(null)} />
    </div>
  );
}
