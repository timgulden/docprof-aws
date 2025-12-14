import type { CitationSpan, SourceCitation } from "../types/chat";

/**
 * Represents a part of parsed content - either text or a citation
 */
export type ContentPart =
  | { type: "text"; text: string }
  | { type: "citation"; citationIds: string[]; start: number; end: number };

/**
 * Parses content string with citation spans into an array of parts.
 * Uses structured citationSpans data from backend instead of regex parsing.
 * 
 * @param content - The message content string
 * @param citationSpans - Array of citation spans with character positions
 * @returns Array of content parts (text or citations)
 */
export function parseContentWithCitations(
  content: string,
  citationSpans: CitationSpan[]
): ContentPart[] {
  if (!citationSpans || citationSpans.length === 0) {
    return [{ type: "text", text: content }];
  }

  // Sort spans by start position
  const sortedSpans = [...citationSpans].sort((a, b) => a.start - b.start);

  const parts: ContentPart[] = [];
  let lastIndex = 0;

  for (const span of sortedSpans) {
    // Add text before this citation
    if (span.start > lastIndex) {
      const textBefore = content.slice(lastIndex, span.start);
      if (textBefore) {
        parts.push({ type: "text", text: textBefore });
      }
    }

    // Add citation
    parts.push({
      type: "citation",
      citationIds: span.citationIds,
      start: span.start,
      end: span.end,
    });

    lastIndex = span.end;
  }

  // Add remaining text after last citation
  if (lastIndex < content.length) {
    const remainingText = content.slice(lastIndex);
    if (remainingText) {
      parts.push({ type: "text", text: remainingText });
    }
  }

  return parts;
}

/**
 * Builds a map from citation ID (e.g., "1", "2") to SourceCitation
 * 
 * @param sources - Array of source citations
 * @returns Map of citation ID to SourceCitation
 */
export function buildCitationMap(
  sources?: SourceCitation[]
): Map<string, SourceCitation> {
  const map = new Map<string, SourceCitation>();
  if (!sources) return map;

  for (const source of sources) {
    // citationId might be "[1]" or "1", normalize to just the number
    const normalizedId = source.citationId.replace(/[\[\]]/g, "");
    map.set(normalizedId, source);
    // Also store with brackets for flexibility
    map.set(source.citationId, source);
  }

  return map;
}

/**
 * Gets citation data for opening PDF viewer
 * 
 * @param citationId - The citation ID (e.g., "1" or "[1]")
 * @param sources - Array of source citations
 * @returns Citation data or null if not found
 */
export function getCitationData(
  citationId: string,
  sources?: SourceCitation[]
): { bookId: string; page: number; bookTitle?: string } | null {
  if (!sources) return null;

  const citationMap = buildCitationMap(sources);
  const normalizedId = citationId.replace(/[\[\]]/g, "");
  const citation = citationMap.get(normalizedId) || citationMap.get(citationId);

  if (!citation) return null;

  const targetPage = citation.targetPage ?? citation.pageStart ?? 1;

  return {
    bookId: citation.bookId,
    page: targetPage,
    bookTitle: citation.bookTitle,
  };
}

/**
 * Formats citation tooltip text
 * 
 * @param citation - Source citation
 * @returns Formatted tooltip string
 */
export function formatCitationTooltip(citation: SourceCitation): string {
  const parts: string[] = [citation.bookTitle];
  
  if (citation.chapterTitle) {
    parts.push(` - ${citation.chapterTitle}`);
  }
  
  if (citation.pageStart) {
    parts.push(` (Page ${citation.pageStart})`);
  }
  
  return parts.join("");
}

