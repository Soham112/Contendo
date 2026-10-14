"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import supabase from "@/lib/supabase";
import { safeRedirectPath } from "@/lib/safe-redirect";
import { AuthShell, GoogleButton, OrDivider } from "@/components/auth/AuthShell";
import { Button } from "@/components/ui/button";
import { FieldMessage, Input, Label } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";

export default function SignUpPage() {
  const searchParams = useSearchParams();
  const redirectTo = safeRedirectPath(searchParams.get("redirect_url"));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleGoogleSignUp() {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo:
          window.location.origin + "/auth/callback?next=" + encodeURIComponent(redirectTo),
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
          encodeURIComponent(redirectTo),
      },
    });
    if (error) {
      setError(error.message);
    } else {
      setSuccess(true);
    }
    setLoading(false);
  }

  return (
    <AuthShell title="Create your account">
      {success ? (
        <div role="status" className="flex flex-col gap-3 text-center">
          <p className="text-[0.9375rem] text-on-surface">Check your email to confirm your account, then sign in.</p>
          <Button asChild variant="secondary"><Link href="/sign-in">Go to sign in</Link></Button>
        </div>
      ) : (
        <>
          {error && <ErrorState message={error} />}
          <GoogleButton onClick={handleGoogleSignUp} />
          <OrDivider />
          <form onSubmit={handleEmailSignUp} className="flex flex-col gap-4">
            <div>
              <Label htmlFor="signup-email">Email</Label>
              <Input id="signup-email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="signup-password">Password</Label>
              <Input id="signup-password" type="password" autoComplete="new-password" required minLength={6} aria-describedby="signup-password-hint" value={password} onChange={(e) => setPassword(e.target.value)} />
              <FieldMessage id="signup-password-hint">At least 6 characters.</FieldMessage>
            </div>
            <Button type="submit" className="mt-1 w-full" loading={loading} disabled={!email.trim() || password.length < 6} disabledReason={!email.trim() ? "Enter your email" : "Use at least 6 characters"}>
              Create account
            </Button>
          </form>
          <p className="text-center text-[0.875rem] text-secondary">
            Already have an account?{" "}
            <Link href="/sign-in" className="inline-flex min-h-11 items-center text-primary underline-offset-4 hover:underline">Sign in</Link>
          </p>
        </>
      )}
    </AuthShell>
  );
}
