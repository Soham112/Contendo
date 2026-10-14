import { afterEach, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { isLegalPath, legalIdentity } from "./legal";
import PrivacyPolicy from "../app/privacy-policy/page";
import TermsOfService from "../app/terms-of-service/page";

afterEach(() => vi.unstubAllEnvs());
it("uses the confirmed public contact without deployment configuration", () => {
  vi.stubEnv("CONTENDO_LEGAL_OPERATOR", "");
  vi.stubEnv("CONTENDO_LEGAL_CONTACT_EMAIL", "");
  expect(legalIdentity()).toEqual({ operator: "Contendo", email: "contendoai@gmail.com" });
});
it.each([PrivacyPolicy, TermsOfService])("renders public legal content and contact without a draft label", (Page) => {
  const html = renderToStaticMarkup(<Page />);
  expect(html).toContain("Contendo");
  expect(html).toContain("mailto:contendoai@gmail.com");
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
