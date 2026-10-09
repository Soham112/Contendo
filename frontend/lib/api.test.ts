import { afterEach, expect, it, vi } from "vitest";
import { useApi } from "./api";
vi.mock("@/lib/supabase", () => ({ default: { auth: { getSession: async () => ({ data: { session: null } }) } } }));
afterEach(() => vi.unstubAllGlobals());
it("shows a retryable operational refine error rather than a regenerate message", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Something went wrong. Please try again." }), { status: 500 })));
  await expect(useApi().refineSelection({ selected_text: "Text", instruction: "Edit", full_post: "Text" })).rejects.toThrow("Something went wrong. Please try again.");
});
