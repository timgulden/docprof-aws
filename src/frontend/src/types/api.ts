import type { AssistantMessagePayload, ChatMessage, ChatStateSnapshot } from "./chat";

export interface ChatMessageRequest {
  message: string;
  withAudio?: boolean;
  sessionId?: string;
}

export interface ChatResponse {
  sessionId: string;
  messages: ChatMessage[];
  uiMessage?: string;
}

export interface BackendChatResponse {
  sessionId?: string;
  messages: AssistantMessagePayload[];
  uiMessage?: string;
}

export interface PersistChatStateRequest {
  snapshot: ChatStateSnapshot;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: {
    user_id: string;
    username: string;
    playback_speed?: number;
  };
}

// Book-related types
export interface Book {
  book_id: string;
  title: string;
  author?: string;
  edition?: string;
  isbn?: string;
  total_pages?: number;
  has_cover?: boolean;
  ingestion_date?: string;
  cover_image_url?: string;
  metadata?: Record<string, any>;
  ingestion_status?: "pending" | "processing" | "complete" | "error";
  ingestion_started_at?: string;
  ingestion_completed_at?: string;
  ingestion_error?: string;
}

export interface BookCoverBatchRequest {
  book_ids: string[];
}

export interface CoverInfo {
  book_id: string;
  has_cover: boolean;
  cover_url?: string;
  format?: string;
}

// Smart Book Upload types
export interface ExtractedMetadata {
  title: string;
  author?: string;
  edition?: string;
  isbn?: string;
  publisher?: string;
  year?: number;
  total_pages?: number;
  confidence?: Record<string, number>;
}

// Response from /books/upload-initial (pre-signed URL)
export interface UploadInitialResponse {
  book_id: string;
  upload_url: string;
  upload_fields: Record<string, string>;
  s3_key: string;
  analyze_url: string;
}

// Response from /books/analyze/{bookId} (cover and metadata extraction)
export interface AnalyzeBookResponse {
  book_id: string;
  cover_url: string | null;  // null if cover extraction failed
  metadata: ExtractedMetadata;
  status: string;
}

export interface StartIngestionRequest {
  title: string;
  author?: string;
  edition?: string;
  isbn?: string;
}

export interface StartIngestionResponse {
  book_id: string;
  task_id: string;
  status: string;
}

export interface IngestionProgress {
  current_step: string;
  progress: number; // 0-100
  message: string;
  started_at?: string;
  updated_at?: string;
}

export interface IngestionStatusResponse {
  book_id: string;
  status: string; // pending, processing, complete, error
  progress?: IngestionProgress;
  error?: string;
}

