/** Technical failures stay in server logs; people get a concrete next step. */
export class RequestError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export function requestErrorMessage(error: unknown, action: string): string {
  if (error instanceof RequestError && error.status === 401) return "Your session has expired. Please sign in again.";
  if (error instanceof RequestError && (error.status === 429 || error.status === 402)) return "You've reached your generation limit. Check Plan and billing for your allowance.";
  if (error instanceof TypeError) return `We couldn't connect to Contendo to ${action}. Check your connection and try again. If this continues, contact contendoai@gmail.com.`;
  return `We couldn't ${action} right now. Please try again shortly. If this continues, contact contendoai@gmail.com.`;
}

export async function requireResponse(response: Response): Promise<Response> {
  if (!response.ok) throw new RequestError(response.status, "Request failed");
  return response;
}
