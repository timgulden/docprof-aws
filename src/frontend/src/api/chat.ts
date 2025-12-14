import type { BackendChatPayload, AssistantMessagePayload, FigureAttachment, SourceCitation } from "../types/chat";
import type { BackendChatResponse } from "../types/api";
import { apiClient } from "./client";

interface RawCitationSpan {
  start: number;
  end: number;
  citation_ids: string[];
}

interface RawGeneralKnowledgeSpan {
  start: number;
  end: number;
}

interface RawAssistantMessage {
  message_id?: string;
  content: string;
  figures?: RawFigureAttachment[];
  sources?: RawSourceCitation[];
  audio_url?: string;
  timestamp?: string;
  citation_spans?: RawCitationSpan[];
  general_spans?: RawGeneralKnowledgeSpan[];
}

interface RawFigureAttachment {
  figure_id: string;
  image_url: string;
  caption: string;
  source?: string;
}

interface RawSourceCitation {
  citation_id: string;
  chunk_id: string;
  chunk_type: "chapter" | "2page" | "figure";
  book_id: string;
  book_title: string;
  chapter_number?: number;
  chapter_title?: string;
  page_start?: number;
  page_end?: number;
  target_page?: number;  // Page to jump to in PDF (center page for 2-page chunks)
  content: string;
  score?: number;
}

interface RawBackendResponse {
  session_id?: string;
  messages?: RawAssistantMessage[];
  ui_message?: string;
}

export const sendChatMessage = async (payload: BackendChatPayload): Promise<BackendChatResponse> => {
  const response = await apiClient.post<RawBackendResponse>("/chat/message", {
    message: payload.message,
    with_audio: payload.withAudio,
    session_id: payload.sessionId,
    context: payload.context,
    book_ids: payload.bookIds,
    ephemeral: payload.ephemeral,
    section_id: payload.sectionId,
    chunk_index: payload.chunkIndex,
  });

  const raw = response.data;
  return {
    sessionId: raw.session_id,
    uiMessage: raw.ui_message,
    messages: (raw.messages ?? []).map(normalizeAssistantMessage),
  };
};

/**
 * Stream chat message response using Server-Sent Events (SSE).
 * Calls the onChunk callback for each text chunk received.
 */
