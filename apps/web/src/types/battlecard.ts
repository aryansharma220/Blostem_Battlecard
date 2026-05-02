export type RunStatus =
  | "queued"
  | "resolving_domain"
  | "crawling"
  | "extracting"
  | "generating"
  | "rendering"
  | "exporting"
  | "completed"
  | "failed";

export interface PipelineEvent {
  stage: string;
  message: string;
  progress: number;
  created_at: string;
}

export interface BattlecardRun {
  id: string;
  competitor_name: string;
  canonical_domain?: string | null;
  status: RunStatus;
  error_message?: string | null;
  markdown?: string | null;
  battlecard?: Record<string, unknown>;
  sources: Array<Record<string, unknown>>;
  snippets: Array<Record<string, unknown>>;
  events: PipelineEvent[];
  created_at: string;
  updated_at: string;
}

export interface GenerateResponse {
  run_id: string;
  status: RunStatus;
}
