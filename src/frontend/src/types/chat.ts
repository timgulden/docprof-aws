export type ChatStatus = "idle" | "awaiting_response" | "restoring";

export interface FigureAttachment {
  figureId: string;
  imageUrl: string;
  caption: string;
  source?: string;
}

export interface ChatError {
  message: string;
  code?: string;
  retryable?: boolean;
  details?: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  figures: FigureAttachment[];
  audioUrl?: string;
  sources?: SourceCitation[];
  citationSpans?: CitationSpan[];
  generalSpans?: GeneralKnowledgeSpan[];
}

export type SessionType = "chat" | "lecture" | "quiz" | "case_study";

export interface ChatState {
  sessionId?: string;
  sessionName?: string;
  sessionType?: SessionType;
  sessionContext?: string;
  createdAt?: string;
  updatedAt?: string;
  messages: ChatMessage[];
  status: ChatStatus;
  error?: ChatError;
  uiMessage?: string | null;
}

export interface ChatStateSnapshot {
  sessionId?: string;
  sessionName?: string;
  sessionType?: SessionType;
  sessionContext?: string;
  createdAt?: string;
  updatedAt?: string;
  messages: ChatMessage[];
}

export interface SessionMetadata {
  sessionId: string;
  sessionName?: string;
  sessionType: SessionType;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  lastMessagePreview?: string | null;
}

export interface BackendChatPayload {
  message: string;
  withAudio?: boolean;
  sessionId?: string;
  context?: string;  // Optional context override (e.g., for lecture Q&A)
  bookIds?: string[];  // Optional list of selected book IDs to filter search
  ephemeral?: boolean;  // If true, don't create or persist session (e.g., for lecture Q&A)
  sectionId?: string;  // Course section ID for lecture Q&A
  chunkIndex?: number;  // Chunk/paragraph index in the lecture
}

export interface SourceCitation {
  citationId: string; // e.g., "[1]", "[2]"
  chunkId: string;
  chunkType: "chapter" | "2page" | "figure";
  bookId: string;
  bookTitle: string;
  chapterNumber?: number;
  chapterTitle?: string;
  pageStart?: number;
  pageEnd?: number;
  targetPage?: number;  // Page to jump to in PDF viewer (center page for 2-page chunks)
  content: string; // The actual text used
  score?: number; // Similarity score
}

export interface CitationSpan {
  start: number;  // Character position start
  end: number;    // Character position end
  citationIds: string[];  // List of citation IDs like ["1", "2"]
}

export interface GeneralKnowledgeSpan {
  start: number;  // Character position start
  end: number;    // Character position end
}

export interface AssistantMessagePayload {
  messageId?: string;
  content: string;
  figures?: FigureAttachment[];
  audioUrl?: string;
  timestamp?: string;
  sources?: SourceCitation[]; // Source citations for this message
  citationSpans?: CitationSpan[]; // Spans of cited text
  generalSpans?: GeneralKnowledgeSpan[]; // Spans of general knowledge
}

export type ChatEvent =
  | { type: "user_submitted_message"; text: string; withAudio?: boolean }
  | { type: "backend_message_received"; sessionId?: string; messages: AssistantMessagePayload[]; uiMessage?: string }
  | { type: "backend_failed"; sessionId?: string; error: ChatError }
  | { type: "session_restored"; snapshot: ChatStateSnapshot }
  | { type: "session_switched"; sessionId: string; snapshot?: ChatStateSnapshot }
  | { type: "session_created"; sessionMetadata: SessionMetadata }
  | { type: "reset_requested" };

export type ChatCommand =
  | { type: "send_chat_message"; payload: BackendChatPayload }
  | { type: "show_error_toast"; message: string; errorCode?: string }
  | { type: "persist_chat_state"; snapshot: ChatStateSnapshot }
  | { type: "track_usage_metric"; metric: string; data?: Record<string, unknown> };

export interface LogicResult<State> {
  newState: State;
  commands: ChatCommand[];
  uiMessage?: string;
}

