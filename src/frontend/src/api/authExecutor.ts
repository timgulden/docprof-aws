import { AxiosError } from "axios";
import { toast } from "react-hot-toast";

import type { AuthCommand, AuthError, User } from "../types/auth";
import { loginUser, registerUser, validateToken, logoutUser } from "./auth";
import { useAuthStore } from "../store/authStore";
import { AUTH_TOKEN_KEY } from "./client";

type PersistAuth = (user: User, token: string) => Promise<void>;
type ShowErrorToast = (message: string, errorCode: string) => Promise<void>;

export interface AuthExecutorDependencies {
  persistAuth?: PersistAuth;
  showErrorToast?: ShowErrorToast;
  login?: typeof loginUser;
  register?: typeof registerUser;
  validate?: typeof validateToken;
  logout?: () => void;
}

const defaultPersistAuth: PersistAuth = async (user, token) => {
  // With Cognito, tokens are managed by Amplify, but we can store user info
  // Token is stored by Amplify automatically
  localStorage.setItem("auth_user", JSON.stringify(user));
  // Note: We don't store the token in localStorage anymore - Cognito handles it
};

const defaultShowErrorToast: ShowErrorToast = async (message, errorCode) => {
  toast.error(message, { id: errorCode });
};

export const initializeAuthExecutor = (deps: AuthExecutorDependencies = {}): void => {
  const persistAuth = deps.persistAuth ?? defaultPersistAuth;
  const showErrorToast = deps.showErrorToast ?? defaultShowErrorToast;
  const login = deps.login ?? loginUser;
  const register = deps.register ?? registerUser;
  const validate = deps.validate ?? validateToken;
  const logout = deps.logout ?? logoutUser;

  const dispatch = useAuthStore.getState().dispatch;

  useAuthStore.getState().setExecutor(async (command: AuthCommand) => {
    switch (command.type) {
      case "send_login_request":
        try {
          const { user, token } = await login({ username: command.username, password: command.password });
          await dispatch({
            type: "login_succeeded",
            user,
            token,
          });
        } catch (error) {
          const authError = mapError(error);
          await dispatch({
            type: "auth_failed",
            error: authError,
          });
        }
        break;
      case "send_register_request":
        try {
          const result = await register({ username: command.username, password: command.password });
          
          // Check if verification is required (handled in RegisterForm now)
          // This executor path is kept for backward compatibility
          if ('requiresVerification' in result && result.requiresVerification) {
            // Verification required - this should be handled by RegisterForm redirect
            await dispatch({
              type: "auth_failed",
              error: {
                message: "Email verification required. Please check your email.",
                code: "verification_required",
              },
            });
          } else if ('user' in result && 'token' in result) {
            // Registration succeeded
          await dispatch({
            type: "register_succeeded",
              user: result.user,
              token: result.token,
          });
          }
        } catch (error) {
          const authError = mapError(error);
          await dispatch({
            type: "auth_failed",
            error: authError,
          });
        }
        break;
      case "send_validate_token_request":
        try {
          const user = await validate(command.token);
          await dispatch({
            type: "token_validated",
            user,
          });
        } catch (error) {
          await dispatch({
            type: "token_validation_failed",
          });
        }
        break;
      case "persist_auth_state":
        await persistAuth(command.user, command.token);
        break;
      case "clear_auth_state":
        await logout(); // logout is now async with Cognito
        break;
      case "show_error_toast":
        await showErrorToast(command.message, command.errorCode);
        break;
      default:
        assertNever(command);
    }
  });
};

const mapError = (error: unknown): AuthError => {
  // Handle Cognito-specific errors
  if (error instanceof Error) {
    // Cognito errors often have specific error names
    if (error.name === 'NotAuthorizedException') {
      return {
        message: 'Incorrect username or password.',
        code: 'not_authorized',
      };
    }
    if (error.name === 'UserNotFoundException') {
      return {
        message: 'User not found. Please check your email address.',
        code: 'user_not_found',
      };
    }
    if (error.name === 'UserNotConfirmedException') {
      return {
        message: 'Please verify your email address before logging in.',
        code: 'user_not_confirmed',
      };
    }
    if (error.name === 'UsernameExistsException') {
      return {
        message: 'An account with this email already exists.',
        code: 'username_exists',
      };
    }
    if (error.name === 'InvalidPasswordException') {
      return {
        message: 'Password does not meet requirements.',
        code: 'invalid_password',
      };
    }
    if (error.name === 'InvalidParameterException') {
      return {
        message: error.message || 'Invalid input. Please check your information.',
        code: 'invalid_parameter',
      };
    }
    
    // Generic error handling
    return {
      message: error.message,
      code: error.name || 'unknown_error',
    };
  }

  if (error instanceof AxiosError) {
    return {
      message: error.response?.data?.detail ?? error.message,
      code: `${error.response?.status ?? "network"}`,
      details: error.response?.data,
    };
  }

  return {
    message: "An unexpected error occurred.",
    code: "unexpected_error",
  };
};

const assertNever = (_command: never): void => {
  throw new Error("Unhandled auth command");
};

