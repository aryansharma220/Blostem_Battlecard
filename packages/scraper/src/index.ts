export interface ScrapedPage {
  url: string;
  title: string;
  text: string;
  domain: string;
}

export function normalizeWhitespace(input: string): string {
  return input.replace(/\s+/g, " ").trim();
}
