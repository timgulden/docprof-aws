import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { initializeChatExecutor } from "./chatExecutor";
import { useChatStore } from "../store/chatStore";
import { createInitialChatState } from "../state/chatLogic";
import type { ChatStore } from "../store/chatStore";

type CommandExecutor = NonNullable<Parameters<ChatStore["setExecutor"]>[0]>;

let originalDispatch: ChatStore["dispatch"];
let originalSetExecutor: ChatStore["setExecutor"];
let dispatchSpy: ChatStore["dispatch"];
let executor: CommandExecutor | undefined;

beforeEach(() => {
  const store = useChatStore.getState();
  originalDispatch = store.dispatch;
  originalSetExecutor = store.setExecutor;
  dispatchSpy = vi.fn(async () => {}) as ChatStore["dispatch"];
  executor = undefined;

  useChatStore.setState({
    state: createInitialChatState(),
    dispatch: dispatchSpy,
    setExecutor: (fn: CommandExecutor) => {
      executor = fn;
    },
  });
});

afterEach(() => {
  useChatStore.setState((store) => ({
    ...store,
    state: createInitialChatState(),
    dispatch: originalDispatch,
    setExecutor: originalSetExecutor,
  }));
  vi.restoreAllMocks();
});

describe("chat command executor", () => {
  it("dispatches backend message events on successful send", async () => {
    const sendMessage = vi.fn(async () => ({
      sessionId: "session-1",
      uiMessage: "Ready",
      messages: [],
    }));

    initializeChatExecutor({ sendMessage });
    expect(executor).toBeDefined();

    await executor!({
      type: "send_chat_message",
      payload: { message: "Hello", withAudio: false, sessionId: undefined },
    });

    expect(sendMessage).toHaveBeenCalledTimes(1);
    expect(dispatchSpy).toHaveBeenCalledWith({
      type: "backend_message_received",
      sessionId: "session-1",
      messages: [],
      uiMessage: "Ready",
    });
  });

  it("dispatches backend failure event when send throws", async () => {
    const sendMessage = vi.fn(async () => {
      throw new Error("network error");
    });

    initializeChatExecutor({ sendMessage });
    expect(executor).toBeDefined();

    await executor!({
      type: "send_chat_message",
      payload: { message: "Hello", withAudio: false },
    });

    expect(dispatchSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "backend_failed",
      }),
    );
  });

  it("persists snapshots when command emitted", async () => {
    const persistSnapshot = vi.fn(async () => {});
    initializeChatExecutor({ persistSnapshot });
    expect(executor).toBeDefined();

    const snapshot = { sessionId: "s", messages: [] };
    await executor!({
      type: "persist_chat_state",
      snapshot,
    });

    expect(persistSnapshot).toHaveBeenCalledWith(snapshot);
  });

  it("routes toast commands to showErrorToast dependency", async () => {
    const showErrorToast = vi.fn(async () => {});
    initializeChatExecutor({ showErrorToast });
    expect(executor).toBeDefined();

    await executor!({
      type: "show_error_toast",
      message: "Boom",
      errorCode: "500",
    });

    expect(showErrorToast).toHaveBeenCalledWith("Boom", "500");
  });

  it("tracks usage metrics when command emitted", async () => {
    const trackMetric = vi.fn(async () => {});
    initializeChatExecutor({ trackMetric });
    expect(executor).toBeDefined();

    await executor!({
      type: "track_usage_metric",
      metric: "chat.test",
      data: { sample: true },
    });

    expect(trackMetric).toHaveBeenCalledWith("chat.test", { sample: true });
  });
});

