import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { confirmSignUpCode, resendConfirmationCode } from "../../api/auth";
import { toast } from "react-hot-toast";

export const VerificationForm = () => {
  const [searchParams] = useSearchParams();
  const email = searchParams.get("email") || "";
  const [code, setCode] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!code.trim() || !email || isLoading) {
      return;
    }

    setIsLoading(true);
    try {
      await confirmSignUpCode(email, code.trim());
      toast.success("Email verified! Please login.");
      navigate("/login", { replace: true });
    } catch (error: any) {
      console.error("Verification error:", error);
      let errorMessage = "Invalid verification code. Please try again.";
      
      if (error.name === "CodeMismatchException") {
        errorMessage = "Invalid verification code. Please check your email and try again.";
      } else if (error.name === "ExpiredCodeException") {
        errorMessage = "Verification code has expired. Please request a new one.";
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendCode = async () => {
    if (!email || isResending) {
      return;
    }

    setIsResending(true);
    try {
      await resendConfirmationCode(email);
      toast.success("Verification code resent! Please check your email.");
    } catch (error: any) {
      console.error("Resend error:", error);
      toast.error("Failed to resend code. Please try again.");
    } finally {
      setIsResending(false);
    }
  };

  if (!email) {
    return (
      <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white shadow-lg p-8">
        <h2 className="text-2xl font-semibold text-slate-900 mb-2">Verification Required</h2>
        <p className="text-sm text-slate-600 mb-6">
          No email provided. Please register again.
        </p>
        <Link
          to="/register"
          className="block w-full text-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700"
        >
          Go to Register
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white shadow-lg p-8">
      <h2 className="text-2xl font-semibold text-slate-900 mb-2">Verify Your Email</h2>
      <p className="text-sm text-slate-600 mb-2">
        We sent a verification code to <strong>{email}</strong>
      </p>
      <p className="text-xs text-slate-500 mb-6">
        Please check your email and enter the code below.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="code" className="block text-sm font-medium text-slate-700 mb-1">
            Verification Code
          </label>
          <input
            id="code"
            type="text"
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 text-center text-2xl tracking-widest"
            required
            disabled={isLoading}
            placeholder="000000"
            maxLength={6}
            autoComplete="one-time-code"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || !code.trim() || code.length !== 6}
          className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
        >
          {isLoading ? "Verifying..." : "Verify Email"}
        </button>
      </form>

      <div className="mt-4 text-center">
        <button
          type="button"
          onClick={handleResendCode}
          disabled={isResending}
          className="text-sm text-blue-600 hover:text-blue-700 disabled:text-slate-400 disabled:cursor-not-allowed"
        >
          {isResending ? "Sending..." : "Resend Code"}
        </button>
      </div>

      <p className="mt-6 text-center text-sm text-slate-600">
        Already verified?{" "}
        <Link to="/login" className="font-medium text-blue-600 hover:text-blue-700">
          Login
        </Link>
      </p>
    </div>
  );
};

