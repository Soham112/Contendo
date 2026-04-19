"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import supabase from "@/lib/supabase";

export default function SignUpPage() {
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect_url") ?? "/create";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleGoogleSignUp() {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin + "/auth/callback",
      },
    });
  }

  async function handleEmailSignUp(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo:
          window.location.origin +
          "/auth/callback?next=" +
          encodeURIComponent(redirectTo.startsWith("/") ? redirectTo : "/create"),
      },
    });
    if (error) {
      setError(error.message);
    } else {
      setSuccess(true);
    }
    setLoading(false);
  }

  const inputCls =
    "w-full bg-[#f3f4f3] border-0 border-b border-b-[#aeb3b2] focus:border-b-2 focus:border-b-[#58614f] outline-none px-3 py-2.5 text-[14px] text-[#2f3333] placeholder-[#aeb3b2] transition-all";

  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center gap-8">
      {/* Wordmark */}
      <div className="flex flex-col items-center gap-1">
        <span className="text-[28px] font-headline italic text-on-surface tracking-tight">
          Contendo
        </span>
        <span className="text-[10px] uppercase tracking-[0.14em] text-secondary">
          Editorial Atelier
        </span>
      </div>

      {/* Card */}
      <div className="w-full max-w-sm flex flex-col gap-5 bg-white rounded-2xl shadow-card px-8 py-8">
        <h1 className="font-headline text-[22px] text-on-surface text-center">
          Create account
        </h1>

        {success ? (
          <div className="flex flex-col gap-3 text-center">
            <p className="text-[14px] text-on-surface">
              Check your email to confirm your account, then sign in.
            </p>
            <Link
              href="/sign-in"
              className="text-primary text-[14px] font-medium hover:underline"
            >
              Go to sign in
            </Link>
          </div>
        ) : (
          <>
            {error && (
              <p className="text-[13px] text-red-600 bg-red-50 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            {/* Google OAuth */}
            <button
              type="button"
              onClick={handleGoogleSignUp}
              className="flex items-center justify-center gap-3 w-full py-2.5 px-4 border border-[#e0e4e0] rounded-xl text-[14px] font-medium text-on-surface hover:bg-[#f5f5f5] transition-colors"
            >
              <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
                <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
                <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
                <path d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" fill="#FBBC05"/>
                <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 7.293C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
              </svg>
              Continue with Google
            </button>

            {/* Divider */}
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-[#e0e4e0]" />
              <span className="text-[12px] text-secondary">or</span>
              <div className="flex-1 h-px bg-[#e0e4e0]" />
            </div>

            {/* Email + password */}
            <form onSubmit={handleEmailSignUp} className="flex flex-col gap-3">
              <input
                type="email"
                required
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputCls}
              />
              <input
                type="password"
                required
                minLength={6}
                placeholder="Password (min 6 characters)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputCls}
              />
              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full py-2.5 rounded-xl text-[14px] font-semibold text-white disabled:opacity-50 disabled:cursor-not-allowed transition-opacity mt-1"
              >
                {loading ? "Creating account…" : "Create account"}
              </button>
            </form>

            <p className="text-center text-[13px] text-secondary">
              Already have an account?{" "}
              <Link href="/sign-in" className="text-primary hover:underline">
                Sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
