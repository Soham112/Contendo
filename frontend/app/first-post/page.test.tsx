import { AuthSessionMissingError } from '@supabase/supabase-js';
import type { ReactElement, ReactNode } from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
const h = vi.hoisted(() => ({states: [] as unknown[], refs: [] as {current: unknown}[], deps: [] as unknown[][],
  cursor: 0, rc: 0, ec: 0, effects: [] as (() => unknown)[], getUser: vi.fn(), replace: vi.fn(), push: vi.fn(),
  storage: new Map<string,string>(), api: {getAccount: vi.fn(), getNicheOptions: vi.fn(), saveSegment: vi.fn(),
    generateFirstPost: vi.fn(), logPost: vi.fn(), recordOnboardingStep: vi.fn(), suggestTakes: vi.fn()}}));
vi.mock('react', async () => ({...await vi.importActual<typeof import('react')>('react'),
  useState: (initial: unknown) => { const i = h.cursor++; if (!(i in h.states)) h.states[i] = initial;
    return [h.states[i], (v: unknown) => {h.states[i] = typeof v === 'function' ? v(h.states[i]) : v;}]; },
  useRef: (initial: unknown) => {const i = h.rc++; return h.refs[i] ||= {current: initial};},
  useEffect: (effect: () => unknown, deps: unknown[]) => {const i = h.ec++;
    if (!h.deps[i] || deps.some((v,j) => v !== h.deps[i][j])) {h.deps[i] = deps; h.effects.push(effect);}}
}));
vi.mock('next/navigation', () => ({useRouter: () => ({replace:h.replace,push:h.push}),useSearchParams:()=>new URLSearchParams()}));
vi.mock('@/lib/supabase', () => ({default:{auth:{getUser:h.getUser}}}));
vi.mock('@/lib/api', () => ({useApi:()=>h.api}));
vi.mock('next/link', () => ({default:({children}:{children:ReactNode})=>children}));
import FirstPostFlow from '@/components/onboarding/FirstPostFlow';
import SegmentQuestion from '@/components/onboarding/SegmentQuestion';
import BusinessSetup from '@/components/onboarding/BusinessSetup';
import IndividualBrief from '@/components/onboarding/IndividualBrief';
import FirstDraft from '@/components/onboarding/FirstDraft';
import RetryNotice from '@/components/RetryNotice';
function render() {h.cursor=0; h.rc=0; h.ec=0; return FirstPostFlow();}
function find(node:ReactNode,type:unknown):ReactElement|undefined {
  if(Array.isArray(node)) return node.map(n=>find(n,type)).find(Boolean);
  if(!node || typeof node !== 'object' || !('props' in node)) return;
  const e=node as ReactElement; return e.type===type ? e : find(e.props.children,type);
}
function text(node:ReactNode):string {
  if(Array.isArray(node))return node.map(text).join(' ');
  if(node==null || typeof node==='boolean')return '';
  if(typeof node!=='object')return String(node);
  const e=node as ReactElement;
  return text(typeof e.type==='function' ? (e.type as (p:unknown)=>ReactNode)(e.props) : e.props.children);
}
async function flush(){for(let i=0;i<20;i++)await Promise.resolve();}
async function load(){render();h.effects.splice(0).forEach(f=>f());await flush();return render();}
async function individual(){const tree=await load();await find(tree,SegmentQuestion)!.props.onChoose('individual');
  find(render(),IndividualBrief)!.props.onChange({topic:'Launch',story:'I fixed a bug.',format:'linkedin post',take:''});}
