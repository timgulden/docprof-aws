import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuthStore } from "../../store/authStore";
import { registerUser } from "../../api/auth";

export const RegisterForm = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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
    if (!email.trim() || !password || password !== confirmPassword || state.isLoading) {
      return;
    }

    try {
      // Try to register - may require verification
      const result = await registerUser({
        username: email.trim(),
      password,
    });

      // Check if verification is required
      if ('requiresVerification' in result && result.requiresVerification) {
        // Redirect to verification page with email
        navigate(`/verify?email=${encodeURIComponent(email.trim())}`, { replace: true });
        return;
      }

      // If registration succeeded (auto-confirmed), dispatch success
      if ('user' in result && 'token' in result) {
        await dispatch({
          type: "register_succeeded",
          user: result.user,
          token: result.token,
        });
      }
    } catch (error: any) {
      // Handle registration errors
      await dispatch({
        type: "auth_failed",
        error: {
          message: error.message || "Registration failed. Please try again.",
          code: error.name || "registration_error",
        },
      });
    }
  };

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white shadow-lg p-8">
      <h2 className="text-2xl font-semibold text-slate-900 mb-2">Register</h2>
      <p className="text-sm text-slate-600 mb-6">Create a new M&A Expert account</p>

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

        <div>
          <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700 mb-1">
            Confirm Password
          </label>
          <input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            required
            disabled={state.isLoading}
          />
          {password && confirmPassword && password !== confirmPassword ? (
            <p className="mt-1 text-xs text-red-600">Passwords do not match</p>
          ) : null}
        </div>

        {state.error ? (
          <div className="text-sm text-red-600">{state.error.message}</div>
        ) : null}

        <button
          type="submit"
          disabled={state.isLoading || !email.trim() || !password || password !== confirmPassword}
          className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
        >
          {state.isLoading ? "Registering..." : "Register"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-600">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-blue-600 hover:text-blue-700">
          Login
        </Link>
      </p>
    </div>
  );
};

