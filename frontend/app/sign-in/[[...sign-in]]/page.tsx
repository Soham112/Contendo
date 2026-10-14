"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import supabase from "@/lib/supabase";
import { safeRedirectPath } from "@/lib/safe-redirect";
import { AuthShell, GoogleButton, OrDivider } from "@/components/auth/AuthShell";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";

export default function SignInPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = safeRedirectPath(searchParams.get("redirect_url"));

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) router.push("/create");
    });
  }, []);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGoogleSignIn() {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo:
          window.location.origin + "/auth/callback?next=" + encodeURIComponent(redirectTo),
      },
    });
  }

  async function handleEmailSignIn(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      setError(error.message);
      setLoading(false);
    } else {
      router.push(redirectTo);
    }
  }

  return (
    <AuthShell title="Sign in">
      {error && <ErrorState message={error} />}
      <GoogleButton onClick={handleGoogleSignIn} />
      <OrDivider />
      <form onSubmit={handleEmailSignIn} className="flex flex-col gap-4">
        <div>
          <Label htmlFor="signin-email">Email</Label>
          <Input id="signin-email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="signin-password">Password</Label>
          <Input id="signin-password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <Button type="submit" className="mt-1 w-full" loading={loading} disabled={!email.trim() || !password} disabledReason="Enter your email and password">
          Sign in
        </Button>
      </form>
      <p className="text-center text-[0.875rem] text-secondary">
        Don&apos;t have an account?{" "}
        <Link href="/sign-up" className="inline-flex min-h-11 items-center text-primary underline-offset-4 hover:underline">Sign up</Link>
      </p>
    </AuthShell>
  );
}
