import { create } from "zustand";

import { createInitialChatState, reduceChatEvent } from "../state/chatLogic";
import type { ChatCommand, ChatEvent, ChatState } from "../types/chat";

type CommandExecutor = (command: ChatCommand) => Promise<void>;

export interface ChatStore {
  state: ChatState;
  dispatch: (event: ChatEvent) => Promise<void>;
  setExecutor: (executor: CommandExecutor) => void;
}

let executorRef: CommandExecutor = async () => {
  // Default no-op executor; should be replaced via setExecutor.
};

export const useChatStore = create<ChatStore>((set, get) => ({
  state: createInitialChatState(),

  setExecutor: (executor: CommandExecutor) => {
    executorRef = executor;
  },

  dispatch: async (event: ChatEvent) => {
    const currentState = get().state;
    const result = reduceChatEvent(currentState, event);

    set({ state: result.newState });

    for (const command of result.commands) {
      await executorRef(command);
    }
  },
}));

export const getChatState = (): ChatState => useChatStore.getState().state;

