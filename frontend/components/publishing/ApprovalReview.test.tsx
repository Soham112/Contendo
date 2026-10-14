import type { ReactElement, ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";

const harness = vi.hoisted(() => ({
  states: [] as unknown[], cursor: 0, effects: [] as (() => void)[],
  api: { reviewPublishText: vi.fn(), approvePublishText: vi.fn() },
}));
vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return { ...actual, useEffect: (fn: () => void) => harness.effects.push(fn),
    useState: (initial: unknown) => {
      const index = harness.cursor++;
      if (!(index in harness.states)) harness.states[index] = initial;
      return [harness.states[index], (value: unknown) => {
        harness.states[index] = typeof value === "function" ? value(harness.states[index]) : value;
      }];
    },
  };
});
vi.mock("@/lib/api", () => ({ useApi: () => harness.api }));
import ApprovalReview from "./ApprovalReview";
import { PaywallError } from "@/lib/commerce-api";

const checked = { id: "r", content: "A young couple paid $900,000.", media: [], post_id: null, approved_at: null,
  flags: [{ id: "age", text: "young", sentence: "", reason: "age not stated" },
    { id: "price", text: "$900,000", sentence: "", reason: "price not stated" }] };
const onApproved = vi.fn();
const onPaywall = vi.fn();
function render() {
  harness.cursor = 0;
  return ApprovalReview({ content: checked.content, postId: null, media: [], onApproved, onPaywall });
}
function elements(node: ReactNode): ReactElement[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!node || typeof node !== "object" || !("props" in node)) return [];
  const element = node as ReactElement;
  return [element, ...elements(element.props.children)];
}
function button(tree: ReactNode) { return elements(tree).find((el) => el.type === "button")!; }
function inputs(tree: ReactNode) { return elements(tree).filter((el) => el.type === "input"); }

beforeEach(() => {
  vi.clearAllMocks(); harness.states = []; harness.effects = [];
  harness.api.reviewPublishText.mockResolvedValue(checked);
  harness.api.approvePublishText.mockResolvedValue({ ...checked, approved_at: "2026-10-13" });
});

it("shows the final text and requires every flag plus explicit reading before approval", async () => {
  let tree = render();
  expect(elements(tree).some((el) => el.type === "p" && el.props.children === checked.content)).toBe(true);
  harness.effects[0](); await Promise.resolve();
  tree = render();
  expect(button(tree).props.disabled).toBe(true);
  await button(tree).props.onClick();
  expect(harness.api.approvePublishText).not.toHaveBeenCalled();
  inputs(tree)[0].props.onChange({ target: { checked: true } });
  inputs(tree)[2].props.onChange({ target: { checked: true } });
  tree = render();
  expect(button(tree).props.disabled).toBe(true); // price is still unresolved
  inputs(tree)[1].props.onChange({ target: { checked: true } });
  tree = render();
  expect(button(tree).props.disabled).toBe(false);
  await button(tree).props.onClick();
  expect(harness.api.approvePublishText).toHaveBeenCalledWith("r", checked.content, ["age", "price"]);
  expect(onApproved).toHaveBeenCalledWith(expect.objectContaining({ content: checked.content, approved_at: "2026-10-13" }));
});


it("opens the existing upgrade flow when checking text requires Pro", async () => {
  const paywall = { code: "upgrade_required" as const, message: "Publishing requires Pro.", entitlements: null };
  harness.api.reviewPublishText.mockRejectedValue(new PaywallError(paywall));
  render(); harness.effects[0]();
  await Promise.resolve(); await Promise.resolve();
  expect(onPaywall).toHaveBeenCalledWith(paywall);
  expect(harness.api.approvePublishText).not.toHaveBeenCalled();
});
