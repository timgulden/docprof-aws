/**
 * API Client for DocProf AWS Backend
 * 
 * This client uses AWS Amplify API to make authenticated requests to API Gateway.
 * Authentication tokens are automatically included via Amplify.
 */

import { fetchAuthSession } from 'aws-amplify/auth';
import axios from 'axios';
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

// Determine API URL from environment variable or use default
function getApiUrl(): string {
  // If explicitly set via env var, use that
  const apiGatewayUrl = import.meta.env.VITE_API_GATEWAY_URL;
  if (apiGatewayUrl) {
    console.log('[API Client] Using API Gateway URL:', apiGatewayUrl);
    return apiGatewayUrl;
  }
  
  // Default to localhost for local development (fallback)
  // NOTE: This should only be used if you're running the local FastAPI backend
  // For AWS deployment, VITE_API_GATEWAY_URL must be set
  console.warn('[API Client] VITE_API_GATEWAY_URL not set, using localhost fallback');
  console.warn('[API Client] If deploying to AWS, set VITE_API_GATEWAY_URL in .env file');
  console.warn('[API Client] Available env vars:', Object.keys(import.meta.env).filter(k => k.startsWith('VITE_')));
  return "http://localhost:8000/api";
}

// Cached at module load - no runtime overhead
const API_URL = getApiUrl();
console.log('[API Client] Final API_URL:', API_URL);

// Export API_URL so other modules can use it for constructing URLs
export { API_URL };

// Create axios instance
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor: adds Cognito auth token
apiClient.interceptors.request.use(
  async (config) => {
    try {
      // Get current auth session from Amplify
      const session = await fetchAuthSession();
      const idToken = session.tokens?.idToken?.toString();
      
      if (idToken) {
        // Add Cognito ID token to Authorization header
        config.headers.Authorization = `Bearer ${idToken}`;
  }
    } catch (error) {
      // If auth session fetch fails, continue without token
      // The API Gateway will return 401 if auth is required
      console.warn('Failed to get auth session:', error);
    }
  
  return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: handles auth errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Handle 401 Unauthorized - user needs to login
    if (error.response?.status === 401) {
      // Clear any stored auth data
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_user");
      
      // Redirect to login page
      if (window.location.pathname !== '/login') {
      window.location.href = "/login";
      }
    }
    
    // Log network errors for debugging
    if (error.code === 'ERR_NETWORK' || !error.response) {
      console.error("Network error - check if backend is running and accessible:", {
        url: error.config?.url,
        baseURL: error.config?.baseURL,
        message: error.message,
      });
    }
    
    return Promise.reject(error);
  }
);

// Legacy AUTH_TOKEN_KEY export for compatibility (not used with Cognito)
export const AUTH_TOKEN_KEY = "auth_token";
