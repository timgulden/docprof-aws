import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Import Amplify configuration first (before any other imports that might use it)
import "./config/amplify";

import "./index.css";
import App from "./App.tsx";
import { bootstrapAuthModule } from "./state/authBootstrap";
import { bootstrapChatModule } from "./state/chatBootstrap";

const queryClient = new QueryClient();

const startApp = async () => {
  try {
    console.log("Starting app bootstrap...");
    await bootstrapAuthModule();
    console.log("Auth module bootstrapped");
    await bootstrapChatModule();
    console.log("Chat module bootstrapped");

    const rootElement = document.getElementById("root");
    if (!rootElement) {
      throw new Error("Root element not found");
    }

    console.log("Rendering app...");
    ReactDOM.createRoot(rootElement).render(
      <React.StrictMode>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </React.StrictMode>,
    );
    console.log("App rendered successfully");
  } catch (error) {
    console.error("Error during app startup:", error);
    const rootElement = document.getElementById("root");
    if (rootElement) {
      rootElement.innerHTML = `
        <div style="padding: 20px; font-family: sans-serif;">
          <h1>Application Error</h1>
          <p>Failed to start the application. Please check the console for details.</p>
          <pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; overflow: auto;">${error instanceof Error ? error.stack : String(error)}</pre>
        </div>
      `;
    }
    throw error;
  }
};

startApp().catch((error) => {
  console.error("Failed to bootstrap app", error);
});
