export interface User {
  userId: string;
  username: string;
  playbackSpeed?: number; // Optional for backward compatibility
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: AuthError | null;
}

export interface AuthError {
  message: string;
  code: string;
  details?: unknown;
}

export type AuthEvent =
  | { type: "login_attempted"; username: string; password: string }
  | { type: "register_attempted"; username: string; password: string }
  | { type: "login_succeeded"; user: User; token: string }
  | { type: "register_succeeded"; user: User; token: string }
  | { type: "auth_failed"; error: AuthError }
  | { type: "logout_requested" }
  | { type: "token_restored"; user: User; token: string }
  | { type: "token_validated"; user: User }
  | { type: "token_validation_failed" };

export type AuthCommand =
  | { type: "send_login_request"; username: string; password: string }
  | { type: "send_register_request"; username: string; password: string }
  | { type: "send_validate_token_request"; token: string }
  | { type: "persist_auth_state"; user: User; token: string }
  | { type: "clear_auth_state" }
  | { type: "show_error_toast"; message: string; errorCode: string };

export interface LogicResult<T> {
  newState: T;
  commands: AuthCommand[];
  uiMessage?: string;
}

