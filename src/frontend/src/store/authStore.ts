import { create } from "zustand";

import { createInitialAuthState, reduceAuthEvent } from "../state/authLogic";
import type { AuthCommand, AuthEvent, AuthState } from "../types/auth";

type CommandExecutor = (command: AuthCommand) => Promise<void>;

interface AuthStore {
  state: AuthState;
  dispatch: (event: AuthEvent) => Promise<void>;
  setExecutor: (executor: CommandExecutor) => void;
}

let executorRef: CommandExecutor = async () => {
  // Default no-op executor; should be replaced via setExecutor.
};

export const useAuthStore = create<AuthStore>((set, get) => ({
  state: createInitialAuthState(),

  setExecutor: (executor: CommandExecutor) => {
    executorRef = executor;
  },

  dispatch: async (event: AuthEvent) => {
    const currentState = get().state;
    const result = reduceAuthEvent(currentState, event);

    set({ state: result.newState });

    for (const command of result.commands) {
      await executorRef(command);
    }
  },
}));

export const getAuthState = (): AuthState => useAuthStore.getState().state;

