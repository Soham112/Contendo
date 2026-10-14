/** Exercise recovery and optional prompts through their actual event handlers. */
import type {ReactElement, ReactNode} from 'react';
import {beforeEach, expect, it, vi} from 'vitest';
const h=vi.hoisted(()=>({states:[] as unknown[],cursor:0,effects:[] as (()=>unknown)[],
  api:{getPublishJobs:vi.fn(),cancelPublishJob:vi.fn(),getPersonalization:vi.fn(),dismissPersonalization:vi.fn()}}));
vi.mock('react',async()=>({...await vi.importActual<typeof import('react')>('react'),
  useState:(initial:unknown)=>{const i=h.cursor++;if(!(i in h.states))h.states[i]=initial;
    return [h.states[i],(v:unknown)=>{h.states[i]=typeof v==='function'?v(h.states[i]):v;}];},
  useCallback:(fn:unknown)=>fn,useEffect:(fn:()=>unknown)=>{h.effects.push(fn);}}));
vi.mock('@/lib/api',()=>({useApi:()=>h.api}));
vi.mock('next/link',()=>({default:({children}:{children:ReactNode})=>children}));
import ScheduledPage from '@/app/scheduled/page';
import PersonalizationPrompt from './PersonalizationPrompt';
import RetryNotice from '@/components/RetryNotice';
function render(component:()=>ReactNode){h.cursor=0;return component();}
function find(node:ReactNode,type:unknown):ReactElement|undefined{
  if(Array.isArray(node))return node.map(n=>find(n,type)).find(Boolean);
  if(!node||typeof node!=='object'||!('props'in node))return;
  const e=node as ReactElement;return e.type===type?e:find(e.props.children,type);
}
function text(node:ReactNode):string{
  if(Array.isArray(node))return node.map(text).join(' ');
  if(node==null||typeof node==='boolean')return '';
  if(typeof node!=='object')return String(node);
  const e=node as ReactElement;return text(e.props.children);
}
async function settle(){for(let i=0;i<12;i++)await Promise.resolve();}
async function mount(component:()=>ReactNode){render(component);h.effects.splice(0).forEach(fn=>fn());await settle();return render(component);}
beforeEach(()=>{vi.clearAllMocks();h.states=[];h.cursor=0;h.effects=[];
  vi.stubGlobal('window',{addEventListener:vi.fn(),removeEventListener:vi.fn()});
  h.api.getPublishJobs.mockResolvedValue([]);h.api.getPersonalization.mockResolvedValue({offer_voice:false});
  h.api.dismissPersonalization.mockResolvedValue(undefined);
});
it('scheduled failure offers retry without claiming an empty schedule',async()=>{
  h.api.getPublishJobs.mockRejectedValueOnce(new TypeError('Failed to fetch'));
  const tree=await mount(ScheduledPage),notice=find(tree,RetryNotice)!;
  expect(notice.props.message).toContain('Check your connection');expect(text(tree)).not.toContain('Nothing here yet');
  await notice.props.onRetry();expect(text(render(ScheduledPage))).toContain('Nothing here yet');
});
it('failed cancellation retains the scheduled post and offers an actionable error',async()=>{
  h.api.getPublishJobs.mockResolvedValue([{id:'job-1',status:'scheduled',content:'Keep this post',results:[],scheduled_at:'2026-10-15T10:00:00Z'}]);
  h.api.cancelPublishJob.mockRejectedValue(new TypeError('Failed to fetch'));
  const tree=await mount(ScheduledPage);await find(tree,'button')!.props.onClick();
  const after=render(ScheduledPage);expect(text(after)).toContain('Keep this post');
  expect(find(after,RetryNotice)!.props.message).toContain('cancel this post');
  expect(find(after,'button')!.props.disabled).toBe(false);
});
it('new users are not shown an unsolicited voice questionnaire',async()=>{
  expect(await mount(PersonalizationPrompt)).toBeNull();
  expect(h.api.getPersonalization).toHaveBeenCalledOnce();
});
it('third-post voice prompt is optional and can be dismissed',async()=>{
  h.api.getPersonalization.mockResolvedValue({offer_voice:true});const tree=await mount(PersonalizationPrompt);
  expect(text(tree)).toContain('optional five-question');expect(text(tree)).toContain('Not now');
  await find(tree,'button')!.props.onClick();expect(render(PersonalizationPrompt)).toBeNull();
});
it('failed dismissal leaves the prompt and offers retry',async()=>{
  const logged=vi.spyOn(console,'error').mockImplementation(()=>{});
  h.api.getPersonalization.mockResolvedValue({offer_voice:true});h.api.dismissPersonalization.mockRejectedValue(new Error('server unavailable'));
  const tree=await mount(PersonalizationPrompt);await find(tree,'button')!.props.onClick();
  expect(text(render(PersonalizationPrompt))).toContain('Please try again');
  expect(text(render(PersonalizationPrompt))).toContain('Not now');logged.mockRestore();
});
