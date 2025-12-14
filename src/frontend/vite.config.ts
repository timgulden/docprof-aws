/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: [
      "localhost",
      ".trycloudflare.com",
      ".cfargotunnel.com",
    ],
    // Proxy only used when frontend is accessed via tunnel URL
    // Local development uses direct connection (http://localhost:8000/api)
    // so this proxy has zero impact on local performance
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        // Cloudflare Tunnel doesn't require special headers
        // No browser warnings - works seamlessly!
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
    globals: true,
    coverage: {
      reporter: ["text", "html"],
    },
    typecheck: {
      tsconfig: "./tsconfig.vitest.json",
    },
  },
});
