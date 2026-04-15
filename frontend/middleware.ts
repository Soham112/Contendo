import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/welcome",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/onboarding",
  "/first-post",
  "/sso-callback",
]);

export default clerkMiddleware(async (auth, req) => {
  const { userId } = auth();

  // Authenticated users hitting / → go to workspace
  if (userId && req.nextUrl.pathname === "/") {
    return NextResponse.redirect(new URL("/create", req.url));
  }

  // Unauthenticated visitors hitting / → show the landing page
  if (!userId && req.nextUrl.pathname === "/") {
    return NextResponse.redirect(new URL("/welcome", req.url));
  }

  // All other protected routes → require sign-in
  if (!isPublicRoute(req) && !userId) {
    const signInUrl = new URL("/sign-in", req.url);
    signInUrl.searchParams.set("redirect_url", req.url);
    return NextResponse.redirect(signInUrl);
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
