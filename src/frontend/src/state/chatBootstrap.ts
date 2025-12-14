import { toast } from "react-hot-toast";

import { initializeChatExecutor } from "../api/chatExecutor";
import { useChatStore } from "../store/chatStore";
import { loadSnapshot, saveSnapshot } from "../utils/chatStorage";
import { trackChatMetric } from "../utils/metrics";

export const bootstrapChatModule = async (): Promise<void> => {
  initializeChatExecutor({
    persistSnapshot: saveSnapshot,
    trackMetric: (metric, data) => trackChatMetric({ metric, data }),
    showErrorToast: async (message, errorCode) => {
      toast.error(message, {
        id: errorCode ?? undefined,
      });
    },
  });

  const snapshot = loadSnapshot();
  if (snapshot) {
    await useChatStore.getState().dispatch({
      type: "session_restored",
      snapshot,
    });
  }
};

