"use client";

import { useEffect, useMemo, useState } from "react";
import { Sparkles } from "lucide-react";

import { BattlecardViewer } from "@/components/battlecard/BattlecardViewer";
import { DownloadPdfButton } from "@/components/battlecard/DownloadPdfButton";
import { ProgressState } from "@/components/battlecard/ProgressState";
import { RecentRuns } from "@/components/battlecard/RecentRuns";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { deleteRun, generateBattlecard, getBattlecard, getRecentRuns, refreshRun } from "@/lib/api";
import type { BattlecardMode, RecentRun } from "@/lib/api";
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
  const [mode, setMode] = useState<BattlecardMode>("live");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<RecentRun | null>(null);

  const isActive = useMemo(() => (run ? ACTIVE_STATUSES.has(run.status) : false), [run]);

  async function refreshRecent() {
    const rows = await getRecentRuns();
    setRecentRuns(rows);
  }

  async function handleDeleteRun(id: string) {
    setError(null);

    try {
      await deleteRun(id);
      if (runId === id) {
        setRunId(null);
        setRun(null);
      }
      await refreshRecent();
    } catch {
      setError("Unable to delete run.");
    }
  }

  function openDeleteDialog(id: string) {
    const target = recentRuns.find((run) => run.id === id) ?? null;
    setDeleteTarget(target);
  }

  async function handleRefreshRun(id: string) {
    setError(null);

    try {
      await refreshRun(id);
      const next = await getBattlecard(id);
      setRunId(id);
      setRun(next);
      await refreshRecent();
    } catch {
      setError("Unable to refresh run.");
    }
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
      const generated = await generateBattlecard(competitor.trim(), mode);
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
          <div className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1">
            <button
              type="button"
              onClick={() => setMode("live")}
              className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${mode === "live" ? "bg-white text-slate-950 shadow-sm" : "text-slate-500"}`}
            >
              Live
            </button>
            <button
              type="button"
              onClick={() => setMode("deep")}
              className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${mode === "deep" ? "bg-white text-slate-950 shadow-sm" : "text-slate-500"}`}
            >
              Deep
            </button>
          </div>
          <Button size="lg" onClick={onGenerate} disabled={loading || isActive}>
            {loading ? "Starting..." : isActive ? "In progress..." : "Generate Battlecard"}
          </Button>
        </div>
        {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
        {run ? (
          <p className="mt-2 text-xs uppercase tracking-wide text-slate-500">
            Run: {run.id} | Mode: {mode} | Status: {run.status}
            {run.confidence_label ? ` | Confidence: ${run.confidence_label}` : ""}
            {run.canonical_domain ? ` | Domain: ${run.canonical_domain}` : ""}
          </p>
        ) : null}
      </section>

      <section className="grid gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
        <div className="space-y-4 opacity-90">
          <ProgressState status={run?.status ?? "queued"} events={run?.events ?? []} />
          <RecentRuns
            runs={recentRuns}
            activeRunId={runId ?? undefined}
            onSelect={(id) => {
              setRunId(id);
              setError(null);
            }}
            onRefresh={handleRefreshRun}
            onDelete={openDeleteDialog}
          />
        </div>

        <BattlecardViewer markdown={run?.markdown} payload={run?.battlecard} events={run?.events} mode={mode} />
      </section>

      <Dialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete recent run?</DialogTitle>
            <DialogDescription>
              This will permanently remove {deleteTarget?.competitor_name ?? "this run"}, including its history and PDF artifact.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              onClick={async () => {
                if (!deleteTarget) {
                  return;
                }
                await handleDeleteRun(deleteTarget.id);
                setDeleteTarget(null);
              }}
            >
              Delete run
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
