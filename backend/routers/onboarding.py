"""Short first-post flow, with explicit persisted onboarding outcomes."""
import logging
from typing import Literal
import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from agents.onboarding_agent import suggest_takes
from agents.ingestion_agent import ingest_content
from auth.supabase_jwt import get_user_id_dep
from llm.client import StructuredOutputError
from memory.account_store import get_account
from memory.onboarding_store import record_step, personalization_status
from memory.profile_store import load_profile, save_profile
from routers.generate import GenerateRequest, GenerateResponse, generate

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/onboarding')
Step = Literal['segment', 'niche', 'business_profile', 'individual_brief', 'takes', 'generation', 'draft', 'enhancement']
Outcome = Literal['started', 'completed', 'skipped', 'error']


class StepEvent(BaseModel):
    step: Step
    outcome: Outcome
    segment: Literal['business', 'individual'] | None = None


class Brief(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    story: str = Field(min_length=1, max_length=4000)
    take: str = Field(default='', max_length=1000)
    format: Literal['linkedin post', 'medium article', 'twitter thread'] = 'linkedin post'


@router.post('/events')
async def event(body: StepEvent, user_id: str = Depends(get_user_id_dep)) -> dict:
    await run_in_threadpool(record_step, user_id, body.step, body.outcome, body.segment)
    return {'recorded': True}


@router.post('/takes')
async def takes(body: Brief, user_id: str = Depends(get_user_id_dep)) -> dict:
    try:
        result = await run_in_threadpool(suggest_takes, body.topic, body.story, user_id)
    except (anthropic.APIError, StructuredOutputError) as exc:
        logger.exception('Onboarding takes failed for user %s', user_id)
        await run_in_threadpool(record_step, user_id, 'takes', 'error', 'individual')
        raise HTTPException(503, 'We couldn’t suggest takes. You can retry or generate with your own words.') from exc
    await run_in_threadpool(record_step, user_id, 'takes', 'completed', 'individual')
    return {'takes': result}


@router.post('/first-post', response_model=GenerateResponse)
async def first_post(body: Brief, user_id: str = Depends(get_user_id_dep)) -> GenerateResponse:
    account = await run_in_threadpool(get_account, user_id)
    if account.get('segment') not in ('individual', 'business'):
        raise HTTPException(409, 'Choose Business or Individual before generating your first post.')
    segment = account['segment']
    if not body.topic.strip() or not body.story.strip():
        raise HTTPException(422, 'Add a topic and one sentence about it.')
    await run_in_threadpool(record_step, user_id, 'generation', 'started', segment)
    try:
        if segment == 'individual':
            # A personal note supplies factual evidence, unlike a topic instruction.
            await run_in_threadpool(ingest_content, body.story.strip(), source_type='personal_note',
                                    source_title='First post: ' + body.topic.strip(), user_id=user_id,
                                    memory_context='work')
        result = await generate(GenerateRequest(
            topic=body.topic, format=body.format, tone=(account.get('business_profile') or {}).get('tone', 'casual'),
            context='Author’s account: ' + body.story + ('\nChosen viewpoint: ' + body.take if body.take else ''),
        ), user_id=user_id)
        if result.post.strip():
            profile = await run_in_threadpool(load_profile, user_id)
            # A profile row marks setup complete. Preserve all existing voice answers.
            await run_in_threadpool(save_profile, profile, user_id)
        await run_in_threadpool(record_step, user_id, 'generation',
                                'completed' if result.post.strip() else 'error', segment)
        return result
    except Exception:
        logger.exception('First-post generation failed for user %s', user_id)
        await run_in_threadpool(record_step, user_id, 'generation', 'error', segment)
        raise


@router.get('/personalization')
async def personalization(user_id: str = Depends(get_user_id_dep)) -> dict:
    return await run_in_threadpool(personalization_status, user_id)


@router.post('/personalization/dismiss')
async def dismiss(user_id: str = Depends(get_user_id_dep)) -> dict:
    profile = await run_in_threadpool(load_profile, user_id)
    await run_in_threadpool(save_profile, {**profile, 'voice_prompt_dismissed': True}, user_id)
    await run_in_threadpool(record_step, user_id, 'enhancement', 'skipped')
    return {'dismissed': True}
