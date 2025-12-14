import type {
  AssistantMessagePayload,
  BackendChatPayload,
  ChatCommand,
  ChatEvent,
  ChatMessage,
  ChatState,
  ChatStateSnapshot,
  LogicResult,
  SessionMetadata,
} from "../types/chat";
import { v4 as uuid } from "uuid";
import { useBooksStore } from "../store/booksStore";

const nowIso = (): string => new Date().toISOString();

export const createInitialChatState = (): ChatState => ({
  sessionId: undefined,
  messages: [],
  status: "idle",
  error: undefined,
  uiMessage: null,
});

export const reduceChatEvent = (state: ChatState, event: ChatEvent): LogicResult<ChatState> => {
  switch (event.type) {
    case "user_submitted_message":
      return processUserMessage(state, event.text, event.withAudio ?? false);
    case "backend_message_received":
      return processBackendSuccess(state, event.messages, event.sessionId, event.uiMessage);
    case "backend_failed":
      return processBackendFailure(state, event.error);
    case "session_restored":
      return rehydrateChatState(state, event.snapshot);
    case "session_switched":
      return processSessionSwitch(state, event.sessionId, event.snapshot);
    case "session_created":
      return processSessionCreated(state, event.sessionMetadata);
    case "reset_requested":
      return resetChatState(state);
    default:
      // Exhaustiveness check
      return exhaustiveCheck(event);
  }
};

const processUserMessage = (state: ChatState, text: string, withAudio: boolean): LogicResult<ChatState> => {
  const userMessage: ChatMessage = {
    id: uuid(),
    role: "user",
    content: text,
    timestamp: nowIso(),
    figures: [],
  };

  const newState: ChatState = {
    ...state,
    messages: [...state.messages, userMessage],
    status: "awaiting_response",
    error: undefined,
    uiMessage: null,
  };

  // Get selected book IDs from the books store
  const selectedBookIds = useBooksStore.getState().selectedBookIds;
  
  const payload: BackendChatPayload = {
    message: text,
    withAudio,
    sessionId: state.sessionId,
    bookIds: selectedBookIds.length > 0 ? selectedBookIds : undefined,
  };

  const commands: ChatCommand[] = [
    { type: "send_chat_message", payload },
    {
      type: "track_usage_metric",
      metric: "chat.user_message_submitted",
      data: { messageId: userMessage.id },
    },
  ];

  return { newState, commands };
};

const processBackendSuccess = (
  state: ChatState,
  payloads: AssistantMessagePayload[],
  sessionId?: string,
  uiMessage?: string,
): LogicResult<ChatState> => {
  const assistantMessages = payloads.map(payloadToChatMessage);
  const newState: ChatState = {
    ...state,
    sessionId: sessionId ?? state.sessionId,
    messages: [...state.messages, ...assistantMessages],
    status: "idle",
    error: undefined,
    uiMessage: uiMessage ?? null,
  };

  const commands: ChatCommand[] = [
    { type: "persist_chat_state", snapshot: snapshotFromState(newState) },
    {
      type: "track_usage_metric",
      metric: "chat.assistant_message_received",
      data: { count: assistantMessages.length },
    },
  ];

  return { newState, commands, uiMessage };
};

const processBackendFailure = (state: ChatState, error: ChatState["error"] extends undefined ? never : NonNullable<ChatState["error"]>): LogicResult<ChatState> => {
  const newState: ChatState = {
    ...state,
    status: "idle",
    error,
    uiMessage: null,
  };

  const commands: ChatCommand[] = [
    {
      type: "show_error_toast",
      message: error.message,
      errorCode: error.code,
    },
    {
      type: "track_usage_metric",
      metric: "chat.backend_error",
      data: { code: error.code, retryable: error.retryable },
    },
  ];

  return { newState, commands, uiMessage: error.message };
};

const rehydrateChatState = (state: ChatState, snapshot: ChatStateSnapshot): LogicResult<ChatState> => {
  const newState: ChatState = {
    ...state,
    sessionId: snapshot.sessionId,
    sessionName: snapshot.sessionName,
    sessionType: snapshot.sessionType,
    sessionContext: snapshot.sessionContext,
    createdAt: snapshot.createdAt,
    updatedAt: snapshot.updatedAt,
    messages: snapshot.messages.map((message) => ({ ...message })),
    status: "idle",
    error: undefined,
    uiMessage: null,
  };

  return { newState, commands: [] };
};

const resetChatState = (state: ChatState): LogicResult<ChatState> => {
  const newState = createInitialChatState();

  const commands: ChatCommand[] = [
    {
      type: "track_usage_metric",
      metric: "chat.session_reset",
      data: { previousSessionId: state.sessionId },
    },
  ];

  return { newState, commands };
};

const payloadToChatMessage = (payload: AssistantMessagePayload): ChatMessage => ({
  id: payload.messageId ?? uuid(),
  role: "assistant",
  content: payload.content,
  timestamp: payload.timestamp ?? nowIso(),
  audioUrl: payload.audioUrl,
  figures: (payload.figures ?? []).map((figure) => ({ ...figure })),
  sources: payload.sources ?? [],
  citationSpans: payload.citationSpans ?? [],
  generalSpans: payload.generalSpans ?? [],
});

export const snapshotFromState = (state: ChatState): ChatStateSnapshot => ({
  sessionId: state.sessionId,
  sessionName: state.sessionName,
  sessionType: state.sessionType,
  sessionContext: state.sessionContext,
  createdAt: state.createdAt,
  updatedAt: state.updatedAt,
  messages: state.messages.map((message) => ({ ...message, figures: message.figures.map((figure) => ({ ...figure })) })),
});

const processSessionSwitch = (
  state: ChatState,
  sessionId: string,
  snapshot?: ChatStateSnapshot,
): LogicResult<ChatState> => {
  if (snapshot) {
    // If snapshot provided, restore from it
    return rehydrateChatState(state, snapshot);
  } else {
    // Otherwise, clear current state and set session ID (will load from backend)
    const newState: ChatState = {
      ...createInitialChatState(),
      sessionId,
      status: "restoring",
    };

    const commands: ChatCommand[] = [
      {
        type: "track_usage_metric",
        metric: "chat.session_switched",
        data: { sessionId },
      },
    ];

    return { newState, commands };
  }
};

const processSessionCreated = (
  _state: ChatState,
  sessionMetadata: SessionMetadata,
): LogicResult<ChatState> => {
  const newState: ChatState = {
    ...createInitialChatState(),
    sessionId: sessionMetadata.sessionId,
    sessionName: sessionMetadata.sessionName,
    sessionType: sessionMetadata.sessionType,
    createdAt: sessionMetadata.createdAt,
    updatedAt: sessionMetadata.updatedAt,
    status: "idle",
  };

  const commands: ChatCommand[] = [
    {
      type: "track_usage_metric",
      metric: "chat.session_created",
      data: { sessionId: sessionMetadata.sessionId, sessionType: sessionMetadata.sessionType },
    },
  ];

  return { newState, commands };
};

const exhaustiveCheck = (_: never): LogicResult<ChatState> => {
  throw new Error("Unhandled chat event");
};

