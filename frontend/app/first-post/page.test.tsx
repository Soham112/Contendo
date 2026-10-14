/** Exercise the page's generate button and resulting screen without a browser or network. */
import type { ReactElement, ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";

const harness = vi.hoisted(() => ({
  states: [] as unknown[], cursor: 0,
  api: { saveProfile: vi.fn(), generatePost: vi.fn(), logPost: vi.fn() },
}));
vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return { ...actual, useEffect: vi.fn(), useRef: () => ({ current: null }),
    useState: (initial: unknown) => {
      const index = harness.cursor++;
      if (!(index in harness.states)) harness.states[index] = initial;
      return [harness.states[index], (value: unknown) => {
        harness.states[index] = typeof value === "function" ? value(harness.states[index]) : value;
      }];
    },
  };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock("@/lib/supabase", () => ({ default: { auth: { getUser: vi.fn() } } }));
vi.mock("@/lib/api", () => ({ useApi: () => harness.api }));
vi.mock("@/lib/useTracking", () => ({ useTracking: () => ({ logEvent: vi.fn() }) }));
vi.mock("@/components/OnboardingIntercept", () => ({ default: () => null }));
import FirstPostPage from "./page";

function renderContent(): ReactElement {
  harness.cursor = 0;
  const wrapper = FirstPostPage();
  const content = wrapper.props.children as ReactElement;
  return (content.type as (props: unknown) => ReactElement)(content.props);
}
function findButton(node: ReactNode): ReactElement | undefined {
  if (Array.isArray(node)) return node.map(findButton).find(Boolean);
  if (!node || typeof node !== "object" || !("props" in node)) return;
  const element = node as ReactElement;
  if (element.type === "button" && typeof element.props.onClick === "function" &&
      element.props.children === "Generate my first post →") return element;
  return findButton(element.props.children);
}
function screenText(node: ReactNode): string {
  if (Array.isArray(node)) return node.map(screenText).join(" ");
  if (node == null || typeof node === "boolean") return "";
  if (typeof node !== "object") return String(node);
  const element = node as ReactElement;
  if (typeof element.type === "function") return screenText((element.type as (props: unknown) => ReactNode)(element.props));
  return screenText(element.props.children);
}
beforeEach(() => {
  vi.clearAllMocks();
  harness.states = [];
  renderContent();
  // Signed-in onboarding user at the final form screen, with profile check completed.
  harness.states[0] = { email: "test@example.invalid", user_metadata: { full_name: "Test" } };
  harness.states[1] = true;
  harness.states[2] = 5;
  harness.states[7] = true;
  harness.api.saveProfile.mockResolvedValue(undefined);
});

it.each([
  ["low_coverage", "Your memory doesn't cover this topic yet. Add a source about it, then generate again."],
  ["draft_empty", "The model returned no post."],
  ["draft_refused", "The model declined to write this post."],
  ["draft_truncated", "The draft was cut off before it finished."],
])("the onboarding page explains %s instead of saving an empty draft", async (status, message) => {
  harness.api.generatePost.mockResolvedValue(new Response(JSON.stringify({ status, post: "", message }), { status: 200 }));
  const button = findButton(renderContent());
  expect(button).toBeDefined();
  await button!.props.onClick();
  expect(harness.api.generatePost).toHaveBeenCalledOnce();
  expect(harness.api.logPost).not.toHaveBeenCalled();
  const text = screenText(renderContent());
  expect(text).toContain(message);
});

it("shows the returned draft and unsupported claim flags on onboarding", async () => {
  const post = "We sold to a young couple.";
  harness.api.generatePost.mockResolvedValue({ ok: true, json: async () => ({ status: "needs_review", post,
    grounding: { outcome: "needs_review", repairs: 2,
      flags: [{ id: "age", text: "young", sentence: post, reason: "Age is not in your sources." }] } }) });
  harness.api.logPost.mockResolvedValue({ ok: true, json: async () => ({ post_id: 1 }) });
  await findButton(renderContent())!.props.onClick();
  const text = screenText(renderContent());
  expect(text).toContain(post);
  expect(text).toContain("Age is not in your sources.");
  expect(text).not.toContain("Something went wrong.");
});
