/** Account snapshots must not survive a setup save on another route. */
import {beforeEach, expect, it, vi} from 'vitest';
const h=vi.hoisted(()=>({states:[] as unknown[],cursor:0,path:'/create',deps:undefined as unknown[]|undefined,
  pending:undefined as (()=>void|(()=>void))|undefined,cleanup:undefined as (()=>void)|undefined,getAccount:vi.fn()}));
vi.mock('react',async()=>({...await vi.importActual<typeof import('react')>('react'),
  useState:(initial:unknown)=>{const i=h.cursor++;if(!(i in h.states))h.states[i]=initial;
    return [h.states[i],(value:unknown)=>{h.states[i]=typeof value==='function'?value(h.states[i]):value;}];},
  useEffect:(effect:()=>void|(()=>void),deps:unknown[])=>{
    if(!h.deps||deps.some((value,i)=>value!==h.deps![i])){h.deps=deps;h.pending=effect;}}
}));
vi.mock('next/navigation',()=>({usePathname:()=>h.path}));
vi.mock('@/lib/api',()=>({useApi:()=>({getAccount:h.getAccount})}));
import {useAccount} from './useAccount';
function render(enabled=true){h.cursor=0;return useAccount(enabled);}
function effects(){if(h.pending){h.cleanup?.();const effect=h.pending;h.pending=undefined;h.cleanup=effect()||undefined;}}
async function settle(){for(let i=0;i<12;i++)await Promise.resolve();}
function deferred<T>(){let resolve!:(value:T)=>void;let reject!:(error:unknown)=>void;
  const promise=new Promise<T>((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
beforeEach(()=>{vi.clearAllMocks();h.states=[];h.cursor=0;h.path='/create';h.deps=undefined;h.pending=undefined;h.cleanup=undefined;});
it('refetches after business setup and hides the stale unanswered snapshot immediately',async()=>{
  h.getAccount.mockResolvedValueOnce({segment:null,ask_segment:true});render();effects();await settle();
  expect(render().account).toEqual({segment:null,ask_segment:true});
  h.path='/first-post';h.getAccount.mockResolvedValueOnce({segment:null,ask_segment:true});render();effects();await settle();
  const saved=deferred<{segment:string;ask_segment:boolean}>();h.getAccount.mockReturnValueOnce(saved.promise);
  h.path='/create';
  // Even before effects execute, the old answer cannot trigger the modal.
  expect(render()).toMatchObject({account:null,loaded:false,error:''});effects();
  expect(render().account).toBeNull();saved.resolve({segment:'business',ask_segment:false});await settle();
  expect(render()).toMatchObject({account:{segment:'business',ask_segment:false},loaded:true,error:''});
  expect(h.getAccount).toHaveBeenCalledTimes(3);
});
it('a failed initial account check returns an explicit error and no guessed segment',async()=>{
  h.getAccount.mockRejectedValue(new TypeError('Failed to fetch'));render();effects();await settle();
  expect(render()).toMatchObject({account:null,loaded:true});expect(render().error).toContain('Please try again');
});
it('retry fetches again and clears the visible failure after success',async()=>{
  h.getAccount.mockRejectedValueOnce(new Error('unavailable'));render();effects();await settle();
  const state=render();expect(state.error).toBeTruthy();
  h.getAccount.mockResolvedValueOnce({segment:'business',ask_segment:false});state.retry();render();effects();await settle();
  expect(render()).toMatchObject({error:'',loaded:true,account:{segment:'business',ask_segment:false}});
});
it('ignores a late response from the previous route',async()=>{
  const old=deferred<{segment:null;ask_segment:boolean}>();h.getAccount.mockReturnValueOnce(old.promise);
  render();effects();h.path='/first-post';h.getAccount.mockResolvedValueOnce({segment:'business',ask_segment:false});
  render();effects();await settle();old.resolve({segment:null,ask_segment:true});await settle();
  expect(render()).toMatchObject({account:{segment:'business',ask_segment:false},loaded:true,error:''});
});
it('disabled account checks make no request',()=>{render(false);effects();expect(h.getAccount).not.toHaveBeenCalled();expect(render(false).loaded).toBe(false);});
