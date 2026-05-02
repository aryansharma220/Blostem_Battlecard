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

export interface CitationSource {
  url: string;
  title: string;
  sourceType: "official" | "external";
  score: number;
}

export interface BattlecardClaim {
  claim: string;
  citations: string[];
}

export interface BattlecardPayload {
  competitor_name: string;
  sections: Record<string, BattlecardClaim[]>;
  sources: Array<{ url: string; title: string }>;
  grounding: string;
}
