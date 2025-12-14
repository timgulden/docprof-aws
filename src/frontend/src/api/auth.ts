/**
 * Authentication API using AWS Cognito
 * 
 * This module provides authentication functions using AWS Amplify Cognito.
 * It replaces the previous custom JWT token-based authentication.
 */

import { signIn, signUp, signOut, confirmSignUp, resendSignUpCode, getCurrentUser as getCognitoUser, fetchAuthSession, updateUserAttributes } from 'aws-amplify/auth';
import type { User } from "../types/auth";

export interface LoginRequest {
  username: string;  // Email address for Cognito
  password: string;
}

export interface RegisterRequest {
  username: string;  // Email address (for backward compatibility)
  password: string;
  email?: string;     // Email (optional, defaults to username)
}

/**
 * Login user with Cognito
 */
export const loginUser = async (request: LoginRequest): Promise<{ user: User; token: string }> => {
  try {
    // Sign in with Cognito
    const { isSignedIn, nextStep } = await signIn({
      username: request.username, // Email
      password: request.password,
    });

    // Check if user needs to verify email
    if (!isSignedIn && nextStep.signInStep === 'CONFIRM_SIGN_UP') {
      const error: any = new Error('Please verify your email address before logging in.');
      error.name = 'UserNotConfirmedException';
      error.email = request.username;
      throw error;
    }

    if (!isSignedIn) {
      throw new Error('Login failed');
    }

    // Get auth session to retrieve tokens
    const session = await fetchAuthSession();
    const idToken = session.tokens?.idToken?.toString();
    
    if (!idToken) {
      throw new Error('Failed to retrieve authentication token');
    }

    // Get current user details
    const cognitoUser = await getCognitoUser();
    
    // Map Cognito user to our User type
    const user: User = {
      userId: cognitoUser.userId,
      username: cognitoUser.username,
      playbackSpeed: 1.0, // Default, can be retrieved from user attributes if needed
    };

  return {
      user,
      token: idToken,
    };
  } catch (error: any) {
    // Re-throw Cognito errors as-is
    if (error.name === 'UserNotConfirmedException') {
      throw error;
    }
    console.error('Login error:', error);
    throw error;
  }
};

/**
 * Register new user with Cognito
 * Returns user/token if auto-confirmed, or throws error with verification required flag
 */
export const registerUser = async (request: RegisterRequest): Promise<{ user: User; token: string } | { requiresVerification: true; email: string }> => {
  try {
    // Use email as username for Cognito
    const email = request.email || request.username;
    
    // Sign up with Cognito
    const { isSignUpComplete, userId, nextStep } = await signUp({
      username: email, // Use email as username
      password: request.password,
      options: {
        userAttributes: {
          email: email,
        },
        // Don't auto-sign in - let user verify email first
        autoSignIn: {
          enabled: false,
        },
      },
    });

    if (!isSignUpComplete && nextStep.signUpStep === 'CONFIRM_SIGN_UP') {
      // Email verification required
      return { requiresVerification: true, email };
    }

    if (!isSignUpComplete) {
      throw new Error('Registration incomplete');
    }

    // After successful signup, sign in to get token
    const loginResult = await loginUser({
      username: email,
      password: request.password,
    });

    return loginResult;
  } catch (error: any) {
    // Check if it's a verification required error
    if (error.name === 'UserNotConfirmedException' || error.message?.includes('verification')) {
      const email = request.email || request.username;
      return { requiresVerification: true, email };
    }
    console.error('Registration error:', error);
    throw error;
  }
};

/**
 * Confirm sign up with verification code
 */
export const confirmSignUpCode = async (email: string, confirmationCode: string): Promise<void> => {
  try {
    await confirmSignUp({
      username: email,
      confirmationCode,
    });
  } catch (error) {
    console.error('Confirmation error:', error);
    throw error;
  }
};

/**
 * Resend confirmation code
 */
export const resendConfirmationCode = async (email: string): Promise<void> => {
  try {
    await resendSignUpCode({
      username: email,
    });
  } catch (error) {
    console.error('Resend confirmation code error:', error);
    throw error;
  }
};

/**
 * Validate current session token
 */
export const validateToken = async (token?: string): Promise<User> => {
  try {
    // Get current user from Cognito
    const cognitoUser = await getCurrentUser();
    
    // Verify session is valid
    const session = await fetchAuthSession();
    if (!session.tokens) {
      throw new Error('No valid session');
    }

    // Get user attributes if needed
    // Note: Cognito doesn't have playbackSpeed by default, 
    // we'd need to add it as a custom attribute or store it elsewhere
    
    return {
      userId: cognitoUser.userId,
      username: cognitoUser.username,
      playbackSpeed: 1.0, // Default, can be retrieved from user attributes
    };
  } catch (error) {
    console.error('Token validation error:', error);
    throw error;
  }
};

/**
 * Update playback speed (stored as custom attribute)
 */
export const updatePlaybackSpeed = async (playbackSpeed: number): Promise<User> => {
  try {
    const cognitoUser = await getCognitoUser();
    
    // Update custom attribute (if configured in Cognito)
    // Note: This requires custom attribute to be defined in Cognito User Pool
    await updateUserAttributes({
      userAttributes: {
        'custom:playback_speed': playbackSpeed.toString(),
      },
    });

    return {
      userId: cognitoUser.userId,
      username: cognitoUser.username,
      playbackSpeed,
    };
  } catch (error) {
    console.error('Update playback speed error:', error);
    // If custom attribute update fails, still return user with updated speed
    // (could store in localStorage as fallback)
    const cognitoUser = await getCurrentUser();
  return {
      userId: cognitoUser.userId,
      username: cognitoUser.username,
      playbackSpeed,
  };
  }
};

/**
 * Get current authenticated user
 */
export const getCurrentUser = async (): Promise<User> => {
  try {
    const cognitoUser = await getCognitoUser();
    const session = await fetchAuthSession();
    
    if (!session.tokens) {
      throw new Error('No valid session');
    }

  return {
      userId: cognitoUser.userId,
      username: cognitoUser.username,
      playbackSpeed: 1.0, // Default
    };
  } catch (error) {
    console.error('Get current user error:', error);
    throw error;
  }
};

/**
 * Logout user
 */
export const logoutUser = async (): Promise<void> => {
  try {
    await signOut();
    // Clear any local storage
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_user");
  } catch (error) {
    console.error('Logout error:', error);
    throw error;
  }
};
