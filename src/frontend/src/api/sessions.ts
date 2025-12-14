import type { SessionMetadata, SessionType } from "../types/chat";
import { apiClient } from "./client";

interface RawSessionMetadata {
  session_id: string;
  session_name?: string;
  session_type: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview?: string | null;
}

interface CreateSessionRequest {
  sessionName?: string;
  sessionType?: SessionType;
  sessionContext?: string;
}

interface UpdateSessionRequest {
  sessionName?: string;
  sessionContext?: string;
}

export const listSessions = async (): Promise<SessionMetadata[]> => {
  const response = await apiClient.get<RawSessionMetadata[]>("/chat/sessions");
  return response.data.map(normalizeSessionMetadata);
};

export const createSession = async (
  request: CreateSessionRequest = {},
): Promise<SessionMetadata> => {
  const response = await apiClient.post<RawSessionMetadata>("/chat/sessions", {
    session_name: request.sessionName,
    session_type: request.sessionType ?? "chat",
    session_context: request.sessionContext,
  });
  return normalizeSessionMetadata(response.data);
};

export const getSessionMetadata = async (sessionId: string, includeMessages = false): Promise<SessionMetadata> => {
  const response = await apiClient.get<RawSessionMetadata>(`/chat/sessions/${sessionId}`, {
    params: { include_messages: includeMessages },
  });
  return normalizeSessionMetadata(response.data);
};

interface RawMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  figures: Array<unknown>;
  audio_url?: string;
}

export const getSessionWithMessages = async (sessionId: string): Promise<{
  metadata: SessionMetadata;
  messages: RawMessage[];
  sessionContext?: string;
}> => {
  const response = await apiClient.get<RawSessionMetadata & {
    messages: RawMessage[];
    session_context?: string;
  }>(`/chat/sessions/${sessionId}`, {
    params: { include_messages: true },
  });
  
  return {
    metadata: normalizeSessionMetadata(response.data),
    messages: response.data.messages || [],
    sessionContext: response.data.session_context,
  };
};

export const updateSession = async (
  sessionId: string,
  request: UpdateSessionRequest,
): Promise<SessionMetadata> => {
  const response = await apiClient.patch<RawSessionMetadata>(`/chat/sessions/${sessionId}`, {
    session_name: request.sessionName,
    session_context: request.sessionContext,
  });
  return normalizeSessionMetadata(response.data);
};

export const deleteSession = async (sessionId: string): Promise<void> => {
  await apiClient.delete(`/chat/sessions/${sessionId}`);
};

const normalizeSessionMetadata = (raw: RawSessionMetadata): SessionMetadata => ({
  sessionId: raw.session_id,
  sessionName: raw.session_name,
  sessionType: raw.session_type as SessionType,
  createdAt: raw.created_at,
  updatedAt: raw.updated_at,
  messageCount: raw.message_count,
  lastMessagePreview: raw.last_message_preview,
});

