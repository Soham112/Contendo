import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { isLegalPath, legalIdentity } from "./legal";
import PrivacyPolicy from "../app/privacy-policy/page";
import TermsOfService from "../app/terms-of-service/page";

beforeEach(() => {
  vi.stubEnv("CONTENDO_LEGAL_OPERATOR", "Test Contendo Operator");
  vi.stubEnv("CONTENDO_LEGAL_CONTACT_EMAIL", "legal@example.test");
});
afterEach(() => vi.unstubAllEnvs());
it("requires real operator and contact configuration instead of inventing defaults", () => {
  expect(legalIdentity()).toEqual({ operator: "Test Contendo Operator", email: "legal@example.test" });
  vi.stubEnv("CONTENDO_LEGAL_CONTACT_EMAIL", "");
  expect(legalIdentity).toThrow("CONTENDO_LEGAL_CONTACT_EMAIL");
});
it.each([PrivacyPolicy, TermsOfService])("renders public legal content and contact without a draft label", (Page) => {
  const html = renderToStaticMarkup(<Page />);
  expect(html).toContain("Test Contendo Operator");
  expect(html).toContain("mailto:legal@example.test");
  expect(html).toContain("Zernio");
  expect(html).toContain("Stripe");
  expect(html).toContain("Anthropic");
  expect(html).not.toContain("Draft: needs legal review");
});
it("matches just the two public legal routes", () => {
  expect(isLegalPath("/privacy-policy")).toBe(true);
  expect(isLegalPath("/terms-of-service")).toBe(true);
  expect(isLegalPath("/settings")).toBe(false);
});
