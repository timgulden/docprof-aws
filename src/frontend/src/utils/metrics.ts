import { apiClient } from "../api/client";

const METRICS_ENDPOINT = "/metrics/chat";

export interface MetricPayload {
  metric: string;
  data?: Record<string, unknown>;
  timestamp?: string;
}

export const trackChatMetric = async ({ metric, data, timestamp }: MetricPayload): Promise<void> => {
  const payload: MetricPayload = {
    metric,
    data,
    timestamp: timestamp ?? new Date().toISOString(),
  };

  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
      const success = navigator.sendBeacon(`${apiClient.defaults.baseURL}${METRICS_ENDPOINT}`, blob);
      if (success) {
        return;
      }
    }
  } catch (error) {
    console.warn("sendBeacon failed, falling back to fetch", error);
  }

  try {
    await apiClient.post(METRICS_ENDPOINT, payload);
  } catch (error) {
    if (import.meta.env.DEV) {
      console.debug("[metric-failed]", metric, data, error);
    }
  }
};

