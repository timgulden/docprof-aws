/**
 * Auth Bootstrap - Initialize authentication on app startup
 * 
 * With Cognito, we check for an existing session instead of localStorage tokens.
 */

import { getCurrentUser as getCognitoUser, fetchAuthSession } from 'aws-amplify/auth';
import { initializeAuthExecutor } from "../api/authExecutor";
import { useAuthStore } from "../store/authStore";
import { getCurrentUser } from "../api/auth";

export const bootstrapAuthModule = async (): Promise<void> => {
  console.log("Initializing auth executor...");
  initializeAuthExecutor();
  console.log("Auth executor initialized");

  // Check for existing Cognito session
  try {
    console.log("Checking for existing Cognito session...");
    const session = await fetchAuthSession();
    
    if (session.tokens) {
      console.log("Valid Cognito session found");
      // Get user details
      try {
        const user = await getCurrentUser();
        const idToken = session.tokens.idToken?.toString();
        
        if (user && idToken) {
          console.log("Dispatching token_restored event...");
          await useAuthStore.getState().dispatch({
            type: "token_restored",
            user,
            token: idToken,
          });
          console.log("Token restored event dispatched");
        }
      } catch (error) {
        console.error("Error getting current user:", error);
        // Session might be invalid, clear it
        await useAuthStore.getState().dispatch({
          type: "token_validation_failed",
        });
      }
    } else {
      console.log("No valid Cognito session found");
    }
  } catch (error) {
    console.log("No existing Cognito session:", error);
    // This is fine - user will need to log in
  }
};
