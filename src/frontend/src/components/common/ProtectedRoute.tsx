/**
 * Protected Route Component
 * 
 * Checks for authenticated Cognito session before rendering protected content.
 */

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { fetchAuthSession } from 'aws-amplify/auth';

import { useAuthStore } from "../../store/authStore";

interface ProtectedRouteProps {
  children: ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const [isChecking, setIsChecking] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const state = useAuthStore((store) => store.state);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        // Check Cognito session
        const session = await fetchAuthSession();
        
        if (session.tokens) {
          // If we have tokens but no user in store, try to restore
          if (!state.user || !state.token) {
            // Dispatch token_restored event to sync state
            await useAuthStore.getState().dispatch({
              type: "token_restored",
              user: {
                userId: 'temp', // Will be updated by the restore handler
                username: 'temp',
              },
              token: session.tokens.idToken?.toString() || '',
            });
          }
          setIsAuthenticated(true);
        } else {
          setIsAuthenticated(false);
        }
      } catch (error) {
        console.error('Auth check failed:', error);
        setIsAuthenticated(false);
      } finally {
        setIsChecking(false);
      }
    };

    checkAuth();
  }, [state.user, state.token]);

  // Show loading while checking auth
  if (isChecking || state.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-slate-600">Loading...</div>
      </div>
    );
  }

  // Check both Cognito session and store state
  if (!isAuthenticated || !state.user || !state.token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};
