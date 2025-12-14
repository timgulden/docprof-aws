import { AxiosError } from "axios";

import type { ChatCommand, ChatError, ChatStateSnapshot } from "../types/chat";
import type { BackendChatResponse } from "../types/api";
import { sendChatMessage } from "./chat";
import { useChatStore } from "../store/chatStore";
import { saveSnapshot } from "../utils/chatStorage";

type PersistSnapshot = (snapshot: ChatStateSnapshot) => Promise<void>;
type TrackMetric = (metric: string, data?: Record<string, unknown>) => Promise<void>;
type ShowErrorToast = (message: string, errorCode?: string) => Promise<void>;

export interface ChatExecutorDependencies {
  persistSnapshot?: PersistSnapshot;
  trackMetric?: TrackMetric;
  showErrorToast?: ShowErrorToast;
  sendMessage?: (command: Extract<ChatCommand, { type: "send_chat_message" }>) => Promise<BackendChatResponse>;
}

const defaultPersistSnapshot: PersistSnapshot = async (snapshot) => {
  await saveSnapshot(snapshot);
};

const defaultTrackMetric: TrackMetric = async (metric, data) => {
  if (import.meta.env.DEV) {
    console.debug("[metric]", metric, data);
  }
};

const defaultShowErrorToast: ShowErrorToast = async (message, errorCode) => {
  console.error("[chat-error]", errorCode ?? "unknown", message);
};

const defaultSendMessage = async (command: Extract<ChatCommand, { type: "send_chat_message" }>) =>
  sendChatMessage(command.payload);

export const initializeChatExecutor = (deps: ChatExecutorDependencies = {}): void => {
  const persistSnapshot = deps.persistSnapshot ?? defaultPersistSnapshot;
  const trackMetric = deps.trackMetric ?? defaultTrackMetric;
  const showErrorToast = deps.showErrorToast ?? defaultShowErrorToast;
  const sendMessage = deps.sendMessage ?? defaultSendMessage;

  const dispatch = useChatStore.getState().dispatch;

  useChatStore.getState().setExecutor(async (command: ChatCommand) => {
    switch (command.type) {
      case "send_chat_message":
        try {
          const response = await sendMessage(command);
          await dispatch({
            type: "backend_message_received",
            sessionId: response.sessionId,
            messages: response.messages ?? [],
            uiMessage: response.uiMessage,
          });
        } catch (error) {
          const chatError = mapError(error);
          await dispatch({
            type: "backend_failed",
            error: chatError,
          });
        }
        break;
      case "persist_chat_state":
        await persistSnapshot(command.snapshot);
        break;
      case "show_error_toast":
        await showErrorToast(command.message, command.errorCode);
        break;
      case "track_usage_metric":
        await trackMetric(command.metric, command.data);
        break;
      default:
        assertNever(command);
    }
  });
};

const mapError = (error: unknown): ChatError => {
  if (error instanceof AxiosError) {
    return {
      message: error.response?.data?.detail ?? error.message,
      code: `${error.response?.status ?? "network"}`,
      retryable: error.response?.status ? error.response.status >= 500 : false,
      details: error.response?.data,
    };
  }

  if (error instanceof Error) {
    return {
      message: error.message,
      code: "unknown_error",
      retryable: false,
    };
  }

  return {
    message: "An unexpected error occurred.",
    code: "unexpected_error",
    retryable: false,
  };
};

const assertNever = (_command: never): void => {
  throw new Error("Unhandled chat command");
};

