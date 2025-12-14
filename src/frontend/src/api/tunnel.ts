import { apiClient } from "./client";

export interface TunnelStatus {
  enabled: boolean;
  backend_url: string | null;
  frontend_url: string | null;
}

export interface TunnelUrls {
  backend_url: string | null;
  frontend_url: string | null;
}

/**
 * Get current tunnel status
 */
export const getTunnelStatus = async (): Promise<TunnelStatus> => {
  const response = await apiClient.get<TunnelStatus>("/tunnel/status");
  return response.data;
};

/**
 * Enable the tunnel
 */
export const enableTunnel = async (): Promise<TunnelStatus> => {
  const response = await apiClient.post<TunnelStatus>("/tunnel/enable");
  return response.data;
};

/**
 * Disable the tunnel
 */
export const disableTunnel = async (): Promise<TunnelStatus> => {
  const response = await apiClient.post<TunnelStatus>("/tunnel/disable");
  return response.data;
};

/**
 * Get tunnel URLs
 */
export const getTunnelUrls = async (): Promise<TunnelUrls> => {
  const response = await apiClient.get<TunnelUrls>("/tunnel/urls");
  return response.data;
};



