import type { BattlecardRun, GenerateResponse } from "@/types/battlecard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function generateBattlecard(competitorName: string): Promise<GenerateResponse> {
  const res = await fetch(`${API_BASE}/api/battlecard/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ competitor_name: competitorName }),
  });
  if (!res.ok) {
    throw new Error("Failed to start generation");
  }
  return res.json();
}

export async function getBattlecard(runId: string): Promise<BattlecardRun> {
  const res = await fetch(`${API_BASE}/api/battlecard/${runId}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error("Failed to fetch run");
  }
  return res.json();
}

export function getPdfUrl(runId: string): string {
  return `${API_BASE}/api/battlecard/${runId}/pdf`;
}

export async function getRecentRuns(): Promise<Array<Record<string, unknown>>> {
  const res = await fetch(`${API_BASE}/api/battlecard/recent/list`, { cache: "no-store" });
  if (!res.ok) {
    return [];
  }
  const data = await res.json();
  return (data.runs as Array<Record<string, unknown>>) || [];
}
