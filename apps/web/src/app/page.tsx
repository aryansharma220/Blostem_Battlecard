"use client";

import { useEffect, useMemo, useState } from "react";
import { Sparkles } from "lucide-react";

import { BattlecardViewer } from "@/components/battlecard/BattlecardViewer";
import { DownloadPdfButton } from "@/components/battlecard/DownloadPdfButton";
import { ProgressState } from "@/components/battlecard/ProgressState";
import { RecentRuns } from "@/components/battlecard/RecentRuns";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { generateBattlecard, getBattlecard, getRecentRuns } from "@/lib/api";
import type { BattlecardRun } from "@/types/battlecard";

const ACTIVE_STATUSES = new Set([
  "queued",
  "resolving_domain",
  "crawling",
  "extracting",
  "generating",
  "rendering",
  "exporting",
]);

export default function HomePage() {
  const [competitor, setCompetitor] = useState("");
  const [run, setRun] = useState<BattlecardRun | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [recentRuns, setRecentRuns] = useState<Array<Record<string, unknown>>>([]);

  const isActive = useMemo(() => (run ? ACTIVE_STATUSES.has(run.status) : false), [run]);

  async function refreshRecent() {
    const rows = await getRecentRuns();
    setRecentRuns(rows);
  }

  useEffect(() => {
    void refreshRecent();
  }, []);

  useEffect(() => {
    if (!runId) {
      return;
    }
    let cancelled = false;
    let interval: NodeJS.Timeout | null = null;

    const tick = async () => {
      try {
        const next = await getBattlecard(runId);
        if (cancelled) {
          return;
        }
        setRun(next);
        if (!ACTIVE_STATUSES.has(next.status) && interval) {
          clearInterval(interval);
          interval = null;
          void refreshRecent();
        }
      } catch {
        if (!cancelled) {
          setError("Unable to fetch run status.");
        }
      }
    };

    void tick();
    interval = setInterval(() => {
      void tick();
    }, 1200);

    return () => {
      cancelled = true;
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [runId]);

  async function onGenerate() {
    setError(null);
    if (competitor.trim().length < 2) {
      setError("Please enter a valid competitor name.");
      return;
    }

    setLoading(true);
    try {
      const generated = await generateBattlecard(competitor.trim());
      setRunId(generated.run_id);
    } catch {
      setError("Generation request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-[1400px] px-4 py-8 md:px-8">
      <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="mb-2 inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <Sparkles className="h-3.5 w-3.5" /> Fintech GTM Intelligence
          </p>
          <h1 className="text-3xl font-semibold text-slateink md:text-4xl">Battlecard Generator</h1>
          <p className="mt-2 text-sm text-slate-600">Generate citation-grounded competitive battlecards in under 60 seconds.</p>
        </div>
        <DownloadPdfButton runId={runId ?? undefined} disabled={!run || run.status !== "completed"} />
      </header>

      <section className="mb-6 rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-panel md:p-5">
        <div className="flex flex-col gap-3 md:flex-row">
          <Input
            placeholder="Enter competitor name (example: Razorpay, Stripe, Adyen)"
            value={competitor}
            onChange={(e) => setCompetitor(e.target.value)}
          />
          <Button size="lg" onClick={onGenerate} disabled={loading || isActive}>
            {loading ? "Starting..." : isActive ? "In progress..." : "Generate Battlecard"}
          </Button>
        </div>
        {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
        {run ? (
          <p className="mt-2 text-xs uppercase tracking-wide text-slate-500">
            Run: {run.id} | Status: {run.status}{run.canonical_domain ? ` | Domain: ${run.canonical_domain}` : ""}
          </p>
        ) : null}
      </section>

      <section className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="space-y-6">
          <ProgressState status={run?.status ?? "queued"} events={run?.events ?? []} />
          <RecentRuns
            runs={recentRuns}
            activeRunId={runId ?? undefined}
            onSelect={(id) => {
              setRunId(id);
              setError(null);
            }}
          />
        </div>

        <BattlecardViewer markdown={run?.markdown} payload={run?.battlecard} events={run?.events} />
      </section>
    </main>
  );
}
