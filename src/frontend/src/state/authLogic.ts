import type { AuthEvent, AuthCommand, AuthState, LogicResult, User } from "../types/auth";

export const createInitialAuthState = (): AuthState => ({
  user: null,
  token: null,
  isLoading: false,
  error: null,
});

export const reduceAuthEvent = (state: AuthState, event: AuthEvent): LogicResult<AuthState> => {
  switch (event.type) {
    case "login_attempted":
      return processLoginAttempt(state, event.username, event.password);
    case "register_attempted":
      return processRegisterAttempt(state, event.username, event.password);
    case "login_succeeded":
      return processAuthSuccess(state, event.user, event.token);
    case "register_succeeded":
      return processAuthSuccess(state, event.user, event.token);
    case "auth_failed":
      return processAuthFailure(state, event.error);
    case "logout_requested":
      return processLogout(state);
    case "token_restored":
      return restoreToken(state, event.user, event.token);
    case "token_validated":
      return validateTokenSuccess(state, event.user);
    case "token_validation_failed":
      return processTokenValidationFailed(state);
    default:
      return exhaustiveCheck(event);
  }
};

const processLoginAttempt = (state: AuthState, username: string, password: string): LogicResult<AuthState> => {
  const newState: AuthState = {
    ...state,
    isLoading: true,
    error: null,
  };

  const commands: AuthCommand[] = [
    {
      type: "send_login_request",
      username,
      password,
    },
  ];

  return { newState, commands };
};

const processRegisterAttempt = (state: AuthState, username: string, password: string): LogicResult<AuthState> => {
  const newState: AuthState = {
    ...state,
    isLoading: true,
    error: null,
  };

  const commands: AuthCommand[] = [
    {
      type: "send_register_request",
      username,
      password,
    },
  ];

  return { newState, commands };
};

const processAuthSuccess = (state: AuthState, user: User, token: string): LogicResult<AuthState> => {
  const newState: AuthState = {
    ...state,
    user,
    token,
    isLoading: false,
    error: null,
  };

  const commands: AuthCommand[] = [
    {
      type: "persist_auth_state",
      user,
      token,
    },
  ];

  return { newState, commands };
};

const processAuthFailure = (state: AuthState, error: AuthState["error"] extends null ? never : NonNullable<AuthState["error"]>): LogicResult<AuthState> => {
  const newState: AuthState = {
    ...state,
    isLoading: false,
    error,
    user: null,
    token: null,
  };

  const commands: AuthCommand[] = [
    {
      type: "show_error_toast",
      message: error.message,
      errorCode: error.code,
    },
  ];

  return { newState, commands };
};

const processLogout = (_state: AuthState): LogicResult<AuthState> => {
  const newState = createInitialAuthState();

  const commands: AuthCommand[] = [
    {
      type: "clear_auth_state",
    },
  ];

  return { newState, commands };
};

const restoreToken = (state: AuthState, user: User, token: string): LogicResult<AuthState> => {
  const newState: AuthState = {
    ...state,
    user,
    token,
    isLoading: false,
    error: null,
  };

  const commands: AuthCommand[] = [
    {
      type: "send_validate_token_request",
      token,
    },
  ];

  return { newState, commands };
};

const validateTokenSuccess = (state: AuthState, user: User): LogicResult<AuthState> => {
  const newState: AuthState = {
    ...state,
    user,
    isLoading: false,
    error: null,
  };

  return { newState, commands: [] };
};

const processTokenValidationFailed = (_state: AuthState): LogicResult<AuthState> => {
  const newState = createInitialAuthState();

  const commands: AuthCommand[] = [
    {
      type: "clear_auth_state",
    },
  ];

  return { newState, commands };
};

const exhaustiveCheck = (_: never): LogicResult<AuthState> => {
  throw new Error("Unhandled auth event");
};

