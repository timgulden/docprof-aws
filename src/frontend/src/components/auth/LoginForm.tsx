import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuthStore } from "../../store/authStore";
import { loginUser } from "../../api/auth";

export const LoginForm = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const state = useAuthStore((store) => store.state);
  const dispatch = useAuthStore((store) => store.dispatch);
  const navigate = useNavigate();

  useEffect(() => {
    if (state.user && state.token && !state.isLoading) {
      navigate("/sources", { replace: true });
    }
  }, [state.user, state.token, state.isLoading, navigate]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!email.trim() || !password || state.isLoading) {
      return;
    }

    try {
      const result = await loginUser({
        username: email.trim(),
        password,
      });

      // Login succeeded
      await dispatch({
        type: "login_succeeded",
        user: result.user,
        token: result.token,
      });
    } catch (error: any) {
      // Check if user needs to verify email
      if (error.name === 'UserNotConfirmedException' && error.email) {
        navigate(`/verify?email=${encodeURIComponent(error.email)}`, { replace: true });
        return;
      }

      // Handle other login errors
      await dispatch({
        type: "auth_failed",
        error: {
          message: error.message || "Login failed. Please check your credentials.",
          code: error.name || "login_error",
        },
      });
    }
  };

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white shadow-lg p-8">
      <h2 className="text-2xl font-semibold text-slate-900 mb-2">Login</h2>
      <p className="text-sm text-slate-600 mb-6">Sign in to your M&A Expert account</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            required
            disabled={state.isLoading}
            placeholder="your.email@example.com"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            required
            disabled={state.isLoading}
          />
        </div>

        {state.error ? (
          <div className="text-sm text-red-600">{state.error.message}</div>
        ) : null}

        <button
          type="submit"
          disabled={state.isLoading || !email.trim() || !password}
          className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
        >
          {state.isLoading ? "Logging in..." : "Login"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-600">
        Don't have an account?{" "}
        <Link to="/register" className="font-medium text-blue-600 hover:text-blue-700">
          Register
        </Link>
      </p>
    </div>
  );
};

