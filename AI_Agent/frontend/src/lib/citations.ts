import type { SourceItem } from "../types";

const NUMERIC_CITATION_RE = /(?<!\[)\[(\d+)\](?!\()/g;

export function linkifyNumericCitations(markdown: string, sources: SourceItem[]): string {
  if (!markdown.trim() || sources.length === 0) {
    return markdown;
  }

  const sourceMap = new Map(sources.map((source) => [String(source.index), source.url]));

  return markdown.replace(NUMERIC_CITATION_RE, (match, rawIndex: string) => {
    const target = sourceMap.get(rawIndex);
    if (!target) {
      return match;
    }
    return `[${rawIndex}](${target})`;
  });
}

export function buildSourceHeading(source: SourceItem): string {
  if (source.source_kind === "section" && source.section_heading) {
    return `${source.path} | ${source.section_heading}`;
  }
  return source.path;
}
