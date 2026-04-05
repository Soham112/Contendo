import { SignIn } from "@clerk/nextjs";

interface SignInPageProps {
  searchParams?: {
    redirect_url?: string;
  };
}

export default function SignInPage({ searchParams }: SignInPageProps) {
  const requestedRedirect = searchParams?.redirect_url;
  const redirectTarget =
    typeof requestedRedirect === "string" && requestedRedirect.startsWith("/")
      ? requestedRedirect
      : "/";
  const signUpUrl = `/sign-up?redirect_url=${encodeURIComponent(redirectTarget)}`;

  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center gap-8">
      <div className="flex flex-col items-center gap-1">
        <span className="text-[28px] font-headline italic text-on-surface tracking-tight">
          Contendo
        </span>
        <span className="text-[10px] uppercase tracking-[0.14em] text-secondary">
          Editorial Atelier
        </span>
      </div>
      <SignIn
        signUpUrl={signUpUrl}
        forceRedirectUrl={redirectTarget}
        fallbackRedirectUrl={redirectTarget}
        appearance={{
          variables: {
            colorPrimary: "#58614f",
            fontFamily: "Inter, sans-serif",
            borderRadius: "12px",
          },
          elements: {
            card: "shadow-card",
            formButtonPrimary: "bg-[#58614f] hover:bg-[#4c5543]",
          },
        }}
      />
    </div>
  );
}
