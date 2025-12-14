import type { ChatStateSnapshot } from "../types/chat";

const STORAGE_KEY = "chat_snapshot";

export const loadSnapshot = (): ChatStateSnapshot | null => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as ChatStateSnapshot;
    if (parsed && Array.isArray(parsed.messages)) {
      return parsed;
    }
  } catch (error) {
    console.warn("Failed to load chat snapshot", error);
  }
  return null;
};

export const saveSnapshot = async (snapshot: ChatStateSnapshot): Promise<void> => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
};

export const clearSnapshot = async (): Promise<void> => {
  localStorage.removeItem(STORAGE_KEY);
};

