import { useEffect, useMemo, useRef } from "react";

import { useChatStore } from "../../store/chatStore";
import { PDFViewer } from "../pdf/PDFViewer";
import { PDFViewerEmpty } from "../pdf/PDFViewerEmpty";
import { MessageBubble } from "./MessageBubble";
import { MessageInput } from "./MessageInput";
import { usePdfViewer } from "../../hooks/usePdfViewer";
import { sortMessagesByTimestamp } from "../../utils/sorting";
import type { SourceCitation } from "../../types/chat";

export const ChatInterface = () => {
  const state = useChatStore((store) => store.state);
  const dispatch = useChatStore((store) => store.dispatch);
  const endRef = useRef<HTMLDivElement | null>(null);
  
  // PDF viewer state management via custom hook
  const pdfViewer = usePdfViewer();

  const isSending = state.status === "awaiting_response";
  
  // Handle citation click - opens PDF viewer
  const handleCitationClick = (citationId: string, sources: SourceCitation[]) => {
    pdfViewer.openPdfFromCitation(citationId, sources);
  };

  // Sort messages by timestamp
  const sortedMessages = useMemo(() => {
    return sortMessagesByTimestamp(state.messages);
  }, [state.messages]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [sortedMessages.length]);

  // Handle message submission
  const handleMessageSubmit = async (text: string) => {
    await dispatch({
      type: "user_submitted_message",
      text,
      withAudio: false,
    });
  };

  return (
    <div className="relative flex h-full">
      <div className="flex-1 flex flex-col w-1/2 border-r border-slate-300">
        <main className="flex-1 space-y-4 overflow-y-auto bg-slate-50 px-4 py-6">
          {sortedMessages.length === 0 && (
            <div className="flex h-full items-center justify-center text-slate-500">
              Let's start the conversation.
            </div>
          )}

          {sortedMessages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onCitationClick={handleCitationClick}
            />
          ))}
          <div ref={endRef} />
        </main>

        <MessageInput 
          onSubmit={handleMessageSubmit} 
          isSending={isSending}
        />

        {state.error ? (
          <div className="border-t bg-white px-4 py-2">
            <div className="text-sm text-red-600">Error: {state.error.message}</div>
          </div>
        ) : null}
      </div>

      {/* PDF Viewer - always visible */}
      <div className="flex-1 w-1/2 bg-white">
        {pdfViewer.isOpen && pdfViewer.bookId ? (
          <PDFViewer
            bookId={pdfViewer.bookId}
            initialPage={pdfViewer.page}
            bookTitle={pdfViewer.bookTitle}
            onClose={pdfViewer.closePdf}
          />
        ) : (
          <PDFViewerEmpty />
        )}
      </div>
    </div>
  );
};

