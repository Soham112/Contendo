export const LEGAL_PATHS = ["/privacy-policy", "/terms-of-service"] as const;
export function isLegalPath(path: string | null): boolean {
  return LEGAL_PATHS.some((legal) => legal === path);
}

/** Public service identity and owner-confirmed contact; these are not deployment secrets. */
export function legalIdentity() {
  return { operator: "Contendo", email: "contendoai@gmail.com" };
}
