import { expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
vi.mock("@supabase/ssr", () => ({ createServerClient: vi.fn(() => { throw new Error("Auth must not block public legal routes"); }) }));
import { middleware } from "../middleware";

it.each(["/privacy-policy", "/terms-of-service"])("%s is reachable without authentication", async (path) => {
  const response = await middleware(new NextRequest(`https://example.test${path}`));
  expect(response.status).toBe(200);
  expect(response.headers.get("location")).toBeNull();
});
