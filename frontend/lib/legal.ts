export const LEGAL_PATHS = ["/privacy-policy", "/terms-of-service"] as const;
export function isLegalPath(path: string | null): boolean {
  return LEGAL_PATHS.some((legal) => legal === path);
}

/** Required public business details; fail the build rather than publish invented contact details. */
export function legalIdentity() {
  const operator = process.env.CONTENDO_LEGAL_OPERATOR?.trim();
  const email = process.env.CONTENDO_LEGAL_CONTACT_EMAIL?.trim();
  if (!operator || !email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new Error("Set CONTENDO_LEGAL_OPERATOR and a valid CONTENDO_LEGAL_CONTACT_EMAIL before building the public legal pages.");
  }
  return { operator, email };
}
