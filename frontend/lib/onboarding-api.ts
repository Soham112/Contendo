import { requireResponse } from './request-errors';
import type { GenerateResponse } from './api';
export type OnboardingStep = 'segment' | 'niche' | 'business_profile' | 'individual_brief' | 'takes' | 'generation' | 'draft' | 'enhancement';
export type StepOutcome = 'started' | 'completed' | 'skipped' | 'error';
export interface FirstPostBrief { topic: string; story: string; take?: string; format: string }
type ApiFetch = (path: string, options?: RequestInit) => Promise<Response>;
export function onboardingApi(fetch: ApiFetch) {
  async function post<T>(path: string, body: unknown): Promise<T> {
    const response = await requireResponse(await fetch('/onboarding' + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }));
    return response.json();
  }
  return {
    recordOnboardingStep: (step: OnboardingStep, outcome: StepOutcome, segment?: string) => post('/events', { step, outcome, segment }),
    suggestTakes: (brief: FirstPostBrief) => post<{ takes: string[] }>('/takes', brief),
    generateFirstPost: (brief: FirstPostBrief) => post<GenerateResponse>('/first-post', brief),
    getPersonalization: async (): Promise<{ offer_voice: boolean }> => (await requireResponse(await fetch('/onboarding/personalization'))).json(),
    dismissPersonalization: () => post('/personalization/dismiss', {}),
  };
}
