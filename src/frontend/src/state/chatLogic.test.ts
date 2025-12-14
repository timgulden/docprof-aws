import { describe, expect, it } from "vitest";

import { createInitialChatState, reduceChatEvent } from "./chatLogic";
import type {
  AssistantMessagePayload,
  ChatError,
  ChatMessage,
  ChatState,
  ChatStateSnapshot,
} from "../types/chat";

const sampleUserMessage = (content: string): ChatMessage => ({
  id: "user-1",
  role: "user",
  content,
  timestamp: new Date().toISOString(),
  figures: [],
});

describe("chat logic reducer", () => {
  it("handles user-submitted messages immutably", () => {
    const initial = createInitialChatState();

    const result = reduceChatEvent(initial, {
      type: "user_submitted_message",
      text: "Hello world",
      withAudio: true,
    });

    expect(result.newState.status).toBe("awaiting_response");
    expect(result.newState.messages).toHaveLength(1);
    expect(initial.messages).toHaveLength(0);
    expect(result.commands[0]).toMatchObject({
      type: "send_chat_message",
      payload: { message: "Hello world", withAudio: true },
    });
    expect(result.commands[1]).toMatchObject({
      type: "track_usage_metric",
      metric: "chat.user_message_submitted",
    });
  });

  it("appends assistant messages on backend success", () => {
    const state: ChatState = {
      ...createInitialChatState(),
      sessionId: "session-1",
      status: "awaiting_response",
      messages: [sampleUserMessage("What is DCF?")],
    };
    const payload: AssistantMessagePayload = {
      messageId: "assistant-1",
      content: "Discounted cash flow (DCF) is ...",
      timestamp: new Date().toISOString(),
    };

    const result = reduceChatEvent(state, {
      type: "backend_message_received",
      sessionId: "session-1",
      messages: [payload],
      uiMessage: "Response ready",
    });

    expect(result.newState.status).toBe("idle");
    expect(result.newState.messages).toHaveLength(2);
    expect(result.newState.messages[1]).toMatchObject({
      role: "assistant",
      content: payload.content,
    });
    expect(result.newState.uiMessage).toBe("Response ready");
    expect(result.commands[0]).toMatchObject({
      type: "persist_chat_state",
    });
    expect(result.commands[1]).toMatchObject({
      type: "track_usage_metric",
      metric: "chat.assistant_message_received",
    });
  });

  it("records backend failures and emits toast/metric commands", () => {
    const state: ChatState = {
      ...createInitialChatState(),
      status: "awaiting_response",
      messages: [sampleUserMessage("Ping?")],
    };
    const error: ChatError = {
      message: "Upstream unavailable",
      code: "503",
      retryable: true,
    };

    const result = reduceChatEvent(state, {
      type: "backend_failed",
      error,
    });

    expect(result.newState.status).toBe("idle");
    expect(result.newState.error).toEqual(error);
    expect(result.commands[0]).toMatchObject({
      type: "show_error_toast",
      message: error.message,
    });
    expect(result.commands[1]).toMatchObject({
      type: "track_usage_metric",
      metric: "chat.backend_error",
      data: { code: "503", retryable: true },
    });
  });

  it("rehydrates state from snapshot", () => {
    const previous: ChatState = {
      ...createInitialChatState(),
      sessionId: "old-session",
      messages: [sampleUserMessage("Hi")],
    };
    const snapshot: ChatStateSnapshot = {
      sessionId: "restored-session",
      messages: [
        {
          id: "assistant-1",
          role: "assistant",
          content: "Welcome back!",
          timestamp: new Date().toISOString(),
          figures: [],
        },
      ],
    };

    const result = reduceChatEvent(previous, {
      type: "session_restored",
      snapshot,
    });

    expect(result.newState.sessionId).toBe("restored-session");
    expect(result.newState.messages).toHaveLength(1);
    expect(result.newState.messages[0].role).toBe("assistant");
    expect(result.newState.status).toBe("idle");
    expect(result.commands).toEqual([]);
  });

  it("resets chat state and tracks metric", () => {
    const state: ChatState = {
      ...createInitialChatState(),
      sessionId: "session-abc",
      messages: [sampleUserMessage("Bye")],
    };

    const result = reduceChatEvent(state, {
      type: "reset_requested",
    });

    expect(result.newState.sessionId).toBeUndefined();
    expect(result.newState.messages).toHaveLength(0);
    expect(result.commands[0]).toMatchObject({
      type: "track_usage_metric",
      metric: "chat.session_reset",
      data: { previousSessionId: "session-abc" },
    });
  });
});

