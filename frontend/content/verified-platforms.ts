// Add a platform only after a production connect, publish, schedule and disconnect
// test succeeds. This is the single source for public platform claims.
export interface VerifiedPlatform { key: string; label: string }
export const VERIFIED_PUBLISHING_PLATFORMS: readonly VerifiedPlatform[] = [];

export function verifiedPlatformFaq(platforms = VERIFIED_PUBLISHING_PLATFORMS) {
  if (!platforms.length) return null;
  return {
    question: "Which platforms can Contendo post to?",
    answer: `Production-verified publishing: ${platforms.map((platform) => platform.label).join(", ")}. You choose the accounts and approve each post before publishing or scheduling.`,
  };
}
