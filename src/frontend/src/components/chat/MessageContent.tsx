import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { CitationSpan, SourceCitation } from "../../types/chat";
import { buildCitationMap } from "../../utils/citations";
import { CitationButton } from "./CitationButton";

interface MessageContentProps {
  content: string;
  citationSpans?: CitationSpan[];
  sources?: SourceCitation[];
  onCitationClick: (citationId: string, sources: SourceCitation[]) => void;
}

/**
 * Component that renders message content with citations.
 * Uses structured citationSpans data from backend to render citations as React components.
 * 
 * Strategy: Use react-markdown's components prop to customize paragraph rendering,
 * processing citations inline within paragraphs to keep them inline with text.
 */
export const MessageContent = ({
  content,
  citationSpans,
  sources,
  onCitationClick,
}: MessageContentProps) => {
  // Build citation map for quick lookup
  const citationMap = useMemo(() => buildCitationMap(sources), [sources]);

  // Helper function to process text nodes and replace citations
  const processTextNode = useMemo(() => {
    return (text: string, keyPrefix: string = ""): React.ReactNode => {
      const citationPattern = /\[(\d+)\]/g;
      if (!citationPattern.test(text)) {
        return text;
      }

      const parts: React.ReactNode[] = [];
      let lastIndex = 0;
      let keyCounter = 0;
      citationPattern.lastIndex = 0;

      const matches = Array.from(text.matchAll(citationPattern));
      for (const match of matches) {
        const matchIndex = match.index ?? 0;
        const matchLength = match[0].length;

        // Add text before citation
        if (matchIndex > lastIndex) {
          const textBefore = text.slice(lastIndex, matchIndex);
          if (textBefore) {
            parts.push(
              <React.Fragment key={`${keyPrefix}text-${keyCounter++}`}>{textBefore}</React.Fragment>
            );
          }
        }

        // Add citation button
        const citationId = match[1];
        const citation = citationMap.get(citationId);
        if (citation && sources && sources.length > 0) {
          parts.push(
            <CitationButton
              key={`${keyPrefix}citation-${keyCounter++}-${citationId}`}
              citationIds={[citationId]}
              sources={sources}
              onCitationClick={onCitationClick}
            />
          );
        } else {
          parts.push(
            <React.Fragment key={`${keyPrefix}fallback-${keyCounter++}`}>{match[0]}</React.Fragment>
          );
        }

        lastIndex = matchIndex + matchLength;
      }

      // Add remaining text
      if (lastIndex < text.length) {
        parts.push(
          <React.Fragment key={`${keyPrefix}text-${keyCounter++}`}>
            {text.slice(lastIndex)}
          </React.Fragment>
        );
      }

      return parts.length > 1 ? <>{parts}</> : text;
    };
  }, [citationMap, sources, onCitationClick]);

  // Helper function to process children recursively
  const processChildren = useMemo(() => {
    return (node: any, keyPrefix: string = ""): React.ReactNode => {
      if (typeof node === "string") {
        return processTextNode(node, keyPrefix);
      }
      if (React.isValidElement(node)) {
        // If it's a React element, check if it has string children
        if (node.props?.children) {
          const processed = processChildren(node.props.children, keyPrefix);
          return React.cloneElement(node, { ...node.props, children: processed });
        }
        return node;
      }
      if (Array.isArray(node)) {
        return node.map((child, idx) => (
          <React.Fragment key={`${keyPrefix}child-${idx}`}>{processChildren(child, `${keyPrefix}${idx}-`)}</React.Fragment>
        ));
      }
      return node;
    };
  }, [processTextNode]);

  // Create custom components that process citations inline
  const components = useMemo(() => ({
    // Override paragraph rendering to process citations inline
    p: ({ children, ...props }: any) => {
      const processedChildren = processChildren(children, "p-");
      return <p {...props}>{processedChildren}</p>;
    },
    // Override list item rendering to process citations inline
    li: ({ children, ...props }: any) => {
      const processedChildren = processChildren(children, "li-");
      return <li {...props}>{processedChildren}</li>;
    },
  }), [processChildren]);

  return (
    <div className="prose prose-sm max-w-none text-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
};