async function generate(){find(render(),IndividualBrief)!.props.onGenerate();await flush();return render();}
beforeEach(()=>{
  vi.clearAllMocks();h.states=[];h.refs=[];h.deps=[];h.effects=[];h.storage.clear();
  vi.stubGlobal('sessionStorage',{getItem:(k:string)=>h.storage.get(k)??null,setItem:(k:string,v:string)=>h.storage.set(k,v)});
  h.getUser.mockResolvedValue({data:{user:{id:'new-user'}},error:null});
  h.api.getAccount.mockResolvedValue({segment:null,ask_segment:true});h.api.getNicheOptions.mockResolvedValue({niches:[]});
  h.api.saveSegment.mockImplementation(async a=>a);h.api.recordOnboardingStep.mockResolvedValue(undefined);
  h.api.logPost.mockResolvedValue(new Response('{}',{status:200}));
});
it('account failure offers retry without silently selecting individual',async()=>{
  h.api.getAccount.mockRejectedValueOnce(new TypeError('Failed to fetch'));const tree=await load();
  const notice=find(tree,RetryNotice)!;expect(notice).toBeDefined();expect(notice.props.message).toContain('Check your connection');
  expect(find(tree,IndividualBrief)).toBeUndefined();expect(h.api.saveSegment).not.toHaveBeenCalled();
  notice.props.onRetry();expect(find(await load(),SegmentQuestion)).toBeDefined();expect(h.api.getAccount).toHaveBeenCalledTimes(2);
});
it('individual generation preserves unsupported flags through workspace handoff',async()=>{
  await individual();const post='We sold to a young couple.';
  const grounding={outcome:'needs_review',repairs:2,flags:[{id:'age',text:'young',sentence:post,reason:'Age is not in your sources.'}]};
  h.api.generateFirstPost.mockResolvedValue({status:'needs_review',post,grounding});const tree=await generate();
  expect(h.api.saveSegment).toHaveBeenCalledWith({segment:'individual'});
  expect(h.api.generateFirstPost).toHaveBeenCalledWith(expect.objectContaining({story:'I fixed a bug.'}));
  const draft=find(tree,FirstDraft)!;expect(draft.props.draft.grounding).toEqual(grounding);
  const draftTree=FirstDraft(draft.props);expect(text(draftTree)).toContain('Age is not in your sources.');
  find(draftTree,'button')!.props.onClick();expect(JSON.parse(h.storage.get('contentOS_last_grounding')!)).toEqual(grounding);
  expect(h.push).toHaveBeenCalledWith('/create');
});
it.each(['draft_empty','draft_refused','draft_truncated','low_coverage'])('does not save an empty %s result',async status=>{
  await individual();h.api.generateFirstPost.mockResolvedValue({status,post:'',message:'Please try another brief.'});const tree=await generate();
  expect(find(tree,FirstDraft)).toBeUndefined();expect(find(tree,IndividualBrief)).toBeDefined();expect(h.api.logPost).not.toHaveBeenCalled();
  expect(text(tree)).toContain(status==='low_coverage'?"Your memory doesn't cover this topic":'Please try another brief.');
});
it('network failure gives an actionable message and retains the brief',async()=>{
  await individual();h.api.generateFirstPost.mockRejectedValue(new TypeError('Failed to fetch'));const tree=await generate();
  expect(text(tree)).toContain('Check your connection');expect(text(tree)).not.toContain('Failed to fetch');
  expect(find(tree,IndividualBrief)!.props.brief.story).toBe('I fixed a bug.');expect(h.api.logPost).not.toHaveBeenCalled();
});
it('business selection opens business setup without individual questions',async()=>{
  const tree=await load();await find(tree,SegmentQuestion)!.props.onChoose('business');
  expect(find(render(),BusinessSetup)).toBeDefined();expect(find(render(),IndividualBrief)).toBeUndefined();expect(h.api.saveSegment).not.toHaveBeenCalled();
});
it('brief offers optional takes with story and clears a stale take when topic changes',()=>{
  const onChange=vi.fn(),onGenerate=vi.fn();const tree=IndividualBrief({brief:{topic:'Launch',story:'I fixed a bug.',format:'linkedin post',take:'Delay was right'},
    onChange,onGenerate,onSuggest:vi.fn(),takes:['Delay was right'],suggesting:false,busy:false});
  expect(text(tree)).toContain('One sentence about it');expect(text(tree)).toContain('Suggest a take (optional)');
  find(tree,'input')!.props.onChange({target:{value:'New topic'}});expect(onChange).toHaveBeenCalledWith(expect.objectContaining({topic:'New topic',take:''}));
  find(tree,'form')!.props.onSubmit({preventDefault:vi.fn()});expect(onGenerate).toHaveBeenCalledOnce();
});
it('brief rejects whitespace-only story',()=>{
  const onGenerate=vi.fn();const tree=IndividualBrief({brief:{topic:'Launch',story:'   ',format:'linkedin post'},onChange:vi.fn(),onGenerate,onSuggest:vi.fn(),takes:[],suggesting:false,busy:false});
  find(tree,'form')!.props.onSubmit({preventDefault:vi.fn()});expect(onGenerate).not.toHaveBeenCalled();
});

it('signed-out entry redirects to sign-in rather than showing an account failure', async () => {
  h.getUser.mockResolvedValue({data: {user: null}, error: new AuthSessionMissingError()});
  const tree = await load();
  expect(h.replace).toHaveBeenCalledWith('/sign-in?redirect_url=%2Ffirst-post');
  expect(find(tree, RetryNotice)).toBeUndefined();
  expect(h.api.getAccount).not.toHaveBeenCalled();
});
