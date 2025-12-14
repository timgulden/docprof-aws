import type { FigureAttachment } from "../../types/chat";
import { API_URL } from "../../api/client";

interface MessageFiguresProps {
  figures: FigureAttachment[];
}

/**
 * Component for displaying figure attachments in a message.
 */
export const MessageFigures = ({ figures }: MessageFiguresProps) => {
  if (!figures || figures.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 space-y-2">
      {figures.map((figure) => {
        // Convert relative URLs to absolute using API_URL (handles tunnel URLs)
        let imageUrl = figure.imageUrl;
        if (imageUrl.startsWith("/api/")) {
          // Replace /api with the full API_URL (which includes /api)
          imageUrl = `${API_URL}${imageUrl.substring(4)}`; // Remove "/api" prefix
        }
        
        return (
          <figure key={figure.figureId} className="rounded-md border bg-white">
            <img
              src={imageUrl}
              alt={figure.caption}
              className="h-auto w-full rounded-t-md object-cover"
            />
          <figcaption className="px-3 py-2 text-xs text-slate-600">
            <strong>{figure.caption}</strong>
            {figure.source ? (
              <span className="ml-2 text-[11px] text-slate-500">{figure.source}</span>
            ) : null}
          </figcaption>
        </figure>
        );
      })}
    </div>
  );
};

