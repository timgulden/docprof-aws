import type { User } from "../types/auth";
import { AUTH_TOKEN_KEY } from "../api/client";

const AUTH_USER_KEY = "auth_user";

export interface AuthSnapshot {
  user: User;
  token: string;
}

export const loadAuthSnapshot = (): AuthSnapshot | null => {
  try {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    const userStr = localStorage.getItem(AUTH_USER_KEY);

    if (!token || !userStr) {
      return null;
    }

    const user = JSON.parse(userStr) as User;
    return { user, token };
  } catch {
    return null;
  }
};

export const saveAuthSnapshot = (snapshot: AuthSnapshot): void => {
  localStorage.setItem(AUTH_TOKEN_KEY, snapshot.token);
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(snapshot.user));
};

export const clearAuthSnapshot = (): void => {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
};

