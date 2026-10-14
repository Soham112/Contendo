import { redirect } from "next/navigation";

// The old onboarding flow was replaced by /first-post. Old links and bookmarks
// are redirected on the server, so nothing from the old flow is ever shown.
export default function OnboardingPage() {
  redirect("/first-post");
}
