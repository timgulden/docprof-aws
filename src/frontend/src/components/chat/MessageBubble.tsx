import type { ChatMessage, SourceCitation } from "../../types/chat";
import { MessageContent } from "./MessageContent";
import { MessageFigures } from "./MessageFigures";
import { MessageAudio } from "./MessageAudio";
import { MessageTimestamp } from "./MessageTimestamp";

interface MessageBubbleProps {
  message: ChatMessage;
  onCitationClick: (citationId: string, sources: SourceCitation[]) => void;
}

/**
 * Component for rendering a single chat message bubble.
 * Handles both user and assistant messages with all their features.
 */
export const MessageBubble = ({ message, onCitationClick }: MessageBubbleProps) => {
  const isUser = message.role === "user";

  return (
    <div className="flex flex-col">
      <div
        className={`max-w-3xl rounded-lg px-4 py-3 shadow-sm ${
          isUser
            ? "ml-auto bg-blue-600 text-white"
            : "mr-auto bg-white text-slate-900"
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap text-sm leading-relaxed">
            {message.content}
          </div>
        ) : (
          <MessageContent
            content={message.content}
            citationSpans={message.citationSpans}
            sources={message.sources}
            onCitationClick={onCitationClick}
          />
        )}

        {message.figures && message.figures.length > 0 && (
          <MessageFigures figures={message.figures} />
        )}

        {message.audioUrl && <MessageAudio audioUrl={message.audioUrl} />}

        <MessageTimestamp timestamp={message.timestamp} role={message.role} />
      </div>
    </div>
  );
};

