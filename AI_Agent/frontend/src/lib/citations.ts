import type { SourceItem } from "../types";

const NUMERIC_CITATION_RE = /(?<!\[)\[(\d+)\](?!\()/g;
const CODE_FENCE_RE = /```[\s\S]*?```/g;
const MATH_SEGMENT_RE = /\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|(?<!\\)\$[^$\n]+?(?<!\\)\$|\\\([^\n]+?\\\)/g;

function normalizeLikelyLatexArtifacts(mathText: string): string {
  return mathText
    .replace(
      /(\\(?:mathrm|mathbf|mathit|operatorname)\s*\{[^{}]+\})\s*\{\s*(\\text\s*\{[^{}]+\})\s*\}/g,
      "$1_{$2}",
    )
    .replace(/\\operatorname\s*\{\s*M\s*i\s*n\s*\}/g, "\\min")
    .replace(/\\operatorname\s*\{\s*M\s*a\s*x\s*\}/g, "\\max")
    .replace(/\\operatorname\s*\{\s*S\s*u\s*m\s*\}/g, "\\sum")
    .replace(/\\left\s*\{/g, "\\left\\{");
}

function extractMathSegments(markdown: string): { markdown: string; segments: string[] } {
  const segments: string[] = [];
  let output = "";
  let cursor = 0;

  for (const match of markdown.matchAll(CODE_FENCE_RE)) {
    const codeStart = match.index ?? 0;
    const codeText = match[0];

    output += markdown.slice(cursor, codeStart).replace(MATH_SEGMENT_RE, (mathMatch) => {
      const token = `@@MATH_SEGMENT_${segments.length}@@`;
      segments.push(normalizeLikelyLatexArtifacts(mathMatch));
      return token;
    });
    output += codeText;
    cursor = codeStart + codeText.length;
  }

  output += markdown.slice(cursor).replace(MATH_SEGMENT_RE, (mathMatch) => {
    const token = `@@MATH_SEGMENT_${segments.length}@@`;
    segments.push(normalizeLikelyLatexArtifacts(mathMatch));
    return token;
  });

  return { markdown: output, segments };
}

function restoreMathSegments(markdown: string, segments: string[]): string {
  return markdown.replace(/@@MATH_SEGMENT_(\d+)@@/g, (match, rawIndex: string) => {
    const segment = segments[Number(rawIndex)];
    return segment ?? match;
  });
}

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

export function prepareMarkdownForRendering(markdown: string, sources: SourceItem[]): string {
  if (!markdown.trim()) {
    return markdown;
  }

  const extracted = extractMathSegments(markdown);
  const withLinkedCitations = linkifyNumericCitations(extracted.markdown, sources);
  return restoreMathSegments(withLinkedCitations, extracted.segments);
}

export function buildSourceHeading(source: SourceItem): string {
  if (source.source_kind === "section" && source.section_heading) {
    return `${source.path} | ${source.section_heading}`;
  }
  return source.path;
}
