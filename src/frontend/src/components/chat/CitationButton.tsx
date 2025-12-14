import { useState } from "react";
import type { SourceCitation } from "../../types/chat";
import { buildCitationMap, formatCitationTooltip } from "../../utils/citations";

interface CitationButtonProps {
  citationIds: string[];
  sources?: SourceCitation[];
  onCitationClick: (citationId: string, sources: SourceCitation[]) => void;
}

/**
 * Button component for displaying citations in message content.
 * Shows citation ID(s) with hover tooltip and click handler.
 */
export const CitationButton = ({
  citationIds,
  sources,
  onCitationClick,
}: CitationButtonProps) => {
  const [isHovered, setIsHovered] = useState(false);

  if (!sources || sources.length === 0) {
    // Fallback: just show the citation ID if no sources
    return (
      <span className="mx-0.5 inline-flex items-center rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-800">
        [{citationIds.join(", ")}]
      </span>
    );
  }

  const citationMap = buildCitationMap(sources);
  
  // Get the first citation for tooltip (if multiple, show first)
  const firstCitationId = citationIds[0]?.replace(/[\[\]]/g, "") || citationIds[0];
  const citation = citationMap.get(firstCitationId) || citationMap.get(citationIds[0] || "");

  const tooltipText = citation ? formatCitationTooltip(citation) : `Citation ${citationIds.join(", ")}`;
  const displayText = `[${citationIds.join(", ")}]`;

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (sources) {
      // Use the first citation ID for the click handler
      onCitationClick(citationIds[0] || "", sources);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="mx-0.5 inline-flex items-center rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-800 hover:bg-blue-200 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer relative group"
      title={tooltipText}
    >
      {displayText}
      {isHovered && (
        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 text-xs text-white bg-slate-900 rounded shadow-lg whitespace-nowrap pointer-events-none z-50">
          {tooltipText}
        </div>
      )}
    </button>
  );
};