export const streamChatMessage = async (
  payload: BackendChatPayload,
  onChunk: (chunk: string) => void,
  onComplete: (fullResponse: BackendChatResponse) => void,
  onError: (error: Error) => void,
  abortSignal?: AbortSignal,
  onAudioChunk?: (audioBase64: string) => void
): Promise<void> => {
  try {
    const token = localStorage.getItem('auth_token');
    // Use API_URL from client.ts which uses VITE_API_GATEWAY_URL
    const API_URL = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8000/api';
    
    // Use fetch with streaming for SSE
    const response = await fetch(`${API_URL}/chat/message-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        message: payload.message,
        with_audio: payload.withAudio,
        session_id: payload.sessionId,
        context: payload.context,
        book_ids: payload.bookIds,
        ephemeral: payload.ephemeral,
        section_id: payload.sectionId,
        chunk_index: payload.chunkIndex,
      }),
      signal: abortSignal,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is not readable');
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let fullContent = '';
    let sessionId: string | undefined;
    let uiMessage: string | undefined;
    let sources: RawSourceCitation[] = [];
    let figures: RawFigureAttachment[] = [];

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim() === '') continue; // Skip empty lines
        
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          
          if (data === '[DONE]') {
            // Stream complete - return full response
            const fullResponse: BackendChatResponse = {
              sessionId: sessionId,
              uiMessage: uiMessage,
              messages: [{
                messageId: undefined,
                content: fullContent,
                audioUrl: undefined,
                timestamp: new Date().toISOString(),
                figures: figures.map(normalizeFigure),
                sources: sources.map(normalizeSource),
                citationSpans: [],
                generalSpans: [],
              }],
            };
            onComplete(fullResponse);
            return;
          }

          try {
            const parsed = JSON.parse(data);
            
            if (parsed.type === 'chunk') {
              // Text chunk - append and call callback
              const chunkContent = parsed.content || '';
              fullContent += chunkContent;
              onChunk(chunkContent);
            } else if (parsed.type === 'audio_chunk') {
              // Audio chunk - decode and call audio callback if provided
              console.log('Received audio_chunk event, has callback:', !!onAudioChunk, 'has audio:', !!parsed.audio);
              if (onAudioChunk && parsed.audio) {
                console.log('Calling onAudioChunk with audio data, length:', parsed.audio.length);
                onAudioChunk(parsed.audio);
              } else {
                console.warn('Audio chunk received but callback missing or no audio data', {
                  hasCallback: !!onAudioChunk,
                  hasAudio: !!parsed.audio
                });
              }
            } else if (parsed.type === 'metadata') {
              // Metadata (session_id, ui_message, etc.)
              if (parsed.session_id) sessionId = parsed.session_id;
              if (parsed.ui_message) uiMessage = parsed.ui_message;
            } else if (parsed.type === 'sources') {
              // Sources received
              sources = parsed.sources || [];
            } else if (parsed.type === 'figures') {
              // Figures received
              figures = parsed.figures || [];
            } else if (parsed.type === 'error') {
              // Error received
              onError(new Error(parsed.message || 'Unknown error'));
              return;
            }
          } catch (e) {
            // Ignore JSON parse errors for non-JSON lines
            console.warn('Failed to parse SSE data:', e, data);
          }
        }
      }
    }

    // If we get here without [DONE], return what we have
    const fullResponse: BackendChatResponse = {
      sessionId: sessionId,
      uiMessage: uiMessage,
      messages: [{
        messageId: undefined,
        content: fullContent,
        audioUrl: undefined,
        timestamp: new Date().toISOString(),
        figures: figures.map(normalizeFigure),
        sources: sources.map(normalizeSource),
        citationSpans: [],
        generalSpans: [],
      }],
    };
    onComplete(fullResponse);
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      // Aborted - don't call onError
      return;
    }
    onError(error instanceof Error ? error : new Error('Unknown error'));
  }
};

const normalizeAssistantMessage = (message: RawAssistantMessage): AssistantMessagePayload => {
  // Backend returns timestamp - Pydantic serializes datetime.utcnow() as ISO string
  // Ensure it's parsed as UTC and converted to ISO string with 'Z' suffix
  let timestamp: string;
  if (message.timestamp) {
    // Parse the timestamp - Pydantic may serialize naive datetime without timezone
    // JavaScript's Date() interprets strings without timezone as LOCAL time, not UTC!
    // So we need to explicitly add 'Z' if there's no timezone indicator
    let dateStr = String(message.timestamp).trim();
    
    // Check if it has a timezone indicator (Z, +, or - after the date part)
    // Patterns: "2024-01-01T12:00:00Z", "2024-01-01T12:00:00+00:00", "2024-01-01T12:00:00+0000"
    const hasZ = dateStr.endsWith('Z');
    const hasOffsetColon = /[+-]\d{2}:\d{2}$/.test(dateStr);
    const hasOffsetNoColon = /[+-]\d{4}$/.test(dateStr);
    const hasTimezone = hasZ || hasOffsetColon || hasOffsetNoColon;
    
    if (!hasTimezone) {
      // No timezone info - this is a naive datetime from backend (datetime.utcnow())
      // JavaScript's Date() interprets strings without timezone as LOCAL time, not UTC!
      // We MUST add 'Z' to force UTC interpretation
      dateStr = dateStr + 'Z';
    }
    
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) {
      console.warn("[normalizeAssistantMessage] Invalid timestamp:", message.timestamp, "parsed as:", dateStr);
      timestamp = new Date().toISOString(); // Fallback to current time
    } else {
      // Always convert to ISO string with 'Z' suffix to ensure UTC
      timestamp = date.toISOString();
    }
  } else {
    timestamp = new Date().toISOString(); // Fallback to current time
  }
  
  return {
    messageId: message.message_id,
    content: message.content,
    audioUrl: message.audio_url,
    timestamp,
    figures: (message.figures ?? []).map(normalizeFigure),
    sources: (message.sources ?? []).map(normalizeSource),
    citationSpans: (message.citation_spans ?? []).map(span => ({
      start: span.start,
      end: span.end,
      citationIds: span.citation_ids,
    })),
    generalSpans: (message.general_spans ?? []).map(span => ({
      start: span.start,
      end: span.end,
    })),
  };
};

const normalizeFigure = (figure: RawFigureAttachment): FigureAttachment => ({
  figureId: figure.figure_id,
  imageUrl: figure.image_url,
  caption: figure.caption,
  source: figure.source,
});

const normalizeSource = (source: RawSourceCitation): SourceCitation => ({
  citationId: source.citation_id,
  chunkId: source.chunk_id,
  chunkType: source.chunk_type,
  bookId: source.book_id,
  bookTitle: source.book_title,
  chapterNumber: source.chapter_number,
  chapterTitle: source.chapter_title,
  pageStart: source.page_start,
  pageEnd: source.page_end,
  targetPage: source.target_page,  // Center page for 2-page chunks, page_start for others
  content: source.content,
  score: source.score,
});

/**
 * Generate audio for existing text (e.g., for old Q&A answers).
 * Returns a blob URL that can be used with an HTMLAudioElement.
 */
export const generateAudioForText = async (text: string): Promise<string> => {
  try {
    const response = await apiClient.post<{ audio: string; format: string; length_bytes: number }>(
      "/chat/generate-audio",
      { text }
    );
    
    // Decode base64 audio data
    const audioBase64 = response.data.audio;
    const audioBytes = Uint8Array.from(atob(audioBase64), c => c.charCodeAt(0));
    const audioBlob = new Blob([audioBytes], { type: "audio/mpeg" });
    
    // Create blob URL
    const audioUrl = URL.createObjectURL(audioBlob);
    return audioUrl;
  } catch (error) {
    console.error("Failed to generate audio for text:", error);
    throw error;
  }
};

