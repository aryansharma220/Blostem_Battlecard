export function formatCitationLabel(index: number): string {
  return `S${index}`;
}

export function safeClaimText(text: string | undefined | null): string {
  const trimmed = (text || "").trim();
  return trimmed.length > 0 ? trimmed : "Not enough public data found.";
}
